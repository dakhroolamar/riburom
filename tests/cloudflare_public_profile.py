"""Profile the full public Flask routes on the existing synthetic SQLite preview."""
import json
from math import ceil
from statistics import median
from time import perf_counter

from sqlalchemy import event
from tests.ui_preview import app, db
from cms_media_models import MediaAsset, MediaCollection, MediaCollectionItem
from models import Package, TravellerReview

ROUTES = ("/", "/all_tours", "/about", "/marketplace", "/stories", "/api/public-section-backgrounds")


def main():
    with app.app_context():
        asset = MediaAsset(path="performance-fixture.jpg", title="Synthetic photo")
        keys = ["hero", "footer_partners", "home_gallery", "home_about_gallery"]
        keys.extend(f"tour-{p.id}" for p in Package.query.all())
        for key in keys:
            collection = MediaCollection(key=key, title=key)
            collection.items.append(MediaCollectionItem(asset=asset, position=0))
            db.session.add(collection)
        db.session.add(TravellerReview(name="Fixture", rating=5, comment="Synthetic", status="published", is_visible=True))
        db.session.commit()
        statements = []
        event.listen(db.engine, "before_cursor_execute", lambda *args: statements.append(1))
    client = app.test_client(use_cookies=False)
    for route in ROUTES:
        client.get(route)
        times, counts = [], []
        for _ in range(30):
            statements.clear()
            start = perf_counter()
            response = client.get(route)
            times.append((perf_counter() - start) * 1000)
            assert response.status_code == 200, (route, response.status_code)
            counts.append(len(statements))
        print(json.dumps(dict(route=route, sql=sorted(set(counts)), samples=len(times),
                              median_ms=round(median(times), 2), p95_ms=round(sorted(times)[ceil(.95*len(times))-1], 2))))


if __name__ == "__main__":
    main()
