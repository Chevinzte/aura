[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repositoryRoot = $PSScriptRoot
$environmentPath = Join-Path $repositoryRoot ".env"
$backendDirectory = Join-Path $repositoryRoot "backend"
$telegramDirectory = Join-Path $repositoryRoot "telegram-bot"
$backendPython = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$telegramPython = Join-Path $telegramDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "Environment file not found: $environmentPath. Complete the README setup first."
}

$internalApiKey = Get-Content -LiteralPath $environmentPath |
    Where-Object { $_ -match '^AURA_INTERNAL_API_KEY=' } |
    Select-Object -First 1
if (-not $internalApiKey -or ($internalApiKey -split '=', 2)[1].Trim('"', "'").Length -lt 32) {
    throw "AURA_INTERNAL_API_KEY must be configured in .env with at least 32 characters."
}

foreach ($pythonPath in @($backendPython, $telegramPython)) {
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw "Python environment not found: $pythonPath. Complete the README setup first."
    }
}

function Stop-ExistingAuraProcess {
    param(
        [Parameter(Mandatory)]
        [string]$PythonPath,

        [Parameter(Mandatory)]
        [string]$CommandPattern
    )

    $pythonPattern = [regex]::Escape($PythonPath)
    $allProcesses = @(Get-CimInstance Win32_Process)
    $processes = $allProcesses | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match $pythonPattern -and
        $_.CommandLine -match $CommandPattern
    }

    $processIds = [System.Collections.Generic.List[int]]::new()
    function Add-ProcessTree {
        param([int]$ProcessId)

        foreach ($child in $allProcesses | Where-Object ParentProcessId -eq $ProcessId) {
            Add-ProcessTree -ProcessId $child.ProcessId
        }
        if (-not $processIds.Contains($ProcessId)) {
            $processIds.Add($ProcessId)
        }
    }

    foreach ($process in $processes) {
        Write-Host "Stopping existing AURA process $($process.ProcessId)..." -ForegroundColor Yellow
        Add-ProcessTree -ProcessId $process.ProcessId
    }
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

Stop-ExistingAuraProcess `
    -PythonPath $backendPython `
    -CommandPattern '-m\s+uvicorn\s+aura_backend\.main:app'
Stop-ExistingAuraProcess `
    -PythonPath $telegramPython `
    -CommandPattern '-m\s+aura_telegram(?:\s|$)'

Write-Host "Starting AURA backend and Telegram bot..." -ForegroundColor Cyan

$backendProcess = Start-Process `
    -FilePath $backendPython `
    -ArgumentList @(
        "-m",
        "uvicorn",
        "aura_backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000"
    ) `
    -WorkingDirectory $backendDirectory `
    -NoNewWindow `
    -PassThru

$telegramProcess = Start-Process `
    -FilePath $telegramPython `
    -ArgumentList @("-m", "aura_telegram") `
    -WorkingDirectory $telegramDirectory `
    -NoNewWindow `
    -PassThru

Write-Host "Backend PID: $($backendProcess.Id)" -ForegroundColor Green
Write-Host "Telegram PID: $($telegramProcess.Id)" -ForegroundColor Green
Write-Host "AURA is running. Press Ctrl+C to stop both services." -ForegroundColor Green

try {
    while (-not $backendProcess.HasExited -and -not $telegramProcess.HasExited) {
        Start-Sleep -Seconds 1
        $backendProcess.Refresh()
        $telegramProcess.Refresh()
    }

    if ($backendProcess.HasExited) {
        Write-Warning "The backend exited with code $($backendProcess.ExitCode)."
    }
    if ($telegramProcess.HasExited) {
        Write-Warning "The Telegram bot exited with code $($telegramProcess.ExitCode)."
    }
}
finally {
    Write-Host "Stopping AURA services..." -ForegroundColor Yellow
    foreach ($process in @($telegramProcess, $backendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "AURA stopped." -ForegroundColor Cyan
}
