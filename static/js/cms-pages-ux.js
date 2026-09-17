(() => {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const buttons = [...document.querySelectorAll('[data-section]')];
    const title = document.getElementById('section-title');

    const select = button => {
      buttons.forEach(candidate => candidate.setAttribute('aria-current', String(candidate === button)));
      if (title) title.textContent = button.textContent.trim();
    };

    buttons.forEach(button => button.addEventListener('click', () => select(button)));

    const selected = buttons.find(button => button.getAttribute('aria-current') === 'true') || buttons[0];
    if (selected) select(selected);
  });
})();
