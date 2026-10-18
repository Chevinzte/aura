import os
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse


router = APIRouter(tags=["landing"])
_PUBLIC_TELEGRAM_URL_ENV = "AURA_PUBLIC_TELEGRAM_URL"

_LANDING_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="AURA learns from clothes and belongings you like, then helps you understand your style and check new items.">
  <meta name="theme-color" content="#f7f5ef">
  <title>AURA &mdash; Understand Your Style</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f8f6f0;
      --paper-deep: #efebe3;
      --card: #fffefa;
      --ink: #252823;
      --muted: #74766f;
      --line: #deddd6;
      --blue: #456ee8;
      --blue-soft: #edf1ff;
      --green: #3f8c62;
      --dark: #26312f;
      --radius: 20px;
      --shadow: 0 20px 50px rgba(41, 43, 39, 0.08);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      min-width: 320px;
      color: var(--ink);
      background: var(--paper);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }

    a { color: inherit; }
    img { display: block; width: 100%; }

    .container {
      width: min(1184px, calc(100% - 48px));
      margin: 0 auto;
    }

    .nav {
      border-bottom: 1px solid var(--line);
      background: rgba(248, 246, 240, 0.94);
    }

    .nav-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 82px;
    }

    .nav-left, .nav-right {
      display: flex;
      align-items: center;
      gap: 42px;
    }

    .brand {
      font-size: 18px;
      font-weight: 900;
      letter-spacing: -0.08em;
      text-decoration: none;
    }

    .hackathon, .nav-link {
      color: var(--muted);
      font-size: 12px;
      text-decoration: none;
    }

    .nav-link { color: var(--ink); }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--green);
      font-size: 12px;
      text-decoration: none;
    }

    .status::before {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #55aa77;
      content: "";
    }

    .hero {
      border-bottom: 1px solid var(--line);
      background:
        radial-gradient(circle at 68% 50%, rgba(219, 227, 249, 0.85), transparent 36%),
        #f6f6f4;
    }

    .hero-inner {
      display: grid;
      grid-template-columns: 1.08fr 0.92fr;
      gap: 88px;
      align-items: center;
      min-height: 680px;
      padding: 70px 0;
    }

    .eyebrow {
      margin: 0 0 22px;
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.17em;
      text-transform: uppercase;
    }

    h1, h2, h3, p { margin-top: 0; }

    h1 {
      max-width: 680px;
      margin-bottom: 26px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 1.7rem;
      font-weight: 400;
      letter-spacing: -0.035em;
      line-height: 1.06;
      white-space: nowrap;
    }

    .hero-copy {
      max-width: 610px;
      margin-bottom: 30px;
      color: var(--muted);
      line-height: 1.55;
    }

    .pills {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      max-width: 500px;
    }

    .pill {
      padding: 8px 14px;
      border: 1px solid #deddd7;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.62);
      font-size: 11px;
      font-weight: 700;
    }

    .hero-action {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-top: 24px;
      padding: 12px 18px;
      border-radius: 999px;
      color: white;
      background: var(--blue);
      box-shadow: 0 8px 20px rgba(69, 110, 232, 0.22);
      font-size: 12px;
      font-weight: 800;
      text-decoration: none;
      transition: background-color 150ms ease, transform 150ms ease;
    }

    .hero-action:hover { background: #355fd9; transform: translateY(-1px); }
    .hero-action:focus-visible { outline: 3px solid rgba(69, 110, 232, 0.3); outline-offset: 3px; }

    .profile-card {
      justify-self: end;
      width: min(100%, 515px);
      padding: 28px;
      border-radius: 22px;
      background: rgba(255, 254, 250, 0.96);
      box-shadow: var(--shadow);
    }

    .profile-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 8px;
    }

    .profile-top .eyebrow { margin: 0; }

    .micro-pill {
      padding: 6px 11px;
      border-radius: 999px;
      color: var(--blue);
      background: var(--blue-soft);
      font-size: 10px;
      font-weight: 800;
    }

    .profile-card h2 {
      margin-bottom: 20px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 22px;
      font-weight: 400;
    }

    .profile-grid {
      display: grid;
      grid-template-columns: 1fr 220px;
      gap: 22px;
      padding-top: 22px;
      border-top: 1px solid var(--line);
    }

    .profile-label {
      margin: 0 0 11px;
      color: #96978f;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    .palette {
      display: flex;
      margin: 0 0 26px;
    }

    .swatch {
      width: 29px;
      height: 29px;
      margin-right: -4px;
      border: 3px solid var(--card);
      border-radius: 50%;
    }

    .swatch:nth-child(1) { background: #e7dfd0; }
    .swatch:nth-child(2) { background: #b8a484; }
    .swatch:nth-child(3) { background: #65706d; }
    .swatch:nth-child(4) { background: #335cbc; }

    .material-row { display: flex; gap: 10px; }

    .material {
      padding: 7px 10px;
      border-radius: 6px;
      color: #77786f;
      background: #f2f1ec;
      font-size: 10px;
      font-weight: 700;
    }

    .hero-image {
      height: 208px;
      border-radius: 13px;
      object-fit: cover;
    }

    .detail-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 24px;
    }

    .detail {
      padding: 7px 11px;
      border-radius: 6px;
      color: #77786f;
      background: #f2f1ec;
      font-size: 10px;
    }

    .detail.blue { color: var(--blue); background: var(--blue-soft); }

    .section { padding: 122px 0; }

    .section-heading {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 48px;
      margin-bottom: 48px;
    }

    .section-heading .eyebrow { margin-bottom: 13px; }

    h2.section-title {
      margin-bottom: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 27px;
      font-weight: 400;
      letter-spacing: -0.025em;
    }

    .section-note {
      width: 340px;
      margin-bottom: 3px;
      color: var(--muted);
      font-size: 12px;
    }

    .process-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 30px;
    }

    .process-card {
      overflow: hidden;
      border-radius: var(--radius);
      background: var(--card);
      box-shadow: 0 14px 36px rgba(43, 44, 39, 0.06);
    }

    .process-card img {
      height: 244px;
      object-fit: cover;
    }

    .process-body { min-height: 168px; padding: 28px; }

    .number {
      margin-bottom: 22px;
      color: var(--blue);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.15em;
    }

    h3 {
      margin-bottom: 10px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 16px;
      font-weight: 400;
    }

    .card-copy {
      margin-bottom: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }

    .possibilities { background: var(--paper-deep); }

    .feature-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    .feature-card {
      min-height: 205px;
      padding: 34px;
      border-radius: var(--radius);
      background: var(--card);
    }

    .feature-profile {
      display: grid;
      grid-template-columns: 290px 1fr;
      min-height: 403px;
      padding: 0;
      overflow: hidden;
    }

    .feature-profile img { height: 100%; object-fit: cover; }

    .feature-profile .feature-content {
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 34px;
    }

    .feature-card .number { margin-bottom: 28px; }
    .feature-card h3 { font-size: 17px; }

    .match-example {
      margin-top: 25px;
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #f6f4ef;
    }

    .example-label {
      margin-bottom: 15px;
      color: #8b8d85;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    .classification {
      display: inline-grid;
      grid-template-columns: 1fr 1fr;
      margin-bottom: 16px;
      padding: 4px;
      border: 1px solid #e4e3de;
      border-radius: 999px;
      background: #efeee9;
    }

    .match-example > input {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      clip-path: inset(50%);
      white-space: nowrap;
    }

    .classification label {
      min-width: 112px;
      padding: 8px 13px;
      border-radius: 999px;
      color: #898a83;
      cursor: pointer;
      font-size: 10px;
      font-weight: 800;
      text-align: center;
      transition: background-color 150ms ease, color 150ms ease, box-shadow 150ms ease;
      user-select: none;
    }

    #visual-fit:checked ~ .classification label[for="visual-fit"],
    #intentional-contrast:checked ~ .classification label[for="intentional-contrast"] {
      color: white;
      background: var(--blue);
      box-shadow: 0 4px 12px rgba(69, 110, 232, 0.24);
    }

    #visual-fit:focus-visible ~ .classification label[for="visual-fit"],
    #intentional-contrast:focus-visible ~ .classification label[for="intentional-contrast"] {
      outline: 2px solid var(--blue);
      outline-offset: 2px;
    }

    .match-explanation { display: none; }
    #visual-fit:checked ~ .visual-fit-explanation { display: block; }
    #intentional-contrast:checked ~ .contrast-explanation { display: block; }

    .inspiration-copy {
      max-width: 760px;
      margin: 18px 0 46px;
      color: var(--muted);
      font-size: 12px;
    }

    .reference-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }

    .reference-grid img {
      height: 285px;
      border-radius: 16px;
      object-fit: cover;
    }

    .caption {
      margin: 18px 0 0;
      color: #8b8c84;
      font-size: 10px;
    }

    .responsible {
      padding: 122px 0;
      color: white;
      background: var(--dark);
    }

    .responsible-grid {
      display: grid;
      grid-template-columns: 0.78fr 1.22fr;
      gap: 120px;
    }

    .responsible .eyebrow { color: #8ca4f3; }

    .responsible h2 {
      margin-bottom: 24px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 27px;
      font-weight: 400;
    }

    .responsible-copy {
      max-width: 390px;
      margin: 0;
      color: rgba(255,255,255,.62);
      font-size: 12px;
    }

    .principles { border-top: 1px solid rgba(255,255,255,.17); }

    .principle {
      padding: 18px 0;
      border-bottom: 1px solid rgba(255,255,255,.17);
      color: rgba(255,255,255,.77);
      font-size: 12px;
    }

    .architecture-copy {
      max-width: 760px;
      margin: 19px 0 48px;
      color: var(--muted);
      font-size: 12px;
    }

    .architecture-flow {
      display: flex;
      align-items: center;
      gap: 22px;
      padding: 34px;
      border-radius: 20px;
      background: var(--card);
      box-shadow: 0 14px 36px rgba(43, 44, 39, 0.05);
    }

    .node {
      padding: 15px 24px;
      border-radius: 9px;
      background: #f3f1eb;
      font-size: 11px;
      font-weight: 800;
    }

    .node.blue { color: var(--blue); background: var(--blue-soft); }
    .arrow { color: var(--blue); font-weight: 800; }

    .footer { border-top: 1px solid var(--line); }

    .footer-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 142px;
      color: var(--muted);
      font-size: 11px;
    }

    .footer strong { color: var(--ink); }

    @media (min-width: 901px) {
      body { font-size: 17.5px; }
      .brand { font-size: 22.5px; }
      .hackathon, .nav-link, .status { font-size: 15px; }
      .eyebrow { font-size: 15px; }
      h1 { font-size: 2.125rem; }
      .hero-copy { font-size: 17.5px; }
      .pill { font-size: 13.75px; }
      .hero-action { font-size: 15px; }
      .micro-pill { font-size: 12.5px; }
      .profile-card h2 { font-size: 27.5px; }
      .profile-label { font-size: 12.5px; }
      .material { font-size: 12.5px; }
      .detail { font-size: 12.5px; }
      h2.section-title { font-size: 33.75px; }
      .section-note { font-size: 15px; }
      .number { font-size: 13.75px; }
      h3 { font-size: 20px; }
      .card-copy { font-size: 15px; }
      .feature-card h3 { font-size: 21.25px; }
      .example-label { font-size: 12.5px; }
      .classification label { min-width: 140px; font-size: 12.5px; }
      .inspiration-copy { font-size: 15px; }
      .caption { font-size: 12.5px; }
      .responsible h2 { font-size: 33.75px; }
      .responsible-copy, .principle { font-size: 15px; }
      .architecture-copy { font-size: 15px; }
      .node { font-size: 13.75px; }
      .footer-inner { font-size: 13.75px; }
    }

    @media (max-width: 900px) {
      .hero-inner, .responsible-grid { grid-template-columns: 1fr; }
      .hero-inner { gap: 52px; padding: 86px 0; }
      .profile-card { justify-self: stretch; width: 100%; }
      .process-grid { gap: 18px; }
      .feature-profile { grid-template-columns: 42% 58%; }
      .responsible-grid { gap: 54px; }
      h1 { white-space: normal; }
    }

    @media (max-width: 700px) {
      .container { width: min(100% - 30px, 1184px); }
      .nav-inner { height: 72px; }
      .nav-left { gap: 18px; }
      .hackathon, .nav-link { display: none; }
      .hero-inner { min-height: 0; }
      .profile-grid { grid-template-columns: 1fr; }
      .hero-image { height: 240px; }
      .section { padding: 82px 0; }
      .section-heading { align-items: start; flex-direction: column; gap: 20px; }
      .section-note { width: auto; }
      .process-grid, .feature-grid, .reference-grid { grid-template-columns: 1fr; }
      .feature-profile { grid-template-columns: 1fr; }
      .feature-profile img { height: 310px; }
      .reference-grid img { height: auto; }
      .responsible { padding: 82px 0; }
      .architecture-flow { align-items: stretch; flex-direction: column; text-align: center; }
      .arrow { transform: rotate(90deg); }
      .footer-inner { align-items: flex-start; flex-direction: column; justify-content: center; gap: 10px; }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
    }
  </style>
