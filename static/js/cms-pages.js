/* Shared page editor and library. Text is always inserted as text, never HTML. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let key = '', state = {items: [], version: 0, limit: 10}, replacement = null, busy = false;
  const status = message => { $('editor-status').textContent = message; };
  const fail = error => status(error.message || 'Unable to save. Please try again.');
  let contentState = null, contentKey = '';
  async function loadContent(section) {
    contentKey = section;
    contentState = await api('content/' + section);
    const root = $('content-fields'); root.replaceChildren();
    $('section-content').hidden = !contentState.fields.length;
    contentState.fields.forEach(item => {
      const label = el('label', item.label, root), input = el('textarea', undefined, label);
      input.value = item.value; input.rows = item.value.length > 150 ? 4 : 2;
      input.addEventListener('input', () => item.value = input.value);
    });
  }
  async function api(path, data, method) {
    const response = await fetch('/workspace/media-api/' + path, {
      method: method || (data ? 'POST' : 'GET'),
      headers: {'X-CSRFToken': csrf, ...(data ? {'Content-Type': 'application/json'} : {})},
      body: data ? JSON.stringify(data) : undefined
    });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(value.error || 'The request failed. Check your input and reload if your session expired.');
    return value;
  }
  function el(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }
  function button(text, parent, click) {
    const node = el('button', text, parent); node.type = 'button';
    node.addEventListener('click', () => Promise.resolve(click()).catch(fail)); return node;
  }
  function field(label, value, parent, change, type = 'text') {
    const wrap = el('label', label, parent), input = el('input', undefined, wrap);
    input.type = type;
    if (type === 'checkbox') input.checked = value; else input.value = value || '';
    input.addEventListener('input', () => change(type === 'checkbox' ? input.checked : input.value));
    return input;
  }
  function metadata(asset, card) {
    const changes = {};
    for (const [name, label] of [['alt','Alt text'], ['caption','Caption (optional)'], ['credit','Credit / source (optional)']]) {
      field(label, asset[name], card, value => {changes[name] = value;});
    }
    button('Save image details', card, async () => {
      await api('assets/' + (asset.asset_id || asset.id), changes);
      Object.assign(asset, changes); status('Image details saved for every use of this photograph.');
    });
  }
  function renderItems() {
    const root = $('collection-items'); root.replaceChildren();
    state.items.forEach((item, index) => {
      const card = el('article', undefined, root); card.className = 'media-card'; card.draggable = true;
      card.addEventListener('dragstart', event => {event.dataTransfer.setData('text/plain', String(index));});
      card.addEventListener('dragover', event => event.preventDefault());
      card.addEventListener('drop', event => {
        event.preventDefault(); const from = Number(event.dataTransfer.getData('text/plain'));
        if (Number.isInteger(from) && from >= 0 && from < state.items.length) {
          state.items.splice(index, 0, state.items.splice(from, 1)[0]); renderItems();
        }
      });
      el('h3', index === 0 ? '1 · First / cover photograph' : 'Photograph ' + (index + 1), card);
      const image = el('img', undefined, card); image.src = item.src; image.alt = item.alt || '';
      image.className = 'focal'; image.style.objectPosition = `${item.focal_x ?? 50}% ${item.focal_y ?? 50}%`;
      const advanced = el('details', undefined, card); el('summary', 'Advanced: crop focus', advanced);
      const focusStatus = el('p', `Focus: ${item.focal_x ?? 50}% across, ${item.focal_y ?? 50}% down`, advanced);
      // Use the full uncropped image for accurate image-relative coordinates.
      const focusImage = el('img', undefined, advanced); focusImage.src = item.src; focusImage.alt = 'Click the subject to set the crop focus';
      focusImage.style.height = 'auto'; focusImage.className = 'focal';
      focusImage.addEventListener('click', event => {
        const rect = focusImage.getBoundingClientRect();
        item.focal_x = Math.round((event.clientX - rect.left) / rect.width * 100);
        item.focal_y = Math.round((event.clientY - rect.top) / rect.height * 100);
        focusStatus.textContent = `Focus: ${item.focal_x}% across, ${item.focal_y}% down`;
        image.style.objectPosition = `${item.focal_x}% ${item.focal_y}%`;
      });
      for (const axis of ['x','y']) {
        const input = field(axis === 'x' ? 'Horizontal focus' : 'Vertical focus', item['focal_' + axis] ?? 50, advanced, value => {item['focal_' + axis] = Number(value);}, 'range');
        input.min = 0; input.max = 100;
      }
      metadata(item, card);
      if (key === 'footer_partners') {
        field('Organization name', item.organization, card, value => item.organization = value);
        field('Website address (optional)', item.url, card, value => item.url = value, 'url');
        field('Short label (optional)', item.label, card, value => item.label = value);
        field('Visible', item.visible !== false, card, value => item.visible = value, 'checkbox');
        field('Open link in new tab', item.new_tab || false, card, value => item.new_tab = value, 'checkbox');
      }
      button('Make first / cover', card, () => {state.items.unshift(state.items.splice(index, 1)[0]); renderItems();});
      button('Move earlier', card, () => {if (index) {state.items.splice(index - 1, 0, state.items.splice(index, 1)[0]); renderItems();}});
      button('Move later', card, () => {if (index < state.items.length - 1) {state.items.splice(index + 1, 0, state.items.splice(index, 1)[0]); renderItems();}});
      button('Replace from library', card, () => openPicker(index));
      const replace = field('Upload replacement', '', card, () => {}, 'file'); replace.accept = 'image/jpeg,image/png,image/webp';
      replace.addEventListener('change', () => uploadFiles(replace.files, index).catch(fail));
      button('Remove from gallery', card, () => {state.items.splice(index, 1); renderItems();});
    });
  }
  async function openCollection(nextKey, title) {
    if (busy) return;
    key = nextKey;
    state = await api('collections/' + key);
    $('media-editor').hidden = false; $('collection-title').textContent = title;
    $('collection-limit').textContent = state.limit;
    $('legacy-media').replaceChildren();
    if (!state.items.length && state.legacy.length) {
      el('p', 'The website currently uses these existing photographs. They remain as fallbacks until you save a new gallery.', $('legacy-media'));
      state.legacy.forEach(src => {const image = el('img', undefined, $('legacy-media')); image.src = src; image.alt = 'Current fallback photograph';});
    }
    renderItems();
  }
  function upload(file) {
    return new Promise((resolve, reject) => {
      if (file.size > 12 * 1024 * 1024) return reject(Error(file.name + ': exceeds 12 MB.'));
      const xhr = new XMLHttpRequest(); xhr.open('POST', '/workspace/media-api/assets');
      xhr.setRequestHeader('X-CSRFToken', csrf);
      xhr.upload.onprogress = event => {if (event.lengthComputable) $('upload-progress').value = event.loaded / event.total * 100;};
      xhr.onload = () => {
        let result = {}; try {result = JSON.parse(xhr.responseText);} catch (_) { /* show a safe generic error */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(result);
        else reject(Error(file.name + ': ' + (result.error || 'Upload failed. Existing photographs are unchanged.')));
      };
      xhr.onerror = () => reject(Error(file.name + ': Network interrupted. Try again.'));
      const form = new FormData(); form.append('image', file); xhr.send(form);
    });
  }
  async function uploadFiles(files, replaceIndex = null) {
    if (busy) return;
    const selected = Array.from(files);
    if (selected.length > 10 || selected.reduce((sum,f) => sum + f.size, 0) > 120 * 1024 * 1024) throw Error('Select up to 10 files, 120 MB total, per batch.');
    if ($('media-editor') && replaceIndex === null && state.items.length + selected.length > state.limit) throw Error('This gallery is full. Remove a photograph first.');
    busy = true; $('upload-progress').hidden = false;
    const errors = [];
    try {
      for (let n = 0; n < selected.length; n++) {
        $('upload-status').textContent = `Uploading ${n + 1} of ${selected.length}: ${selected[n].name}`;
        try {
          const asset = await upload(selected[n]);
          if ($('media-editor')) {
            const item = {asset_id: asset.id, src: asset.src, focal_x:50, focal_y:50, visible:true};
            if (replaceIndex !== null) state.items[replaceIndex] = item; else state.items.push(item);
            renderItems();
          }
        } catch (error) {errors.push(error.message);}
      }
    } finally {busy = false; $('upload-progress').hidden = true;}
    $('upload-status').textContent = `${selected.length - errors.length} uploaded. ` + errors.join(' ');
    if ($('library-page')) await renderLibrary();
    else status('Uploads are in the library. Save gallery to apply your changes.');
  }
  async function openPicker(index = null) {replacement = index; await pickerResults(); $('library-picker').showModal();}
  async function pickerResults() {
    const assets = await api('assets?q=' + encodeURIComponent($('picker-search').value));
    $('picker-results').replaceChildren();
    assets.forEach(asset => {
      const card = el('article', undefined, $('picker-results')); card.className = 'media-card';
      const img = el('img', undefined, card); img.src = asset.src; img.alt = asset.alt;
      button(asset.title, card, () => {
        const item = {...asset, asset_id:asset.id, focal_x:50, focal_y:50, visible:true};
        if (replacement !== null) state.items[replacement] = item;
        else if (state.items.length < state.limit) state.items.push(item);
        else throw Error('This gallery is full.');
        renderItems(); $('library-picker').close();
      });
    });
    if (!assets.length) el('p', 'No images found. Upload a photograph to get started.', $('picker-results'));
  }
  async function renderLibrary() {
    const assets = await api('assets?q=' + encodeURIComponent($('library-search').value));
    const filter = $('library-filter').value; $('library-results').replaceChildren();
    assets.filter(a => filter === 'all' || (filter === 'used' ? a.usage.length : !a.usage.length)).forEach(asset => {
      const card = el('article', undefined, $('library-results')); card.className = 'media-card';
      const image = el('img', undefined, card); image.src = asset.src; image.alt = asset.alt; image.loading = 'lazy';
      el('h2', asset.title, card);
      el('p', `${asset.width || '?'} × ${asset.height || '?'} · ${asset.byte_size ? Math.round(asset.byte_size / 1024) + ' KB uploaded' : 'Size unknown'}`, card);
      el('p', new Date(asset.created_at).toLocaleDateString(), card);
      el('p', 'Used in: ' + (asset.usage.join(', ') || 'No collections'), card);
      metadata(asset, card);
      if (!asset.usage.length) button('Remove from library', card, async () => {await api('assets/' + asset.id, null, 'DELETE'); await renderLibrary();});
    });
  }
  document.querySelectorAll('[data-panel]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tab]').forEach(tab => tab.hidden = tab.dataset.tab !== button.dataset.panel);
    document.querySelectorAll('[data-panel]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  }));
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', async () => {
    if (busy) return status('Wait for the upload to finish.');
    $('section-title').textContent = button.textContent;
    loadContent(button.dataset.section).catch(fail);
    $('logo-editor').hidden = button.dataset.section !== 'hero';
    if (button.dataset.collection) {
      try {await openCollection(button.dataset.collection, button.textContent); document.querySelector('[data-panel="media"]').click();} catch (error) {fail(error);}
    } else {$('media-editor').hidden = true; document.querySelector('[data-panel="content"]').click();}
  }));
  if ($('save-collection')) {
    $('section-content').onsubmit = async event => {
      event.preventDefault();
      try {
        contentState = await api('content/' + contentKey, {token:contentState.token, values:Object.fromEntries(contentState.fields.map(f => [f.name,f.value]))});
        status('Section text saved.');
      } catch (error) {fail(error);}
    };
    loadContent(document.querySelector('[data-cms-page]').dataset.cmsPage === 'home' ? 'hero' : document.querySelector('[data-cms-page]').dataset.cmsPage).catch(fail);
    $('save-collection').onclick = async () => {
      if (busy) return;
      try {const result = await api('collections/' + key, state); state.version = result.version; status('Gallery saved.');} catch (error) {fail(error);}
    };
    $('upload-images').onchange = event => uploadFiles(event.target.files).catch(fail);
    $('choose-library').onclick = () => openPicker().catch(fail);
    $('picker-find').onclick = () => pickerResults().catch(fail);
    $('picker-close').onclick = () => $('library-picker').close();
    $('upload-drop').ondragover = event => event.preventDefault();
    $('upload-drop').ondrop = event => {event.preventDefault(); uploadFiles(event.dataTransfer.files).catch(fail);};
  }
  if ($('library-page')) {
    $('library-refresh').onclick = () => renderLibrary().catch(fail);
    $('library-filter').onchange = () => renderLibrary().catch(fail);
    $('library-upload').onchange = event => uploadFiles(event.target.files).catch(fail);
    renderLibrary().catch(fail);
  }
  if ($('logo-editor')) {
    let placement = {settings:{}, version:0};
    const values = () => placement.settings[$('logo-device').value] || {size:60,x:50,y:50};
    function preview() {
      const v = values(); for (const k of ['size','x','y']) $('logo-' + k).value = v[k];
      $('logo-preview').style.maxWidth = ({desktop:700,tablet:540,mobile:320})[$('logo-device').value] + 'px';
      Object.assign($('preview-logo').style, {width:v.size+'%', left:v.x+'%', top:v.y+'%'});
    }
    api('hero-placement').then(data => {placement=data; preview();}).catch(fail);
    $('logo-device').onchange = preview;
    for (const k of ['size','x','y']) $('logo-' + k).oninput = () => {
      placement.settings[$('logo-device').value] = {...values(), [k]:Number($('logo-' + k).value)}; preview();
    };
    $('logo-reset').onclick = () => {placement.settings[$('logo-device').value] = {size:60,x:50,y:50}; preview();};
    $('logo-save').onclick = async () => {try {const result=await api('hero-placement', placement); placement.version=result.version; status('Logo placement saved.');} catch(error) {fail(error);}};
  }
})();
