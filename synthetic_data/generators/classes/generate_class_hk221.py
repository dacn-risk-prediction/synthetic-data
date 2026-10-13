import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semester_generator import generate_class


if __name__ == "__main__":
    generate_class("HK221")
