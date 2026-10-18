[CmdletBinding()]
param(
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

$repositoryRoot = $PSScriptRoot
$environmentPath = Join-Path $repositoryRoot ".env"

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "Environment file not found: $environmentPath"
}

$settings = @{}
Get-Content -LiteralPath $environmentPath |
    Where-Object { $_ -match '^[^#][^=]*=' } |
    ForEach-Object {
        $name, $value = $_ -split '=', 2
        $settings[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }

$requiredSettings = @(
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_ACCESS_TOKEN"
)
foreach ($name in $requiredSettings) {
    if (-not $settings[$name]) {
        throw "$name is required in .env."
    }
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    throw "Docker is required by Supabase CLI database exports."
}
& $docker.Source info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but its engine is not running."
}

if (-not $OutputDirectory) {
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutputDirectory = Join-Path $repositoryRoot "backups\aura-$timestamp"
} elseif (-not [IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot $OutputDirectory
}

if (Test-Path -LiteralPath $OutputDirectory) {
    $existingEntries = @(Get-ChildItem -LiteralPath $OutputDirectory -Force)
    if ($existingEntries.Count -gt 0) {
        throw "Backup destination is not empty: $OutputDirectory"
    }
}

$databaseDirectory = Join-Path $OutputDirectory "database"
$storageDirectory = Join-Path $OutputDirectory "storage\item-images"
New-Item -ItemType Directory -Force -Path $databaseDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $storageDirectory | Out-Null

$env:SUPABASE_ACCESS_TOKEN = $settings["SUPABASE_ACCESS_TOKEN"]
$env:SUPABASE_DB_PASSWORD = $settings["SUPABASE_DB_PASSWORD"]

function Invoke-Supabase {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & npx.cmd --yes supabase @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Supabase CLI command failed."
    }
}

Write-Host "Backing up database roles, schema, and data..." -ForegroundColor Cyan
Invoke-Supabase @(
    "db", "dump", "--linked", "--role-only",
    "--file", (Join-Path $databaseDirectory "roles.sql")
)
Invoke-Supabase @(
    "db", "dump", "--linked",
    "--file", (Join-Path $databaseDirectory "schema.sql")
)
Invoke-Supabase @(
    "db", "dump", "--linked", "--data-only", "--use-copy",
    "-x", "storage.buckets_vectors",
    "-x", "storage.vector_indexes",
    "--file", (Join-Path $databaseDirectory "data.sql")
)

$databaseFiles = @(Get-ChildItem -LiteralPath $databaseDirectory -File)
if ($databaseFiles.Count -ne 3 -or @($databaseFiles | Where-Object Length -le 0).Count) {
    throw "Database backup validation failed."
}

Write-Host "Listing and downloading private item images..." -ForegroundColor Cyan
$listingOutput = & npx.cmd --yes supabase storage ls `
    "ss:///item-images" `
    --linked `
    --experimental `
    --recursive `
    --output-format json 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Supabase Storage listing failed."
}
$listing = ($listingOutput -join "`n") | ConvertFrom-Json
$remotePaths = @($listing.paths)
$storageManifest = [System.Collections.Generic.List[object]]::new()
$supabaseBaseUrl = $settings["SUPABASE_URL"].TrimEnd("/")
$secretKey = $settings["SUPABASE_SECRET_KEY"]

foreach ($remotePath in $remotePaths) {
    $objectPath = $remotePath -replace '^/item-images/', ''
    if ($objectPath -eq $remotePath -or $objectPath -notlike "users/*") {
        throw "Unexpected object path returned for the item-images bucket."
    }

    $destination = Join-Path $storageDirectory ($objectPath -replace '/', '\')
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) |
        Out-Null
    $encodedPath = (($objectPath -split '/') | ForEach-Object {
        [uri]::EscapeDataString($_)
    }) -join '/'
    Invoke-WebRequest `
        -Uri "$supabaseBaseUrl/storage/v1/object/authenticated/item-images/$encodedPath" `
        -Headers @{ apikey = $secretKey } `
        -UserAgent "aura-backup/1.0" `
        -UseBasicParsing `
        -OutFile $destination `
        -TimeoutSec 60 |
        Out-Null

    $file = Get-Item -LiteralPath $destination
    $storageManifest.Add([pscustomobject]@{
        path = $objectPath
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    })
}

$storageManifestPath = Join-Path $storageDirectory "manifest.json"
$storageManifest | ConvertTo-Json -Depth 3 |
    Set-Content -LiteralPath $storageManifestPath -Encoding utf8
$storageFiles = @(
    Get-ChildItem -LiteralPath $storageDirectory -Recurse -File |
        Where-Object FullName -ne $storageManifestPath
)
if (
    $storageFiles.Count -ne $remotePaths.Count -or
    @($storageFiles | Where-Object Length -le 0).Count
) {
    throw "Storage backup validation failed."
}

$backupManifest = [pscustomobject]@{
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    project_ref = ([uri]$settings["SUPABASE_URL"]).Host.Split('.')[0]
    database = @($databaseFiles | Sort-Object Name | ForEach-Object {
        [pscustomobject]@{
            file = "database/$($_.Name)"
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    })
    storage = [pscustomobject]@{
        bucket = "item-images"
        object_count = $storageFiles.Count
        total_bytes = [long](($storageFiles | Measure-Object Length -Sum).Sum)
        manifest = "storage/item-images/manifest.json"
    }
}
$backupManifest | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $OutputDirectory "backup-manifest.json") `
        -Encoding utf8

Write-Host "Backup verified: $OutputDirectory" -ForegroundColor Green
Write-Host "Database files: $($databaseFiles.Count)" -ForegroundColor Green
Write-Host "Storage objects: $($storageFiles.Count)" -ForegroundColor Green
