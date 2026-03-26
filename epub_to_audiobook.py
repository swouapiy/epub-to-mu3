#!/usr/bin/env python3
"""
epub_to_audiobook.py
--------------------
Convert an epub file to MP3 chapters using Kokoro TTS.
Outputs are ready to copy to a Kindle.

Requirements:
    pip install ebooklib beautifulsoup4 kokoro soundfile numpy

Usage:
    python epub_to_audiobook.py mybook.epub
    python epub_to_audiobook.py mybook.epub --voice af_heart --output ./audiobook
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ── Dependency check ────────────────────────────────────────────────────────
def check_deps():
    missing = []
    for pkg in ["ebooklib", "bs4", "kokoro", "soundfile", "numpy"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("Missing dependencies. Run:\n")
        pip_names = {"bs4": "beautifulsoup4"}
        pkgs = " ".join(pip_names.get(p, p) for p in missing)
        print(f"  pip install {pkgs}\n")
        sys.exit(1)

check_deps()

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import soundfile as sf
import numpy as np

# ── Text extraction ──────────────────────────────────────────────────────────

def extract_chapters(epub_path: str) -> list[dict]:
    """Extract chapters from epub as list of {title, text}."""
    book = epub.read_epub(epub_path)
    chapters = []

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        soup = BeautifulSoup(item.get_body_content(), "html.parser")

        # Try to get a chapter title
        title_tag = soup.find(["h1", "h2", "h3"])
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract and clean body text
        text = clean_text(soup.get_text(separator=" "))

        # Skip very short fragments (nav pages, covers, etc.)
        if len(text) < 200:
            continue

        chapters.append({"title": title or f"Chapter {len(chapters)+1}", "text": text})

    return chapters


def clean_text(text: str) -> str:
    """Remove noise from extracted text."""
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove lines that are just numbers (page numbers)
    text = re.sub(r"(?<!\w)\d{1,4}(?!\w)", "", text)
    # Remove common epub artifacts
    text = re.sub(r"\[.*?\]", "", text)
    return text.strip()


# ── TTS synthesis ────────────────────────────────────────────────────────────

def synthesize_chapter(text: str, voice: str, output_path: Path, pipeline):
    """Use Kokoro to generate audio for a chapter and save as MP3."""
    import soundfile as sf

    # Kokoro works best with chunks under ~500 words
    chunks = chunk_text(text, max_words=400)
    audio_segments = []

    for i, chunk in enumerate(chunks):
        print(f"    Synthesizing chunk {i+1}/{len(chunks)}...", end="\r")
        generator = pipeline(chunk, voice=voice)
        for _, _, audio in generator:
            audio_segments.append(audio)

    if not audio_segments:
        print("    [Warning] No audio generated for this chapter.")
        return

    combined = np.concatenate(audio_segments)

    # Save as WAV first, then convert to MP3 via ffmpeg if available
    wav_path = output_path.with_suffix(".wav")
    sf.write(str(wav_path), combined, 24000)

    # Try converting to MP3 (smaller, Kindle-friendly)
    mp3_path = output_path.with_suffix(".mp3")
    ffmpeg_result = os.system(
        f'ffmpeg -y -i "{wav_path}" -codec:a libmp3lame -qscale:a 4 "{mp3_path}" -loglevel quiet'
    )
    if ffmpeg_result == 0:
        wav_path.unlink()  # Remove WAV after successful conversion
        print(f"    Saved: {mp3_path.name}          ")
    else:
        # Keep WAV if ffmpeg not available
        wav_path.rename(output_path.with_suffix(".wav"))
        print(f"    Saved: {output_path.with_suffix('.wav').name} (install ffmpeg for MP3)")


def chunk_text(text: str, max_words: int = 400) -> list[str]:
    """Split text into sentence-aware chunks."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current, count = [], [], 0

    for sentence in sentences:
        words = len(sentence.split())
        if count + words > max_words and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(sentence)
        count += words

    if current:
        chunks.append(" ".join(current))

    return chunks


# ── Playlist ─────────────────────────────────────────────────────────────────

def write_playlist(output_dir: Path, filenames: list[str]):
    """Write an M3U playlist for the Kindle audio player."""
    playlist_path = output_dir / "playlist.m3u"
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name in filenames:
            f.write(f"{name}\n")
    print(f"\nPlaylist saved: {playlist_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

AVAILABLE_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"
]

def main():
    parser = argparse.ArgumentParser(
        description="Convert epub to audiobook MP3s using Kokoro TTS"
    )
    parser.add_argument("epub", help="Path to the input .epub file")
    parser.add_argument(
        "--voice", default="af_heart",
        help=f"Kokoro voice to use. Options: {', '.join(AVAILABLE_VOICES)} (default: af_heart)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (default: <epub_name>_audiobook/)"
    )
    parser.add_argument(
        "--list-voices", action="store_true",
        help="Print available voices and exit"
    )
    args = parser.parse_args()

    if args.list_voices:
        print("Available voices:")
        for v in AVAILABLE_VOICES:
            print(f"  {v}")
        sys.exit(0)

    epub_path = Path(args.epub)
    if not epub_path.exists():
        print(f"Error: File not found: {epub_path}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else epub_path.parent / f"{epub_path.stem}_audiobook"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📖 Loading epub: {epub_path.name}")
    chapters = extract_chapters(str(epub_path))
    print(f"   Found {len(chapters)} chapters\n")

    if not chapters:
        print("Error: No readable chapters found in epub.")
        sys.exit(1)

    print(f"🔊 Loading Kokoro TTS (voice: {args.voice})...")
    try:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code="a")  # 'a' = American English
    except Exception as e:
        print(f"Error loading Kokoro: {e}")
        print("Make sure you've installed it: pip install kokoro")
        sys.exit(1)

    generated_files = []

    for i, chapter in enumerate(chapters):
        filename_stem = f"{i+1:02d}_{sanitize_filename(chapter['title'])}"
        output_path = output_dir / filename_stem
        ext = ".mp3"  # Will fall back to .wav if ffmpeg missing

        print(f"[{i+1}/{len(chapters)}] {chapter['title']}")

        try:
            synthesize_chapter(chapter["text"], args.voice, output_path, pipeline)
            # Record whichever file was actually saved
            mp3 = output_path.with_suffix(".mp3")
            wav = output_path.with_suffix(".wav")
            if mp3.exists():
                generated_files.append(mp3.name)
            elif wav.exists():
                generated_files.append(wav.name)
        except Exception as e:
            print(f"    [Error] Skipping chapter: {e}")

    write_playlist(output_dir, generated_files)

    print(f"\n✅ Done! {len(generated_files)} chapters saved to:")
    print(f"   {output_dir.resolve()}\n")
    print("📱 To use on Kindle:")
    print("   1. Connect Kindle via USB")
    print("   2. Copy the output folder to your Kindle's 'music' or 'audiobooks' directory")
    print("   3. Play with KOReader's music player or a KUAL audio extension\n")


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r"[^\w\s-]", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    return name[:50] or "chapter"


if __name__ == "__main__":
    main()