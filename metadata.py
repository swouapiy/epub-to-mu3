"""
metadata.py
===========
ID3 metadata and cover image handling.

Handles:
- ID3v2.4 metadata embedding (title, artist, album, track number)
- Cover art extraction and embedding
- Thumbnail creation from cover images
- Image format detection and conversion
"""

import io
from pathlib import Path
from typing import Optional

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TRCK, COMM, TCON

try:
    from PIL import Image
except ImportError:
    Image = None


def create_thumbnail(cover_data: Optional[bytes], output_dir: Path, book_title: str) -> Optional[str]:
    """Create a thumbnail version of the cover art for display.
    
    Args:
        cover_data: Raw cover image bytes
        output_dir: Directory to save thumbnail
        book_title: Book title for filename
    
    Returns:
        Path to thumbnail file if successful, None otherwise
    """
    if not cover_data or Image is None:
        return None
    
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(cover_data))
        
        # Create thumbnail (width: 200px for display/embed)
        img.thumbnail((200, 300), Image.Resampling.LANCZOS)
        
        # Save thumbnail
        thumb_path = output_dir / f"cover_thumbnail.jpg"
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(str(thumb_path), quality=85)
        
        return str(thumb_path)
    except Exception as e:
        print(f"    [Warning] Could not create thumbnail: {e}")
        return None


def embed_comprehensive_metadata(mp3_path, metadata: dict, chapter_num: int, 
                                 chapter_title: str, cover_data: Optional[bytes] = None) -> None:
    """Embed comprehensive ID3 metadata into MP3 file.
    
    Includes: title, artist, album, track number, chapter info, cover art.
    
    Args:
        mp3_path: Path to MP3 file
        metadata: Book metadata dict with 'title' and 'author'
        chapter_num: Chapter number for ID3 tags
        chapter_title: Chapter title for ID3 tags
        cover_data: Cover image bytes (JPG or PNG)
    """
    mp3_path = Path(mp3_path)
    
    if not mp3_path.exists():
        return
    
    try:
        # Create or load ID3 tag
        try:
            audio = MP3(str(mp3_path), ID3=ID3)
        except:
            audio = MP3(str(mp3_path))
            audio.add_tags()
        
        # Add text metadata
        audio["TIT2"] = TIT2(encoding=3, text=[chapter_title])  # Chapter title
        audio["TPE1"] = TPE1(encoding=3, text=[metadata.get("author", "Unknown")])  # Artist/Author
        audio["TALB"] = TALB(encoding=3, text=[metadata.get("title", "Audiobook")])  # Album/Book title
        audio["TRCK"] = TRCK(encoding=3, text=[str(chapter_num)])  # Track number
        
        # Add chapter comment
        audio["COMM"] = COMM(encoding=3, lang="eng", desc="", text=[
            f"Chapter {chapter_num}: {chapter_title}\nFrom: {metadata.get('title', 'Unknown')}"
        ])
        
        # Add genre
        audio["TCON"] = TCON(encoding=3, text=["Audiobook"])
        
        # Add cover art if available
        if cover_data:
            # Detect image type
            if cover_data[:3] == b'\xff\xd8\xff':
                mime_type = "image/jpeg"
            elif cover_data[:4] == b'\x89PNG':
                mime_type = "image/png"
            else:
                mime_type = "image/jpeg"
            
            # Add cover art
            audio["APIC"] = APIC(
                encoding=3,
                mime=mime_type,
                type=3,  # Cover front
                desc="Cover",
                data=cover_data
            )
        
        audio.save(v2_version=4)
        
    except Exception as e:
        print(f"    [Warning] Could not embed metadata: {e}")
