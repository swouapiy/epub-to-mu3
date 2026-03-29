#!/usr/bin/env python3
from __future__ import annotations
"""
epub_to_audiobook.py
--------------------
Main entry point for converting EPUB files to MP3/WAV audiobooks using Kokoro TTS.

This is a modular application with features separated into logical modules:
- epub_handler.py: EPUB parsing and text extraction
- tts_synthesis.py: TTS and audio processing
- metadata.py: ID3 metadata and cover handling
- config_manager.py: Configuration and progress tracking
- utils.py: Utility functions

To use on Kindle, outputs are ready to copy.

Features:
- High-quality parallel chunk synthesis (faster processing)
- Comprehensive ID3v2.4 metadata embedding (author, title, cover art)
- Automatic audio normalization (consistent volume)
- Improved chapter auto-detection using EPUB spine order
- Cover thumbnail extraction for display
- Resume capability with progress tracking
- Quality and bitrate control for MP3s
- Config file support for default settings

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

Output Structure:
    mybook_audiobook/
    ├── cover_thumbnail.jpg       # Extracted cover thumbnail for display
    ├── mp3/
    │   ├── 01_chapter1.mp3       # With full metadata and cover art in ID3
    │   ├── 02_chapter2.mp3
    │   └── playlist.m3u
    └── wav/
        ├── 01_chapter1.wav
        ├── 02_chapter2.wav
        └── playlist.m3u

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import soundfile as sf
import numpy as np
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TRCK, COMM, TCON
import io

try:
    from PIL import Image
except ImportError:
    Image = None

# Import from feature modules
from epub_handler import chunk_text, extract_chapters, extract_cover, extract_metadata
from tts_synthesis import synthesize_chapter_parallel, normalize_audio, synthesize_chunk
from metadata import create_thumbnail, embed_comprehensive_metadata
from config_manager import load_config, save_config, load_progress, save_progress, clear_progress
from utils import sanitize_filename, write_playlist

# ── Available voices ────────────────────────────────────────────────────────

AVAILABLE_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"
]


# ── Main ──────────────────────────────────────────────────────────────────────

AVAILABLE_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"
]

# ── Main processing ────────────────────────────────────────────────────────

def process_epub(epub_path: Path, voice: str, speed: float, quality: int, 
                 output_base: str, enable_resume: bool, pipeline):
    """Process a single EPUB file with optional resume capability.
    
    Features:
    - Parallel chunk synthesis for faster processing
    - Comprehensive ID3 metadata embedding
    - Audio normalization for consistent volume
    - Thumbnail cover extraction
    - Progress tracking for resume functionality
    
    Args:
        epub_path: Path to EPUB file
        voice: Kokoro voice to use
        speed: Speech speed multiplier
        quality: MP3 quality (0-9)
        output_base: Base output directory
        enable_resume: Whether to enable resume from previous progress
        pipeline: Kokoro TTS pipeline instance
    """
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

    # Extract metadata for ID3 tags
    metadata = extract_metadata(str(epub_path))
    print(f"   📝 Title: {metadata['title']}")
    print(f"   👤 Author: {metadata['author']}\n")

    # Load progress if resuming
    completed = load_progress(epub_path) if enable_resume else set()
    if enable_resume and completed:
        print(f"📍 Resuming from chapter {max(completed) + 2} (already have {len(completed)} chapters)\n")

    # Extract cover once
    cover_data = extract_cover(str(epub_path))
    if cover_data:
        print(f"   🖼️  Cover extracted ({len(cover_data)} bytes)")
        
        # Create thumbnail for display
        thumb_path = create_thumbnail(cover_data, output_dir, metadata['title'])
        if thumb_path:
            print(f"   📸 Thumbnail created: {Path(thumb_path).name}\n")
        else:
            print()

    generated_files = []

    for i, chapter in enumerate(chapters, 1):
        # Skip if already processed
        if enable_resume and (i - 1) in completed:
            print(f"[{i}/{len(chapters)}] {chapter['title']} (skipped - already done)")
            continue
        
        chapter_num = f"{i:02d}"
        chapter_name = sanitize_filename(chapter['title'])
        
        # Output file path (will be moved to correct directory)
        temp_output = output_dir / f"{chapter_num}_{chapter_name}"

        print(f"[{i}/{len(chapters)}] {chapter['title']}")

        try:
            # Use parallel synthesis for faster processing
            synthesize_chapter_parallel(
                chapter["text"],
                voice,
                speed,
                temp_output,
                pipeline,
                quality=quality,
                metadata=metadata,
                chapter_num=i,
                chapter_title=chapter['title'],
                cover_data=cover_data,
                max_workers=2  # Parallel workers for chunk synthesis
            )
            
            # Move files to correct directories
            temp_mp3 = temp_output.with_suffix(".mp3")
            temp_wav = temp_output.with_suffix(".wav")
            
            if temp_mp3.exists():
                mp3_final = mp3_dir / f"{chapter_num}_{chapter_name}.mp3"
                temp_mp3.rename(mp3_final)
                generated_files.append((mp3_final.name, "mp3"))
            
            if temp_wav.exists():
                wav_final = wav_dir / f"{chapter_num}_{chapter_name}.wav"
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


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """Parse arguments and process EPUB files."""
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


if __name__ == "__main__":
    main()