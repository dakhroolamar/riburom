/* GSAP 3.12.5 + ScrollTrigger 3.12.5, vendored; complete static art on failure. */
(() => {
  'use strict';
  const root = document.querySelector('[data-rb-waterfall]');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';
  const svg = root.querySelector('.rb-waterfall');
  const paths = [...svg.querySelectorAll('path')];
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) return;
  gsap.registerPlugin(ScrollTrigger);
  const mm = gsap.matchMedia();
  mm.add('(prefers-reduced-motion: no-preference)', () => {
    const animation = gsap.timeline({scrollTrigger: {
      trigger: root, start: 'top 70%', end: 'bottom 90%', scrub: 1,
      invalidateOnRefresh: true
    }});
    paths.forEach(path => {
      const length = path.getTotalLength();
      animation.fromTo(path, {strokeDasharray: length, strokeDashoffset: length},
        {strokeDashoffset: 0, duration: 1, ease: 'none'}, 0);
    });
    // Three waypoints, only active while passing their part of the story.
    svg.querySelectorAll('circle').forEach((drop, index) => {
      animation.fromTo(drop, {opacity: .15}, {opacity: .7, duration: .08, repeat: 1, yoyo: true}, .2 + index * .25);
    });
    const roots = root.querySelector('[data-rb-roots]');
    if (roots) gsap.fromTo(roots, {y: -8}, {y: 8, ease: 'none', scrollTrigger: {
      trigger: roots, start: 'top bottom', end: 'bottom top', scrub: 1
    }});
    return () => paths.forEach(path => {
      path.style.removeProperty('stroke-dasharray');
      path.style.removeProperty('stroke-dashoffset');
    });
  });
  // CMS visibility/order, late media and resize can change the journey height.
  let pending;
  const observer = new ResizeObserver(() => {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => ScrollTrigger.refresh());
  });
  observer.observe(root);
  window.addEventListener('pagehide', event => {
    if (event.persisted) return; // Keep the animation context for back/forward cache.
    observer.disconnect(); cancelAnimationFrame(pending); mm.revert();
  });
})();
