from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PaperUiContractTests(unittest.TestCase):
    def test_home_preserves_cms_and_form_contracts(self):
        source = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        for section in ('hero', 'about', 'tours', 'why', 'blog', 'contact'):
            self.assertIn(f'public.home.visibility.{section}', source)
            if section != 'blog':
                self.assertIn(f'home_order_index.{section}', source)
        for binding in ('public.content.hero_title', 'public.content.hero_subtitle',
                        'name="csrf_token"',
                        'action="/send_message"', 'name="tour_interest"'):
            self.assertIn(binding, source)

    def test_paper_typography_respects_cms_font_tokens(self):
        source = (ROOT / 'static/css/ri-burom-ui.css').read_text(encoding='utf-8')
        self.assertIn("--rb-font-cultural:var(--rb-heading-font", source)
        self.assertIn("--rb-font-body:var(--rb-body-font", source)

    def test_editorial_hero_keeps_copy_visible_and_preserves_cms_logo(self):
        js = (ROOT / 'static/js/ri-burom-home-fixes.js').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-editorial.css').read_text(encoding='utf-8')
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        landscape = (ROOT / 'templates/_paper_landscape.html').read_text(encoding='utf-8')
        editorial = js.split("if (document.body.classList.contains('rb-studio-public')) {", 1)[1].split('return;', 1)[0]
        self.assertIn('stage.appendChild(video)', editorial)
        self.assertIn("video.classList.add('rb-hero-opening-film')", editorial)
        self.assertNotIn('logo.style.setProperty', editorial)
        self.assertNotIn('originalWidth * 2', editorial)
        self.assertIn('settings.hero_logo_width', home)
        self.assertIn('settings.hero_animation_video', home)
        self.assertIn('rb-studio-public', home)
        self.assertIn('rb-editorial-hero', home)
        self.assertIn('.rb-hero-content', css)
        self.assertIn('visibility:visible!important', css)
        self.assertIn('pointer-events:auto!important', css)
        self.assertIn('[data-reveal]{opacity:1;', css)
        self.assertIn("ri-burom-home-fixes.css') }}?v=9", home)
        self.assertIn("ri-burom-home-fixes.js') }}?v=11", home)
        self.assertNotIn('ri-burom-home-fixes', landscape)

    def test_home_gallery_interactions_are_cms_driven(self):
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        js = (ROOT / 'static/js/ri-burom-home-fixes.js').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-home-fixes.css').read_text(encoding='utf-8')
        cms = (ROOT / 'cms_backgrounds.py').read_text(encoding='utf-8')
        cms_template = (ROOT / 'templates/cms_backgrounds.html').read_text(encoding='utf-8')
        gallery_template = (ROOT / 'templates/_cms_gallery.html').read_text(encoding='utf-8')

        self.assertIn('data-gallery-prev', gallery_template)
        self.assertIn('data-gallery-next', gallery_template)
        self.assertIn('data-gallery-pause', gallery_template)
        self.assertIn('data-gallery-prev', home)
        self.assertIn('data-gallery-next', home)
        self.assertIn('data-gallery-pause', home)
        self.assertIn('class="rb-rail-button" type="button" data-rb-rail-prev', home)
        self.assertIn('class="rb-rail-button" type="button" data-rb-rail-next', home)
        self.assertNotIn('data-rb-water-shield', gallery_template)
        self.assertNotIn('data-rb-water-shield', home)
        for contract in ('data-rb-river-gallery-host', 'data-rb-river-gallery',
                         'data-rb-about-gallery', 'data-rb-about-flip',
                         'rb-experience-rail', 'data-rb-rail-track'):
            self.assertIn(contract, home)
        for contract in ('home_gallery', 'home_about_gallery', 'window.RiBuromGallery.init',
                         'scrollBy', 'is-flipping-next'):
            self.assertIn(contract, js)
        for contract in ('scroll-snap-type:x mandatory', '.rb-experience-rail',
                         '.rb-about-flip', '@keyframes rb-calendar-flip-next'):
            self.assertIn(contract, css)
        self.assertIn('GALLERY_LIMIT = 10', cms)
        self.assertIn("request.files.getlist('images')", cms)
        self.assertIn("/workspace/cms/galleries/save", cms)
        self.assertIn('multiple required', cms_template)

    def test_why_section_uses_open_editorial_layout_with_cms_content(self):
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-editorial.css').read_text(encoding='utf-8')
        self.assertIn('rb-editorial-values', home)
        self.assertIn('public.content.home_why_title', home)
        for number in range(1, 5):
            self.assertIn(f'public.content.why{number}_title', home)
            self.assertIn(f'public.content.why{number}_text', home)
        self.assertNotIn('rb-aged-paper-tear', home)
        self.assertNotIn('class="rb-story rb-paper-edge bg-green-900 text-white rb-section-space"', home)
        self.assertIn('rb-home-why', css)
        self.assertIn('background:transparent!important', css)
        self.assertIn('border-radius:0!important', css)

    def test_tour_art_is_separate_from_dynamic_title(self):
        source = (ROOT / 'templates/tour_detail.html').read_text(encoding='utf-8')
        self.assertIn('<h1 class="rb-hero-title">{{ pkg.title }}</h1>', source)
        self.assertIn('<figure class="rb-tour-art"><img', source)
        self.assertNotIn('background-image:', source)
        for field in ('location', 'duration', 'difficulty', 'itinerary', 'included',
                      'excluded', 'price', 'best_season', 'pdf_file'):
            self.assertIn(f'pkg.{field}', source)

    def test_homepage_has_no_river_runtime_or_artwork(self):
        home = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        css = (ROOT / 'static/css/ri-burom-ui.css').read_text(encoding='utf-8')
        gallery = (ROOT / 'templates/_cms_gallery.html').read_text(encoding='utf-8')
        for forbidden in ('ri-burom-waterfall.js', 'gsap.min.js', 'ScrollTrigger.min.js',
                          'data-rb-waterfall', 'data-rb-water-canvas', 'rb-waterfall',
                          'rb-water-route', 'rb-water-static', 'data-rb-water-shield',
                          'data-rb-water-source'):
            self.assertNotIn(forbidden, home)
        for forbidden in ('.rb-water-canvas', '.rb-waterfall', '.rb-water-route',
                          '.rb-water-static', '.rb-water-live', '.rb-water-shield',
                          '--rb-river-gutter'):
            self.assertNotIn(forbidden, css)
        self.assertNotIn('data-rb-water-shield', gallery)
        landscape = (ROOT / 'templates/_paper_landscape.html').read_text(encoding='utf-8')
        about_fallback = (ROOT / 'templates/_paper_falls.html').read_text(encoding='utf-8')
        for water_token in ('#4fa8c7', '#c4e9e9', '#85c4cf'):
            self.assertNotIn(water_token, landscape)
            self.assertNotIn(water_token, about_fallback)
        self.assertIn("ri-burom-home-fixes.js') }}?v=11", home)

    def test_marketplace_form_and_shared_footer_remain(self):
        provider = (ROOT / 'templates/marketplace_provider.html').read_text(encoding='utf-8')
        for contract in ('name="csrf_token"', 'name="provider_id"', 'name="service_ids"',
                         "url_for('marketplace_inquiry_create')", 'rb-provider-layout'):
            self.assertIn(contract, provider)
        self.assertIn("include '_footer.html'", (ROOT / 'templates/tours.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
