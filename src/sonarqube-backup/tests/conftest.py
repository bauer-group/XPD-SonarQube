import sys
from pathlib import Path

# Ensure the project root (which contains the `src` package) is importable
# regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
