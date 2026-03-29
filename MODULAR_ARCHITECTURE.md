# Modular Architecture Guide

## Overview

The `epub-to-mu3` application has been refactored into a **modular architecture** for better:
- ✅ **Troubleshooting** - Isolate bugs to specific feature modules
- ✅ **Upgrades** - Update features independently without affecting others  
- ✅ **Maintainability** - Clear separation of concerns
- ✅ **Reusability** - Import specific functions in other projects
- ✅ **Testing** - Test individual modules in isolation

## Module Structure

```
epub-to-mu3/
├── epub_to_audiobook.py       ← Main entry point (CLI orchestration)
├── epub_handler.py            ← EPUB parsing & text extraction
├── tts_synthesis.py           ← TTS & audio processing
├── metadata.py                ← ID3 metadata & cover handling
├── config_manager.py          ← Config loading & progress tracking
└── utils.py                   ← Helper utilities
```

---

## Module Details

### 1. **epub_to_audiobook.py** (Main Application)
**Responsibility:** CLI orchestration and process flow

**What it does:**
- Parses command-line arguments
- Loads configuration defaults
- Orchestrates the EPUB processing workflow
- Calls functions from other modules to build the pipeline

**Key Functions:**
- `main()` - Entry point, CLI argument parsing
- `process_epub()` - Coordinates the entire EPUB-to-audiobook conversion
- `AVAILABLE_VOICES` - List of supported TTS voices

**Dependencies:** All other modules
**Usage:**
```python
python epub_to_audiobook.py mybook.epub --voice af_heart --quality 4
```

---

### 2. **epub_handler.py** (EPUB Parsing)
**Responsibility:** Reading EPUB files and extracting content

**What it does:**
- Extracts chapter text from EPUB structure
- Cleans extracted text (removes page numbers, headers, footers)
- Splits text into synthesis-friendly chunks
- Extracts cover images
- Extracts book metadata (title, author, language)

**Key Functions:**
- `extract_chapters(epub_path) → list[dict]` - Get chapters with structured data
- `clean_text(text) → str` - Remove EPUB artifacts and noise
- `chunk_text(text, max_words) → list[str]` - Split into manageable pieces
- `extract_cover(epub_path) → bytes | None` - Get cover image
- `extract_metadata(epub_path) → dict` - Extract title, author, language

**No Dependencies:** Uses only standard libraries + ebooklib, BeautifulSoup

**Usage:**
```python
from epub_handler import extract_chapters, extract_metadata

chapters = extract_chapters("mybook.epub")
metadata = extract_metadata("mybook.epub")

for chapter in chapters:
    print(chapter['title'])
    print(chapter['text'][:100])  # First 100 chars
```

---

### 3. **tts_synthesis.py** (Text-to-Speech & Audio)
**Responsibility:** TTS synthesis and audio processing

**What it does:**
- Synthesizes text chunks using Kokoro TTS
- Runs chunk synthesis in parallel (ThreadPoolExecutor)
- Normalizes audio for consistent loudness
- Encodes audio as WAV and MP3 via ffmpeg
- Handles audio concatenation and file output

**Key Functions:**
- `synthesize_chunk(chunk, voice, speed, pipeline) → ndarray` - Synthesize one text chunk
- `normalize_audio(audio, target_loudness) → ndarray` - Normalize audio loudness
- `synthesize_chapter_parallel(...)` - Full chapter synthesis with parallel chunks + metadata embedding

**Dependencies:** Kokoro TTS, numpy, soundfile, ffmpeg (subprocess)

**Usage:**
```python
from tts_synthesis import synthesize_chapter_parallel
from kokoro import KPipeline

pipeline = KPipeline(lang_code='a')

synthesize_chapter_parallel(
    text="Chapter content...",
    voice="af_heart",
    speed=0.8,
    output_path=Path("output.mp3"),
    pipeline=pipeline,
    quality=4,
    metadata={"title": "MyBook", "author": "Me"},
    chapter_num=1,
    chapter_title="Chapter 1"
)
```

