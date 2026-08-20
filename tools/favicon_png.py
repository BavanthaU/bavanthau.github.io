#!/usr/bin/env python3
"""Rasterise the BU mark to PNG fallbacks.

Kept out of build.py on purpose: build.py is standard library only, and turning SVG text
into pixels needs a font rasteriser. Run this only when the mark itself changes.

    python3 tools/favicon_png.py

Writes assets/favicon-32.png (legacy tab icon) and assets/favicon-180.png (apple-touch).
Needs a headless Chrome on PATH.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import _bu_svg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [("favicon-32.png", 32, 4), ("favicon-180.png", 180, 0)]


def chrome():
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("no headless Chrome found on PATH")


def main():
    exe = chrome()
    for name, size, radius in TARGETS:
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "icon.html"
            page.write_text(
                "<body style='margin:0;background:transparent'>"
                + _bu_svg(radius, size)
                + "</body>"
            )
            out = Path(td) / "shot.png"
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                 "--default-background-color=00000000",
                 f"--screenshot={out}", f"--window-size={size},{size}", str(page)],
                check=True, capture_output=True)
            (ROOT / "assets" / name).write_bytes(out.read_bytes())
            print(f"wrote assets/{name}  ({size}x{size})")


if __name__ == "__main__":
    main()
