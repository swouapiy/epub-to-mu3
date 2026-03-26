# epub-to-audiobook

Convert EPUB files to MP3 + WAV audiobook chapters using **Kokoro TTS**. Perfect for creating audiobooks to listen on your devices.

## Features

✨ **Multi-format output** – Generates both MP3 and WAV files for each chapter  
📚 **Batch processing** – Convert a single EPUB or an entire folder of EPUBs at once  
🌍 **Multi-language support** – English, French, German, and more  
🎤 **Multiple voices** – Choose from 11 different voices  
📱 **Kindle-ready** – Includes M3U playlist for easy playback  
⚙️ **Smart chunking** – Splits long chapters into manageable audio chunks  

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd epub-to-mu3
```

### 2. Create a Python virtual environment

```bash
python3 -m venv audiobook
source audiobook/bin/activate  # On Windows: audiobook\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Single file conversion
```bash
python epub_to_audiobook.py mybook.epub
```

### Convert with custom voice
```bash
python epub_to_audiobook.py mybook.epub --voice af_bella
```

### Convert to French
```bash
python epub_to_audiobook.py mybook.epub --language f --voice af_heart
```

### Batch convert folder
```bash
python epub_to_audiobook.py ./books  # Converts all .epub files
```

### Custom output directory
```bash
python epub_to_audiobook.py mybook.epub --output ./my_audiobooks
```

### List available voices
```bash
python epub_to_audiobook.py --list-voices
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `path` | - | Path to `.epub` file or folder containing `.epub` files |
| `--voice` | `af_heart` | Kokoro voice (see available voices below) |
| `--language` | `a` | Language code: `a` (US English), `b` (British), `f` (French), `z` (German) |
| `--output` | `<epub_name>_audiobook/` | Output directory for audio files |
| `--list-voices` | - | Show available voices and exit |

## Available Voices

Female voices:
- `af_heart`, `af_bella`, `af_nicole`, `af_sarah`, `af_sky`

Male voices:
- `am_adam`, `am_michael`, `bm_george`, `bm_lewis`

Mixed:
- `bf_emma`, `bf_isabella`

## Output Structure

```
my_audiobook_folder/
├── 01_Chapter_One.mp3
├── 01_Chapter_One.wav
├── 02_Chapter_Two.mp3
├── 02_Chapter_Two.wav
└── playlist.m3u
```

## Using on Kindle

1. Connect your Kindle via USB
2. Copy the output folder to your Kindle's `music/` or `audiobooks/` directory
3. Open the folder on your Kindle and play using:
   - KOReader's music player, or
   - A KUAL audio extension

## Requirements

- Python 3.10+
- `ebooklib` – EPUB parsing
- `beautifulsoup4` – HTML content extraction
- `kokoro` – TTS engine
- `soundfile` – Audio file writing
- `numpy` – Audio processing
- `ffmpeg` (optional, but recommended) – MP3 conversion from WAV

To install ffmpeg:
- **macOS**: `brew install ffmpeg`
- **Ubuntu**: `sudo apt-get install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org)

## Troubleshooting

**Missing ffmpeg?** WAV files will still be generated, but MP3 conversion will be skipped.

**Language not working?** Check that your Kokoro version supports the language code.

**Permission errors?** Your Kindle may need to be in file transfer mode.

## License

MIT
