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

    def test_paper_typography_respects_cms_font_tokens(self):
        source = (ROOT / 'static/css/ri-burom-ui.css').read_text(encoding='utf-8')
        self.assertIn("--rb-font-cultural:var(--rb-heading-font", source)
        self.assertIn("--rb-font-body:var(--rb-body-font", source)

    def test_hero_opening_film_keeps_landscape_gap_and_larger_logo(self):
        js = (ROOT / 'static/js/ri-burom-home-fixes.js').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-home-fixes.css').read_text(encoding='utf-8')
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        landscape = (ROOT / 'templates/_paper_landscape.html').read_text(encoding='utf-8')

        self.assertIn("video.classList.add('rb-hero-opening-film')", js)
        self.assertIn("video.parentElement !== hero", js)
        self.assertNotIn("stage.appendChild(video)", js)
        self.assertIn("ri-burom-home-fixes.css?v=4", js)
        self.assertIn("landscapeRect.top - heroRect.top - configuredGap", js)
        self.assertIn("originalWidth * 2", js)
        self.assertIn("--rb-hero-landscape-gap", css)
        self.assertIn("var(--rb-home-landscape-height) - var(--rb-hero-landscape-gap)", css)
        self.assertIn("object-fit:cover!important", css)
        self.assertIn("rb-hero-video-playing .rb-hero-content", css)
        self.assertIn("max-width:min(86vw,320px)!important", css)
        self.assertIn("max-height:220px!important", css)
        self.assertIn("ri-burom-home-fixes.css') }}?v=4", home)
        self.assertIn("ri-burom-home-fixes.js') }}?v=4", home)
        self.assertNotIn('ri-burom-home-fixes', landscape)

    def test_home_gallery_interactions_are_cms_driven(self):
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        js = (ROOT / 'static/js/ri-burom-home-fixes.js').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-home-fixes.css').read_text(encoding='utf-8')
        cms = (ROOT / 'cms_backgrounds.py').read_text(encoding='utf-8')
        cms_template = (ROOT / 'templates/cms_backgrounds.html').read_text(encoding='utf-8')

        for contract in ('data-rb-river-gallery-host', 'data-rb-river-gallery',
                         'data-rb-about-gallery', 'data-rb-about-flip',
                         'rb-experience-rail', 'data-rb-rail-track'):
            self.assertIn(contract, home)
        for contract in ('home_gallery', 'home_about_gallery', 'bindGalleryExitZoom',
                         'scrollBy', 'is-flipping-next', 'requestAnimationFrame'):
            self.assertIn(contract, js)
        for contract in ('scroll-snap-type:x mandatory', '.rb-experience-rail',
                         '.rb-about-flip', '@keyframes rb-calendar-flip-next'):
            self.assertIn(contract, css)
        self.assertIn('GALLERY_LIMIT = 10', cms)
        self.assertIn("request.files.getlist('images')", cms)
        self.assertIn("/workspace/cms/galleries/save", cms)
        self.assertIn('multiple required', cms_template)

    def test_why_section_uses_torn_aged_paper_not_flat_green_panel(self):
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-home-fixes.css').read_text(encoding='utf-8')
        self.assertIn('rb-aged-paper-tear', home)
        self.assertNotIn('class="rb-story rb-paper-edge bg-green-900 text-white rb-section-space"', home)
        self.assertIn('clip-path:polygon(', css)
        self.assertIn('repeating-linear-gradient', css)
        self.assertIn('repeating-radial-gradient', css)
        self.assertIn('drop-shadow', css)

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
                        'ResizeObserver', 'dataset.initialized', 'pointermove',
                        'nearestVisiblePoint', 'rippleContribution', 'data-rb-water-canvas'):
            self.assertIn(feature, source)
        css = (ROOT / 'static/css/ri-burom-ui.css').read_text(encoding='utf-8')
        for feature in ('.rb-water-canvas', '.rb-water-route', '.rb-water-live', '.rb-water-shield'):
            self.assertIn(feature, css)
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        self.assertIn('viewBox="0 0 1000 1800"', home)
        self.assertIn('data-rb-water-canvas', home)
        self.assertIn('data-rb-water-shield', home)
        self.assertIn('class="rb-water-route" fill="none"', home)
        self.assertIn("ri-burom-waterfall.js') }}?v=17", home)
        theme = (ROOT / 'templates/_public_theme.html').read_text(encoding='utf-8')
        self.assertIn("ri-burom-ui.css') }}?v=16", theme)

    def test_marketplace_form_and_shared_footer_remain(self):
        provider = (ROOT / 'templates/marketplace_provider.html').read_text(encoding='utf-8')
        for contract in ('name="csrf_token"', 'name="provider_id"', 'name="service_ids"',
                         "url_for('marketplace_inquiry_create')", 'rb-provider-layout'):
            self.assertIn(contract, provider)
        self.assertIn("include '_footer.html'", (ROOT / 'templates/tours.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
