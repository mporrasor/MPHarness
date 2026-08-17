# Bootstrap script for Windows (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "Checking environment dependencies..." -ForegroundColor Cyan

# 1. Check for uv (Python manager)
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed. Installing uv..." -ForegroundColor Yellow
    Invoke-RestMethod -Uri https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = "$HOME\.local\bin;" + $env:PATH
} else {
    Write-Host "uv is installed." -ForegroundColor Green
}

# 2. Check for virtual environment
if (!(Test-Path ".venv")) {
    Write-Host "Setting up Python environment..." -ForegroundColor Yellow
    uv venv .venv
    uv pip install -e .
}

# 3. Check for Git
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: Git is not installed. Some features might be limited." -ForegroundColor Red
}

# Run the harness CLI
Write-Host "Starting Harness..." -ForegroundColor Cyan
uv run harness $args
