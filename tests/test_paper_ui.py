from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PaperUiContractTests(unittest.TestCase):
    def test_home_preserves_cms_and_form_contracts(self):
        source = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        for section in ('hero', 'about', 'tours', 'why', 'blog', 'contact'):
            self.assertIn(f'public.home.visibility.{section}', source)
            self.assertIn(f'home_order_index.{section}', source)
        for binding in ('public.content.hero_title', 'public.content.hero_subtitle',
                        'settings.hero_animation_video', 'name="csrf_token"',
                        'action="/send_message"', 'name="tour_interest"'):
            self.assertIn(binding, source)

    def test_tour_art_is_separate_from_dynamic_title(self):
        source = (ROOT / 'templates/tour_detail.html').read_text(encoding='utf-8')
        self.assertIn('<h1 class="rb-hero-title">{{ pkg.title }}</h1>', source)
        self.assertIn('<figure class="rb-tour-art"><img', source)
        self.assertNotIn('background-image:', source)
        for field in ('location', 'duration', 'difficulty', 'itinerary', 'included',
                      'excluded', 'price', 'best_season', 'pdf_file'):
            self.assertIn(f'pkg.{field}', source)

    def test_waterfall_is_home_only_and_pinned(self):
        pages = ('index', 'tour_detail', 'tours', 'marketplace_public', 'marketplace_provider', 'about')
        for page in pages:
            source = (ROOT / f'templates/{page}.html').read_text(encoding='utf-8')
            self.assertEqual('js/ri-burom-waterfall.js' in source, page == 'index')
        for name in ('gsap', 'ScrollTrigger'):
            self.assertIn('3.12.5', (ROOT / f'static/vendor/gsap-3.12.5/{name}.min.js').read_text(encoding='utf-8')[:300])
        source = (ROOT / 'static/js/ri-burom-waterfall.js').read_text(encoding='utf-8')
        for feature in ('prefers-reduced-motion', 'gsap.registerPlugin(ScrollTrigger)',
                        'ResizeObserver', 'strokeDashoffset', 'dataset.initialized'):
            self.assertIn(feature, source)

    def test_marketplace_form_and_shared_footer_remain(self):
        provider = (ROOT / 'templates/marketplace_provider.html').read_text(encoding='utf-8')
        for contract in ('name="csrf_token"', 'name="provider_id"', 'name="service_ids"',
                         "url_for('marketplace_inquiry_create')", 'rb-provider-layout'):
            self.assertIn(contract, provider)
        self.assertIn("include '_footer.html'", (ROOT / 'templates/tours.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
