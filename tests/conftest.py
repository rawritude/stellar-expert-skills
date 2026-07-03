"""Make the bundled CLI importable as `stellar_expert` from the tests."""
import pathlib
import sys

SCRIPT_DIR = (
    pathlib.Path(__file__).resolve().parents[1]
    / "skills" / "stellar-expert" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
