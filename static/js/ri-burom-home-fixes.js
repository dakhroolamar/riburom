(function () {
  'use strict';

  function ensureHomeFixStyles() {
    const current = document.querySelector('link[data-rb-home-fixes-css]');
    if (current && /[?&]v=3(?:&|$)/.test(current.href)) return;
    if (current) current.remove();
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-home-fixes.css?v=3';
    link.dataset.rbHomeFixesCss = '1';
    document.head.appendChild(link);
  }

  function syncHeroOpeningFilm() {
    const hero = document.getElementById('rb-home-hero');
    const stage = document.querySelector('[data-rb-hero-video-stage]');
    const video = document.querySelector('[data-rb-hero-animation-video]');
    const logo = document.querySelector('.rb-hero-permanent-logo');
    const landscape = hero && hero.querySelector('.rb-paper-landscape');

    if (!hero || !stage || !video || !logo) return;

    /* ri-burom-motion.js owns playback state. This layer owns presentation:
       the opening film fills the complete white hero area, stopping exactly
       where the landscape begins. */
    if (video.parentElement !== hero) hero.appendChild(video);
    video.classList.remove('rb-hero-animation-video--background');
    video.classList.add('rb-hero-opening-film');

    const sizeOpeningFilm = () => {
      const heroHeight = hero.getBoundingClientRect().height;
      const landscapeHeight = landscape ? landscape.getBoundingClientRect().height : 0;
      const whiteAreaHeight = Math.max(280, Math.round(heroHeight - landscapeHeight));
      video.style.setProperty('position', 'absolute', 'important');
      video.style.setProperty('top', '0', 'important');
      video.style.setProperty('right', '0', 'important');
      video.style.setProperty('bottom', 'auto', 'important');
      video.style.setProperty('left', '0', 'important');
      video.style.setProperty('width', '100%', 'important');
      video.style.setProperty('height', whiteAreaHeight + 'px', 'important');
      video.style.setProperty('max-width', 'none', 'important');
      video.style.setProperty('max-height', 'none', 'important');
      video.style.setProperty('object-fit', 'cover', 'important');
      video.style.setProperty('object-position', 'center center', 'important');
      video.style.setProperty('z-index', '18', 'important');
    };

    sizeOpeningFilm();
    window.addEventListener('resize', sizeOpeningFilm, { passive: true });

    /* Make the post-animation logo exactly 2x the CMS-configured width. Store
       the original value so repeated load/resize hooks never double it again. */
    if (!logo.dataset.rbOriginalHeroWidth) {
      const configuredWidth = parseFloat(logo.style.width) || Math.round(logo.getBoundingClientRect().width) || 80;
      logo.dataset.rbOriginalHeroWidth = String(configuredWidth);
    }
    const originalWidth = parseFloat(logo.dataset.rbOriginalHeroWidth) || 80;
    const doubledWidth = Math.min(originalWidth * 2, 320);
    logo.style.setProperty('width', doubledWidth + 'px', 'important');
    logo.style.setProperty('max-width', 'min(86vw, 320px)', 'important');
    logo.style.setProperty('max-height', '220px', 'important');
    stage.style.setProperty('width', 'auto', 'important');
    stage.style.setProperty('max-width', '86vw', 'important');
  }

  function applyHomeAboutFrame() {
    const section = document.getElementById('rb-home-about');
    const frame = section && section.querySelector('.rb-story-art');
    if (!section || !frame) return;

    fetch('/api/public-section-backgrounds', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        const image = payload && payload.backgrounds && payload.backgrounds.home_about;
        if (!image) return;

        frame.innerHTML = '';
        const img = document.createElement('img');
        img.src = image;
        img.alt = 'RI BUROM about us';
        img.loading = 'lazy';
        img.decoding = 'async';
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.display = 'block';
        img.style.objectFit = 'cover';
        frame.appendChild(img);

        const clearSectionBackground = () => {
          if (section.style.getPropertyValue('background-image') !== 'none') {
            section.style.setProperty('background-image', 'none', 'important');
          }
        };
        clearSectionBackground();
        new MutationObserver(clearSectionBackground).observe(section, { attributes: true, attributeFilter: ['style'] });
      })
      .catch(() => {});
  }

  function run() {
    ensureHomeFixStyles();
    syncHeroOpeningFilm();
    applyHomeAboutFrame();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
  window.addEventListener('load', syncHeroOpeningFilm, { once: true });
})();
