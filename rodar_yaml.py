import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "src"))

from pascalpy.cli import main  # noqa: E402


if __name__ == "__main__":
    arguments = sys.argv[1:] or ["meu_experimento.yaml"]
    raise SystemExit(main(arguments))

