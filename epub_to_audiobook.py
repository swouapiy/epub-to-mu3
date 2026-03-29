#!/usr/bin/env python3
from __future__ import annotations
"""
epub_to_audiobook.py
--------------------
Convert epub files to MP3 + WAV audiobook chapters using Kokoro TTS.
Outputs are ready to copy to a Kindle.

Setup:
    pip install -r requirements.txt

Basic Usage:
    python epub_to_audiobook.py mybook.epub
    python epub_to_audiobook.py mybook.epub --voice af_heart --language f  # French
    python epub_to_audiobook.py mybook.epub --speed 1.0  # Normal speed
    python epub_to_audiobook.py mybook.epub --quality 2  # Higher quality MP3
    python epub_to_audiobook.py ./books  # Process all .epub files in a folder

Advanced Usage:
    # Save current settings as default
    python epub_to_audiobook.py book.epub --voice bm_george --quality 2 --save-config
    
    # Resume from interrupted job
    python epub_to_audiobook.py book.epub --resume
    
    # Start fresh (clear progress)
    python epub_to_audiobook.py book.epub --restart
    
    # Use custom config file
    python epub_to_audiobook.py book.epub --config /path/to/config.json

Config File (~/.audiobook_config.json):
    {
      "voice": "af_heart",
      "language": "a",
      "speed": 0.8,
      "quality": 4
    }

Language codes: 'a' (American English), 'b' (British), 'f' (French), 'z' (German), etc.
Speed: 0.5 (slow), 0.8 (slower), 1.0 (normal), 2.0 (fast)
Quality: 0-1 (high), 4 (good/default), 9 (low)
"""


import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import soundfile as sf
import numpy as np
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
import io

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
    """Remove noise from extracted text with improved filtering."""
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    # Remove common epub artifacts (brackets, braces)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\{.*?\}", "", text)
    
    # Remove page numbers (standalone numbers at word boundaries)
    text = re.sub(r"\b\d{1,4}\b", "", text)
    
    # Remove chapter numbers like "Chapter 1", "C1", etc.
    text = re.sub(r"(?:chapter|ch|c|part|p)\s*\d+", "", text, flags=re.IGNORECASE)
    
    # Remove common headers/footers (centered text patterns)
    text = re.sub(r"^\s*-+\s*$", "", text, flags=re.MULTILINE)
    
    # Remove repeated punctuation
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    
    # Remove URLs
    text = re.sub(r"http[s]?://\S+", "", text)
    
    # Remove leading/trailing punctuation from lines
    text = re.sub(r"^[.,;:!?—–-]+\s+|[.,;:!?—–-]+$", "", text, flags=re.MULTILINE)
    
    # Final cleanup of extra spaces
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


# ── Cover extraction ─────────────────────────────────────────────────────────

def extract_cover(epub_path: str) -> Optional[bytes]:
    """Extract the cover image from epub. Tries JPEG first, then PNG."""
    try:
        book = epub.read_epub(epub_path)
        
        # Try to find cover in manifest
        for item in book.get_items():
            if "cover" in item.get_name().lower():
                mimetype = item.get_type()
                if mimetype in ["image/jpeg", "image/png"]:
                    return item.get_body_content()
        
        # Try images by type
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            mimetype = item.get_type()
            if mimetype in ["image/jpeg", "image/png"]:
                return item.get_body_content()
        
        return None
    except Exception as e:
        print(f"    [Warning] Could not extract cover: {e}")
        return None


def embed_cover_to_mp3(mp3_path: Path, cover_data: bytes) -> None:
    """Embed cover image into MP3 file as ID3 tag."""
    if not cover_data:
        return
    
    try:
        audio = MP3(str(mp3_path), ID3=ID3)
        
        # Detect image type
        if cover_data[:3] == b'\xff\xd8\xff':
            mime_type = "image/jpeg"
        elif cover_data[:4] == b'\x89PNG':
            mime_type = "image/png"
        else:
            return
        
        # Add cover art
        audio["APIC"] = APIC(
            encoding=3,
            mime=mime_type,
            type=3,  # Cover front
            desc="Cover",
            data=cover_data
        )
        audio.save()
    except Exception as e:
        print(f"    [Warning] Could not embed cover: {e}")


# ── TTS synthesis ────────────────────────────────────────────────────────────

