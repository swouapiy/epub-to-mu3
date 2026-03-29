# New Features Implementation Guide

## Summary of Improvements

All requested features have been successfully implemented in the EPUB-to-audiobook converter:

### 1. ✅ Python 3.9 Type Hints Fix
- **Issue**: Used `bytes | None` syntax (Python 3.10+ only)
- **Solution**: Changed to `Optional[bytes]` with proper import from `typing` module
- **Impact**: Code now runs on Python 3.9 without syntax errors
- **Location**: Lines ~96, ~157 in epub_to_audiobook.py

Example before:
```python
def extract_cover(epub_path: str) -> bytes | None:
```

Example after:
```python
from typing import Optional
def extract_cover(epub_path: str) -> Optional[bytes]:
```

---

### 2. ✅ Quality/Bitrate Options for MP3
- **CLI Argument**: `--quality` (0-9 scale)
  - 0-1: High quality (larger file)
  - 4: Good quality (default, balanced)
  - 9: Low quality (smaller file)
  
**Usage**:
```bash
# Default quality (4)
python epub_to_audiobook.py book.epub

# High quality
python epub_to_audiobook.py book.epub --quality 1

# Lower quality/smaller file
python epub_to_audiobook.py book.epub --quality 8
```

**Technical Details**:
- Uses ffmpeg's `-qscale:a` parameter for libmp3lame encoder
- Default is 4 (good balance between quality and file size)
- Can be saved to config for consistent use

---

