import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ui import render_app


render_app()
