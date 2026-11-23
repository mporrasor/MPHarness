# MPHarness installer for Windows (PowerShell).
# Installs uv (if missing) and the pinned MPHarness version as the global 'harness' command.
$ErrorActionPreference = "Stop"

$Version = if ($env:MPHARNESS_VERSION) { $env:MPHARNESS_VERSION } else { "v0.2.0" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (Python tool manager)..."
    powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = "$HOME\.local\bin;$env:PATH"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is required. Install it from https://git-scm.com (or: winget install Git.Git) and run this script again." -ForegroundColor Red
    exit 1
}

Write-Host "Installing MPHarness $Version..."
uv tool install --force "git+https://github.com/mporrasor/MPHarness@$Version"
uv tool update-shell | Out-Null

Write-Host ""
Write-Host "Done. Open a new terminal, go to your project folder and run:  harness init" -ForegroundColor Green
