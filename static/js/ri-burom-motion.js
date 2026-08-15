(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Reveal sections as the visitor scrolls.
  const revealItems = document.querySelectorAll('[data-reveal]');
  if (reduceMotion) {
    revealItems.forEach((el) => el.classList.add('is-visible'));
  } else if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealItems.forEach((el) => observer.observe(el));
  } else {
    revealItems.forEach((el) => el.classList.add('is-visible'));
  }

  // Light stagger for card grids without JavaScript libraries.
  document.querySelectorAll('.rb-stagger').forEach((group) => {
    Array.from(group.children).forEach((child, index) => {
      child.style.setProperty('--rb-delay', `${Math.min(index, 6) * 90}ms`);
    });
  });

  // Give the sticky navigation a subtle change after scrolling.
  const nav = document.querySelector('.rb-site-nav');
  if (nav) {
    const syncNav = () => nav.classList.toggle('rb-scrolled', window.scrollY > 16);
    syncNav();
    window.addEventListener('scroll', syncNav, { passive: true });
  }

  // Apply CMS-managed section background images after the public theme loads.
  const sectionMap = {
    hero: '#rb-home-hero',
    home_about: '#rb-home-about',
    home_tours: '#rb-home-tours',
    home_why: '#rb-home-why',
    home_blog: '#rb-home-blog',
    home_contact: '#rb-home-contact',
    about_header: '#rb-about-header',
    about_belief: '#about-belief',
    about_pillars: '#about-pillars',
    about_extra1: '#about-extra1',
    about_extra2: '#about-extra2',
    about_team: '#about-team',
    about_logo: '#about-logo',
    about_blog: '#about-blog',
    footer: '.rb-footer'
  };

  const applySectionBackgrounds = async () => {
    try {
      const response = await fetch('/api/public-section-backgrounds', { credentials: 'same-origin' });
      if (!response.ok) return;
      const payload = await response.json();
      const backgrounds = payload.backgrounds || {};
      const styles = payload.styles || {};

      Object.entries(backgrounds).forEach(([key, image]) => {
        const el = document.querySelector(sectionMap[key]);
        if (!el || !image) return;
        const style = styles[key] || {};
        const overlayColor = style.overlay_color || '#000000';
        const opacity = Number(style.overlay_opacity ?? 0) / 100;
        let overlay = overlayColor;
        const match = overlayColor.match(/^#([0-9a-f]{6})$/i);
        if (match) {
          const hex = match[1];
          overlay = `rgba(${parseInt(hex.slice(0, 2), 16)},${parseInt(hex.slice(2, 4), 16)},${parseInt(hex.slice(4, 6), 16)},${opacity})`;
        }
        el.style.backgroundImage = `linear-gradient(${overlay},${overlay}),url("${image}")`;
        el.style.backgroundSize = 'cover';
        el.style.backgroundPosition = 'center';
      });
    } catch (_) {
      // Background customization is optional; never block the public page if it fails.
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applySectionBackgrounds);
  } else {
    applySectionBackgrounds();
  }
})();
