"""Download a sample MP4 from a URL for ad-hoc testing.

The platform is validated with deterministic synthetic videos
(``generate_test_videos.py``); this helper only fetches an external clip when
you want to eyeball detection/tracking on real footage. It does NOT provide
ground truth, so it is not part of the reproducible benchmark.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    urllib.request.urlretrieve(url, dest)  # noqa: S310 - operator-supplied URL
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a sample video")
    parser.add_argument("--url", required=True, help="direct URL to an .mp4 file")
    parser.add_argument("--out", default="datasets/videos/sample.mp4")
    args = parser.parse_args()
    path = download(args.url, Path(args.out))
    print(f"Saved {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
