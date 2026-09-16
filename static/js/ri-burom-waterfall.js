/* GSAP 3.12.5 + ScrollTrigger 3.12.5, vendored.
   The SVG supplies the route and static fallback; a lightweight viewport canvas
   renders the live multi-band water and local pointer ripples. */
(() => {
  'use strict';

  const root = document.querySelector('[data-rb-waterfall]');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';

  const svg = root.querySelector('.rb-waterfall');
  const route = svg?.querySelector('.rb-water-route');
  const canvas = root.querySelector('[data-rb-water-canvas]');
  const ctx = canvas?.getContext('2d', {alpha: true});
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;

  // Static SVG remains a complete fallback when canvas/GSAP is unavailable.
  if (!svg || !route || !canvas || !ctx || !gsap || !ScrollTrigger) return;

  gsap.registerPlugin(ScrollTrigger);
  const mm = gsap.matchMedia();
  const DPR_CAP = 1.5;
  const SAMPLE_COUNT = 180;
  const state = {reveal: 0, scrollPhase: 0};
  let points = [];
  let raf = 0;
  let frame = 0;
  let canvasWidth = 0;
  let canvasHeight = 0;
  let dpr = 1;
  let active = false;
  let hoverPoint = null;
  let ripples = [];
  let lastMoveRipple = 0;
  let lastScrollY = window.scrollY;

  const bands = [
    {width: 18, color: '#155a8c', alpha: .50, amp: 1.3, freq: .22, speed: .75, phase: .2},
    {width: 11, color: '#3f97c9', alpha: .72, amp: 2.2, freq: .27, speed: 1.05, phase: 1.6},
    {width: 5.2, color: '#8fd3ee', alpha: .88, amp: 2.8, freq: .32, speed: 1.28, phase: 3.1},
    {width: 1.6, color: '#f2fbff', alpha: .92, amp: 1.2, freq: .40, speed: 1.55, phase: 4.5}
  ];

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function rebuildRoutePoints() {
    const length = route.getTotalLength();
    points = [];
    for (let i = 0; i <= SAMPLE_COUNT; i += 1) {
      const p = route.getPointAtLength(length * i / SAMPLE_COUNT);
      points.push({x:p.x, y:p.y, t:i / SAMPLE_COUNT});
    }
  }

  function resizeCanvas() {
    dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
    canvasWidth = Math.max(1, window.innerWidth);
    canvasHeight = Math.max(1, window.innerHeight);
    canvas.width = Math.round(canvasWidth * dpr);
    canvas.height = Math.round(canvasHeight * dpr);
    canvas.style.width = canvasWidth + 'px';
    canvas.style.height = canvasHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    rebuildRoutePoints();
  }

  function screenPoints() {
    const ctm = route.getScreenCTM();
    if (!ctm) return [];
    const limit = state.reveal + .006;
    return points.filter(p => p.t <= limit).map(p => ({
      x: ctm.a * p.x + ctm.c * p.y + ctm.e,
      y: ctm.b * p.x + ctm.d * p.y + ctm.f,
      t: p.t
    }));
  }

  function shieldRects() {
    return [...root.querySelectorAll('[data-rb-water-shield]')].map(el => {
      const r = el.getBoundingClientRect();
      return {left:r.left - 16, right:r.right + 16, top:r.top - 16, bottom:r.bottom + 16};
    });
  }

  function isShielded(point, shields) {
    return shields.some(r => point.x >= r.left && point.x <= r.right && point.y >= r.top && point.y <= r.bottom);
  }

  function rippleContribution(t, now) {
    let total = 0;
    for (const ripple of ripples) {
      const age = (now - ripple.born) / 1000;
      const spread = .018 + age * .075;
      const distance = t - ripple.t;
      const envelope = Math.exp(-(distance * distance) / (2 * spread * spread));
      const decay = Math.exp(-age * 1.7);
      total += ripple.amp * decay * envelope * Math.sin(age * 12 - Math.abs(distance) * 85);
    }
    return total;
  }

  function addRipple(t, amp) {
    ripples.push({t, amp, born:performance.now()});
    if (ripples.length > 12) ripples.shift();
  }

  function normalAt(list, index) {
    const prev = list[Math.max(0, index - 1)];
    const next = list[Math.min(list.length - 1, index + 1)];
    const dx = next.x - prev.x;
    const dy = next.y - prev.y;
    const mag = Math.hypot(dx, dy) || 1;
    return {x:-dy / mag, y:dx / mag};
  }

  function drawBand(list, shields, band, elapsed, now) {
    if (list.length < 2) return;
    ctx.save();
    ctx.lineWidth = band.width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = band.color;
    ctx.globalAlpha = band.alpha;
    if (band.width >= 11) {
      ctx.shadowColor = 'rgba(31,111,168,.16)';
      ctx.shadowBlur = 3;
    }

    ctx.beginPath();
    let drawing = false;
    for (let i = 0; i < list.length; i += 1) {
      const p = list[i];
      if (p.y < -80 || p.y > canvasHeight + 80 || isShielded(p, shields)) {
        drawing = false;
        continue;
      }
      const n = normalAt(list, i);
      const wave = band.amp * Math.sin(p.t * 46 + band.phase + elapsed * band.speed + state.scrollPhase);
      const ripple = rippleContribution(p.t, now);
      const x = p.x + n.x * (wave + ripple);
      const y = p.y + n.y * (wave + ripple);
      if (!drawing) {
        ctx.moveTo(x, y);
        drawing = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawHoverRipple(now, list) {
    if (!hoverPoint) return;
    const age = (now - hoverPoint.born) / 1000;
    const pulse = 8 + (age % 1.2) * 11;
    const alpha = .46 * (1 - (age % 1.2) / 1.2);
    ctx.save();
    ctx.strokeStyle = `rgba(220,248,252,${alpha})`;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(hoverPoint.x, hoverPoint.y, pulse, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function render(now) {
    if (!active) return;
    raf = requestAnimationFrame(render);
    frame += 1;
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    const rootRect = root.getBoundingClientRect();
    if (rootRect.bottom < 0 || rootRect.top > canvasHeight) return;

    const list = screenPoints();
    if (list.length < 2) return;
    const shields = shieldRects();
    const elapsed = now / 1000;

    for (const band of bands) drawBand(list, shields, band, elapsed, now);
    drawHoverRipple(now, list);

    ripples = ripples.filter(r => now - r.born < 2600);
    root.dataset.waterProgress = state.reveal.toFixed(3);
    root.dataset.waterFrame = String(frame);
  }

  function nearestVisiblePoint(clientX, clientY) {
    const list = screenPoints();
    const shields = shieldRects();
    let nearest = null;
    let distance = Infinity;
    for (const p of list) {
      if (p.y < -40 || p.y > canvasHeight + 40 || isShielded(p, shields)) continue;
      const d = Math.hypot(p.x - clientX, p.y - clientY);
      if (d < distance) {
        distance = d;
        nearest = p;
      }
    }
    return distance <= 92 ? nearest : null;
  }

  function onPointerMove(event) {
    if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
    const nearest = nearestVisiblePoint(event.clientX, event.clientY);
    if (!nearest) {
      hoverPoint = null;
      root.dataset.waterInteractive = 'false';
      return;
    }

    hoverPoint = {x:nearest.x, y:nearest.y, t:nearest.t, born:performance.now()};
    root.dataset.waterInteractive = 'true';
    const now = performance.now();
    if (now - lastMoveRipple > 120) {
      lastMoveRipple = now;
      addRipple(nearest.t, 3.1);
    }
  }

  function onPointerDown(event) {
    if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
    const nearest = nearestVisiblePoint(event.clientX, event.clientY);
    if (nearest) addRipple(nearest.t, 6.2);
  }

  function onPointerLeave() {
    hoverPoint = null;
    root.dataset.waterInteractive = 'false';
  }

  function onScroll() {
    const y = window.scrollY;
    const delta = clamp(y - lastScrollY, -120, 120);
    state.scrollPhase += delta * .012;
    lastScrollY = y;
    hoverPoint = null;
    root.dataset.waterInteractive = 'false';
  }

  mm.add('(prefers-reduced-motion: no-preference)', () => {
    root.classList.add('rb-water-live');
    active = true;
    resizeCanvas();
    state.reveal = 0;
    const revealTween = gsap.to(state, {
      reveal: 1,
      ease: 'none',
      scrollTrigger: {
        trigger: root,
        start: 'top 72%',
        end: 'bottom 92%',
        scrub: 1,
        invalidateOnRefresh: true
      }
    });

    const roots = root.querySelector('[data-rb-roots]');
    const rootTween = roots ? gsap.fromTo(roots, {y:-8}, {y:8, ease:'none', scrollTrigger:{
      trigger:roots, start:'top bottom', end:'bottom top', scrub:1
    }}) : null;

    root.addEventListener('pointermove', onPointerMove, {passive:true});
    root.addEventListener('pointerdown', onPointerDown, {passive:true});
    root.addEventListener('pointerleave', onPointerLeave, {passive:true});
    window.addEventListener('scroll', onScroll, {passive:true});
    window.addEventListener('resize', resizeCanvas, {passive:true});
    raf = requestAnimationFrame(render);

    return () => {
      active = false;
      cancelAnimationFrame(raf);
      revealTween.kill();
      rootTween?.kill();
      root.classList.remove('rb-water-live');
      root.dataset.waterInteractive = 'false';
      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
      root.removeEventListener('pointermove', onPointerMove);
      root.removeEventListener('pointerdown', onPointerDown);
      root.removeEventListener('pointerleave', onPointerLeave);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', resizeCanvas);
      ripples = [];
      hoverPoint = null;
    };
  });

  mm.add('(prefers-reduced-motion: reduce)', () => {
    state.reveal = 1;
    root.classList.remove('rb-water-live');
    root.dataset.waterProgress = '1.000';
    root.dataset.waterInteractive = 'false';
  });

  let pending;
  const refresh = () => {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => {
      rebuildRoutePoints();
      ScrollTrigger.refresh();
    });
  };
  const observer = 'ResizeObserver' in window ? new ResizeObserver(refresh) : null;
  if (observer) observer.observe(root);

  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    observer?.disconnect();
    cancelAnimationFrame(pending);
    cancelAnimationFrame(raf);
    mm.revert();
  });
})();
