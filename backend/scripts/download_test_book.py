"""
Download a public domain test book for development.
Uses Project Gutenberg (public domain — no copyright issues).
Usage: python scripts/download_test_book.py
"""
import os

import httpx

# Pride and Prejudice — Project Gutenberg (public domain)
GUTENBERG_URL = "https://www.gutenberg.org/files/1342/1342-0.txt"
OUTPUT_PATH = "tests/fixtures/pride_and_prejudice.txt"


def download():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with httpx.stream("GET", GUTENBERG_URL) as r:
        with open(OUTPUT_PATH, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"Downloaded to {OUTPUT_PATH} ({os.path.getsize(OUTPUT_PATH):,} bytes)")


if __name__ == "__main__":
    download()
