"""Explicit, one-time data setup for RI BUROM's isolated Cloudflare rehearsal.

Never import real customers, staff, messages, invoices, or production credentials.
The caller must check the exact staging host, mode and HTTP Basic access first.
"""
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def initialize_staging(app, password):
    """Create an isolated Owner and two labeled demonstration tours exactly once."""
    from models import AuditLog, Package, User, db

    if not password or len(password) < 16:
        return {"status": "staging_access_password_too_short"}, 503

    with app.app_context():
        # Refuse any database with live-looking business records. This is a
        # safety interlock, not a replacement for validating Hyperdrive's target.
        counts = {}
        for table in ("users", "packages", "messages", "marketplace_inquiries"):
            counts[table] = db.session.execute(
                text(f"SELECT count(*) FROM {table}")
            ).scalar_one()

        if counts["users"]:
            if db.session.query(User.id).filter_by(username="staging-owner", role="owner").first():
                return {"status": "already_initialized", "username": "staging-owner"}, 200
            return {"status": "refused_existing_staff"}, 409
        if any(counts[table] for table in ("packages", "messages", "marketplace_inquiries")):
            return {"status": "refused_nonempty_business_database"}, 409

        owner = User(
            username="staging-owner",
            full_name="Staging Demo Owner",
            password_hash=generate_password_hash(
                password, method="scrypt:16384:8:1"
            ),
            role="owner",
            is_active=True,
        )
        db.session.add(owner)
        db.session.flush()
        db.session.add(AuditLog(
            user_id=owner.id, username=owner.username,
            action="staging_initial_owner_created",
            details="Isolated rehearsal-only initial owner",
        ))
        db.session.add_all([
            Package(
                title="[STAGING DEMO] Jowai Heritage Walk",
                slug="staging-demo-jowai-heritage",
                description="SYNTHETIC TEST TOUR. This is not a real offer or a copy of production data.",
                location="Jowai, Meghalaya",
                duration="1 Day",
                price="Price on request",
                category="Culture",
                itinerary="Demo itinerary for testing only.",
                included="Demo content only.",
                excluded="Not bookable.",
                published=True, featured=True, sort_order=1,
            ),
            Package(
                title="[STAGING DEMO] Dawki River Experience",
                slug="staging-demo-dawki-river",
                description="SYNTHETIC TEST TOUR. This is not a real offer or a copy of production data.",
                location="Dawki, Meghalaya",
                duration="1 Day",
                price="Price on request",
                category="Nature",
                itinerary="Demo itinerary for testing only.",
                included="Demo content only.",
                excluded="Not bookable.",
                published=True, featured=True, sort_order=2,
            ),
        ])
        db.session.commit()
        return {"status": "initialized", "username": "staging-owner", "demo_tours": 2}, 200
