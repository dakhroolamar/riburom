(function () {
  'use strict';

  function ensureHomeFixStyles() {
    if (document.querySelector('link[data-rb-home-fixes-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-home-fixes.css?v=2';
    link.dataset.rbHomeFixesCss = '1';
    document.head.appendChild(link);
  }

  function syncHeroOpeningFilm() {
    const hero = document.getElementById('rb-home-hero');
    const stage = document.querySelector('[data-rb-hero-video-stage]');
    const video = document.querySelector('[data-rb-hero-animation-video]');
    const logo = document.querySelector('.rb-hero-permanent-logo');

    if (!hero || !stage || !video || !logo) return;

    /* ri-burom-motion.js owns playback state. This layer only decides where
       the film is presented: across the full white hero story area. */
    if (video.parentElement !== hero) hero.appendChild(video);
    video.classList.remove('rb-hero-animation-video--background');
    video.classList.add('rb-hero-opening-film');
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
