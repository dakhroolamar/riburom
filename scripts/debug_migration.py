import os
import sys
import traceback

# Render executes this file from the scripts/ directory, so explicitly add
# the repository root to Python's import path before importing the Flask app.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app
from flask_migrate import upgrade


with app.app_context():
    print("=== STARTING MIGRATION ===", flush=True)
    try:
        upgrade(directory="migrations")
        print("=== MIGRATION COMPLETE ===", flush=True)
    except Exception:
        print("=== MIGRATION FAILED ===", flush=True)
        traceback.print_exc()
        raise
