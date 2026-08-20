(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureMotionStyles() {
    if (document.querySelector('link[data-rb-motion-css]')) return;
    const critical = document.createElement('style');
    critical.textContent = '#rb-page-loader{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;background:#0b3b23;opacity:1;visibility:visible;transition:opacity .55s ease,visibility .55s linear}.rb-loader-core{display:flex;flex-direction:column;align-items:center;gap:14px;color:#fff}.rb-loader-mark{width:90px;height:90px;object-fit:contain}.rb-loader-line{width:110px;height:2px;background:rgba(255,255,255,.18);overflow:hidden;border-radius:999px}.rb-loader-line:after{content:"";display:block;width:42%;height:100%;background:#f3c969;animation:rb-loader-line 1.15s ease-in-out infinite}.rb-logo-assembly{position:relative;width:min(78vw,560px);max-height:420px}.rb-logo-assembly-sizer{width:100%;height:auto;visibility:hidden;display:block}.rb-logo-fragment,.rb-logo-final{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.rb-logo-final{opacity:0}.rb-logo-fragment{opacity:0;filter:blur(10px);animation:rb-logo-fragment-in 1.28s cubic-bezier(.16,1,.3,1) forwards;animation-delay:var(--rb-delay)}@keyframes rb-loader-line{0%{transform:translateX(-120%)}100%{transform:translateX(270%)}}@keyframes rb-logo-fragment-in{0%{opacity:0;transform:translate3d(var(--rb-x),var(--rb-y),0) rotate(var(--rb-r)) scale(.75);filter:blur(12px)}100%{opacity:1;transform:none;filter:blur(0)}}';
    document.head.appendChild(critical);
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ri-burom-motion.css';
    link.dataset.rbMotionCss = '1';
    document.head.appendChild(link);
  }

  function getBrandImage() {
    const hero = document.getElementById('rbHeroLogo');
    if (hero && hero.currentSrc) return hero.currentSrc;
    const mark = document.querySelector('.rb-brand img:last-child');
    if (mark && mark.currentSrc) return mark.currentSrc;
    const wordmark = document.querySelector('.rb-brand img:first-child');
    return wordmark ? wordmark.currentSrc : '';
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

  function cinematicHero() {
    const hero = document.getElementById('rb-home-hero');
    if (!hero || reduceMotion) return;
    const background = getComputedStyle(hero).backgroundImage;
    if (!background || background === 'none') return;
    const media = document.createElement('div');
    media.className = 'rb-hero-media';
    media.style.backgroundImage = background;
    hero.style.backgroundImage = 'none';
    hero.insertBefore(media, hero.firstChild);
  }

  function assembleHeroLogo() {
    const original = document.getElementById('rbHeroLogo');
    if (!original || original.dataset.assembled === '1') return;

    const wrapper = document.createElement('div');
    wrapper.className = 'rb-logo-assembly';
    wrapper.setAttribute('aria-label', original.alt || 'Ri Burom Tours and Travels');
    wrapper.dataset.assembled = '1';

    const sizer = document.createElement('img');
    sizer.className = 'rb-logo-assembly-sizer';
    sizer.src = original.currentSrc || original.src;
    sizer.alt = '';
    sizer.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(sizer);

    const source = sizer.src;
    const fragments = [
      ['0 66.67% 66.67% 0','-55vw','-38vh','-18deg','40ms'],
      ['0 33.33% 66.67% 33.33%','-12vw','-48vh','12deg','150ms'],
      ['0 0 66.67% 66.67%','46vw','-38vh','18deg','260ms'],
      ['33.33% 66.67% 33.33% 0','-58vw','2vh','-15deg','110ms'],
      ['33.33% 33.33% 33.33% 33.33%','0','46vh','-8deg','220ms'],
      ['33.33% 0 33.33% 66.67%','58vw','6vh','16deg','330ms'],
      ['66.67% 66.67% 0 0','-48vw','38vh','-22deg','180ms'],
      ['66.67% 33.33% 0 33.33%','15vw','46vh','11deg','290ms'],
      ['66.67% 0 0 66.67%','52vw','36vh','-18deg','400ms'],
    ];

    fragments.forEach((item, index) => {
      const img = document.createElement('img');
      img.className = 'rb-logo-fragment';
      img.src = source;
      img.alt = '';
      img.setAttribute('aria-hidden', 'true');
      img.style.clipPath = 'inset(' + item[0] + ')';
      img.style.setProperty('--rb-x', item[1]);
      img.style.setProperty('--rb-y', item[2]);
      img.style.setProperty('--rb-r', item[3]);
      img.style.setProperty('--rb-delay', item[4]);
      wrapper.appendChild(img);
    });

    const final = original.cloneNode(true);
    final.removeAttribute('id');
    final.className = 'rb-logo-final';
    final.alt = original.alt;
    final.style.cssText = '';
    wrapper.appendChild(final);

    original.replaceWith(wrapper);

    if (reduceMotion) {
      final.classList.add('is-ready');
      return;
    }

    setTimeout(() => {
      final.classList.add('is-ready');
      wrapper.querySelectorAll('.rb-logo-fragment').forEach(fragment => fragment.classList.add('is-done'));
    }, 1850);
  }

  function scrollReveal() {
    const items = document.querySelectorAll('[data-reveal]');
    if (reduceMotion) {
      items.forEach(el => el.classList.add('is-visible'));
      return;
    }
    if (!('IntersectionObserver' in window)) {
      items.forEach(el => el.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    items.forEach(item => observer.observe(item));

    document.querySelectorAll('.rb-stagger').forEach(group => {
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
    fetch('/api/public-section-backgrounds', { credentials:'same-origin' })
      .then(response => response.ok ? response.json() : null)
      .then(payload => {
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
    cinematicHero();
    assembleHeroLogo();
    scrollReveal();
    syncNav();
    applySectionBackgrounds();
  }

  bootstrap();
})();
