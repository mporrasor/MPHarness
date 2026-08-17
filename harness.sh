#!/usr/bin/env bash
# Bootstrap script for Mac/Linux

set -e

echo "Checking environment dependencies..."

# 1. Check for uv (Python manager)
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv is installed."
fi

# 2. Check for virtual environment
if [ ! -d ".venv" ]; then
    echo "Setting up Python environment..."
    uv venv .venv
    uv pip install -e .
fi

# 3. Check for Git
if ! command -v git &> /dev/null; then
    echo "Warning: Git is not installed. Some features might be limited."
fi

# Run the harness CLI
echo "Starting Harness..."
uv run harness "$@"
