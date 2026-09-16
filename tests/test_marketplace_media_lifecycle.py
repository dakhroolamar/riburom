import os
import unittest
from unittest.mock import patch

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceMediaLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_media_lifecycle')
        import wsgi
        from app import app, db
        from marketplace_models import Provider, Service, ServiceCategory, ServiceImage

        cls.app = app
        cls.db = db
        cls.Provider = Provider
        cls.Service = Service
        cls.ServiceCategory = ServiceCategory
        cls.ServiceImage = ServiceImage
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = app.app_context()
        cls.context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def setUp(self):
        self.db.session.query(self.ServiceImage).delete()
        self.db.session.query(self.Service).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.query(self.ServiceCategory).delete()
        self.db.session.commit()

    def _service(self):
        provider = self.Provider(
            name='Media Provider',
            slug='media-provider',
            status='APPROVED',
            is_active=True,
        )
        category = self.ServiceCategory(
            name='Media Category',
            slug='media-category',
            is_active=True,
            sort_order=1,
        )
        service = self.Service(
            provider=provider,
            service_category=category,
            name='Media Service',
            slug='media-service',
            status='PUBLISHED',
            is_active=True,
        )
        self.db.session.add_all([provider, category, service])
        self.db.session.commit()
        return service

    def test_referenced_gallery_media_is_not_deleted(self):
        from media_lifecycle import delete_marketplace_media_if_unreferenced

        service = self._service()
        old_url = 'https://res.cloudinary.com/test/image/upload/v1/riburom/old.jpg'
        service.image_url = 'https://res.cloudinary.com/test/image/upload/v1/riburom/new.jpg'
        self.db.session.add(self.ServiceImage(
            service=service,
            image_url=old_url,
            sort_order=0,
        ))
        self.db.session.commit()

        with patch('media_lifecycle.delete_media') as delete:
            removed = delete_marketplace_media_if_unreferenced(old_url)

        self.assertFalse(removed)
        delete.assert_not_called()

    def test_unreferenced_marketplace_media_is_deleted(self):
        from media_lifecycle import delete_marketplace_media_if_unreferenced

        old_url = 'https://res.cloudinary.com/test/image/upload/v1/riburom/orphan.jpg'
        with patch('media_lifecycle.delete_media') as delete:
            removed = delete_marketplace_media_if_unreferenced(old_url)

        self.assertTrue(removed)
        delete.assert_called_once_with(old_url)

    def test_primary_gallery_replacement_excludes_deleted_image(self):
        service = self._service()
        first = self.ServiceImage(
            service=service,
            image_url='uploads/first.jpg',
            sort_order=0,
        )
        second = self.ServiceImage(
            service=service,
            image_url='uploads/second.jpg',
            sort_order=1,
        )
        service.image_url = first.image_url
        self.db.session.add_all([first, second])
        self.db.session.commit()

        remaining = next(
            (candidate for candidate in service.images if candidate.id != first.id),
            None,
        )
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining.image_url, second.image_url)


if __name__ == '__main__':
    unittest.main()
