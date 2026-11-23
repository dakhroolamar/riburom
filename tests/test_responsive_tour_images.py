"""Safe responsive Cloudinary variants for public tour covers."""
import unittest

from cms_pages import card_srcset

ORIGINAL = (
    "https://res.cloudinary.com/gpxpatvk/image/upload/"
    "v1789578684/riburom/heritage.jpg"
)


class ResponsiveTourImagesTests(unittest.TestCase):
    def test_versioned_original_is_limited_to_compact_card_sizes(self):
        result = card_srcset(ORIGINAL)
        self.assertEqual(len(result.split(", ")), 2)
        self.assertIn("/f_auto,q_auto,w_360,c_limit/v1789578684/", result)
        self.assertIn("/f_auto,q_auto,w_640,c_limit/v1789578684/", result)
        self.assertNotIn("w_800", result)

    def test_existing_cms_800_pixel_cover_is_safely_rederived(self):
        cover = ORIGINAL.replace("/image/upload/", "/image/upload/f_auto,q_auto,w_800,c_limit/")
        self.assertEqual(card_srcset(cover), card_srcset(ORIGINAL))

    def test_unknown_hosts_signed_urls_and_foreign_transforms_unchanged(self):
        self.assertEqual(card_srcset(""), "")
        self.assertEqual(card_srcset("https://example.com/image.jpg"), "")
        self.assertEqual(card_srcset(ORIGINAL + "?signature=private"), "")
        self.assertEqual(card_srcset(ORIGINAL.replace(
            "/image/upload/", "/image/upload/c_fill,w_100/")), "")


if __name__ == "__main__":
    unittest.main()
