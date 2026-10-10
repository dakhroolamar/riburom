(() => {
  'use strict';
  const status = message => { const node = document.getElementById('cr-status'); if (node) node.textContent = message; };
  window.ControlRoom = {status};
  document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.open)?.showModal()));
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  }));
  const menu = document.querySelector('[data-menu]');
  menu?.addEventListener('click', () => {
    const open = document.getElementById('cr-sidebar').classList.toggle('is-open');
    menu.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => {if (event.key === 'Escape') {document.getElementById('cr-sidebar')?.classList.remove('is-open'); menu?.setAttribute('aria-expanded','false');}});
  document.querySelectorAll('[data-tab-group]').forEach(group => {
    const buttons = [...group.querySelectorAll('[data-tab-target]')];
    buttons.forEach(button => {
      button.setAttribute('aria-pressed', String(button.classList.contains('active')));
      button.addEventListener('click', () => buttons.forEach(other => {
        const active = other === button;
        other.classList.toggle('active', active);
        other.setAttribute('aria-pressed', String(active));
        const panel = document.getElementById(other.dataset.tabTarget);
        if (panel) panel.hidden = !active;
      }));
    });
  });
  document.querySelectorAll('[data-table-search],[data-table-filter]').forEach(input => {
    const id = input.dataset.tableSearch || input.dataset.tableFilter;
    const filter = () => {
      const search = document.querySelector(`[data-table-search="${id}"]`)?.value.toLowerCase() || '';
      const selected = document.querySelector(`[data-table-filter="${id}"]`)?.value || '';
      document.querySelectorAll(`#${id} tbody tr`).forEach(row => {row.hidden = !row.textContent.toLowerCase().includes(search) || !!(selected && row.dataset.status !== selected);});
    };
    input.addEventListener('input', filter);
  });
  document.querySelector('[data-page-search]')?.addEventListener('input', event => document.querySelectorAll('.cr-page-link').forEach(link => {link.hidden = !link.textContent.toLowerCase().includes(event.target.value.toLowerCase());}));
  document.querySelector('[data-password-toggle]')?.addEventListener('click', event => {
    const input = document.getElementById('cr-login-password');
    input.type = input.type === 'password' ? 'text' : 'password';
    event.currentTarget.setAttribute('aria-label', input.type === 'password' ? 'Show password' : 'Hide password');
  });
  document.querySelector('[data-forgot]')?.addEventListener('click', () => {document.getElementById('cr-login-help').hidden = false;});
  document.querySelector('[data-print]')?.addEventListener('click', () => window.print());
  const dirtyForms = new Set(), baselines = new WeakMap();
  const snapshot = form => JSON.stringify([...new FormData(form)].filter(([key]) => !['csrf_token', 'token', 'work_token'].includes(key))
    .map(([key, value]) => [key, value instanceof File ? (value.name ? [value.name, value.size, value.lastModified] : null) : value]));
  const refreshDirty = form => {if (snapshot(form) === baselines.get(form)) dirtyForms.delete(form); else dirtyForms.add(form);};
  document.querySelectorAll('[data-dirty-form]').forEach(form => {
    baselines.set(form, snapshot(form));
    form.addEventListener('input', () => refreshDirty(form));
    form.addEventListener('change', () => refreshDirty(form));
    form.addEventListener('submit', event => {queueMicrotask(() => {if (!event.defaultPrevented) dirtyForms.delete(form);});});
  });
  window.addEventListener('beforeunload', event => {if (dirtyForms.size) {event.preventDefault(); event.returnValue = '';}});
  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    const unsaved = dirtyForms.size && form.action.includes('/publish');
    const message = form.dataset.confirm + (unsaved ? ' Unsaved page text will not be included. Continue publishing the saved draft?' : '');
    if (!confirm(message)) event.preventDefault();
    else if (unsaved) dirtyForms.clear();
  }));
  document.querySelectorAll('[data-block-up],[data-block-down]').forEach(button => button.addEventListener('click', () => {
    const block = button.closest('.cr-block');
    if ('blockUp' in button.dataset && block.previousElementSibling) block.parentNode.insertBefore(block,block.previousElementSibling);
    if ('blockDown' in button.dataset && block.nextElementSibling) block.parentNode.insertBefore(block.nextElementSibling,block);
    const form = block.closest('form'); if (form) refreshDirty(form);
  }));
  document.querySelectorAll('[data-dismiss-notice]').forEach(button => button.addEventListener('click', () => button.parentElement.remove()));

})();