def synthesize_chapter(text: str, voice: str, speed: float, output_path: Path, pipeline, quality: int = 4, cover_data: Optional[bytes] = None):
    """Use Kokoro to generate audio for a chapter and save as MP3 + WAV.
    
    Args:
        quality: MP3 quality (0-9, lower is better). Default 4 (good balance).
                 0-1 = high quality, 4 = good quality, 9 = low quality
    """
    import soundfile as sf

    # Kokoro works best with chunks under ~500 words
    chunks = chunk_text(text, max_words=400)
    audio_segments = []

    for i, chunk in enumerate(chunks):
        print(f"    Synthesizing chunk {i+1}/{len(chunks)}...", end="\r")
        generator = pipeline(chunk, voice=voice, speed=speed)
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
        f'ffmpeg -y -i "{wav_path}" -codec:a libmp3lame -qscale:a {quality} "{mp3_path}" -loglevel quiet'
    )
    if ffmpeg_result == 0:
        # Embed cover art if available
        if cover_data:
            embed_cover_to_mp3(mp3_path, cover_data)
        print(f"    Saved: {mp3_path.name} & {wav_path.name}          ")
    else:
        # Keep WAV if ffmpeg not available
        print(f"    Saved: {wav_path.name} (install ffmpeg for MP3)")


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


# ── Config file handling ─────────────────────────────────────────────────────

