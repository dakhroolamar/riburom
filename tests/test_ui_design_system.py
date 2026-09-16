from pathlib import Path
import unittest


class UiDesignSystemTests(unittest.TestCase):
    def test_public_theme_loads_shared_design_system(self):
        root = Path(__file__).resolve().parents[1]
        theme = (root / 'templates' / '_public_theme.html').read_text(encoding='utf-8')
        self.assertIn("css/ri-burom-ui.css", theme)

    def test_design_system_exposes_core_tokens_and_components(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / 'static' / 'css' / 'ri-burom-ui.css').read_text(encoding='utf-8')
        for token in (
            '--rb-radius-lg',
            '--rb-shadow-md',
            '--rb-container',
            '.rb-container',
            '.rb-card',
            '.rb-control',
            '.rb-segmented',
            '.rb-empty',
        ):
            self.assertIn(token, css)


if __name__ == '__main__':
    unittest.main()
