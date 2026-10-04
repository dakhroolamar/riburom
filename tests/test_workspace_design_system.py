from pathlib import Path
import unittest


WORKSPACE_TEMPLATES = (
    'workspace.html',
    'cms.html',
    'cms_media.html',
    'cms_structure.html',
    'cms_backgrounds.html',
    'marketplace.html',
    'marketplace_appearance.html',
    'marketplace_inquiries.html',
    'marketplace_inquiry_detail.html',
    'customer_analytics.html',
    'account.html',
    'edit_package.html',
    'edit_team_member.html',
)


class WorkspaceDesignSystemTests(unittest.TestCase):
    def test_workspace_templates_load_shared_css(self):
        root = Path(__file__).resolve().parents[1]
        for filename in WORKSPACE_TEMPLATES:
            source = (root / 'templates' / filename).read_text(encoding='utf-8')
            with self.subTest(template=filename):
                self.assertIn("extends 'control_room/base.html'", source)

    def test_workspace_css_exposes_core_primitives(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / 'static' / 'css' / 'control-room.css').read_text(encoding='utf-8')
        for token in (
            '--cr-forest',
            '--cr-canvas',
            '.cr-shell',
            '.cr-page-heading',
            '.cr-toolbar',
            '.cr-badge',
        ):
            self.assertIn(token, css)


if __name__ == '__main__':
    unittest.main()
