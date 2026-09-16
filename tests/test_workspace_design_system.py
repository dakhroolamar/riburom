from pathlib import Path
import unittest


class WorkspaceDesignSystemTests(unittest.TestCase):
    def test_workspace_css_exposes_core_primitives(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / 'static' / 'css' / 'ri-burom-workspace.css').read_text(encoding='utf-8')
        for token in (
            '--rbw-brand',
            '--rbw-surface',
            '.rbw-page-frame',
            '.rbw-page-heading',
            '.rbw-toolbar',
            '.rbw-status',
        ):
            self.assertIn(token, css)


if __name__ == '__main__':
    unittest.main()
