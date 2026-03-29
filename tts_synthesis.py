"""
tts_synthesis.py
================
Text-to-speech synthesis and audio processing.

Handles:
- Audio normalization (consistent loudness)
- Individual chunk synthesis for parallel processing
- Full chapter synthesis with parallel chunk processing
- Audio concatenation and MP3 encoding via ffmpeg
"""

import os
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import numpy as np
import soundfile as sf

from epub_handler import chunk_text


# ── Audio processing ────────────────────────────────────────────────────────

def normalize_audio(audio: np.ndarray, target_loudness: float = -20.0) -> np.ndarray:
    """Normalize audio to consistent perceived loudness using peak normalization.
    
    Args:
        audio: Audio array (samples as floats)
        target_loudness: Target loudness adjustment (normalized to 0dB peak)
    
    Returns:
        Normalized audio array
    """
    if len(audio) == 0:
        return audio
    
    # Find peak amplitude
    peak = np.max(np.abs(audio))
    
    if peak > 0:
        # Normalize to prevent clipping (peak at ~0.95)
        normalized = audio * (0.95 / peak)
    else:
        normalized = audio
    
    return normalized.astype(np.float32)


# ── Chunk synthesis ────────────────────────────────────────────────────────

def synthesize_chunk(chunk: str, voice: str, speed: float, pipeline) -> np.ndarray:
    """Synthesize a single chunk of text to audio. For use in parallel processing.
    
    Args:
        chunk: Text chunk to synthesize
        voice: Kokoro voice to use
        speed: Speech speed (0.5-2.0)
        pipeline: Kokoro TTS pipeline
    
    Returns:
        Audio data as numpy array
    """
    try:
        audio_data = np.array([], dtype=np.float32)
        generator = pipeline(chunk, voice=voice, speed=speed)
        for _, _, audio in generator:
            audio_data = np.concatenate([audio_data, audio]) if len(audio_data) > 0 else audio
        return audio_data
    except Exception as e:
        print(f"    [Error synthesizing chunk] {e}")
        return np.array([], dtype=np.float32)


# ── Chapter synthesis with parallel processing ──────────────────────────────

def synthesize_chapter_parallel(text: str, voice: str, speed: float, output_path: Path, 
                                 pipeline, quality: int = 4, metadata: Optional[dict] = None,
                                 chapter_num: int = 1, chapter_title: str = "Chapter",
                                 cover_data: Optional[bytes] = None, max_workers: int = 2):
    """Synthesize chapter using parallel chunk processing for speed.
    
    Args:
        text: Chapter text
        voice: Kokoro voice
        speed: Speech speed
        output_path: Output file path (without extension)
        pipeline: Kokoro TTS pipeline
        quality: MP3 quality (0-9, where 0 is highest)
        metadata: Book metadata dict
        chapter_num: Chapter number for ID3 tags
        chapter_title: Chapter title for ID3 tags
        cover_data: Cover image bytes
        max_workers: Number of parallel workers (threads)
    """
    from metadata import embed_comprehensive_metadata
    
    # Split text into chunks
    chunks = chunk_text(text, max_words=400)
    
    if not chunks:
        print("    [Warning] No audio chunks generated for this chapter.")
        return
    
    audio_segments = [None] * len(chunks)  # Preserve order
    lock = Lock()
    
    print(f"    Processing {len(chunks)} chunks in parallel (up to {max_workers} workers)...")
    
    # Process chunks in parallel but maintain order
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and map to indices
        future_to_idx = {
            executor.submit(synthesize_chunk, chunks[i], voice, speed, pipeline): i 
            for i in range(len(chunks))
        }
        
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                audio_segments[idx] = future.result()
                completed += 1
                print(f"    Synthesized chunk {completed}/{len(chunks)}...", end="\r")
            except Exception as e:
                print(f"    [Error] Chunk {idx + 1} failed: {e}")
                audio_segments[idx] = np.array([], dtype=np.float32)
    
    # Filter out empty segments and concatenate in order
    audio_data = [seg for seg in audio_segments if seg is not None and len(seg) > 0]
    
    if not audio_data:
        print("\n    [Warning] No audio generated for this chapter.")
        return
    
    combined = np.concatenate(audio_data)
    
    # Apply normalization for consistent volume
    combined = normalize_audio(combined)
    
    # Save as WAV first
    wav_path = output_path.with_suffix(".wav")
    sf.write(str(wav_path), combined, 24000)
    
    # Convert to MP3
    mp3_path = output_path.with_suffix(".mp3")
    ffmpeg_result = os.system(
        f'ffmpeg -y -i "{wav_path}" -codec:a libmp3lame -qscale:a {quality} "{mp3_path}" -loglevel quiet'
    )
    
    if ffmpeg_result == 0:
        # Embed comprehensive metadata
        if not metadata:
            metadata = {"title": "Audiobook", "author": "Unknown"}
        
        embed_comprehensive_metadata(mp3_path, metadata, chapter_num, chapter_title, cover_data)
        print(f"✓ Saved: {mp3_path.name} & {wav_path.name}         ")
    else:
        print(f"    Saved: {wav_path.name} (install ffmpeg for MP3)")
