(() => {
  const intro = document.querySelector('[data-code-intro]');
  if (!intro || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const key = 'rb-code-intro-v1';
  try {
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, 'seen');
  } catch (_) {
    // If session storage is blocked, leave the usable static homepage visible.
    return;
  }
  const scene = intro.querySelector('[data-intro-scene]');
  const finish = () => { intro.hidden = true; };
  scene.addEventListener('error', finish, { once: true });
  scene.addEventListener('load', () => {
    intro.hidden = false;
    intro.classList.add('is-playing');
    setTimeout(finish, 4600);
  }, { once: true });
  scene.src = scene.dataset.introScene;
})();
