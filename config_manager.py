"""
config_manager.py
=================
Configuration file handling and progress tracking.

Handles:
- Loading and saving user configuration
- Tracking progress for resume capability
- Progress file management
"""

import json
from pathlib import Path


# ── Configuration management ────────────────────────────────────────────────

def load_config(config_path: Optional[str] = None) -> dict:
    """Load config from ~/.audiobook_config.json or specified path.
    
    Args:
        config_path: Custom path to config file (optional)
    
    Returns:
        Config dict with keys: voice, language, speed, quality
    """
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
    """Save current settings to config file.
    
    Args:
        config: Config dict to save
        config_path: Custom path to config file (optional)
    """
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


# ── Progress tracking ──────────────────────────────────────────────────────

def load_progress(epub_path: Path) -> set:
    """Load list of already-processed chapters.
    
    Args:
        epub_path: Path to EPUB file
    
    Returns:
        Set of completed chapter indices
    """
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
    """Save progress of processed chapters.
    
    Args:
        epub_path: Path to EPUB file
        completed_indices: Set of completed chapter indices
    """
    progress_file = epub_path.parent / f".{epub_path.stem}_progress.json"
    
    try:
        with open(progress_file, 'w') as f:
            json.dump({"completed": sorted(list(completed_indices))}, f)
    except Exception as e:
        print(f"⚠️  Warning: Could not save progress: {e}")


def clear_progress(epub_path: Path) -> None:
    """Clear progress file (useful for starting fresh).
    
    Args:
        epub_path: Path to EPUB file
    """
    progress_file = epub_path.parent / f".{epub_path.stem}_progress.json"
    if progress_file.exists():
        progress_file.unlink()
        print(f"🔄 Progress cleared for {epub_path.name}")


# Fix missing import
from typing import Optional
