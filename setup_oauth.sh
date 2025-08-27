#!/usr/bin/env bash
set -euo pipefail

# Setup script for YouTube Music bulk-like tools
# - Creates/uses a uv virtualenv (.venv)
# - Installs requirements
# - Prompts for OAuth client credentials (TVs & Limited Input devices)
# - Runs ytmusicapi OAuth device flow to create oauth.json
# - Verifies auth

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "== YouTube Music setup (uv + OAuth) =="

# 0) Check for uv
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 'uv' is not installed."
  echo "Install instructions: https://docs.astral.sh/uv/"
  exit 1
fi

# 1) Create venv if missing
if [[ ! -d ".venv" ]]; then
  echo "-- Creating virtual environment (.venv)…"
  uv venv
else
  echo "-- Using existing .venv"
fi

# 2) Install requirements
if [[ -f "requirements.txt" ]]; then
  echo "-- Installing requirements…"
  uv pip install -r requirements.txt
else
  echo "WARNING: requirements.txt not found; installing core deps…"
  uv pip install ytmusicapi httpx
fi

# 3) Get OAuth client credentials (TVs & Limited Input devices)
echo
echo "-- Enter your Google OAuth Client credentials"
echo "   (from Google Cloud Console → Credentials → OAuth client ID"
echo "    Application type: TVs and Limited Input devices)"
read -r -p "Client ID: " CLIENT_ID
# Secret may be empty for some TV clients; that's OK.
read -r -p "Client Secret (press Enter if none): " CLIENT_SECRET

# 4) Save oauth_credentials.json (needed for token refresh)
cat > oauth_credentials.json <<JSON
{
  "client_id": "${CLIENT_ID}",
  "client_secret": "${CLIENT_SECRET}"
}
JSON
echo "-- Wrote oauth_credentials.json"

# 5) Remove existing oauth.json if user agrees
if [[ -f "oauth.json" ]]; then
  read -r -p "oauth.json already exists. Overwrite it? [y/N]: " OVER
  case "${OVER:-N}" in
    [yY]*) rm -f oauth.json ;;
    *) echo "Keeping existing oauth.json";;
  esac
fi

# 6) Run the OAuth device flow to create oauth.json
echo "-- Starting OAuth device flow…"
if [[ -n "${CLIENT_SECRET}" ]]; then
  uv run ytmusicapi oauth --client-id "${CLIENT_ID}" --client-secret "${CLIENT_SECRET}"
else
  uv run ytmusicapi oauth --client-id "${CLIENT_ID}"
fi

# 7) Verify
echo "-- Verifying credentials…"
uv run python - <<'PY'
from ytmusicapi import YTMusic
YTMusic('oauth.json', oauth_credentials='oauth_credentials.json')
print("Auth OK ✅")
PY

echo
echo "All set! You can now run:"
echo "  uv run python like_all_playlists.py"
echo "or a single playlist:"
echo "  uv run python like_playlist.py <PLAYLIST_ID>"
