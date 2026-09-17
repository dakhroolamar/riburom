(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  document.querySelectorAll('[data-cms-gallery]').forEach(gallery => {
    const track = gallery.querySelector('.cms-gallery-track');
    const slides = [...track.children];
    const load = index => {const image=slides[index]?.querySelector('img'); if(image?.dataset.src) {image.src=image.dataset.src; delete image.dataset.src;}};
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {if(entry.isIntersecting) load(slides.indexOf(entry.target));}), {root:track,rootMargin:'0px 60px'});
    slides.forEach(slide => observer.observe(slide));
    function move(direction) {
      const index = Math.max(0,Math.min(slides.length-1,Math.round(track.scrollLeft/track.clientWidth)+direction));
      load(index); track.scrollTo({left:index*track.clientWidth,behavior:reduced.matches?'instant':'smooth'});
    }
    gallery.querySelector('[data-gallery-prev]')?.addEventListener('click',()=>move(-1));
    gallery.querySelector('[data-gallery-next]')?.addEventListener('click',()=>move(1));
    track.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowLeft'?-1:1);}});
    track.addEventListener('scroll',()=>{const count=gallery.querySelector('[data-gallery-count]');if(count)count.textContent=`${Math.round(track.scrollLeft/track.clientWidth)+1} / ${slides.length}`;},{passive:true});
    if (gallery.hasAttribute('data-gallery-autoplay') && slides.length > 1) {
      let visible=false, hovered=false, focused=false, paused=false, timer=null, resumeAt=0;
      const connection=navigator.connection;
      const pauseButton=gallery.querySelector('[data-gallery-pause]');
      function schedule() {
        clearTimeout(timer); timer=null;
        if (!visible || hovered || focused || paused || document.hidden || reduced.matches || connection?.saveData) return;
        timer=setTimeout(() => {
          const index=(Math.round(track.scrollLeft/track.clientWidth)+1)%slides.length;
          load(index); track.scrollTo({left:index*track.clientWidth,behavior:'smooth'}); schedule();
        }, Math.max(8000, resumeAt-Date.now()));
      }
      const interaction=()=>{resumeAt=Date.now()+20000;schedule();};
      for (const event of ['pointerdown','wheel','keydown']) gallery.addEventListener(event,interaction,{passive:true});
      gallery.addEventListener('mouseenter',()=>{hovered=true;schedule();});
      gallery.addEventListener('mouseleave',()=>{hovered=false;schedule();});
      gallery.addEventListener('focusin',()=>{focused=true;schedule();});
      gallery.addEventListener('focusout',event=>{focused=gallery.contains(event.relatedTarget);schedule();});
      document.addEventListener('visibilitychange',schedule); reduced.addEventListener('change',schedule);
      connection?.addEventListener('change',schedule);
      new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;schedule();},{threshold:.2}).observe(gallery);
      pauseButton.addEventListener('click',()=>{paused=!paused;pauseButton.textContent=paused?'▶':'Ⅱ';pauseButton.setAttribute('aria-label',paused?'Resume automatic photographs':'Pause automatic photographs');schedule();});
    }
  });
})();
