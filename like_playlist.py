#!/usr/bin/env python3
# like_playlist.py
# Like every unliked track from a single YouTube Music playlist.
# - Uses OAuth tokens in oauth.json + client creds in oauth_credentials.json
# - Gentle rate limiting + retries + ETA
# - Uses OAuthCredentials object (not dict) to avoid refresh_token errors

import os, sys, time, random, json
from datetime import datetime
from typing import Tuple
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials

# ---- Config ----
OAUTH_FILE = "oauth.json"
OAUTH_CREDS_FILE = "oauth_credentials.json"

# per-like delay with jitter (increase if you see throttling)
DELAY_RANGE_SEC: Tuple[float, float] = (0.35, 0.80)

# retries on transient errors
MAX_RETRIES = 5
BACKOFF_START = 1.0   # seconds
BACKOFF_CAP = 30.0    # seconds

# max tracks fetched per playlist (YTM caps anyway)
PLAYLIST_LIMIT = 10000

PROGRESS_EVERY = 25


def load_creds_obj(path: str = OAUTH_CREDS_FILE) -> OAuthCredentials:
    if not os.path.exists(path):
        raise SystemExit(f"Missing {path} in {os.getcwd()}")
    with open(path, "r") as f:
        data = json.load(f)
    client_id = data.get("client_id")
    client_secret = data.get("client_secret", "")
    if not client_id:
        raise SystemExit(f"{path} is missing 'client_id'")
    return OAuthCredentials(client_id, client_secret)


def make_ytmusic() -> YTMusic:
    if not os.path.exists(OAUTH_FILE):
        raise SystemExit(f"Missing {OAUTH_FILE} in {os.getcwd()}")
    creds_obj = load_creds_obj()
    return YTMusic(OAUTH_FILE, oauth_credentials=creds_obj)


def polite_sleep():
    time.sleep(random.uniform(*DELAY_RANGE_SEC))


def like_with_retries(yt: YTMusic, video_id: str) -> Tuple[bool, YTMusic]:
    """Attempt to like a track, with retries and optional client re-init on token refresh issues.
    Returns (success, possibly-updated-yt-instance)."""
    delay = BACKOFF_START
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            yt.rate_song(video_id, "LIKE")
            return True, yt
        except Exception as e:
            msg = str(e)
            # self-heal on refresh issues by re-instantiating with proper OAuthCredentials
            if "refresh_token" in msg:
                yt = make_ytmusic()
            if attempt == MAX_RETRIES:
                print(f"ERROR: failed to like {video_id}: {e}", file=sys.stderr)
                return False, yt
            print(f"Transient error on {video_id} (attempt {attempt}): {e}. Retrying in {delay:.1f}s…", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, BACKOFF_CAP)
    return False, yt  # safety


def main():
    # Accept playlist ID via CLI arg
    if len(sys.argv) >= 2:
        playlist_id = sys.argv[1]
    else:
        print("Usage: uv run python like_playlist.py <PLAYLIST_ID>")
        sys.exit(2)

    yt = make_ytmusic()
    print(f"Auth OK — starting at {datetime.now().strftime('%H:%M:%S')}…")

    pl = yt.get_playlist(playlist_id, limit=PLAYLIST_LIMIT)
    tracks = pl.get("tracks", []) or []
    total = len(tracks)

    liked = already = skipped = errors = 0
    start = time.time()

    for idx, t in enumerate(tracks, start=1):
        vid = t.get("videoId")
        like = t.get("likeStatus")  # "LIKE" | "DISLIKE" | "INDIFFERENT" | None

        if not vid:
            skipped += 1
        elif like == "LIKE":
            already += 1
        else:
            ok, yt = like_with_retries(yt, vid)
            if ok:
                liked += 1
            else:
                errors += 1
            polite_sleep()

        if idx % PROGRESS_EVERY == 0 or idx == total:
            elapsed = time.time() - start
            rate = max(1e-6, idx / elapsed)
            eta = (total - idx) / rate
            print(f"[{idx}/{total}] liked:{liked} already:{already} skipped:{skipped} errors:{errors} "
                  f"| ETA ~ {int(eta//60)}m{int(eta%60):02d}s")

    elapsed = time.time() - start
    print(f"Done ✅ Liked {liked} new tracks (already:{already}, skipped:{skipped}, errors:{errors}). "
          f"Took {elapsed/60:.1f} min.")


if __name__ == "__main__":
    main()
