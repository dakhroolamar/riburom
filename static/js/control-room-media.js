(() => {
  'use strict';
  const $ = id => document.getElementById(id), csrf = document.querySelector('meta[name="csrf-token"]').content;
  let items = [], selected = null, newest = true, metadataDirty = false, requestTicket = 0;
  let pageNumber = 1, loadController, metadataSaving = false;
  const snapshot = form => JSON.stringify([...new FormData(form)]);
  const report = error => {if (error.name !== 'AbortError') status(error.message);};
  const status = window.ControlRoom.status;
  const url = value => /^https?:\/\//.test(value) ? value : '/static/' + value;
  function node(tag, text, parent, className) {const result = document.createElement(tag); if (text !== undefined) result.textContent = text; if (className) result.className = className; if (parent) parent.append(result); return result;}
  async function api(path, data, method='GET', signal) {
    const response = await fetch(path,{method,body:data,headers:{'X-CSRFToken':csrf},signal});
    if (response.redirected) throw Error('Your session expired. Sign in again.');
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const result = isJson ? await response.json() : null;
    if (!response.ok) throw Error(result?.error || `Unable to save (${response.status}). Check your input and try again.`);
    return result;
  }
  function field(parent, name, label, value, multiline=false) {
    const wrap = node('label',label,parent), input = node(multiline ? 'textarea' : 'input',undefined,wrap);
    input.name = name; input.value = value || ''; input.addEventListener('input',()=>{const form=input.closest('form');metadataDirty=snapshot(form)!==form.dataset.savedFields;}); return input;
  }
  function display() {
    const term = $('cr-media-search').value.toLowerCase(), kind=$('cr-media-kind').value, usage=$('cr-media-usage').value;
    const visible = items.filter(item => (!kind || item.kind === kind) && `${item.title} ${item.location || ''} ${item.tags || ''}`.toLowerCase().includes(term) && (!usage || (usage === 'used' ? item.usage?.length : !item.usage?.length)));
    visible.sort((a,b)=>newest ? b.created_at.localeCompare(a.created_at) : a.created_at.localeCompare(b.created_at));
    const grid = $('cr-media-grid'); grid.replaceChildren();
    for (const item of visible) {
      const card = node('button',undefined,grid,'cr-media-card' + (selected?.id === item.id && selected?.kind === item.kind ? ' active' : ''));
      card.type='button';card.setAttribute('aria-label','Select '+item.title);card.setAttribute('aria-pressed',String(selected?.id===item.id && selected?.kind===item.kind));
      const media=node(item.kind==='video'?'video':'img',undefined,card);media.src=item.kind==='video'?url(item.path):item.src;
      if(item.kind==='image'){media.alt=item.alt||'';media.loading='lazy';media.decoding='async';}else {media.preload='none';media.muted=true;}
      const content=node('div',undefined,card,'cr-media-card-content');node('strong',item.title,content);
      const chips=node('div',undefined,content,'cr-chip-row');for(const tag of (item.tags || item.category || (item.kind==='video'?'Video':'Photograph')).split(',').slice(0,3))node('span',tag.trim(),chips,'cr-chip');
      const footer=node('div',undefined,content,'cr-media-card-footer');node('span',new Date(item.created_at+'Z').toLocaleDateString('en-GB'),footer);node('span',item.usage?.length ? item.usage.length+' uses' : 'Unused',footer,'cr-badge '+(item.usage?.length?'green':'slate'));
      card.onclick=()=>{if(metadataSaving)return;if(metadataDirty&&!confirm('Discard unsaved image details?'))return;selected=item;metadataDirty=false;inspect();display();};
    }
    if(!visible.length) {const empty=node('div',undefined,grid,'cr-empty');node('h3','No media found',empty);node('p','Upload photographs or videos, or try a different filter.',empty);}
  }
  function inspect() {
    const root=$('cr-media-inspector');root.replaceChildren();if(!selected)return;
    const item=selected;
    const media=node(item.kind==='video'?'video':'img',undefined,root,'cr-media-preview');media.src=item.kind==='video'?url(item.path):(item.preview_src || item.src);
    if(item.kind==='image')media.alt=item.alt||'';else media.controls=true;
    node('h2',item.title,root);
    for (const use of item.usage_links || []) {const link=node('a','Edit '+use.label,root,'cr-button secondary small');link.href=use.href;}
    const dl=node('dl',undefined,root);for(const [label,value] of [['File type',item.kind==='video'?'Video':'Image'],['File size',item.byte_size ? (item.byte_size/1048576).toFixed(2)+' MB':'Unknown'],['Dimensions',item.width?`${item.width} × ${item.height} px`:'Not available'],['Upload date',new Date(item.created_at+'Z').toLocaleDateString('en-GB')],['Usage',item.usage?.join(', ')||'Not used on a page']]){node('dt',label,dl);node('dd',value,dl);}
    if(item.kind==='video') {
      const help=node('p','Use this video as the homepage opening film.',root,'cr-muted');
      const publish=node('button','Use as Opening Film',root);publish.type='button';publish.onclick=async()=>{if(!confirm('Replace the live homepage opening film with this video?'))return;try{await api('/workspace/control/media/videos/'+item.id+'/publish',new FormData(),'POST');status('Homepage opening film updated.');}catch(e){status(e.message);}};
      return;
    }
    const form=node('form',undefined,root);field(form,'title','Title',item.title).required=true;field(form,'alt','Alt text',item.alt);field(form,'caption','Caption',item.caption,true);field(form,'location','Location',item.location);field(form,'category','Category',item.category);field(form,'tags','Tags (comma separated)',item.tags);
    form.elements.title.placeholder='e.g. Dawki riverside campsite';
    form.elements.location.placeholder='e.g. Dawki, West Jaintia Hills';
    form.elements.tags.placeholder='e.g. camping, family, river';
    node('p','Use a descriptive title so staff can find this photo. If it appears sideways, rotate the original before replacing it. Adjust its focal crop in the page gallery editor.',form,'cr-muted');
    form.dataset.savedFields=snapshot(form);
    node('p','Image metadata is shared across every use of this photograph.',form,'cr-muted');
    const actions=node('div',undefined,form,'cr-actions');actions.style.marginTop='15px';node('button','Save Metadata',actions);
    const replace=node('label','Replace',actions,'cr-button secondary small');const replaceInput=node('input',undefined,replace);replaceInput.type='file';replaceInput.accept='image/jpeg,image/png,image/webp';replaceInput.hidden=true;
    replaceInput.onchange=async()=>{if(!replaceInput.files.length)return;if(!confirm('Replace this photograph in every collection that uses it?'))return;const data=new FormData();data.append('image',replaceInput.files[0]);try{await api('/workspace/control/media/assets/'+item.id+'/replace',data,'POST');await load(item.id);status('Photograph replaced.');}catch(e){status(e.message);}};
    const remove=node('button','Remove Unused Image',form,'secondary small');remove.type='button';remove.style.marginTop='10px';remove.disabled=!!item.usage?.length;remove.onclick=async()=>{if(!confirm('Remove this unused library record?'))return;try{await api('/workspace/media-api/assets/'+item.id,null,'DELETE');selected=null;await load();root.replaceChildren();status('Unused image removed.');}catch(e){status(e.message);}};
    form.onsubmit=async event=>{
      event.preventDefault();if(metadataSaving)return;
      const data=new FormData(form);data.append('version',item.version);
      metadataSaving=true;form.setAttribute('aria-busy','true');
      const controls=[...form.querySelectorAll('input,textarea,button')].map(control=>[control,control.disabled]);
      controls.forEach(([control])=>{control.disabled=true;});
      try{const result=await api('/workspace/control/media/metadata/'+item.id,data,'POST');item.version=result.version;metadataDirty=false;await load(item.id);status('Image metadata saved.');}
      catch(e){status(e.message);}
      finally{metadataSaving=false;form.removeAttribute('aria-busy');controls.forEach(([control,disabled])=>{control.disabled=disabled;});}
    };
  }
  async function load(id, append=false) {
    const ticket=++requestTicket;
    loadController?.abort(); loadController=new AbortController();
    const nextPage=append?pageNumber+1:1, kind=$('cr-media-kind').value, usage=$('cr-media-usage').value;
    const query='?page='+nextPage+'&q='+encodeURIComponent($('cr-media-search').value)+'&sort='+(newest?'newest':'oldest')+'&usage='+usage;
    const empty={items:[],total:0,has_next:false};
    const [images,videos]=await Promise.all([
      kind==='video'?empty:api('/workspace/control/media/assets'+query,null,'GET',loadController.signal),
      kind==='image'?empty:api('/workspace/control/media/videos'+query,null,'GET',loadController.signal)
    ]);if(ticket!==requestTicket)return;
    pageNumber=nextPage;items=append?[...items,...images.items,...videos.items]:[...images.items,...videos.items];
    $('cr-media-more').hidden=!(images.has_next||videos.has_next);
    $('cr-media-count').textContent=`${items.length} of ${images.total+videos.total} media files loaded`;
    if(id){
      selected=items.find(item=>item.kind==='image'&&item.id===id);
      if(!selected){const detail=await api('/workspace/control/media/assets?asset_id='+id,null,'GET',loadController.signal);if(ticket!==requestTicket)return;selected=detail.items[0];}
      inspect();
    }
    display();
  }
  function upload(file,index,total) {
    return new Promise((resolve,reject)=>{
      const video=file.type.startsWith('video/'),data=new FormData();data.append(video?'file':'image',file);
      const xhr=new XMLHttpRequest();xhr.open('POST',video?'/workspace/control/media/videos':'/workspace/media-api/assets');xhr.setRequestHeader('X-CSRFToken',csrf);
      xhr.upload.onprogress=event=>{if(event.lengthComputable)$('cr-media-progress').value=(index+event.loaded/event.total)/total*100;};
      xhr.onload=()=>{let result;try{result=JSON.parse(xhr.responseText);}catch{result={error:'Upload failed. Check your session and file type.'};}if(xhr.status>=200&&xhr.status<300)resolve(result);else reject(Error(file.name+': '+(result.error||'Upload failed.')));};xhr.onerror=()=>reject(Error('Network interrupted. Try uploading again.'));xhr.send(data);
    });
  }
  $('cr-upload').onchange=async event=>{
    const files=[...event.target.files];if(!files.length)return;$('cr-media-progress').hidden=false;$('cr-upload').disabled=true;
    let completed=0;const errors=[];
    for(let index=0;index<files.length;index++){try{await upload(files[index],index,files.length);completed++;}catch(error){errors.push(error.message);}}
    $('cr-upload-status').textContent=`${completed} of ${files.length} uploaded. `+errors.join(' ');$('cr-media-progress').hidden=true;$('cr-upload').disabled=false;$('cr-upload').value='';await load();
  };
  for(const id of ['cr-media-kind','cr-media-usage'])$(id).addEventListener('input',()=>load().catch(report));
  let searchTimer; $('cr-media-search').addEventListener('input',()=>{display();loadController?.abort();clearTimeout(searchTimer);searchTimer=setTimeout(()=>load().catch(report),250);});
  $('cr-media-search').value=new URLSearchParams(location.search).get('q')||'';
  $('cr-media-sort').onclick=()=>{newest=!newest;$('cr-media-sort').textContent=newest?'Upload Date ↓':'Upload Date ↑';load().catch(report);};
  $('cr-media-more').onclick=async()=>{const button=$('cr-media-more');button.disabled=true;try{await load(null,true);}catch(error){report(error);}finally{button.disabled=false;}};
  $('cr-media-view').onclick=()=>{$('cr-media-grid').classList.toggle('list-mode');};
  window.addEventListener('beforeunload',event=>{if(metadataDirty){event.preventDefault();event.returnValue='';}});
  load().catch(report);
})();
