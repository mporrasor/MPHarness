#!/usr/bin/env bash
# MPHarness installer for macOS / Linux.
# Installs uv (if missing) and the pinned MPHarness version as the global 'harness' command.
set -euo pipefail

VERSION="${MPHARNESS_VERSION:-v0.2.0}"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (Python tool manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Git is required. Install it from https://git-scm.com and run this script again." >&2
  exit 1
fi

echo "Installing MPHarness $VERSION..."
uv tool install --force "git+https://github.com/mporrasor/MPHarness@$VERSION"
uv tool update-shell >/dev/null 2>&1 || true

echo
echo "Done. Open a new terminal, go to your project folder and run:  harness init"
