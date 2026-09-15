import traceback

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
