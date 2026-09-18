/* Shared page editor and library. Text is always inserted as text, never HTML. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let key = '', state = {items: [], version: 0, limit: 10}, replacement = null, busy = false;
  const status = message => { $('editor-status').textContent = message; };
  const fail = error => status(error.message || 'Unable to save. Please try again.');
  function setBusy(value) {
    busy = value;
    const surface = document.querySelector('.editor-surface');
    if (surface) surface.inert = value;
  }
  let contentState = null, contentKey = '', designState = null, selectedIndex = 0;
  let collectionDirty = false, textDirty = false, designDirty = false, logoDirty = false, requestId = 0;
  let galleryDesign = null, galleryDesignDirty = false;
  const supportsGallery = section => ['hero', 'home_gallery'].includes(section) || section.startsWith('tour-');
  const metadataChanges = new Map();
  const page = document.querySelector('[data-cms-page]');
  const canContent = page?.dataset.canContent === 'true';
  const canMedia = page?.dataset.canMedia === 'true';
  const dirty = () => collectionDirty || textDirty || designDirty || galleryDesignDirty || logoDirty || metadataChanges.size > 0;
  const changed = () => {collectionDirty = true; summary();};
  function summary() {
    if ($('gallery-summary')) $('gallery-summary').textContent = `${state.items.length} of ${state.limit} photographs · ${collectionDirty || metadataChanges.size ? 'Unsaved changes' : 'Saved'}`;
  }
  window.addEventListener('beforeunload', event => {if (dirty() || busy) {event.preventDefault(); event.returnValue = '';}});
  if (matchMedia('(max-width: 760px)').matches) document.querySelector('.mobile-navigation').open = false;
  async function loadContent(section, ticket) {
    if (!canContent) return;
    const result = await api('content/' + section);
    if (ticket !== requestId) return;
    contentState = result;
    const root = $('content-fields'); root.replaceChildren();
    $('section-content').hidden = !result.fields.length;
    $('content-empty').hidden = !!result.fields.length;
    result.fields.forEach(item => {
      const label = el('label', item.label, root), input = el('textarea', undefined, label);
      input.value = item.value; input.rows = item.value.length > 150 ? 4 : 2;
      input.addEventListener('input', () => {item.value = input.value; textDirty = true;});
    });
  }
  async function loadDesign(section, ticket) {
    if (!canContent) return;
    const result = await api('design/' + section);
    if (ticket !== requestId) return;
    designState = result;
    $('design-fields').replaceChildren();
    $('section-design').hidden = !result.fields.length;
    $('design-empty').hidden = !!result.fields.length || (canMedia && supportsGallery(section));
    result.fields.forEach(item => field(item.label, item.value, $('design-fields'), value => {
      item.value = value; designDirty = true;
    }, 'color'));
  }
  function syncTokens(token) {
    for (const draft of [contentState, designState, galleryDesign]) if (draft) draft.token = token;
  }
  async function loadGalleryDesign(section, ticket) {
    if (!canMedia || !supportsGallery(section)) return;
    const result = await api('gallery-design/' + section);
    if (ticket !== requestId) return;
    galleryDesign = result;
    $('gallery-autoplay').checked = result.values.autoplay;
    $('gallery-interval').value = String(result.values.interval);
    $('gallery-ratio').value = result.values.ratio;
    $('image-preview').style.aspectRatio = matchMedia('(max-width:600px)').matches ? '4/3' : result.values.ratio;
    $('gallery-design').hidden = false;
  }
  async function api(path, data, method) {
    const response = await fetch('/workspace/media-api/' + path, {
      method: method || (data ? 'POST' : 'GET'),
      headers: {'X-CSRFToken': csrf, ...(data ? {'Content-Type': 'application/json'} : {})},
      body: data ? JSON.stringify(data) : undefined
    });
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw Error('Your session expired. Reload the editor to sign in again.');
    const value = await response.json();
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
    node.addEventListener('click', () => Promise.resolve().then(click).catch(fail)); return node;
  }
  function field(label, value, parent, change, type = 'text') {
    const wrap = el('label', label, parent), input = el('input', undefined, wrap);
    input.type = type;
    if (type === 'checkbox') input.checked = value; else input.value = value || '';
    input.addEventListener('input', () => change(type === 'checkbox' ? input.checked : input.value));
    return input;
  }
  function metadata(asset, card) {
    const id = asset.asset_id || asset.id;
    const changes = metadataChanges.get(id) || {};
    for (const [name, label] of [['alt','Alt text'], ['caption','Caption (optional)'], ['credit','Credit / source (optional)']]) {
      field(label, changes[name] ?? asset[name], card, value => {changes[name] = value; metadataChanges.set(id, changes);});
    }
    button('Save image details', card, async () => {
      await api('assets/' + (asset.asset_id || asset.id), changes);
      Object.assign(asset, changes); metadataChanges.delete(id); status('Image details saved for every use of this photograph.');
    });
  }
  function renderItems() {
    const root = $('collection-items'); root.replaceChildren();
    const preview = $('image-preview'); preview.replaceChildren();
    const inspector = $('image-inspector'); inspector.replaceChildren();
    selectedIndex = Math.max(0, Math.min(selectedIndex, state.items.length - 1));
    state.items.forEach((item, index) => {
      const thumb = button('', root, () => {selectedIndex = index; renderItems();});
      thumb.setAttribute('aria-label', `Select photograph ${index + 1}`);
      thumb.setAttribute('aria-pressed', String(index === selectedIndex));
      const img = el('img', undefined, thumb); img.src = item.src; img.alt = item.alt || '';
      el('span', String(index + 1), thumb);
      thumb.draggable = true;
      thumb.addEventListener('dragstart', event => event.dataTransfer.setData('text/plain', String(index)));
      thumb.addEventListener('dragover', event => event.preventDefault());
      thumb.addEventListener('drop', event => {
        event.preventDefault(); const raw = event.dataTransfer.getData('text/plain');
        const from = Number(raw);
        if (raw !== '' && Number.isInteger(from) && from >= 0 && from < state.items.length) {
          state.items.splice(index, 0, state.items.splice(from, 1)[0]); selectedIndex = index; changed(); renderItems();
        }
      });
    });
    const item = state.items[selectedIndex];
    if (!item) {
      el('p', 'Add photographs to tell your story.', preview);
      el('h3', 'Your gallery starts here', inspector);
      el('p', 'Choose existing images or upload new photographs. The first image becomes the cover.', inspector);
      summary(); return;
    }
    const image = el('img', undefined, preview); image.src = item.preview_src || item.src; image.alt = item.alt || '';
    const updateFocus = () => image.style.objectPosition = `${item.focal_x ?? 50}% ${item.focal_y ?? 50}%`;
    updateFocus();
    el('h3', `Photograph ${selectedIndex + 1}`, inspector);
    el('p', selectedIndex === 0 ? 'First image · Gallery cover' : 'Edit this photograph', inspector);
    const assetId = item.asset_id || item.id;
    for (const [name,label] of [['alt','Alt text'], ['caption','Caption (optional)']]) {
      field(label, metadataChanges.get(assetId)?.[name] ?? item[name], inspector, value => {
        metadataChanges.set(assetId, {...metadataChanges.get(assetId), [name]:value}); summary();
      });
    }
    const advanced = el('details', undefined, inspector); el('summary', 'Credit & crop focus', advanced);
    field('Credit / source', metadataChanges.get(assetId)?.credit ?? item.credit, advanced, value => {
      metadataChanges.set(assetId, {...metadataChanges.get(assetId), credit:value}); summary();
    });
    for (const axis of ['x','y']) {
      const input = field(axis === 'x' ? 'Horizontal focus' : 'Vertical focus', item['focal_' + axis] ?? 50, advanced, value => {
        item['focal_' + axis] = Number(value); updateFocus(); changed();
      }, 'range'); input.min = 0; input.max = 100;
    }
    el('p', 'Alt text, captions and credits apply everywhere this image is used.', advanced);
    if (key === 'footer_partners') {
      for (const [name,label,type] of [['organization','Organization name','text'],['url','Website address','url'],['label','Short label','text'],['visible','Visible','checkbox'],['new_tab','Open in new tab','checkbox']]) {
        field(label, item[name], inspector, value => {item[name] = value; changed();}, type);
      }
    }
    const order = el('div', undefined, inspector); order.className = 'toolbar';
    button('← Earlier', order, () => reorder(-1)).disabled = selectedIndex === 0;
    button('Later →', order, () => reorder(1)).disabled = selectedIndex === state.items.length - 1;
    function reorder(direction) {
      state.items.splice(selectedIndex + direction, 0, state.items.splice(selectedIndex, 1)[0]);
      selectedIndex += direction; changed(); renderItems();
    }
    const actions = el('div', undefined, inspector); actions.className = 'toolbar';
    button('Replace image', actions, () => openPicker(selectedIndex)).className = 'secondary';
    button('Remove', actions, () => {state.items.splice(selectedIndex, 1); metadataChanges.delete(assetId); changed(); renderItems();}).className = 'secondary';
    const upload = el('details', undefined, inspector); el('summary', 'Upload a replacement', upload);
    const replace = field('Replacement photograph', '', upload, () => {}, 'file'); replace.accept = 'image/jpeg,image/png,image/webp';
    replace.addEventListener('change', () => uploadFiles(replace.files, selectedIndex).catch(fail));
    summary();
  }
  async function openCollection(nextKey, title, ticket) {
    const result = await api('collections/' + nextKey);
    if (ticket !== requestId) return;
    key = nextKey; state = result; selectedIndex = 0;
    $('media-editor').hidden = false; $('other-media').hidden = true;
    $('collection-title').textContent = title;
    $('collection-limit').textContent = state.limit;
    $('legacy-media').replaceChildren();
    if (!state.items.length && state.legacy.length) {
      el('p', 'Existing photographs stay on the website until you save a new selection.', $('legacy-media'));
      state.legacy.forEach(src => {const image = el('img', undefined, $('legacy-media')); image.src = src; image.alt = 'Current website photograph';});
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
    setBusy(true); $('upload-progress').hidden = false;
    const errors = [];
    try {
      for (let n = 0; n < selected.length; n++) {
        $('upload-status').textContent = `Uploading ${n + 1} of ${selected.length}: ${selected[n].name}`;
        try {
          const asset = await upload(selected[n]);
          if ($('media-editor')) {
            const item = {asset_id: asset.id, src: asset.src, focal_x:50, focal_y:50, visible:true};
            if (replaceIndex !== null) state.items[replaceIndex] = item; else state.items.push(item);
            changed(); renderItems();
          }
        } catch (error) {errors.push(error.message);}
      }
    } finally {setBusy(false); $('upload-progress').hidden = true;}
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
        changed(); renderItems(); $('library-picker').close();
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
      const details = el('details', undefined, card); el('summary', 'Image details', details); metadata(asset, details);
      if (!asset.usage.length) button('Remove from library', card, async () => {await api('assets/' + asset.id, null, 'DELETE'); await renderLibrary();});
    });
  }
  document.querySelectorAll('[data-panel]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tab]').forEach(tab => tab.hidden = tab.dataset.tab !== button.dataset.panel);
    document.querySelectorAll('[data-panel]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  }));
  async function selectSection(button) {
    if (busy) return status('Wait for the current save or upload to finish.');
    if (dirty() && !confirm('Discard unsaved changes before changing sections?')) return;
    window.dispatchEvent(new Event('cms-discard'));
    const ticket = ++requestId;
    collectionDirty = textDirty = designDirty = galleryDesignDirty = logoDirty = false; metadataChanges.clear();
    contentState = designState = galleryDesign = null;
    if ($('gallery-design')) $('gallery-design').hidden = true;
    $('image-preview').style.aspectRatio = '';
    contentKey = button?.dataset.section || page.dataset.cmsPage;
    key = '';
    $('section-title').textContent = button?.textContent || document.querySelector('h1').textContent;
    document.querySelectorAll('[data-section]').forEach(node => node.setAttribute('aria-pressed', String(node === button)));
    if ($('logo-editor')) $('logo-editor').hidden = contentKey !== 'hero';
    $('media-editor').hidden = true; $('other-media').hidden = false;
    $('section-content').hidden = true;
    if ($('section-design')) $('section-design').hidden = true;
    status('Loading section…');
    const collection = button?.dataset.collection;
    document.querySelector(`[data-panel="${canMedia && collection && contentKey !== 'hero' ? 'media' : canContent ? 'content' : 'appearance'}"]`)?.click();
    try {
      await Promise.all([loadContent(contentKey, ticket), loadDesign(contentKey, ticket), loadGalleryDesign(contentKey, ticket),
        canMedia && collection ? openCollection(collection, button.textContent, ticket) : Promise.resolve()]);
      if (ticket !== requestId) return;
      status('');
    } catch (error) {if (ticket === requestId) fail(error);}
  }
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => selectSection(button)));
  if ($('save-collection')) {
    $('section-content').onsubmit = async event => {
      event.preventDefault(); if (!contentState || busy) return;
      setBusy(true);
      try {
        contentState = await api('content/' + contentKey, {token:contentState.token, values:Object.fromEntries(contentState.fields.map(f => [f.name,f.value]))});
        syncTokens(contentState.token);
        textDirty = false; status('Section text saved.');
      } catch (error) {fail(error);} finally {setBusy(false);}
    };
    if ($('section-design')) $('section-design').onsubmit = async event => {
      event.preventDefault(); if (!designState || busy) return;
      setBusy(true);
      try {
        designState = await api('design/' + contentKey, {token:designState.token, values:Object.fromEntries(designState.fields.map(f => [f.name,f.value]))});
        syncTokens(designState.token);
        designDirty = false; status('Section design saved.');
      } catch (error) {fail(error);} finally {setBusy(false);}
    };
    $('save-collection').onclick = async () => {
      if (busy || !key) return;
      setBusy(true); $('save-collection').disabled = true;
      try {
        const result = await api('collections/' + key, state); state.version = result.version; collectionDirty = false;
        for (const [id, values] of metadataChanges) {
          await api('assets/' + id, values);
          state.items.filter(item => (item.asset_id || item.id) === id).forEach(item => Object.assign(item, values));
          metadataChanges.delete(id);
        }
        summary(); status('Gallery and image details saved.');
      } catch (error) {summary(); fail(error);} finally {setBusy(false); $('save-collection').disabled = false;}
    };
    $('upload-images').onchange = event => uploadFiles(event.target.files).catch(fail);
    $('choose-library').onclick = () => openPicker().catch(fail);
    $('picker-find').onclick = () => pickerResults().catch(fail);
    $('picker-close').onclick = () => $('library-picker').close();
    $('upload-drop').ondragover = event => event.preventDefault();
    $('upload-drop').ondrop = event => {event.preventDefault(); uploadFiles(event.dataTransfer.files).catch(fail);};
    const requested = [...document.querySelectorAll('[data-section]')].find(button => '#' + button.dataset.section === location.hash);
    selectSection(requested || document.querySelector('[data-section]'));
  }
  if ($('library-page')) {
    $('library-refresh').onclick = () => renderLibrary().catch(fail);
    $('library-filter').onchange = () => renderLibrary().catch(fail);
    $('library-upload').onchange = event => uploadFiles(event.target.files).catch(fail);
    renderLibrary().catch(fail);
  }
  if ($('gallery-design')) {
    $('gallery-design').addEventListener('input', () => {
      galleryDesignDirty = true;
      $('image-preview').style.aspectRatio = matchMedia('(max-width:600px)').matches ? '4/3' : $('gallery-ratio').value;
    });
    $('gallery-design').onsubmit = async event => {
      event.preventDefault(); if (busy || !galleryDesign) return;
      setBusy(true);
      try {
        galleryDesign = await api('gallery-design/' + contentKey, {token:galleryDesign.token, values:{
          autoplay:$('gallery-autoplay').checked, interval:Number($('gallery-interval').value), ratio:$('gallery-ratio').value
        }});
        syncTokens(galleryDesign.token); galleryDesignDirty = false; status('Gallery design saved.');
      } catch (error) {fail(error);} finally {setBusy(false);}
    };
  }
  if ($('logo-editor')) {
    let placement = {settings:{}, version:0}, savedPlacement = structuredClone(placement);
    window.addEventListener('cms-discard', () => {placement = structuredClone(savedPlacement); preview();});
    const values = () => placement.settings[$('logo-device').value] || {size:60,x:50,y:50};
    function preview() {
      const v = values(); for (const k of ['size','x','y']) $('logo-' + k).value = v[k];
      $('logo-preview').style.maxWidth = ({desktop:700,tablet:540,mobile:320})[$('logo-device').value] + 'px';
      Object.assign($('preview-logo').style, {width:v.size+'%', left:v.x+'%', top:v.y+'%'});
    }
    api('hero-placement').then(data => {placement=data; savedPlacement=structuredClone(data); preview();}).catch(fail);
    $('logo-device').onchange = preview;
    for (const k of ['size','x','y']) $('logo-' + k).oninput = () => {
      placement.settings[$('logo-device').value] = {...values(), [k]:Number($('logo-' + k).value)}; logoDirty = true; preview();
    };
    $('logo-reset').onclick = () => {placement.settings[$('logo-device').value] = {size:60,x:50,y:50}; logoDirty = true; preview();};
    $('logo-save').onclick = async () => {if (busy) return; setBusy(true); try {const result=await api('hero-placement', placement); placement.version=result.version; savedPlacement=structuredClone(placement); logoDirty = false; status('Logo placement saved.');} catch(error) {fail(error);} finally {setBusy(false);}};
  }
})();
