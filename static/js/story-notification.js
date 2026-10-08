document.querySelector('.rb-story-notification-close')?.addEventListener('click', () => {
  document.querySelector('.rb-story-notification').hidden = true;
});

document.querySelector('a[href="#write-review"]')?.addEventListener('click', () => {
  document.getElementById('write-review').open = true;
});

if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  document.querySelectorAll('.rb-review-scroll').forEach(row => {
    let paused = false;
    let direction = 1;
    let last = 0;
    row.addEventListener('mouseenter', () => { paused = true; });
    row.addEventListener('mouseleave', () => { paused = false; });
    row.addEventListener('focusin', () => { paused = true; });
    row.addEventListener('focusout', () => { paused = false; });
    row.addEventListener('touchstart', () => { paused = true; }, { passive: true });
    const tick = now => {
      if (last && !paused && !document.hidden) {
        const end = row.scrollWidth - row.clientWidth;
        if (end > 0) {
          row.scrollLeft += direction * Math.min(now - last, 50) * .018;
          if (row.scrollLeft >= end - 1) direction = -1;
          if (row.scrollLeft <= 0) direction = 1;
        }
      }
      last = now;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