</head>
<body>
  <header class="nav">
    <div class="container nav-inner">
      <div class="nav-left">
        <a class="brand" href="/" aria-label="AURA home">AURA.</a>
        <span class="hackathon">AI Lodge Hackathon 2026</span>
      </div>
      <div class="nav-right">
        <a class="nav-link" href="#how-it-works">How it works</a>
        <a class="status" href="/health">Service Online</a>
      </div>
    </div>
  </header>

  <main>
    <section class="hero">
      <div class="container hero-inner">
        <div>
          <p class="eyebrow">Your personal style, made clearer</p>
          <h1>Understand your <span style="font-weight: bold; color: var(--blue);">aesthetic</span>.</h1>
          <p class="hero-copy">Show AURA clothes and belongings you already love. It finds the style details you share and helps you decide whether new items feel like you.</p>
          <div class="pills">
            <span class="pill">Private experience</span>
            <span class="pill">Evidence-based</span>
            <span class="pill">User-controlled</span>
          </div>
          <a class="hero-action" href="/try-aura" target="_blank" rel="noopener noreferrer">Try AURA on Telegram</a>
        </div>

        <aside class="profile-card" aria-label="Illustrative style profile">
          <div class="profile-top">
            <p class="eyebrow">Example style profile</p>
            <span class="micro-pill">STYLE DETAILS</span>
          </div>
          <h2>What your personal style is made of</h2>
          <div class="profile-grid">
            <div>
              <p class="profile-label">Colours</p>
              <div class="palette" aria-label="Neutral colours with a blue accent">
                <span class="swatch"></span><span class="swatch"></span><span class="swatch"></span><span class="swatch"></span>
              </div>
              <p class="profile-label">Materials</p>
              <div class="material-row" aria-label="Example materials">
                <span class="material">Cotton</span><span class="material">Denim</span><span class="material">Knit</span>
              </div>
            </div>
            <img class="hero-image" src="/static/landing/hero-wardrobe.png" alt="Neutral garments arranged on a wardrobe rail">
          </div>
          <p class="profile-label" style="margin-top: 24px">Details that appear often</p>
          <div class="detail-row">
            <span class="detail">Relaxed fit</span>
            <span class="detail">Soft fabrics</span>
            <span class="detail blue">Blue accents</span>
          </div>
        </aside>
      </div>
    </section>

    <section class="section" id="how-it-works">
      <div class="container">
        <div class="section-heading">
          <div><p class="eyebrow">The process</p><h2 class="section-title">How it works</h2></div>
          <p class="section-note">Start with items you already love.<br>AURA learns from the details you share.</p>
        </div>
        <div class="process-grid">
          <article class="process-card">
            <img src="/static/landing/process-build.png" alt="A curated outfit arranged on a bed">
            <div class="process-body"><p class="number">01 / ADD ITEMS</p><h3>Add your favourites</h3><p class="card-copy">Upload photos of clothes and belongings you genuinely like.</p></div>
          </article>
          <article class="process-card">
            <img src="/static/landing/process-understand.png" alt="Layered neutral fabric textures">
            <div class="process-body"><p class="number">02 / LEARN</p><h3>Know your patterns</h3><p class="card-copy">AURA finds colours, materials, shapes and style details that appear often.</p></div>
          </article>
          <article class="process-card">
            <img src="/static/landing/process-explore.png" alt="A neutral garment held against a plain background">
            <div class="process-body"><p class="number">03 / CHECK &amp; EXPLORE</p><h3>Check and explore</h3><p class="card-copy">See how new items fit your style and get ideas for building your wardrobe.</p></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section possibilities">
      <div class="container">
        <div class="section-heading">
          <div><p class="eyebrow">What AURA can do</p><h2 class="section-title">See your style, check new items and stay in control.</h2></div>
        </div>
        <div class="feature-grid">
          <article class="feature-card feature-profile">
            <img src="/static/landing/profile-wardrobe.png" alt="A coordinated wardrobe with neutral and blue garments">
            <div class="feature-content"><p class="number">01 / PROFILE</p><h3>Your personal style profile</h3><p class="card-copy">See the colours, shapes, materials and style details that appear most often in your favourite items.</p></div>
          </article>
          <article class="feature-card">
            <p class="number">02 / MATCHING</p><h3>Check how an item fits your style</h3><p class="card-copy">AURA shows which details match your profile and which details are different.</p>
            <div class="match-example">
              <p class="example-label">Example result</p>
              <input type="radio" id="visual-fit" name="match-perspective" checked>
              <input type="radio" id="intentional-contrast" name="match-perspective">
              <div class="classification" role="radiogroup" aria-label="Example match perspective">
                <label for="visual-fit">Visual Fit</label>
                <label for="intentional-contrast">Intentional Contrast</label>
              </div>
              <p class="card-copy match-explanation visual-fit-explanation">The soft fabric and relaxed shape are similar to items in this example wardrobe, so it may feel familiar.</p>
              <p class="card-copy match-explanation contrast-explanation">The bright cobalt blue is stronger than the quieter colours in this example wardrobe, so it may add intentional contrast.</p>
            </div>
          </article>
          <article class="feature-card">
            <p class="number">03 / INSPIRATION</p><h3>Get wardrobe ideas</h3><p class="card-copy">AURA can create visual examples of items that could add to your wardrobe.</p>
          </article>
          <article class="feature-card">
            <p class="number">04 / CONTROL</p><h3>Review and correct your items</h3><p class="card-copy">Check what AURA saved, correct any details or ask it to analyse an item again.</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <p class="eyebrow">Ideas for your wardrobe</p>
        <h2 class="section-title">Suggestions, not rules.</h2>
        <p class="inspiration-copy">AURA can create visual ideas based on your style, such as familiar materials, useful colour contrasts and new items to consider.</p>
        <div class="reference-grid">
          <img src="/static/landing/reference-coat.png" alt="Illustrative neutral coat reference">
          <img src="/static/landing/reference-top.png" alt="Illustrative blue top reference">
          <img src="/static/landing/reference-pants.png" alt="Illustrative dark pants reference">
        </div>
        <p class="caption">Example images only. These are not products for sale.</p>
      </div>
    </section>

    <section class="responsible">
      <div class="container responsible-grid">
        <div>
          <p class="eyebrow">How AURA uses AI responsibly</p>
          <h2>You stay in control.</h2>
          <p class="responsible-copy">Your style is personal. AURA explains why it gives an answer and makes it clear what it can and cannot do.</p>
        </div>
        <div class="principles">
          <div class="principle">Suggestions are opinions, not fashion rules.</div>
          <div class="principle">AURA explains its answers using details it can see.</div>
          <div class="principle">Checking a new item does not add it to your profile.</div>
          <div class="principle">You choose your fashion preference. AURA does not guess it.</div>
          <div class="principle">Your uploaded photos are stored privately.</div>
          <div class="principle">Your feedback is saved, but it does not automatically change your profile or AURA's results.</div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <p class="eyebrow">How AURA works behind the scenes</p>
        <h2 class="section-title">AI looks at the details.<br>AURA keeps the decision process clear.</h2>
        <p class="architecture-copy">AI identifies visible details in your photos. AURA's own rules then build your profile, compare items and choose what to explain.</p>
        <div class="architecture-flow" aria-label="AURA architecture">
          <span class="node">Telegram chat</span><span class="arrow">&rarr;</span><span class="node">AURA backend</span><span class="arrow">&rarr;</span><span class="node blue">Private storage + AI services</span>
        </div>
      </div>
    </section>
  </main>

  <footer class="footer">
    <div class="container footer-inner">
      <strong>AURA - an AI-powered personal style matching</strong>
      <span>Built for the AI Lodge Hackathon 2026</span>
    </div>
  </footer>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page() -> HTMLResponse:
    """Present AURA's public product overview without exposing private access."""
    return HTMLResponse(
        content=_LANDING_PAGE,
        headers={
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/try-aura", include_in_schema=False)
async def try_aura() -> RedirectResponse:
    """Redirect to the configured public Telegram demo without exposing it in Git."""
    public_url = os.getenv(_PUBLIC_TELEGRAM_URL_ENV, "").strip()
    parsed_url = urlparse(public_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc.lower() != "t.me"
        or not parsed_url.path.strip("/")
    ):
        raise HTTPException(status_code=503, detail="PUBLIC_DEMO_LINK_NOT_CONFIGURED")
    return RedirectResponse(public_url, status_code=307)
