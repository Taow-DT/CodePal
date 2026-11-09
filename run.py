"""Root entry script (used by `python -m codepal` and by PyInstaller)."""
import sys
from pathlib import Path

# Ensure the project root is importable when frozen / invoked as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from codepal.main import main  # noqa: E402

if __name__ == "__main__":
    main()
