(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureMotionStyles() {
    if (document.querySelector('link[data-rb-motion-css]')) return;
    const critical = document.createElement('style');
    critical.textContent = '#rb-page-loader{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;background:#0b3b23;opacity:1;visibility:visible;transition:opacity .55s ease,visibility .55s linear}.rb-loader-core{display:flex;flex-direction:column;align-items:center;gap:14px;color:#fff}.rb-loader-mark{width:90px;height:90px;object-fit:contain}.rb-loader-line{width:110px;height:2px;background:rgba(255,255,255,.18);overflow:hidden;border-radius:999px}.rb-loader-line:after{content:"";display:block;width:42%;height:100%;background:#f3c969;animation:rb-loader-line 1.15s ease-in-out infinite}@keyframes rb-loader-line{0%{transform:translateX(-120%)}100%{transform:translateX(270%)}}';
    document.head.appendChild(critical);
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-motion.css?v=8';
    link.dataset.rbMotionCss = '1';
    document.head.appendChild(link);
  }

  function getBrandImage() {
    const logo = document.querySelector('.rb-hero-permanent-logo');
    if (logo && logo.currentSrc) return logo.currentSrc;
    const mark = document.querySelector('.rb-brand img:last-child');
    if (mark && mark.currentSrc) return mark.currentSrc;
    const wordmark = document.querySelector('.rb-brand img:first-child');
    return wordmark ? (wordmark.currentSrc || wordmark.getAttribute('src') || '') : '';
  }

  function showLoader() {
    if (document.getElementById('rb-page-loader')) return;
    const loader = document.createElement('div');
    loader.id = 'rb-page-loader';
    const src = getBrandImage();
    loader.innerHTML = '<div class="rb-loader-core">' +
      (src ? '<img class="rb-loader-mark" src="' + src + '" alt="" aria-hidden="true">' : '<div style="font-weight:800;letter-spacing:.08em">RI BUROM</div>') +
      '<div class="rb-loader-line" aria-hidden="true"></div></div>';
    document.body.prepend(loader);
    const hide = () => setTimeout(() => loader.classList.add('is-hidden'), reduceMotion ? 120 : 650);
    if (document.readyState === 'complete') hide();
    else window.addEventListener('load', hide, { once: true });
    setTimeout(hide, 1800);
  }

  function makeSoundControl(hero, video) {
    if (hero.querySelector('.rb-hero-video-sound')) return hero.querySelector('.rb-hero-video-sound');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'rb-hero-video-sound';
    button.textContent = 'Enable sound';
    button.setAttribute('aria-label', 'Enable sound for the hero animation');
    button.hidden = true;
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      video.muted = false;
      video.removeAttribute('muted');
      const playback = video.play();
      if (playback && typeof playback.catch === 'function') {
        playback.catch(() => {});
      }
      button.hidden = true;
    });
    hero.appendChild(button);
    return button;
  }

  function initHeroAnimationVideo() {
    const stage = document.querySelector('[data-rb-hero-video-stage]');
    const video = stage && stage.querySelector('[data-rb-hero-animation-video]');
    const hero = document.getElementById('rb-home-hero');
    if (!stage || !video || !hero) return;

    const soundButton = makeSoundControl(hero, video);
    hero.classList.add('rb-hero-video-enabled');

    // Move the video out of the logo stage and into the hero itself so it can
    // cover the complete hero viewport while the permanent logo stays in the
    // content layer as the durable fallback/final state.
    hero.appendChild(video);
    video.classList.add('rb-hero-animation-video--background');

    const fallback = () => {
      hero.classList.remove('rb-hero-video-playing', 'rb-hero-video-complete');
      hero.classList.add('rb-hero-video-fallback');
      stage.classList.remove('is-playing', 'is-complete');
      stage.classList.add('is-fallback');
      try { video.pause(); } catch (_) {}
      soundButton.hidden = true;
    };

    const complete = () => {
      hero.classList.remove('rb-hero-video-playing', 'rb-hero-video-fallback');
      hero.classList.add('rb-hero-video-complete');
      stage.classList.remove('is-playing', 'is-fallback');
      stage.classList.add('is-complete');
      try { video.pause(); } catch (_) {}
      soundButton.hidden = true;
    };

    if (reduceMotion) {
      hero.classList.add('rb-hero-video-fallback');
      stage.classList.add('is-fallback');
      video.pause();
      return;
    }

    video.addEventListener('playing', () => {
      hero.classList.remove('rb-hero-video-fallback', 'rb-hero-video-complete');
      hero.classList.add('rb-hero-video-playing');
      stage.classList.remove('is-fallback', 'is-complete');
      stage.classList.add('is-playing');
    }, { once: true });
    video.addEventListener('ended', complete, { once: true });
    video.addEventListener('error', fallback, { once: true });
    video.addEventListener('abort', fallback, { once: true });

    // Try audible autoplay first. Browsers that disallow audible autoplay will
    // reject play(); in that case we immediately fall back to muted autoplay
    // and expose a small, explicit sound control for user-initiated playback.
    video.muted = false;
    video.removeAttribute('muted');
    let playback;
    try {
      playback = video.play();
    } catch (_) {
      playback = null;
    }
    if (playback && typeof playback.catch === 'function') {
      playback.catch(() => {
        video.muted = true;
        video.setAttribute('muted', '');
        soundButton.hidden = false;
        const mutedPlayback = video.play();
        if (mutedPlayback && typeof mutedPlayback.catch === 'function') {
          mutedPlayback.catch(fallback);
        }
      });
    }

    // A normal user interaction on the hero also provides a valid browser
    // gesture for enabling audio, without requiring the visitor to find the
    // small control first.
    hero.addEventListener('pointerdown', () => {
      if (!video.muted || video.paused || video.ended) return;
      video.muted = false;
      video.removeAttribute('muted');
      const userPlayback = video.play();
      if (userPlayback && typeof userPlayback.catch === 'function') {
        userPlayback.catch(() => { video.muted = true; });
      } else {
        soundButton.hidden = true;
      }
    }, { passive: true, once: false });
  }

  function scrollReveal() {
    const items = document.querySelectorAll('[data-reveal]');
    if (reduceMotion) {
      items.forEach((el) => el.classList.add('is-visible'));
      return;
    }
    if (!('IntersectionObserver' in window)) {
      items.forEach((el) => el.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    items.forEach((item) => observer.observe(item));
    document.querySelectorAll('.rb-stagger').forEach((group) => {
      Array.from(group.children).forEach((child, index) => child.style.setProperty('--rb-delay', `${Math.min(index, 6) * 90}ms`));
    });
  }

  function syncNav() {
    const nav = document.querySelector('.rb-site-nav');
    if (!nav) return;
    const update = () => nav.classList.toggle('rb-scrolled', window.scrollY > 16);
    update();
    window.addEventListener('scroll', update, { passive: true });
  }

  function applySectionBackgrounds() {
    const sectionMap = {
      hero: '#rb-home-hero', home_about: '#rb-home-about', home_tours: '#rb-home-tours', home_why: '#rb-home-why',
      home_blog: '#rb-home-blog', home_contact: '#rb-home-contact', about_header: 'body > header:not(.rb-site-nav)',
      about_belief: '#about-belief', about_pillars: '#about-pillars', about_extra1: '#about-extra1', about_extra2: '#about-extra2',
      about_team: '#about-team', about_logo: '#about-logo', about_blog: '#about-blog', footer: '.rb-footer'
    };
    fetch('/api/public-section-backgrounds', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        if (!payload) return;
        Object.entries(payload.backgrounds || {}).forEach(([key, image]) => {
          const el = document.querySelector(sectionMap[key]);
          if (!el || !image) return;
          const style = payload.styles?.[key] || {};
          const overlayColor = style.overlay_color || '#000000';
          const opacity = Number(style.overlay_opacity ?? 0) / 100;
          const hex = overlayColor.match(/^#([0-9a-f]{6})$/i);
          const overlay = hex ? `rgba(${parseInt(hex[1].slice(0,2),16)},${parseInt(hex[1].slice(2,4),16)},${parseInt(hex[1].slice(4,6),16)},${opacity})` : overlayColor;
          el.style.backgroundImage = `linear-gradient(${overlay},${overlay}),url("${image}")`;
          el.style.backgroundSize = 'cover';
          el.style.backgroundPosition = 'center';
        });
      })
      .catch(() => {});
  }

  function bootstrap() {
    ensureMotionStyles();
    showLoader();
    initHeroAnimationVideo();
    scrollReveal();
    syncNav();
    applySectionBackgrounds();
  }

  bootstrap();
})();
