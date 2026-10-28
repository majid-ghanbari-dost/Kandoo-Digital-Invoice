"""PyInstaller entry point for the Windows one-folder CLI build."""

from __future__ import annotations

import sys

from image_extraction_adapter.cli import main


if __name__ == "__main__":
    sys.exit(main())
