#!/usr/bin/env python3
# like_all_playlists.py
# Like every unliked track from *all* your YouTube Music library playlists (skips "Liked Music" by default).
# - Uses OAuth tokens in oauth.json + client creds in oauth_credentials.json
# - Gentle rate limiting + retries + ETA
# - Uses OAuthCredentials object (not dict) to avoid refresh_token errors

import os, sys, time, random, json
from datetime import datetime
from typing import Set, Tuple
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

# progress cadence
PROGRESS_EVERY = 25

# skip the special Liked Music playlist (id usually starts with "LM")
SKIP_LIKED_PLAYLIST = True


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


def like_with_retries(yt: YTMusic, video_id: str):
    delay = BACKOFF_START
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            yt.rate_song(video_id, "LIKE")
            return True, yt
        except Exception as e:
            msg = str(e)
            if "refresh_token" in msg:
                yt = make_ytmusic()
            if attempt == MAX_RETRIES:
                print(f"  ERROR: failed to like {video_id}: {e}", file=sys.stderr)
                return False, yt
            print(f"  Transient error on {video_id} (attempt {attempt}): {e}. Retrying in {delay:.1f}s…", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, BACKOFF_CAP)


def seed_known_liked(yt: YTMusic) -> Set[str]:
    """Seed a set with current liked songs to avoid duplicate calls across playlists."""
    vids: Set[str] = set()
    try:
        for s in yt.get_library_songs(limit=10000) or []:
            v = s.get("videoId")
            if v:
                vids.add(v)
    except Exception:
        pass
    return vids


def process_playlist(yt: YTMusic, playlist_id: str, title: str, known_liked: Set[str]):
    """Returns (liked, already, skipped, errors, yt)."""
    pl = yt.get_playlist(playlist_id, limit=PLAYLIST_LIMIT)
    tracks = pl.get("tracks", []) or []
    total = len(tracks)
    liked = already = skipped = errors = 0

    print(f"▶ {title} — {total} tracks")
    start = time.time()

    for idx, t in enumerate(tracks, start=1):
        vid = t.get("videoId")
        like = t.get("likeStatus")  # "LIKE" | "DISLIKE" | "INDIFFERENT" | None

        if not vid:
            skipped += 1
        elif like == "LIKE" or vid in known_liked:
            already += 1
        else:
            ok, yt = like_with_retries(yt, vid)
            if ok:
                liked += 1
                known_liked.add(vid)
            else:
                errors += 1
            polite_sleep()

        if idx % PROGRESS_EVERY == 0 or idx == total:
            elapsed = time.time() - start
            rate = max(1e-6, idx / elapsed)
            eta = (total - idx) / rate
            print(f"  [{idx}/{total}] liked:{liked} already:{already} skipped:{skipped} errors:{errors} "
                  f"| ETA ~ {int(eta//60)}m{int(eta%60):02d}s")

    print(f"  ✓ Done: {title} | liked:{liked} already:{already} skipped:{skipped} errors:{errors}\n")
    return liked, already, skipped, errors, yt


def main():
    yt = make_ytmusic()
    print(f"Auth OK — starting at {datetime.now().strftime('%H:%M:%S')}…")

    playlists = yt.get_library_playlists(limit=1000) or []
    if not playlists:
        print("No library playlists found.")
        return

    filtered = []
    for p in playlists:
        pid = p.get("playlistId") or p.get("id")
        title = p.get("title", "Untitled")
        if not pid:
            continue
        if SKIP_LIKED_PLAYLIST and str(pid).startswith("LM"):
            continue
        filtered.append((pid, title, p.get("count")))

    print(f"Found {len(filtered)} playlists to process.\n")

    known_liked: Set[str] = seed_known_liked(yt)
    g_liked = g_already = g_skipped = g_errors = 0

    for idx, (pid, title, count) in enumerate(filtered, start=1):
        print(f"[{idx}/{len(filtered)}] Processing playlist: {title}")
        l, a, s, e, yt = process_playlist(yt, pid, title, known_liked)
        g_liked += l; g_already += a; g_skipped += s; g_errors += e

    print("All playlists complete ✅")
    print(f"Total liked:{g_liked} already:{g_already} skipped:{g_skipped} errors:{g_errors}")


if __name__ == "__main__":
    main()
