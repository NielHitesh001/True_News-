"""Render the source transparency page to docs/transparency.html.

Usage: PYTHONPATH=src:. .venv/bin/python scripts/render_transparency.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from newsx.transparency import render_transparency_page


def main() -> None:
    out = render_transparency_page(ROOT / "docs" / "transparency.html")
    print(f"Successfully generated Source Transparency Registry: {out}")


if __name__ == "__main__":
    main()
