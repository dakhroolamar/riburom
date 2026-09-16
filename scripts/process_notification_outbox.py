"""Retry durable RI BUROM notification outbox rows.

Intended for an operator-triggered job or future scheduled worker. Importing
the Flask app is side-effect free; this script does not run schema migrations.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from notifications import process_pending_notifications  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()

    with app.app_context():
        summary = process_pending_notifications(limit=args.limit)

    print(
        'Notification outbox processed: '
        f"sent={summary['sent']} failed={summary['failed']} skipped={summary['skipped']}",
        flush=True,
    )


if __name__ == '__main__':
    main()
