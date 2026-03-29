"""
utils.py
========
General utility functions.

Handles:
- Filename sanitization
- Playlist generation
"""

import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename.
    
    Args:
        name: Input string
    
    Returns:
        Sanitized filename (alphanumeric, underscores, hyphens)
    """
    name = re.sub(r"[^\w\s-]", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    return name[:50] or "chapter"


def write_playlist(output_dir: Path, filenames: list[str]):
    """Write an M3U playlist for the Kindle audio player.
    
    Args:
        output_dir: Directory to save playlist
        filenames: List of audio filenames to include
    """
    playlist_path = output_dir / "playlist.m3u"
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name in filenames:
            f.write(f"{name}\n")
    print(f"\nPlaylist saved: {playlist_path}")