def load_config(config_path: Optional[str] = None) -> dict:
    """Load config from ~/.audiobook_config.json or specified path."""
    if config_path is None:
        config_path = Path.home() / ".audiobook_config.json"
    else:
        config_path = Path(config_path)
    
    defaults = {
        "voice": "af_heart",
        "language": "a",
        "speed": 0.8,
        "quality": 4
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            # Merge with defaults (config overrides defaults)
            defaults.update(config)
            print(f"📋 Config loaded from: {config_path}")
            return defaults
        except Exception as e:
            print(f"⚠️  Warning: Could not load config from {config_path}: {e}")
    
    return defaults


def save_config(config: dict, config_path: Optional[str] = None) -> None:
    """Save current settings to config file."""
    if config_path is None:
        config_path = Path.home() / ".audiobook_config.json"
    else:
        config_path = Path(config_path)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✅ Config saved to: {config_path}")
    except Exception as e:
        print(f"⚠️  Warning: Could not save config: {e}")


# ── Progress tracking ────────────────────────────────────────────────────────

def load_progress(epub_path: Path) -> set:
    """Load list of already-processed chapters."""
    progress_file = epub_path.parent / f".{epub_path.stem}_progress.json"
    
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                data = json.load(f)
            return set(data.get("completed", []))
        except Exception as e:
            print(f"⚠️  Warning: Could not load progress: {e}")
    
    return set()


def save_progress(epub_path: Path, completed_indices: set) -> None:
    """Save progress of processed chapters."""
    progress_file = epub_path.parent / f".{epub_path.stem}_progress.json"
    
    try:
        with open(progress_file, 'w') as f:
            json.dump({"completed": sorted(list(completed_indices))}, f)
    except Exception as e:
        print(f"⚠️  Warning: Could not save progress: {e}")


def clear_progress(epub_path: Path) -> None:
    """Clear progress file (useful for starting fresh)."""
    progress_file = epub_path.parent / f".{epub_path.stem}_progress.json"
    if progress_file.exists():
        progress_file.unlink()
        print(f"🔄 Progress cleared for {epub_path.name}")


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
    # Load config first to use as defaults
    config = load_config()
    
    parser = argparse.ArgumentParser(
        description="Convert epub to audiobook MP3s using Kokoro TTS"
    )
    parser.add_argument("path", help="Path to a .epub file or directory containing .epub files")
    parser.add_argument(
        "--voice", default=config["voice"],
        help=f"Kokoro voice to use. Options: {', '.join(AVAILABLE_VOICES)} (default: {config['voice']})"
    )
    parser.add_argument(
        "--language", default=config["language"],
        help=f"Language code: 'a' (American), 'b' (British), 'f' (French), etc. (default: {config['language']})"
    )
    parser.add_argument(
        "--speed", type=float, default=config["speed"],
        help=f"Speech speed: 0.5 (slow), 0.8 (slower), 1.0 (normal), 2.0 (fast) (default: {config['speed']})"
    )
    parser.add_argument(
        "--quality", type=int, default=config["quality"],
        help=f"MP3 quality: 0-1 (high), 4 (good, default), 9 (low) (default: {config['quality']})"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (default: <epub_name>_audiobook/)"
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to config file (default: ~/.audiobook_config.json)"
    )
    parser.add_argument(
        "--save-config", action="store_true",
        help="Save current settings to config file for future use"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume processing from last unfinished chapter (skips completed chapters)"
    )
    parser.add_argument(
        "--restart", action="store_true",
        help="Clear progress and start fresh"
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

    input_path = Path(args.path)
    if not input_path.exists():
        print(f"Error: File or directory not found: {input_path}")
        sys.exit(1)

    # Collect all epub files to process
    epub_files = []
    if input_path.is_file():
        if input_path.suffix.lower() == ".epub":
            epub_files = [input_path]
        else:
            print(f"Error: {input_path} is not an .epub file")
            sys.exit(1)
    elif input_path.is_dir():
        epub_files = sorted(input_path.glob("*.epub"))
        if not epub_files:
            print(f"Error: No .epub files found in {input_path}")
            sys.exit(1)
    else:
        print(f"Error: {input_path} is neither a file nor directory")
        sys.exit(1)

    # Save config if requested
    if args.save_config:
        config_to_save = {
            "voice": args.voice,
            "language": args.language,
            "speed": args.speed,
            "quality": args.quality
        }
        save_config(config_to_save, args.config)

    # Load Kokoro once for all files
    print(f"🔊 Loading Kokoro TTS (voice: {args.voice}, language: {args.language})...")
    try:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code=args.language)
    except Exception as e:
        print(f"Error loading Kokoro: {e}")
        print("Make sure you've installed it: pip install kokoro")
        sys.exit(1)

    # Process each epub file
    for epub_path in epub_files:
        if args.restart:
            clear_progress(epub_path)
        
        process_epub(epub_path, args.voice, args.speed, args.quality, args.output, 
                    args.resume, pipeline)


def process_epub(epub_path: Path, voice: str, speed: float, quality: int, output_base: str, enable_resume: bool, pipeline):
    """Process a single epub file with optional resume capability."""
    output_dir = Path(output_base) if output_base else epub_path.parent / f"{epub_path.stem}_audiobook"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create separate subdirectories for MP3 and WAV
    mp3_dir = output_dir / "mp3"
    wav_dir = output_dir / "wav"
    mp3_dir.mkdir(exist_ok=True)
    wav_dir.mkdir(exist_ok=True)

    print(f"\n📖 Loading epub: {epub_path.name}")
    chapters = extract_chapters(str(epub_path))
    print(f"   Found {len(chapters)} chapters\n")

    if not chapters:
        print("Error: No readable chapters found in epub.")
        return

    # Load progress if resuming
    completed = load_progress(epub_path) if enable_resume else set()
    if enable_resume and completed:
        print(f"📍 Resuming from chapter {max(completed) + 2} (already have {len(completed)} chapters)\n")

    # Extract cover once
    cover_data = extract_cover(str(epub_path))
    if cover_data:
        print(f"   Cover extracted ({len(cover_data)} bytes)\n")

    generated_files = []

    for i, chapter in enumerate(chapters, 1):
        # Skip if already processed
        if enable_resume and (i - 1) in completed:
            print(f"[{i}/{len(chapters)}] {chapter['title']} (skipped - already done)")
            continue
        
        chapter_num = f"{i:02d}"
        chapter_name = sanitize_filename(chapter['title'])
        
        # Save files to appropriate directories
        mp3_filename = f"{chapter_num}_{chapter_name}"
        wav_filename = f"{chapter_num}_{chapter_name}"
        
        mp3_path = mp3_dir / mp3_filename
        wav_path = wav_dir / wav_filename

        print(f"[{i}/{len(chapters)}] {chapter['title']}")

        try:
            # Create a temp path for synthesis, then move files
            temp_output = output_dir / mp3_filename
            synthesize_chapter(chapter["text"], voice, speed, temp_output, pipeline, quality, cover_data)
            
            # Move files to correct directories
            temp_mp3 = temp_output.with_suffix(".mp3")
            temp_wav = temp_output.with_suffix(".wav")
            
            if temp_mp3.exists():
                mp3_final = mp3_path.with_suffix(".mp3")
                temp_mp3.rename(mp3_final)
                generated_files.append((mp3_final.name, "mp3"))
            
            if temp_wav.exists():
                wav_final = wav_path.with_suffix(".wav")
                temp_wav.rename(wav_final)
                generated_files.append((wav_final.name, "wav"))
            
            # Mark as completed
            completed.add(i - 1)
            save_progress(epub_path, completed)
                
        except Exception as e:
            print(f"    [Error] Skipping chapter: {e}")

    # Clear progress on successful completion
    if len(completed) == len(chapters):
        clear_progress(epub_path)

    # Write playlists for each format
    write_playlist(mp3_dir, [f for f, fmt in generated_files if fmt == "mp3"])
    write_playlist(wav_dir, [f for f, fmt in generated_files if fmt == "wav"])

    print(f"\n✅ Done! Files saved to:")
    print(f"   📁 {mp3_dir.resolve()}")
    print(f"   📁 {wav_dir.resolve()}\n")
    print("📱 To use on Kindle:")
    print("   1. Connect Kindle via USB")
    print("   2. Copy the mp3/ folder to your Kindle's 'music' or 'audiobooks' directory")
    print("   3. Play with KOReader's music player or a KUAL audio extension\n")


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r"[^\w\s-]", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    return name[:50] or "chapter"


if __name__ == "__main__":
    main()