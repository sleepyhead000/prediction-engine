# setup_env.ps1 — Run this on a fresh PC to set up prediction-engine
# Sets environment variables, installs deps, creates directories

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== prediction-engine setup ===" -ForegroundColor Cyan
Write-Host "Root: $ROOT"

# --- 1. Environment variables (avoid C: drive bloat) ---
Write-Host "`n[1/5] Setting environment variables..." -ForegroundColor Yellow

$cacheDir = Join-Path $ROOT "cache"
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

[System.Environment]::SetEnvironmentVariable("HF_HOME", (Join-Path $cacheDir "huggingface"), "User")
[System.Environment]::SetEnvironmentVariable("EASYOCR_MODEL_PATH", (Join-Path $cacheDir "easyocr"), "User")
[System.Environment]::SetEnvironmentVariable("TRANSFORMERS_CACHE", (Join-Path $cacheDir "huggingface"), "User")

# Also set for current session
$env:HF_HOME = Join-Path $cacheDir "huggingface"
$env:EASYOCR_MODEL_PATH = Join-Path $cacheDir "easyocr"
$env:TRANSFORMERS_CACHE = Join-Path $cacheDir "huggingface"

Write-Host "  HF_HOME = $env:HF_HOME"
Write-Host "  EASYOCR_MODEL_PATH = $env:EASYOCR_MODEL_PATH"

# --- 2. Create directory structure ---
Write-Host "`n[2/5] Creating directories..." -ForegroundColor Yellow

$dirs = @(
    "data",
    "data\_images",
    "data\_book_images",
    "data\_ingest_failures",
    "data\_review_queue",
    "cache\llm",
    "cache\huggingface",
    "cache\easyocr",
    "out",
    "config",
    "sources\exams",
    "sources\books",
    "ground_truth"
)

foreach ($dir in $dirs) {
    $path = Join-Path $ROOT $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        Write-Host "  Created: $dir"
    }
}

# --- 3. Install Python dependencies ---
Write-Host "`n[3/5] Installing Python dependencies..." -ForegroundColor Yellow

# Check Python version
$pythonVersion = python --version 2>&1
Write-Host "  Python: $pythonVersion"

# Install from pyproject.toml
pip install -e ".[dev]" 2>&1 | ForEach-Object { Write-Host "  $_" }

# --- 4. Verify installations ---
Write-Host "`n[4/5] Verifying installations..." -ForegroundColor Yellow

$packages = @("chromadb", "easyocr", "sentence_transformers", "pymupdf", "pydantic", "httpx", "lxml", "selectolax", "rapidfuzz", "pytest", "ruff")

foreach ($pkg in $packages) {
    $result = pip show $pkg 2>&1 | Select-String "Version:"
    if ($result) {
        Write-Host "  OK: $pkg ($($result.Line.Split(':')[1].Trim()))" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $pkg" -ForegroundColor Red
    }
}

# --- 5. Quick sanity check ---
Write-Host "`n[5/5] Sanity checks..." -ForegroundColor Yellow

# Test engine import
$importResult = python -c "import engine; print(f'engine v{engine.__version__}')" 2>&1
Write-Host "  $importResult"

# Test schema round-trip
$testResult = python -m pytest tests/test_schemas.py -v --tb=short 2>&1 | Select-Object -Last 5
$testResult | ForEach-Object { Write-Host "  $_" }

# Check disk space
Write-Host "`nDisk space:" -ForegroundColor Yellow
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -gt 0 } | ForEach-Object {
    $freeGB = [math]::Round($_.Free / 1GB, 2)
    $usedGB = [math]::Round($_.Used / 1GB, 2)
    $totalGB = [math]::Round(($_.Free + $_.Used) / 1GB, 2)
    $pct = [math]::Round($_.Free / ($_.Free + $_.Used) * 100, 1)
    $color = if ($freeGB -lt 5) { "Red" } elseif ($freeGB -lt 20) { "Yellow" } else { "Green" }
    Write-Host "  $($_.Name): ${freeGB}GB free / ${totalGB}GB total (${pct}% free)" -ForegroundColor $color
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Next steps:"
Write-Host "  1. Place exam PDFs in sources\exams\"
Write-Host "  2. Place board book PDFs in sources\books\"
Write-Host "  3. Run: python -m pytest tests/ -v"
Write-Host "  4. Start with Phase 1: python -m engine.ingest"
