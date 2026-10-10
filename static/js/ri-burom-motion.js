(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureMotionStyles() {
    if (document.querySelector('link[data-rb-motion-css]')) return;
    const critical = document.createElement('style');
    critical.textContent = '#rb-page-loader{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;background:#0b3b23;opacity:1;visibility:visible;transition:opacity .55s ease,visibility .55s linear}.rb-loader-core{display:flex;flex-direction:column;align-items:center;gap:14px;color:#fff}.rb-loader-mark{width:90px;height:90px;object-fit:contain}.rb-loader-line{width:110px;height:2px;background:rgba(255,255,255,.18);overflow:hidden;border-radius:999px}.rb-loader-line:after{content:"";display:block;width:42%;height:100%;background:#f3c969;animation:rb-loader-line 1.15s ease-in-out infinite}@keyframes rb-loader-line{0%{transform:translateX(-120%)}100%{transform:translateX(270%)}}' +
      '.rb-success-modal{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px 16px;background:rgba(0,0,0,.62);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);opacity:1;visibility:visible;animation:rb-success-fade-in .22s ease-out both}' +
      '.rb-success-card{position:relative;width:100%;max-width:430px;background:#fff;border-radius:24px;box-shadow:0 25px 70px rgba(0,0,0,.3);padding:36px 28px;text-align:center;overflow:hidden;animation:rb-success-pop .5s cubic-bezier(.22,.7,.25,1) both}' +
      '.rb-success-icon{position:relative;z-index:2;width:82px;height:82px;margin:0 auto 20px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#dcfce7;color:#166534;font-size:42px;font-weight:800;animation:rb-success-icon-pop .6s cubic-bezier(.22,.7,.25,1) .08s both}' +
      '.rb-success-check{display:block;opacity:0;animation:rb-success-check .4s ease-out .36s both}' +
      '.rb-success-eyebrow{position:relative;z-index:2;margin:0 0 8px;color:#166534;font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase}' +
      '.rb-success-card h2{position:relative;z-index:2;margin:0 0 14px;color:#14532d;font-size:30px;line-height:1.15;font-weight:800}' +
      '.rb-success-message{position:relative;z-index:2;margin:0 auto 26px;max-width:350px;color:#4b5563;font-size:16px;line-height:1.6}' +
      '.rb-success-close{position:relative;z-index:3;border:0;cursor:pointer;color:#fff;background:#15803d;font-weight:800;padding:12px 28px;border-radius:999px;box-shadow:0 8px 20px rgba(21,128,61,.22)}' +
      '.rb-success-close:hover{background:#166534}' +
      '.rb-success-confetti{position:absolute;inset:0;z-index:1;pointer-events:none;overflow:hidden}' +
      '.rb-success-confetti span{position:absolute;left:50%;top:40%;width:7px;height:12px;border-radius:2px;opacity:0;will-change:transform,opacity;animation:rb-success-confetti-fly .85s cubic-bezier(.18,.75,.25,1) forwards;animation-delay:var(--d)}' +
      '@keyframes rb-success-fade-in{from{opacity:0}to{opacity:1}}' +
      '@keyframes rb-success-pop{0%{opacity:0;transform:translateY(18px) scale(.95)}70%{transform:translateY(-2px) scale(1.01)}100%{opacity:1;transform:none}}' +
      '@keyframes rb-success-icon-pop{0%{transform:scale(.35);opacity:0}65%{transform:scale(1.1);opacity:1}100%{transform:scale(1);opacity:1}}' +
      '@keyframes rb-success-check{from{opacity:0;transform:scale(.5)}to{opacity:1;transform:scale(1)}}' +
      '@keyframes rb-success-confetti-fly{0%{opacity:1;transform:translate(-50%,-50%) rotate(0deg)}100%{opacity:0;transform:translate(calc(-50% + var(--x)),calc(-50% + var(--y))) rotate(var(--r))}}' +
      '@media (prefers-reduced-motion:reduce){.rb-success-modal,.rb-success-card,.rb-success-icon,.rb-success-check,.rb-success-confetti span{animation:none!important}.rb-success-check{opacity:1}}';
    document.head.appendChild(critical);
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-motion.css?v=9';
    link.dataset.rbMotionCss = '1';
    document.head.appendChild(link);
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
      if (playback && typeof playback.catch === 'function') playback.catch(() => {});
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

    if (reduceMotion || navigator.connection?.saveData) {
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

    video.muted = true;
    video.setAttribute('muted', '');
    soundButton.hidden = false;
    let playback;
    try { playback = video.play(); } catch (_) { playback = null; }
    if (playback && typeof playback.catch === 'function') {
      playback.catch(() => {
        fallback();
      });
    }

  }

  function fixHeroCta() {
    const button = document.querySelector('.rb-hero .rb-button-accent[href="#tours"]');
    if (button) button.setAttribute('href', '/all_tours');
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
    window.RiBuromPublicMedia = window.RiBuromPublicMedia || fetch('/api/public-section-backgrounds', { credentials: 'same-origin' }).then(response => response.ok ? response.json() : null).catch(() => null);
    window.RiBuromPublicMedia
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
    document.querySelectorAll('[data-dismiss-notice]').forEach(button => button.addEventListener('click', () => button.parentElement.remove()));
    initHeroAnimationVideo();
    fixHeroCta();
    scrollReveal();
    syncNav();
    applySectionBackgrounds();
  }

  bootstrap();
})();