---

### 4. **metadata.py** (ID3 Tags & Cover Art)
**Responsibility:** MP3 metadata embedding and image processing

**What it does:**
- Embeds ID3v2.4 tags into MP3 files
- Adds chapter title, author, album info
- Embeds full-resolution cover art
- Creates thumbnail versions of cover images
- Handles image format detection (JPEG/PNG)

**Key Functions:**
- `create_thumbnail(cover_data, output_dir, title) → str | None` - Generate small cover thumbnail
- `embed_comprehensive_metadata(mp3_path, metadata, chapter_num, chapter_title, cover_data)` - Write ID3 tags

**Dependencies:** mutagen, Pillow (PIL)

**Usage:**
```python
from metadata import create_thumbnail, embed_comprehensive_metadata

# Create thumbnail (200x300px)
thumb_path = create_thumbnail(cover_bytes, Path("output/"), "My Book")

# Embed full metadata into MP3
embed_comprehensive_metadata(
    mp3_path=Path("output/chapter1.mp3"),
    metadata={"title": "My Book", "author": "John Doe"},
    chapter_num=1,
    chapter_title="Introduction",
    cover_data=cover_bytes
)
```

---

### 5. **config_manager.py** (Settings & Progress)
**Responsibility:** Configuration loading and resume functionality

**What it does:**
- Loads config from `~/.audiobook_config.json`
- Saves user preferences as defaults
- Tracks progress (which chapters completed)
- Enables resume from interrupted jobs
- Manages progress checkpoint files

**Key Functions:**
- `load_config(config_path) → dict` - Get user settings + defaults
- `save_config(config, path)` - Save current settings for next time
- `load_progress(epub_path) → set` - Get completed chapter indices
- `save_progress(epub_path, completed)` - Track progress
- `clear_progress(epub_path)` - Clear checkpoints for fresh start

**No Runtime Dependencies:** Uses only standard JSON

**Usage:**
```python
from config_manager import load_config, save_progress, load_progress
from pathlib import Path

# Load config (merges user config + defaults)
config = load_config()
voice = config['voice']        # User preference or default
speed = config['speed']

# Track progress for resume
completed = load_progress(Path("book.epub"))
print(f"Already completed: chapters {sorted(completed)}")

completed.add(1)  # Mark chapter 1 done
save_progress(Path("book.epub"), completed)
```

---

### 6. **utils.py** (Utility Functions)
**Responsibility:** General-purpose helper functions

**What it does:**
- Sanitizes filenames (removes special characters)
- Creates M3U playlists for media players

**Key Functions:**
- `sanitize_filename(name) → str` - Clean filename for filesystem
- `write_playlist(output_dir, filenames)` - Generate M3U playlist

**No Dependencies:** Uses only standard libraries

**Usage:**
```python
from utils import sanitize_filename, write_playlist
from pathlib import Path

# Safe filenames
safe_name = sanitize_filename("Chapter 1: The Beginning!")
# → "Chapter_1_The_Beginning"

# Create playlist
write_playlist(
    Path("output/mp3/"),
    ["01_intro.mp3", "02_chapter1.mp3", "03_chapter2.mp3"]
)
# → Creates output/mp3/playlist.m3u
```

---

## How Modules Work Together

### Flow: EPUB → Audiobook

```
epub_to_audiobook.py (main)
    ↓
[CLI parsing & config loading]
    ↓
    ├─→ epub_handler.extract_chapters()       [Parse EPUB structure]
    ├─→ epub_handler.extract_metadata()       [Get title/author]
    ├─→ epub_handler.extract_cover()          [Get cover image]
    ├─→ metadata.create_thumbnail()           [Shrink cover for display]
    │
    └─→ FOR EACH CHAPTER:
        ├─→ tts_synthesis.synthesize_chapter_parallel()
        │   ├─→ epub_handler.chunk_text()     [Split chapter]
        │   ├─→ tts_synthesis.synthesize_chunk() [TTS synthesis ×N parallel]
        │   ├─→ tts_synthesis.normalize_audio() [Loudness leveling]
        │   └─→ ffmpeg [encode WAV→MP3]
        │
        ├─→ metadata.embed_comprehensive_metadata() [ID3 tags]
        ├─→ config_manager.save_progress()   [Mark chapter done]
        └─→ utils.write_playlist()           [Update M3U]
```

