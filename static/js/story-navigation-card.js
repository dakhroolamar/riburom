(function () {
  'use strict';
  const card = document.querySelector('[data-story-shortcut]');
  if (!card) return;
  const key = 'riburom-stories-card-dismissed';
  try { card.hidden = sessionStorage.getItem(key) === '1'; } catch { /* Optional persistence. */ }
  card.querySelector('button').addEventListener('click', () => {
    card.hidden = true;
    try { sessionStorage.setItem(key, '1'); } catch { /* Dismiss still works. */ }
  });
})();
