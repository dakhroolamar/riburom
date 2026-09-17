(function () {
  'use strict';

  function repairHeroFilmSpacing() {
    const hero = document.getElementById('rb-home-hero');
    const film = hero && hero.querySelector('[data-rb-hero-animation-video]');
    const landscape = hero && hero.querySelector('.rb-paper-landscape');
    if (!hero || !film || !landscape) return;

    /* The shared homepage script promotes the film to the hero. Wait until that
       has happened, then size the film from actual geometry so it can never run
       into the landscape/gallery. */
    if (!film.classList.contains('rb-hero-opening-film')) return;

    const heroRect = hero.getBoundingClientRect();
    const landscapeRect = landscape.getBoundingClientRect();
    const cssGap = parseFloat(getComputedStyle(hero).getPropertyValue('--rb-hero-landscape-gap')) || 48;
    const minimumGap = window.innerWidth <= 767 ? 36 : 48;
    const gap = Math.max(cssGap, minimumGap);
    const available = Math.floor(landscapeRect.top - heroRect.top - gap);

    if (available > 180) {
      film.style.setProperty('height', available + 'px', 'important');
      film.style.setProperty('top', '0', 'important');
      film.style.setProperty('bottom', 'auto', 'important');
      hero.dataset.rbCriticalFilmGap = String(Math.round(landscapeRect.top - heroRect.top - available));
    }
  }

  function scheduleRepair() {
    requestAnimationFrame(() => requestAnimationFrame(repairHeroFilmSpacing));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleRepair, { once:true });
  } else {
    scheduleRepair();
  }

  window.addEventListener('load', scheduleRepair, { once:true });
  window.addEventListener('resize', scheduleRepair, { passive:true });

  const hero = document.getElementById('rb-home-hero');
  if (hero && 'ResizeObserver' in window) {
    const observer = new ResizeObserver(scheduleRepair);
    observer.observe(hero);
    const landscape = hero.querySelector('.rb-paper-landscape');
    if (landscape) observer.observe(landscape);
  }
})();
