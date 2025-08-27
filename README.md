# YouTube Music – Bulk Like Setup & Usage

This repo contains scripts to **like all tracks** from your YouTube Music playlists using [`ytmusicapi`](https://github.com/sigma67/ytmusicapi). It uses the **Device OAuth** flow and a `uv` virtual environment.

## Prerequisites

- **Python** (3.10+ recommended)
- **uv** (package & venv manager). Install: https://docs.astral.sh/uv/
- A Google Cloud project with:
  1. **YouTube Data API v3** **enabled** (APIs & Services → Library)
  2. **OAuth consent screen** set to **Testing** and your Google account added under **Test users**
  3. **OAuth client ID** of type **“TVs and Limited Input devices”** (Credentials → Create credentials)

> ❗ Keep your OAuth **Client ID/Secret** safe. Do **not** commit `oauth.json`, `oauth_credentials.json`, or any `client_secret*.json` files.

## One-time setup

1. Clone/download this folder and open a terminal in it.
2. Ensure `.gitignore` is present (it already ignores auth files and `.venv`).
3. Run the setup script (interactive):
   ```bash
   bash setup_oauth.sh
   ```
   - It will create `.venv` with `uv`, install `requirements.txt`,
   - Ask for your **TVs & Limited Input devices** **Client ID** and **Client Secret**,
   - Create `oauth_credentials.json`,
   - Launch the **Device OAuth** flow to create `oauth.json`,
   - Verify the credentials.

If the browser shows “App isn’t verified”, click **Advanced → Continue**. Make sure you sign in with the **Test user** you added on the consent screen.

## Running the scripts

### Like **all** playlists in your library
```bash
uv run python like_all_playlists.py
```

### Like a **single** playlist
```bash
uv run python like_playlist.py <PLAYLIST_ID>
# Example URL: https://music.youtube.com/playlist?list=PLabc123
# The ID is the part after list= (e.g., PLabc123).
```

## Configuration

Both scripts have a small delay between likes to avoid throttling:
```python
DELAY_RANGE_SEC = (0.35, 0.80)   # increase if you see 429/403
```
You can also tweak retries and exponential backoff in the script.

## Troubleshooting

- **`invalid_client` during OAuth**  
  The OAuth client type may not be **TVs & Limited Input devices**, or you enabled **YouTube Data API v3** in a different project. Recreate the client in the correct project.

- **`oauth_credentials not provided`**  
  Pass both files to the library: the scripts already do this. In custom code:
  ```python
  YTMusic('oauth.json', oauth_credentials='oauth_credentials.json')
  ```

- **403/429 rate limits**  
  Increase the delay range, or run again later. The scripts are idempotent: already-liked tracks are counted as `already` and skipped.

- **Token expired**  
  Re-run `bash setup_oauth.sh` to refresh `oauth.json`, or run:
  ```bash
  uv run ytmusicapi oauth --client-id "<ID>" --client-secret "<SECRET>"
  ```

## Security

- Don’t commit `oauth.json`, `oauth_credentials.json`, or any client secret files.
- Rotate/delete any OAuth client secrets you accidentally shared publicly.
