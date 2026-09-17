(() => {
  'use strict';

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-cms-gallery]').forEach((gallery) => {
    const track = gallery.querySelector('.cms-gallery-track');
    if (!track) return;

    const slides = [...track.children];
    if (!slides.length) return;

    const count = gallery.querySelector('[data-gallery-count]');
    const pauseButton = gallery.querySelector('[data-gallery-pause]');
    const connection = navigator.connection;

    const load = (index) => {
      const image = slides[index]?.querySelector('img');
      if (image?.dataset.src) {
        image.src = image.dataset.src;
        delete image.dataset.src;
      }
    };

    const indexFromScroll = () => {
      const width = Math.max(track.clientWidth, 1);
      return Math.max(0, Math.min(slides.length - 1, Math.round(track.scrollLeft / width)));
    };

    const syncCount = () => {
      if (count) count.textContent = `${indexFromScroll() + 1} / ${slides.length}`;
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) load(slides.indexOf(entry.target));
      });
    }, { root: track, rootMargin: '0px 80px' });
    slides.forEach((slide) => observer.observe(slide));

    function goTo(index, behavior = reduced.matches ? 'auto' : 'smooth') {
      const target = ((index % slides.length) + slides.length) % slides.length;
      load(target);
      track.scrollTo({ left: target * track.clientWidth, behavior });
    }

    function move(direction) {
      goTo(indexFromScroll() + direction);
    }

    gallery.querySelector('[data-gallery-prev]')?.addEventListener('click', () => move(-1));
    gallery.querySelector('[data-gallery-next]')?.addEventListener('click', () => move(1));
    track.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        move(event.key === 'ArrowLeft' ? -1 : 1);
      }
    });
    track.addEventListener('scroll', syncCount, { passive: true });
    syncCount();

    if (gallery.hasAttribute('data-gallery-autoplay') && slides.length > 1) {
      let visible = false;
      let paused = false;
      let timer = null;
      let resumeAt = 0;

      const schedule = () => {
        clearTimeout(timer);
        timer = null;

        if (!visible || paused || document.hidden || reduced.matches || connection?.saveData) return;

        const wait = Math.max(6000, resumeAt - Date.now());
        timer = setTimeout(() => {
          goTo(indexFromScroll() + 1);
          schedule();
        }, wait);
      };

      const temporarilyPause = () => {
        resumeAt = Date.now() + 12000;
        schedule();
      };

      // Manual interaction pauses briefly, then autoplay resumes. Merely hovering no longer
      // freezes the gallery, which made autoplay appear broken on desktop.
      for (const event of ['pointerdown', 'wheel', 'keydown', 'touchstart']) {
        gallery.addEventListener(event, temporarilyPause, { passive: event !== 'keydown' });
      }

      gallery.querySelector('[data-gallery-prev]')?.addEventListener('click', temporarilyPause);
      gallery.querySelector('[data-gallery-next]')?.addEventListener('click', temporarilyPause);
      document.addEventListener('visibilitychange', schedule);
      reduced.addEventListener('change', schedule);
      connection?.addEventListener('change', schedule);

      new IntersectionObserver((entries) => {
        visible = Boolean(entries[0]?.isIntersecting);
        schedule();
      }, { threshold: 0.2 }).observe(gallery);

      if (pauseButton) {
        pauseButton.addEventListener('click', () => {
          paused = !paused;
          pauseButton.textContent = paused ? '▶' : 'Ⅱ';
          pauseButton.setAttribute('aria-label', paused ? 'Resume automatic photographs' : 'Pause automatic photographs');
          schedule();
        });
      }
    }
  });
})();
