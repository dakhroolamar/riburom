(function () {
  'use strict';

  function syncHeroMedia() {
    const hero = document.getElementById('rb-home-hero');
    const stage = document.querySelector('[data-rb-hero-video-stage]');
    const video = document.querySelector('[data-rb-hero-animation-video]');
    const logo = document.querySelector('.rb-hero-permanent-logo');
    const heroImage = document.querySelector('.rb-home-landscape-photo');

    if (heroImage) {
      heroImage.style.setProperty('opacity', '1', 'important');
      heroImage.style.setProperty('mix-blend-mode', 'normal', 'important');
      heroImage.style.setProperty('position', 'absolute', 'important');
      heroImage.style.setProperty('inset', '0', 'important');
      heroImage.style.setProperty('width', '100%', 'important');
      heroImage.style.setProperty('height', '100%', 'important');
      heroImage.style.setProperty('object-fit', 'cover', 'important');
    }

    if (!hero || !stage || !video || !logo) return;

    if (video.parentElement !== stage) stage.appendChild(video);
    video.classList.remove('rb-hero-animation-video--background');

    stage.style.setProperty('position', 'relative', 'important');
    stage.style.setProperty('width', 'min(78vw, 560px)', 'important');
    stage.style.setProperty('max-width', '100%', 'important');
    stage.style.setProperty('margin', '0 auto 1.5rem', 'important');

    video.style.setProperty('position', 'absolute', 'important');
    video.style.setProperty('inset', '0', 'important');
    video.style.setProperty('width', '100%', 'important');
    video.style.setProperty('height', '100%', 'important');
    video.style.setProperty('max-width', '100%', 'important');
    video.style.setProperty('max-height', '100%', 'important');
    video.style.setProperty('object-fit', 'contain', 'important');
    video.style.setProperty('object-position', 'center', 'important');
    video.style.setProperty('pointer-events', 'none', 'important');
    video.style.setProperty('background', 'transparent', 'important');
    video.style.setProperty('z-index', '2', 'important');

    const syncState = () => {
      const playing = hero.classList.contains('rb-hero-video-playing') && !video.ended;
      video.style.setProperty('opacity', playing ? '1' : '0', 'important');
      video.style.setProperty('visibility', playing ? 'visible' : 'hidden', 'important');
      logo.style.setProperty('opacity', playing ? '0' : '1', 'important');
      logo.style.setProperty('visibility', 'visible', 'important');
    };

    syncState();
    new MutationObserver(syncState).observe(hero, { attributes: true, attributeFilter: ['class'] });
    video.addEventListener('playing', syncState);
    video.addEventListener('ended', syncState);
    video.addEventListener('error', syncState);
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
    syncHeroMedia();
    applyHomeAboutFrame();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
  window.addEventListener('load', syncHeroMedia, { once: true });
})();
