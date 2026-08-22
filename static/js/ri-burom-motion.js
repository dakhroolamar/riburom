(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureMotionStyles() {
    if (document.querySelector('link[data-rb-motion-css]')) return;
    const critical = document.createElement('style');
    critical.textContent = '#rb-page-loader{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;background:#0b3b23;opacity:1;visibility:visible;transition:opacity .55s ease,visibility .55s linear}.rb-loader-core{display:flex;flex-direction:column;align-items:center;gap:14px;color:#fff}.rb-loader-mark{width:90px;height:90px;object-fit:contain}.rb-loader-line{width:110px;height:2px;background:rgba(255,255,255,.18);overflow:hidden;border-radius:999px}.rb-loader-line:after{content:"";display:block;width:42%;height:100%;background:#f3c969;animation:rb-loader-line 1.15s ease-in-out infinite}.rb-hero-logo-stage{position:relative;width:min(78vw,560px);max-height:420px;margin-bottom:32px}.rb-hero-logo-base{position:relative;z-index:1;display:block;max-width:78vw;max-height:420px;height:auto;object-fit:contain;opacity:1;filter:drop-shadow(0 18px 34px rgba(0,0,0,.3));transition:opacity .48s cubic-bezier(.22,.7,.25,1)}.rb-hero-logo-stage.is-assembling .rb-hero-logo-base{opacity:0}.rb-hero-logo-fragment-layer{position:absolute;inset:0;z-index:2;pointer-events:none}.rb-logo-fragment{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;opacity:0;will-change:transform,opacity,filter}@keyframes rb-loader-line{0%{transform:translateX(-120%)}100%{transform:translateX(270%)}}';
    document.head.appendChild(critical);
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-motion.css?v=6';
    link.dataset.rbMotionCss = '1';
    document.head.appendChild(link);
  }

  function imageSource(element) {
    return element.currentSrc || element.getAttribute('src') || '';
  }

  function waitForImage(image) {
    if (image.complete) {
      return Promise.resolve(image.naturalWidth > 0);
    }
    return new Promise((resolve) => {
      const finish = (ok) => {
        image.removeEventListener('load', onLoad);
        image.removeEventListener('error', onError);
        resolve(ok);
      };
      const onLoad = () => finish(true);
      const onError = () => finish(false);
      image.addEventListener('load', onLoad, { once: true });
      image.addEventListener('error', onError, { once: true });
    });
  }

  async function resolveHeroLogo(image) {
    const candidates = [
      imageSource(image),
      image.dataset.fallbackSrc || '',
      image.dataset.fallbackSrcSecondary || ''
    ].filter(Boolean);

    const seen = new Set();
    for (const src of candidates) {
      if (seen.has(src)) continue;
      seen.add(src);
      if (imageSource(image) !== src) {
        image.src = src;
      }
      const loaded = await waitForImage(image);
      if (loaded && image.naturalWidth > 0) {
        if (image.decode) {
          try { await image.decode(); } catch (_) {}
        }
        return src;
      }
    }
    return '';
  }

  function getBrandImage() {
    const hero = document.getElementById('rbHeroLogo');
    if (hero) return imageSource(hero);
    const mark = document.querySelector('.rb-brand img:last-child');
    if (mark) return imageSource(mark);
    const wordmark = document.querySelector('.rb-brand img:first-child');
    return wordmark ? imageSource(wordmark) : '';
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

  function createFragment(layer, source, clip) {
    const img = document.createElement('img');
    img.className = 'rb-logo-fragment';
    img.src = source;
    img.alt = '';
    img.setAttribute('aria-hidden', 'true');
    img.style.clipPath = 'inset(' + clip + ')';
    layer.appendChild(img);
    return img;
  }

  function playFragment(img, x, y, rotation, delay) {
    if (typeof img.animate !== 'function') return null;
    const from = 'translate3d(' + x + ', ' + y + ', 0) rotate(' + rotation + ') scale(.72)';
    const to = 'translate3d(0, 0, 0) rotate(0deg) scale(1)';
    return img.animate(
      [
        { opacity: 0, transform: from, filter: 'blur(14px) drop-shadow(0 24px 30px rgba(0,0,0,.28))' },
        { opacity: 1, offset: 0.28 },
        { opacity: 1, transform: to, filter: 'blur(0) drop-shadow(0 18px 28px rgba(0,0,0,.22))' }
      ],
      { duration: 1180, delay, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' }
    );
  }

  async function assembleHeroLogo() {
    const stage = document.querySelector('[data-rb-hero-logo-stage]');
    const original = document.getElementById('rbHeroLogo');
    if (!stage || !original || stage.dataset.assembled === '1' || reduceMotion) return;

    const source = await resolveHeroLogo(original);
    if (!source || original.naturalWidth === 0 || typeof Element.prototype.animate !== 'function') return;

    stage.dataset.assembled = '1';
    const layer = document.createElement('div');
    layer.className = 'rb-hero-logo-fragment-layer';
    layer.setAttribute('aria-hidden', 'true');
    stage.appendChild(layer);

    const fragments = [
      ['0 66.67% 66.67% 0', '-54vw', '-38vh', '-18deg', 20],
      ['0 33.33% 66.67% 33.33%', '-18vw', '-46vh', '11deg', 150],
      ['0 0 66.67% 66.67%', '48vw', '-38vh', '18deg', 280],
      ['33.33% 66.67% 33.33% 0', '-58vw', '2vh', '-14deg', 90],
      ['33.33% 33.33% 33.33% 33.33%', '0', '45vh', '-8deg', 210],
      ['33.33% 0 33.33% 66.67%', '58vw', '5vh', '16deg', 330],
      ['66.67% 66.67% 0 0', '-48vw', '37vh', '-20deg', 170],
      ['66.67% 33.33% 0 33.33%', '16vw', '46vh', '10deg', 300],
      ['66.67% 0 0 66.67%', '52vw', '36vh', '-16deg', 430]
    ];

    const nodes = fragments.map((item) => ({
      img: createFragment(layer, source, item[0]),
      x: item[1], y: item[2], rotation: item[3], delay: item[4]
    }));

    stage.classList.add('is-assembling');
    requestAnimationFrame(() => {
      nodes.forEach((item) => playFragment(item.img, item.x, item.y, item.rotation, item.delay));
    });

    const assemblyEnd = 1750;
    window.setTimeout(() => {
      stage.classList.remove('is-assembling');
      nodes.forEach(({ img }) => {
        img.getAnimations().forEach((animation) => animation.cancel());
        img.animate(
          [{ opacity: 1 }, { opacity: 0 }],
          { duration: 420, easing: 'cubic-bezier(.22,.7,.25,1)', fill: 'forwards' }
        );
      });
      window.setTimeout(() => layer.remove(), 460);
    }, assemblyEnd);
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
    assembleHeroLogo();
    scrollReveal();
    syncNav();
    applySectionBackgrounds();
  }

  bootstrap();
})();
