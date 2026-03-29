"""
epub_handler.py
===============
EPUB file parsing, chapter extraction, and text processing.

Handles:
- Reading EPUB files and extracting chapters
- Cover image extraction
- Metadata extraction (author, title, language, etc.)
- Text cleaning and noise removal
- Text chunking for TTS
"""

import re
from pathlib import Path
from typing import Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


def extract_chapters(epub_path: str) -> list[dict]:
    """Extract chapters from epub as list of {title, text}.
    
    Improved detection using:
    - Heading tags (h1, h2, h3)
    - Spine order from EPUB structure
    - Table of contents when available
    """
    book = epub.read_epub(epub_path)
    chapters = []

    # Get spine order for better chapter ordering
    spine = book.spine if hasattr(book, 'spine') else []
    
    # Process items in spine order when available
    items_to_process = []
    if spine:
        for spine_item in spine:
            if isinstance(spine_item, tuple):
                item_id = spine_item[0]
            else:
                item_id = str(spine_item)
            
            item = book.get_item(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                items_to_process.append(item)
    
    # Fallback: process all document items
    if not items_to_process:
        items_to_process = [item for item in book.get_items() 
                           if item.get_type() == ebooklib.ITEM_DOCUMENT]

    for item in items_to_process:
        soup = BeautifulSoup(item.get_body_content(), "html.parser")

        # Try to get a chapter title from heading tags
        title_tag = soup.find(["h1", "h2", "h3", "h4"])
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


def chunk_text(text: str, max_words: int = 400) -> list[str]:
    """Split text into sentence-aware chunks.
    
    Args:
        text: Input text to chunk
        max_words: Maximum words per chunk
    
    Returns:
        List of text chunks
    """
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


def extract_cover(epub_path: str) -> Optional[bytes]:
    """Extract the cover image from epub. Tries JPEG first, then PNG.
    
    Args:
        epub_path: Path to EPUB file
    
    Returns:
        Cover image bytes or None if not found
    """
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


def extract_metadata(epub_path: str) -> dict:
    """Extract metadata from EPUB file.
    
    Args:
        epub_path: Path to EPUB file
    
    Returns:
        Dict with title, author, language, publisher
    """
    metadata = {
        "title": "Unknown",
        "author": "Unknown",
        "language": "en",
        "publisher": "Unknown"
    }
    
    try:
        book = epub.read_epub(epub_path)
        
        # Extract metadata
        if book.get_metadata('DC', 'title'):
            metadata["title"] = book.get_metadata('DC', 'title')[0][0]
        
        if book.get_metadata('DC', 'creator'):
            metadata["author"] = book.get_metadata('DC', 'creator')[0][0]
        
        if book.get_metadata('DC', 'language'):
            metadata["language"] = book.get_metadata('DC', 'language')[0][0]
        
        if book.get_metadata('DC', 'publisher'):
            metadata["publisher"] = book.get_metadata('DC', 'publisher')[0][0]
        
    except Exception as e:
        print(f"    [Warning] Could not extract full metadata: {e}")
    
    return metadata