---

## Troubleshooting by Module

| Problem | Module | Solution |
|---------|--------|----------|
| EPUB text is messy/incomplete | `epub_handler.py` | Improve `clean_text()` regex patterns |
| Audio sounds weird/distorted | `tts_synthesis.py` | Check `normalize_audio()` or ffmpeg settings |
| MP3 metadata not showing in players | `metadata.py` | Verify ID3 tag writing in `embed_comprehensive_metadata()` |
| Resume doesn't work | `config_manager.py` | Check progress JSON file format |
| Filenames have weird characters | `utils.py` | Update `sanitize_filename()` regex |
| Config not loading | `config_manager.py` | Check `~/.audiobook_config.json` format |

---

## Upgrading Features

### Example 1: Add New Voice Support
**File:** `epub_to_audiobook.py`
```python
AVAILABLE_VOICES = [
    "af_heart", ...,
    "my_new_voice"  # ← Just add here
]
```

### Example 2: Improve Text Cleaning
**File:** `epub_handler.py` → `clean_text()`
```python
def clean_text(text: str) -> str:
    """Add new regex patterns here"""
    text = re.sub(r"YOUR_PATTERN", "", text)  # ← Add pattern
    return text
```

### Example 3: Add New MP3 Tag
**File:** `metadata.py` → `embed_comprehensive_metadata()`
```python
# Add new ID3 frame
audio["TYER"] = TYER(encoding=3, text=["2025"])  # Year tag
```

### Example 4: Better Audio Normalization
**File:** `tts_synthesis.py` → `normalize_audio()`
```python
def normalize_audio(audio, target_loudness=-20.0):
    # Replace with scipy LUFS normalization, etc.
    pass
```

---

## Testing Individual Modules

```bash
# Test EPUB parsing
python -c "from epub_handler import extract_chapters; chapters = extract_chapters('test.epub'); print(f'Found {len(chapters)} chapters')"

# Test config loading
python -c "from config_manager import load_config; cfg = load_config(); print(f'Voice: {cfg[\"voice\"]}')"

# Test filename sanitization
python -c "from utils import sanitize_filename; print(sanitize_filename('Ch@pt&er 1!'))"

# Check syntax of all files
python -m py_compile *.py && echo "✅ All files OK"
```

---

## Dependencies per Module

| Module | Imports | External Deps |
|--------|---------|---------------|
| `epub_handler.py` | ebooklib, BeautifulSoup4 | None (stdlib only) |
| `tts_synthesis.py` | numpy, soundfile, ffmpeg | Kokoro, ffmpeg |
| `metadata.py` | mutagen, PIL | Pillow (optional) |
| `config_manager.py` | json, pathlib | None (stdlib only) |
| `utils.py` | pathlib, re | None (stdlib only) |
| `epub_to_audiobook.py` | All others | All of the above |

---

## File Organization Benefits

✅ **Each module is <300 lines** - Easy to understand and debug
✅ **One responsibility per file** - Easier to test  
✅ **Reusable components** - Use `metadata.py` in other projects
✅ **Clear dependencies** - Know what each module needs
✅ **Parallel development** - Two developers can work on different modules simultaneously
✅ **Bug isolation** - Problem in MP3 encoding? Check `tts_synthesis.py` only

---

## Next Steps

1. **Review** each module's `__doc__` strings for detailed info
2. **Test** individual modules in Python REPL (see "Testing" section above)
3. **Modify** any module independently for upgrades
4. **Debug** issues in isolation by module

Happy modular coding! 🎉
