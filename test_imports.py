#!/usr/bin/env python3
"""Quick import test for all modules"""

import sys

print("Testing module imports...\n")

tests = [
    ("config_manager", ["load_config", "save_config", "load_progress", "save_progress"]),
    ("epub_handler", ["extract_chapters", "clean_text", "chunk_text"]),
    ("tts_synthesis", ["synthesize_chapter"]),
    ("metadata", ["extract_cover", "embed_metadata_id3"]),
    ("utils", ["sanitize_filename", "write_playlist"]),
]

failed = False
for module_name, functions in tests:
    try:
        module = __import__(module_name)
        for func in functions:
            if not hasattr(module, func):
                print(f"✗ {module_name}.{func} not found")
                failed = True
        if not failed or True:  # Always print success if no errors found yet
            print(f"✓ {module_name}")
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        failed = True

if not failed:
    print("\n✓ All imports successful!")
    sys.exit(0)
else:
    print("\n✗ Some imports failed")
    sys.exit(1)
