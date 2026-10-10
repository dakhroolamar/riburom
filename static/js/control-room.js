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
    const state = form.querySelector('[data-save-state]');
    if (state) {
      const original = state.textContent;
      const show = () => {state.textContent = dirtyForms.has(form) ? 'Unsaved changes' : original;};
      form.addEventListener('input', show); form.addEventListener('change', show);
    }
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

  const packageForm = document.getElementById('package-editor');
  if (packageForm) {
    const mode = packageForm.querySelector('[data-price-mode]');
    const amount = packageForm.querySelector('[data-price-amount]');
    const syncPrice = () => {
      amount.disabled = mode.value !== 'amount'; amount.required = mode.value === 'amount';
      packageForm.elements.price_basis.disabled = mode.value !== 'amount';
      packageForm.elements.price.readOnly = mode.value !== 'legacy';
    };
    syncPrice(); baselines.set(packageForm, snapshot(packageForm));
    mode.addEventListener('change', () => {syncPrice(); refreshDirty(packageForm);});
    packageForm.querySelector('[data-add-day]')?.addEventListener('click', () => {
      const input = packageForm.querySelector('[data-itinerary-day]');
      const text = input.value.trim(); if (!text) return;
      const target = packageForm.elements.itinerary;
      const count = target.value.split('\n').filter(line => line.trim()).length;
      target.value = (target.value.trim() ? target.value.trim() + '\n' : '') + `Day ${count + 1}: ${text}`;
      input.value = ''; target.dispatchEvent(new Event('input', {bubbles:true})); input.focus();
    });
  }
  const checkedLeads = () => [...document.querySelectorAll('input[name="keys"][form="lead-bulk"]')];
  const showSelected = () => {
    const count = checkedLeads().filter(input => input.checked).length;
    const node = document.querySelector('[data-selection-count]'); if (node) node.textContent = `${count} selected`;
    document.querySelectorAll('#lead-bulk button').forEach(button => {button.disabled = count === 0;});
  };
  document.querySelector('[data-select-leads]')?.addEventListener('change', event => {checkedLeads().forEach(input => {input.checked = event.target.checked;}); showSelected();});
  checkedLeads().forEach(input => input.addEventListener('change', showSelected)); showSelected();
  const templates = JSON.parse(document.getElementById('operation-templates')?.textContent || '[]');
  const applyValues = (form, values) => {
    if (Object.entries(values).some(([key, value]) => form.elements[key]?.value && form.elements[key].value !== String(value)) && !confirm('Replace the existing itinerary/details with this template?')) return;
    Object.entries(values).forEach(([key, value]) => {const input = form.elements[key]; if (input) {input.value = value; input.dispatchEvent(new Event('input', {bubbles:true}));}});
  };
  document.querySelectorAll('[data-apply-package]').forEach(button => button.addEventListener('click', () => {
    const form = button.closest('form');
    const packageData = templates.find(item => String(item.id) === form.querySelector('[data-package-template]').value);
    if (!packageData) return;
    if (button.dataset.applyPackage === 'quote') {
      applyValues(form, {summary:packageData.summary});
      form.querySelector('[data-package-price]').textContent = `Starting price: ${packageData.price || 'Not set'}. Enter the confirmed group total below.`;
    } else applyValues(form, {destination:packageData.destination, itinerary:packageData.itinerary});
  }));
  document.querySelectorAll('[data-copy-trip]').forEach(button => button.addEventListener('click', async () => {
    const form = button.closest('form'), id = form.querySelector('[data-trip-template]').value;
    if (!id) return;
    button.disabled = true;
    try {
      const response = await fetch(`/workspace/control/trips/${encodeURIComponent(id)}/template`);
      if (!response.ok) throw new Error('Could not load that trip. Reload and try again.');
      applyValues(form, await response.json());
      status('Trip itinerary and assignments loaded. Set traveller name and new departure dates before saving.');
    } catch(error) {status(error.message);} finally {button.disabled = false;}
  }));
  const presets = JSON.parse(document.getElementById('permission-presets')?.textContent || '{}');
  document.querySelectorAll('[data-permission-preset]').forEach(button => button.addEventListener('click', () => {
    const form = button.closest('form'), selected = presets[button.dataset.permissionPreset];
    if (!selected) return;
    form.querySelectorAll('input[name="permissions"]').forEach(input => {input.checked = selected.includes(input.value);});
    form.elements.role.value = button.dataset.permissionPreset;
    form.dispatchEvent(new Event('input', {bubbles:true}));
    status('Tourism Operations permissions selected. Save the member to apply them.');
  }));
  const requestedDialog = new URLSearchParams(location.search).get('open');
  if (['partner-new','trip-new'].includes(requestedDialog)) document.getElementById(requestedDialog)?.showModal();

})();
