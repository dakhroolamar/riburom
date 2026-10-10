(function () {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let homeMediaPromise = null;

  function ensureHomeFixStyles() {
    const current = document.querySelector('link[data-rb-home-fixes-css]');
    if (current && /[?&]v=9(?:&|$)/.test(current.href)) return;
    if (current) current.remove();
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-home-fixes.css?v=9';
    link.dataset.rbHomeFixesCss = '1';
    document.head.appendChild(link);
  }

  function syncHeroOpeningFilm() {
    const hero = document.getElementById('rb-home-hero');
    const stage = document.querySelector('[data-rb-hero-video-stage]');
    const video = document.querySelector('[data-rb-hero-animation-video]');
    const logo = document.querySelector('.rb-hero-permanent-logo');
    const landscape = hero && hero.querySelector('.rb-paper-landscape');

    if (!hero || !stage || !logo) return;

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

    if (!video) return;

    /* ri-burom-motion.js owns playback state. This layer owns presentation:
       the opening film fills the hero story area but deliberately stops before
       the landscape/gallery so the transition has visible breathing room. */
    if (video.parentElement !== hero) hero.appendChild(video);
    video.classList.remove('rb-hero-animation-video--background');
    video.classList.add('rb-hero-opening-film');

    const sizeOpeningFilm = () => {
      const heroRect = hero.getBoundingClientRect();
      const landscapeRect = landscape ? landscape.getBoundingClientRect() : null;
      const configuredGap = parseFloat(getComputedStyle(hero).getPropertyValue('--rb-hero-landscape-gap')) || 0;
      const filmBottom = landscapeRect ? landscapeRect.top - heroRect.top - configuredGap : heroRect.height;
      const whiteAreaHeight = Math.max(280, Math.round(filmBottom));
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
    if (!hero.dataset.rbFilmResizeBound) {
      window.addEventListener('resize', sizeOpeningFilm, { passive: true });
      hero.dataset.rbFilmResizeBound = '1';
    }
  }

  function fetchHomeMedia() {
    if (homeMediaPromise) return homeMediaPromise;
    homeMediaPromise = window.RiBuromPublicMedia || (window.RiBuromPublicMedia = fetch('/api/public-section-backgrounds', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .catch(() => null));
    return homeMediaPromise;
  }

  function makeImage(src, alt, eager) {
    const img = document.createElement('img');
    img.src = src;
    img.alt = alt;
    img.loading = eager ? 'eager' : 'lazy';
    img.decoding = 'async';
    return img;
  }

  function scrollRail(track, direction) {
    if (!track) return;
    const amount = Math.max(260, track.clientWidth * 0.78) * direction;
    track.scrollBy({ left: amount, behavior: reducedMotion.matches ? 'auto' : 'smooth' });
  }

  function bindRailControls(shell) {
    if (!shell || shell.dataset.rbRailBound === '1') return;
    const track = shell.querySelector('[data-rb-rail-track]');
    const prev = shell.querySelector('[data-rb-rail-prev]');
    const next = shell.querySelector('[data-rb-rail-next]');
    if (!track) return;
    if (prev) prev.addEventListener('click', () => scrollRail(track, -1));
    if (next) next.addEventListener('click', () => scrollRail(track, 1));
    shell.dataset.rbRailBound = '1';
  }

  function initStaticRails() {
    document.querySelectorAll('[data-rb-rail-shell]').forEach(bindRailControls);
  }

  function renderRiverGallery(payload) {
    const host = document.querySelector('[data-rb-river-gallery-host]');
    const gallery = host && host.querySelector('[data-rb-river-gallery]');
    const track = gallery && gallery.querySelector('[data-rb-rail-track]');
    const fallback = host && host.querySelector('[data-rb-river-gallery-fallback]');
    const images = payload && payload.galleries && Array.isArray(payload.galleries.home_gallery)
      ? payload.galleries.home_gallery.slice(0, 10)
      : [];

    if (!host || !gallery || !track || !fallback || !images.length) return;

    track.innerHTML = '';
    images.forEach((src, index) => {
      const figure = document.createElement('figure');
      figure.className = 'rb-river-gallery-slide';
      figure.setAttribute('role', 'group');
      figure.setAttribute('aria-label', 'Gallery image ' + (index + 1) + ' of ' + images.length);
      const detail = payload.media_details?.home_gallery?.[index];
      const photo = makeImage(src, detail?.alt || 'Meghalaya travel gallery image ' + (index + 1), false);
      if (detail) photo.style.objectPosition = `${detail.focal_x}% ${detail.focal_y}%`;
      figure.appendChild(photo);
      if (detail?.caption || detail?.credit) {
        const caption = document.createElement('figcaption');
        caption.textContent = [detail.caption, detail.credit].filter(Boolean).join(' · ');
        figure.appendChild(caption);
      }
      track.appendChild(figure);
    });

    fallback.hidden = true;
    gallery.hidden = false;
    host.classList.add('has-river-gallery');
    window.RiBuromGallery.init(gallery);
    syncHeroOpeningFilm();
  }

  function clearHomeAboutSectionBackground(section) {
    if (!section) return;
    const clear = () => {
      if (section.style.getPropertyValue('background-image') !== 'none') {
        section.style.setProperty('background-image', 'none', 'important');
      }
    };
    clear();
    if (!section.dataset.rbBackgroundObserver) {
      new MutationObserver(clear).observe(section, { attributes: true, attributeFilter: ['style'] });
      section.dataset.rbBackgroundObserver = '1';
    }
  }

  function renderAboutGallery(payload) {
    const section = document.getElementById('rb-home-about');
    const host = section && section.querySelector('[data-rb-about-gallery]');
    const fallback = host && host.querySelector('[data-rb-about-gallery-fallback]');
    const flip = host && host.querySelector('[data-rb-about-flip]');
    const page = flip && flip.querySelector('[data-rb-about-flip-page]');
    const image = page && page.querySelector('img');
    const counter = flip && flip.querySelector('[data-rb-about-counter]');
    const prev = flip && flip.querySelector('[data-rb-about-prev]');
    const next = flip && flip.querySelector('[data-rb-about-next]');
    if (!section || !host || !fallback || !flip || !page || !image) return;

    let images = payload && payload.galleries && Array.isArray(payload.galleries.home_about_gallery)
      ? payload.galleries.home_about_gallery.slice(0, 10)
      : [];
    if (!images.length && payload && payload.backgrounds && payload.backgrounds.home_about) {
      images = [payload.backgrounds.home_about];
    }
    if (!images.length) return;

    let index = 0;
    let flipping = false;
    const sync = () => {
      image.src = images[index];
      const detail = payload.media_details?.home_about_gallery?.[index];
      image.alt = detail?.alt || 'RI BUROM about gallery image ' + (index + 1);
      if (detail) image.style.objectPosition = `${detail.focal_x}% ${detail.focal_y}%`;
      let caption = flip.querySelector('[data-cms-about-caption]');
      if (!caption) {
        caption = document.createElement('p');
        caption.dataset.cmsAboutCaption = '1';
        caption.className = 'cms-about-caption';
        flip.appendChild(caption);
      }
      caption.textContent = detail ? [detail.caption, detail.credit].filter(Boolean).join(' · ') : '';
      caption.hidden = !caption.textContent;
      if (counter) counter.textContent = (index + 1) + ' / ' + images.length;
    };
    const move = (direction) => {
      if (flipping || images.length < 2) return;
      const target = (index + direction + images.length) % images.length;
      if (reducedMotion.matches) {
        index = target;
        sync();
        return;
      }
      flipping = true;
      page.classList.remove('is-flipping-next', 'is-flipping-prev');
      void page.offsetWidth;
      page.classList.add(direction > 0 ? 'is-flipping-next' : 'is-flipping-prev');
      window.setTimeout(() => {
        index = target;
        sync();
      }, 240);
      window.setTimeout(() => {
        page.classList.remove('is-flipping-next', 'is-flipping-prev');
        flipping = false;
      }, 560);
    };

    sync();
    fallback.hidden = true;
    flip.hidden = false;
    clearHomeAboutSectionBackground(section);
    if (images.length < 2) {
      if (prev) prev.hidden = true;
      if (next) next.hidden = true;
    } else {
      if (prev) prev.addEventListener('click', () => move(-1));
      if (next) next.addEventListener('click', () => move(1));
    }
  }

  function hydrateHomeMedia() {
    fetchHomeMedia().then((payload) => {
      if (!payload) return;
      renderRiverGallery(payload);
      renderAboutGallery(payload);
    });
  }

  function run() {
    ensureHomeFixStyles();
    syncHeroOpeningFilm();
    initStaticRails();
    hydrateHomeMedia();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
  window.addEventListener('load', syncHeroOpeningFilm, { once: true });
})();
