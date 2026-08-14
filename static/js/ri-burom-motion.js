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
})();
