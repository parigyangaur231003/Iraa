"""
Lightweight Spotify integration used by Iraa.

This module authenticates with Spotify using the Client Credentials flow,
performs simple track searches, and opens the selected track in the user's
default browser or Spotify client. It avoids storing refresh tokens by
reusing the short-lived app token until it expires.
"""

from __future__ import annotations

import os
import time
import webbrowser
import platform
import subprocess
from contextlib import contextmanager
from typing import Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

_TOKEN_CACHE: Dict[str, object] = {
    "access_token": None,
    "expires_at": 0.0,
}

_AUTO_PAUSE_LISTENING = (os.getenv("SPOTIFY_AUTO_PAUSE_LISTENING") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class SpotifyAuthError(RuntimeError):
    """Raised when Spotify credentials or authentication fail."""


class SpotifyApiError(RuntimeError):
    """Raised when Spotify API calls fail."""


class SpotifyPlaybackError(RuntimeError):
    """Raised when direct playback control fails."""


def _client_credentials() -> tuple[str, str]:
    client_id = (os.getenv("SPOTIFY_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise SpotifyAuthError("Spotify client ID/secret missing. Please update your environment variables.")
    return client_id, client_secret


def _fetch_access_token(force_refresh: bool = False) -> str:
    """Fetch (and cache) a Spotify access token via client credentials flow."""
    if not force_refresh:
        token = _TOKEN_CACHE.get("access_token")
        expiry = float(_TOKEN_CACHE.get("expires_at") or 0)
        if token and time.time() < expiry - 30:  # small buffer
            return token

    client_id, client_secret = _client_credentials()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(client_id, client_secret),
        timeout=10,
    )
    if resp.status_code != 200:
        raise SpotifyAuthError(f"Spotify token request failed ({resp.status_code}): {resp.text}")

    payload = resp.json()
    token = payload.get("access_token")
    expires_in = payload.get("expires_in", 3600)
    if not token:
        raise SpotifyAuthError("Spotify token response did not include an access token.")

    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = time.time() + float(expires_in)
    return token


def _authorized_headers() -> Dict[str, str]:
    token = _fetch_access_token()
    return {"Authorization": f"Bearer {token}"}


def search_tracks(query: str, limit: int = 5) -> List[Dict[str, object]]:
    """Search Spotify tracks by free-form text."""
    if not query:
        return []

    params = {"q": query, "type": "track", "limit": limit}
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/search",
            headers=_authorized_headers(),
            params=params,
            timeout=10,
        )
        if resp.status_code == 401:
            # Token likely expired; refresh once.
            resp = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {_fetch_access_token(force_refresh=True)}"},
                params=params,
                timeout=10,
            )
        if resp.status_code != 200:
            raise SpotifyApiError(f"Spotify search failed ({resp.status_code}): {resp.text}")
    except requests.RequestException as exc:
        raise SpotifyApiError(f"Could not reach Spotify: {exc}") from exc

    data = resp.json()
    tracks = data.get("tracks", {}).get("items", [])
    results: List[Dict[str, object]] = []
    for item in tracks:
        track_id = item.get("id")
        name = item.get("name")
        artists = ", ".join(artist.get("name", "") for artist in item.get("artists", []) if artist.get("name"))
        url = item.get("external_urls", {}).get("spotify")
        preview_url = item.get("preview_url")
        if not track_id or not name or not url:
            continue
        results.append(
            {
                "id": track_id,
                "name": name,
                "artists": artists or "Unknown Artist",
                "url": url,
                "preview_url": preview_url,
                "album": (item.get("album") or {}).get("name"),
            }
        )
    return results


def open_track(track: Dict[str, object]) -> bool:
    """Open the selected track in the default browser."""
    url = track.get("url") if isinstance(track, dict) else None
    if not isinstance(url, str) or not url:
        return False
    try:
        opened = webbrowser.open(url, new=1)
        return bool(opened)
    except Exception:
        return False


def describe_track(track: Dict[str, object]) -> str:
    """Return a short spoken description of a track."""
    if not isinstance(track, dict):
        return "Unknown track"
    name = track.get("name") or "Unknown title"
    artist = track.get("artists") or "Unknown artist"
    album = track.get("album")
    if album:
        return f"{name} by {artist} from the album {album}"
    return f"{name} by {artist}"


def _control_via_osascript(command: str) -> bool:
    """Execute a short AppleScript command against the Spotify app."""
    if platform.system() != "Darwin":
        raise SpotifyPlaybackError("Spotify playback controls require the Spotify desktop app on macOS.")
    try:
        proc = subprocess.run(
            ["osascript", "-e", f'tell application "Spotify" to {command}'],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except FileNotFoundError as exc:
        raise SpotifyPlaybackError("osascript utility is not available on this system.") from exc
    except subprocess.SubprocessError as exc:
        raise SpotifyPlaybackError("Spotify playback command did not complete successfully.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise SpotifyPlaybackError(stderr or "Spotify is not responding to playback commands.")
    return True


def pause_playback() -> bool:
    """Pause the current Spotify track if the desktop app is running."""
    return _control_via_osascript("pause")


def resume_playback() -> bool:
    """Resume playback for the current Spotify queue."""
    return _control_via_osascript("play")


def next_track() -> bool:
    """Skip to the next Spotify track."""
    return _control_via_osascript("next track")


def _player_state() -> str:
    """Return Spotify player state (playing/paused/stopped) if available."""
    if platform.system() != "Darwin":
        return "unsupported"
    try:
        proc = subprocess.run(
            ["osascript", "-e", 'tell application "Spotify" to player state as string'],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except FileNotFoundError as exc:
        raise SpotifyPlaybackError("osascript utility is not available on this system.") from exc
    except subprocess.SubprocessError as exc:
        raise SpotifyPlaybackError("Could not determine Spotify player state.") from exc

    stderr = (proc.stderr or "").strip().lower()
    if proc.returncode != 0:
        if "application isn't running" in stderr:
            return "stopped"
        raise SpotifyPlaybackError(stderr or "Spotify did not report its player state.")

    state = (proc.stdout or "").strip().lower()
    if not state:
        return "unknown"
    return state


def is_playing() -> bool:
    """Return True if Spotify is currently playing a track."""
    try:
        return _player_state() == "playing"
    except SpotifyPlaybackError:
        raise
    except Exception as exc:
        print(f"[spotify] is_playing warning: {exc}")
        return False


@contextmanager
def pause_for_listening():
    """
    Temporarily pause Spotify playback while recording audio so voice capture is clearer.

    Yields True if playback was paused and will be resumed on exit.
    """
    if not _AUTO_PAUSE_LISTENING:
        yield False
        return
    paused_here = False
    try:
        state = _player_state()
        if state == "playing":
            pause_playback()
            paused_here = True
    except SpotifyPlaybackError as exc:
        print(f"[spotify] pause_for_listening warning: {exc}")
    except Exception as exc:
        print(f"[spotify] pause_for_listening unexpected error: {exc}")
    try:
        yield paused_here
    finally:
        if paused_here:
            try:
                resume_playback()
            except Exception as exc:
                print(f"[spotify] Could not resume playback after listening: {exc}")