### 3. ✅ Config File for Default Settings
- **Location**: `~/.audiobook_config.json` (user's home directory)
- **Custom Path**: `--config /path/to/config.json`

**Config File Structure**:
```json
{
  "voice": "af_heart",
  "language": "a",
  "speed": 0.8,
  "quality": 4
}
```

**How to Use**:
```bash
# Create/update config with current settings
python epub_to_audiobook.py book.epub --voice bm_george --quality 2 --save-config

# Next time, these settings are used by default
python epub_to_audiobook.py book.epub

# Override individual settings
python epub_to_audiobook.py book.epub --voice af_heart

# Use a custom config file
python epub_to_audiobook.py book.epub --config /path/to/my_config.json
```

**Benefits**:
- No need to specify common preferences every time
- Can have different configs for different use cases
- Config loads automatically on startup

---

### 4. ✅ Improved Text Preprocessing
Enhanced `clean_text()` function now removes:

**Features Added**:
- ✅ Better page number removal (word boundary matching)
- ✅ Chapter numbers (Chapter 1, C1, Part 5, etc.)
- ✅ Repeated punctuation (... becomes .)
- ✅ URL removal (http/https links)
- ✅ Brackets, braces, and common artifacts
- ✅ Leading/trailing punctuation from lines
- ✅ Header/footer patterns (lines with just dashes)

**Before**:
```python
def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<!\w)\d{1,4}(?!\w)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    return text.strip()
```

**After**: (Much more comprehensive)
```python
def clean_text(text: str) -> str:
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    # Remove common epub artifacts
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\{.*?\}", "", text)
    
    # Remove page numbers
    text = re.sub(r"\b\d{1,4}\b", "", text)
    
    # Remove chapter numbers
    text = re.sub(r"(?:chapter|ch|c|part|p)\s*\d+", "", text, flags=re.IGNORECASE)
    
    # Remove repeated punctuation, URLs, etc.
    # ... (see full implementation)
```

**Result**: Cleaner, more natural-sounding audio output.

---

### 5. ✅ Resume Capability with Progress Tracking
- **Progress File**: `.{filename}_progress.json` in the same directory as the EPUB
- **Automatically Saves**: After each successful chapter synthesis
- **Automatically Clears**: When all chapters are successfully processed

**Usage**:
```bash
# Start processing
python epub_to_audiobook.py book.epub
# [Interrupt with Ctrl+C after 5 chapters]

# Resume from chapter 6
python epub_to_audiobook.py book.epub --resume
# Skips chapters 1-5, continues from chapter 6

# Start completely fresh (clear progress)
python epub_to_audiobook.py book.epub --restart
```

**How it Works**:
1. Loads `.{filename}_progress.json` if it exists
2. Tracks completed chapter indices
3. Skips already-processed chapters with `--resume` flag
4. Saves progress after each chapter
5. Auto-clears progress file on 100% completion

**Example Progress File**:
```json
{
  "completed": [0, 1, 2, 3, 4]
}
```

**Benefits**:
- Process large books without fear of losing progress
- Resume after power loss, network issues, or interruptions
- No wasted processing time on already-completed chapters
- Clean progress tracking with JSON

---

## Complete Usage Examples

### Basic Usage
```bash
python epub_to_audiobook.py book.epub
```

### With All New Features
```bash
# Process with custom voice and high quality, save as defaults
python epub_to_audiobook.py book.epub \
  --voice bm_george \
  --language f \
  --speed 1.0 \
  --quality 1 \
  --save-config

# Later, just use defaults
python epub_to_audiobook.py another_book.epub

# If interrupted, resume easily
python epub_to_audiobook.py another_book.epub --resume

# Start over if needed
python epub_to_audiobook.py another_book.epub --restart
```

### Batch Processing with Config
```bash
# Create config for French audiobooks
python epub_to_audiobook.py dummy.epub --language f --speed 0.8 --save-config

# Process all French books with saved settings
python epub_to_audiobook.py ./french_books/
```

### Quality Variations
```bash
# High quality (for personal listening)
python epub_to_audiobook.py book.epub --quality 1

# Balanced (default)
python epub_to_audiobook.py book.epub --quality 4

# Smaller files (for storage-limited devices)
python epub_to_audiobook.py book.epub --quality 8
```

---

## Technical Changes Summary

### Files Modified:
1. **epub_to_audiobook.py** - Main application file with all improvements
   - Added imports: `json`, `Optional` from typing
   - Removed: `check_deps()` function (now requires requirements.txt)
   - New functions: `load_config()`, `save_config()`, `load_progress()`, `save_progress()`, `clear_progress()`
   - Enhanced: `clean_text()`, `synthesize_chapter()`, `process_epub()`, `main()`
   - Fixed all type hints for Python 3.9 compatibility

### Files Created:
1. **.audiobook_config.example.json** - Example config template for users

### Dependencies:
- All existing dependencies still required (no new ones added)
- Config and progress tracking use only standard library (`json`)

---

## Testing Recommendations

1. **Test Python 3.9 Compatibility**:
   ```bash
   source audiobook/bin/activate
   python --version  # Should be 3.9.x
   python -m py_compile epub_to_audiobook.py  # Should pass
   ```

2. **Test Config System**:
   ```bash
   python epub_to_audiobook.py book.epub --save-config
   cat ~/.audiobook_config.json  # Verify config saved
   python epub_to_audiobook.py book.epub  # Should use saved settings
   ```

3. **Test Resume Capability**:
   ```bash
   # Start processing
   python epub_to_audiobook.py book.epub
   # Interrupt with Ctrl+C after few chapters
   
   # Check progress file exists
   ls .book_progress.json
   
   # Resume
   python epub_to_audiobook.py book.epub --resume
   # Should skip completed chapters
   
   # Check cleanup
   ls .book_progress.json  # Should be deleted after completion
   ```

4. **Test Text Preprocessing**:
   - Process a book and verify cleaner text in audio
   - Check for removal of page numbers, chapter markers, etc.

5. **Test Quality Options**:
   ```bash
   python epub_to_audiobook.py book.epub --quality 1  # High quality
   python epub_to_audiobook.py book.epub --quality 4  # Default
   python epub_to_audiobook.py book.epub --quality 9  # Low quality
   # Compare file sizes and listen to samples
   ```

---

## Backward Compatibility

✅ **Fully Backward Compatible**
- All new features are optional
- Old commands still work: `python epub_to_audiobook.py book.epub`
- Default behavior unchanged
- Only improvement without user action: text preprocessing quality

---

## Future Enhancement Ideas

- Batch config per directory
- Progress UI with percentage
- Parallel chapter processing
- Cover art caching between books
- Chapter merging options
- Metadata tagging (author, date)
- Support for PDF inputs
