/* Shared by server galleries and the asynchronously rendered river gallery. */
(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  function init(gallery) {
    const track = gallery.querySelector('.cms-gallery-track');
    if (!track?.children.length || gallery.dataset.galleryReady) return;
    gallery.dataset.galleryReady = 'true';
    const slides = [...track.children];
    const interval = [1000, 2000, 5000, 6000, 7000].includes(Number(gallery.dataset.galleryInterval)) ? Number(gallery.dataset.galleryInterval) : 6000;
    const count = gallery.querySelector('[data-gallery-count]');
    const pause = gallery.querySelector('[data-gallery-pause]');
    let visible = false, paused = false, held = false, hovered = gallery.matches(':hover'), focused = false, timer, resumeAt = 0;
    let animation = 0;
    const offset = slide => slide.getBoundingClientRect().left - track.getBoundingClientRect().left + track.scrollLeft;
    const index = () => slides.reduce((best, slide, n) =>
      Math.abs(offset(slide) - track.scrollLeft) < Math.abs(offset(slides[best]) - track.scrollLeft) ? n : best, 0);
    const load = n => {
      const img = slides[(n + slides.length) % slides.length]?.querySelector('img');
      if (img) img.loading = 'eager';
      if (img?.dataset.src) { img.src = img.dataset.src; delete img.dataset.src; }
    };
    const sync = () => {
      const n = index();
      if (count) count.textContent = `${n + 1} / ${slides.length}`;
      gallery.dataset.galleryIndex = String(n);
      gallery.style.setProperty('--gallery-progress', `${(n + 1) / slides.length * 100}%`);
      load(n);
      load(n + 1);
    };
    function go(n) {
      n = (n + slides.length) % slides.length;
      load(n);
      load(n + 1);
      cancelAnimationFrame(animation);
      const start = track.scrollLeft, end = offset(slides[n]);
      if (reduced.matches || (n === 0 && index() === slides.length - 1)) {
        track.scrollTo({left:end, behavior:'instant'});
        if (!reduced.matches) slides[n].animate([{opacity:.65},{opacity:1}],{duration:350});
        sync();
        return;
      }
      track.style.scrollSnapType = 'none';
      const began = performance.now();
      const step = now => {
        const progress = Math.min((now - began) / 400, 1);
        const eased = progress * progress * (3 - 2 * progress);
        track.scrollLeft = start + (end - start) * eased;
        if (progress < 1) animation = requestAnimationFrame(step);
        else { animation = 0; track.style.scrollSnapType = ''; sync(); }
      };
      animation = requestAnimationFrame(step);
    }
    function schedule() {
      clearTimeout(timer);
      if (!visible || paused || held || hovered || focused || document.hidden || reduced.matches || navigator.connection?.saveData ||
          !gallery.hasAttribute('data-gallery-autoplay') || slides.length < 2) return;
      timer = setTimeout(() => {go(index() + 1); schedule();}, Math.max(interval, resumeAt - Date.now()));
    }
    function manual() { resumeAt = Date.now() + interval; schedule(); }
    gallery.addEventListener('pointerenter', event => {
      if (event.pointerType === 'touch') return;
      hovered = true;
      cancelAnimationFrame(animation);
      animation = 0;
      track.scrollTo({left:track.scrollLeft, behavior:'instant'});
      schedule();
    });
    gallery.addEventListener('pointerleave', () => { hovered = false; schedule(); });
    gallery.addEventListener('focusin', event => { focused = event.target.matches(':focus-visible'); schedule(); });
    gallery.addEventListener('focusout', event => {
      focused = gallery.contains(event.relatedTarget) && event.relatedTarget.matches(':focus-visible');
      schedule();
    });
    for (const [selector, direction] of [['[data-gallery-prev]', -1], ['[data-gallery-next]', 1]]) {
      const button = gallery.querySelector(selector);
      if (button) {
        button.disabled = slides.length < 2;
        button.addEventListener('click', () => {manual(); go(index() + direction);});
      }
    }
    track.addEventListener('keydown', event => {
      if (['ArrowLeft', 'ArrowRight'].includes(event.key)) {
        event.preventDefault(); manual(); go(index() + (event.key === 'ArrowLeft' ? -1 : 1));
      }
    });
    track.addEventListener('scroll', () => { if (!animation) sync(); }, {passive:true});
    track.addEventListener('wheel', manual, {passive:true});
    track.addEventListener('pointerdown', () => {held = true; manual();}, {passive:true});
    for (const event of ['pointerup', 'pointercancel']) window.addEventListener(event, () => {
      if (held) {held = false; manual();}
    }, {passive:true});
    if (pause) {
      pause.hidden = slides.length < 2 || !gallery.hasAttribute('data-gallery-autoplay');
      pause.addEventListener('click', () => {
        paused = !paused;
        pause.textContent = paused ? '▶' : 'Ⅱ';
        pause.setAttribute('aria-label', paused ? 'Resume automatic photographs' : 'Pause automatic photographs');
        pause.setAttribute('aria-pressed', String(paused));
        schedule();
      });
    }
    new IntersectionObserver(entries => {
      const next = entries[0].intersectionRatio >= 0.2;
      if (next !== visible) {visible = next; schedule();}
    }, {threshold:[0, 0.2]}).observe(gallery);
    const loader = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) load(slides.indexOf(entry.target));
    }), {root:track});
    slides.forEach(slide => loader.observe(slide));
    document.addEventListener('visibilitychange', schedule);
    reduced.addEventListener('change', schedule);
    navigator.connection?.addEventListener('change', schedule);
    load(0); sync();
  }
  window.RiBuromGallery = {init};
  document.querySelectorAll('[data-cms-gallery]').forEach(init);
})();
