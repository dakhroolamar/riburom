(() => {
  'use strict';

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-cms-gallery]').forEach(gallery => {
    const track = gallery.querySelector('.cms-gallery-track');
    if (!track) return;

    const slides = [...track.children];
    if (!slides.length) return;

    const load = index => {
      const image = slides[index]?.querySelector('img');
      if (image?.dataset.src) {
        image.src = image.dataset.src;
        delete image.dataset.src;
      }
    };

    const slideLeft = slide => {
      const trackRect = track.getBoundingClientRect();
      const slideRect = slide.getBoundingClientRect();
      return Math.max(0, track.scrollLeft + slideRect.left - trackRect.left);
    };

    const currentIndex = () => {
      const trackRect = track.getBoundingClientRect();
      const center = trackRect.left + trackRect.width / 2;
      let best = 0;
      let distance = Infinity;
      slides.forEach((slide, index) => {
        const rect = slide.getBoundingClientRect();
        const nextDistance = Math.abs(rect.left + rect.width / 2 - center);
        if (nextDistance < distance) {
          best = index;
          distance = nextDistance;
        }
      });
      return best;
    };

    const syncState = () => {
      const index = currentIndex();
      const count = gallery.querySelector('[data-gallery-count]');
      if (count) count.textContent = `${index + 1} / ${slides.length}`;
      slides.forEach((slide, slideIndex) => slide.classList.toggle('is-active', slideIndex === index));
      load(index);
      load((index + 1) % slides.length);
    };

    const go = (index, behavior = reduced.matches ? 'auto' : 'smooth') => {
      const normalized = (index + slides.length) % slides.length;
      load(normalized);
      load((normalized + 1) % slides.length);
      track.scrollTo({left: slideLeft(slides[normalized]), behavior});
      slides.forEach((slide, slideIndex) => slide.classList.toggle('is-active', slideIndex === normalized));
    };

    const move = direction => go(currentIndex() + direction);

    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) load(slides.indexOf(entry.target));
    }), {root: track, rootMargin: '0px 120px'});
    slides.forEach(slide => observer.observe(slide));

    gallery.querySelector('[data-gallery-prev]')?.addEventListener('click', () => move(-1));
    gallery.querySelector('[data-gallery-next]')?.addEventListener('click', () => move(1));
    track.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        move(event.key === 'ArrowLeft' ? -1 : 1);
      }
    });

    let scrollFrame = 0;
    track.addEventListener('scroll', () => {
      cancelAnimationFrame(scrollFrame);
      scrollFrame = requestAnimationFrame(syncState);
    }, {passive: true});

    load(0);
    load(1);
    syncState();

    if (gallery.hasAttribute('data-gallery-autoplay') && slides.length > 1) {
      let visible = false;
      let focused = false;
      let paused = false;
      let timer = null;
      let resumeAt = 0;
      const connection = navigator.connection;
      const pauseButton = gallery.querySelector('[data-gallery-pause]');

      const schedule = () => {
        clearTimeout(timer);
        timer = null;
        if (!visible || focused || paused || document.hidden || reduced.matches || connection?.saveData) return;
        const delay = Math.max(5200, resumeAt - Date.now());
        timer = setTimeout(() => {
          go(currentIndex() + 1);
          schedule();
        }, delay);
      };

      const interaction = () => {
        resumeAt = Date.now() + 9000;
        schedule();
      };

      for (const event of ['pointerdown', 'wheel', 'keydown']) {
        gallery.addEventListener(event, interaction, {passive: event !== 'keydown'});
      }

      gallery.addEventListener('focusin', () => {
        focused = true;
        schedule();
      });
      gallery.addEventListener('focusout', event => {
        focused = gallery.contains(event.relatedTarget);
        schedule();
      });
      document.addEventListener('visibilitychange', schedule);
      reduced.addEventListener('change', schedule);
      connection?.addEventListener('change', schedule);

      new IntersectionObserver(entries => {
        visible = entries[0].isIntersecting;
        schedule();
      }, {threshold: .25}).observe(gallery);

      pauseButton?.addEventListener('click', () => {
        paused = !paused;
        pauseButton.textContent = paused ? '▶' : 'Ⅱ';
        pauseButton.setAttribute('aria-label', paused ? 'Resume automatic photographs' : 'Pause automatic photographs');
        schedule();
      });
    }
  });
})();
