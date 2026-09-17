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
  const SAMPLE_COUNT = 540;
  const state = {reveal: 0, scrollPhase: 0, frontier: null};
  let routeLength = 0;
  let lastFrameTime = 0;
  let droplets = [];
  let splashTotal = 0;
  let lastGlint = 0;
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

  // Widths are CSS pixels: broad surfaces, independent of SVG scaling.
  const bands = [
    {width: 116, color: '#123f63', alpha: .94, amp: 4, speed: .65, phase: .2, offset: 0},
    {width: 96, color: '#17688f', alpha: .96, amp: 8, speed: .88, phase: 1.6, offset: -5},
    {width: 71, color: '#279ebc', alpha: .92, amp: 12, speed: 1.12, phase: 3.1, offset: 5},
    {width: 43, color: '#65ccdc', alpha: .88, amp: 15, speed: 1.35, phase: 4.5, offset: -5},
    {width: 22, color: '#b3e9ee', alpha: .84, amp: 16, speed: 1.6, phase: 2.2, offset: 4},
    {width: 7, color: '#f1fcf8', alpha: .86, amp: 18, speed: 1.85, phase: 5.4, offset: 1}
  ];
  root.dataset.waterBandCount = String(bands.length);
  const waterScale = () => clamp(canvasWidth / 1200, .40, 1);

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function rebuildRoutePoints() {
    // Route through the actual layout, rather than stretching one drawing over
    // unrelated section heights. CSS reserves banks and crossing space.
    const width = root.clientWidth;
    const height = root.offsetHeight;
    const gutter = parseFloat(getComputedStyle(root).getPropertyValue('--rb-river-gutter')) || 100;
    const bank = gutter * .42;
    const sections = [...root.children].filter(el => el.matches('header, section') && el.offsetHeight)
      .sort((a, b) => a.offsetTop - b.offsetTop);
    const first = sections[0];
    if (!first || !height) return;
    const landscape = first.querySelector('.rb-paper-landscape');
    let x = landscape ? width * .5 : bank;
    let y = landscape ? first.offsetTop + first.offsetHeight - Math.min(100, landscape.offsetHeight * .5) : first.offsetTop;
    const commands = [`M${x} ${y}`];
    if (landscape) {
      // The source is concealed by the hero image. Hold the centre until the
      // water emerges beneath it, then follow the existing first crossing.
      y = first.offsetTop + first.offsetHeight + 12;
      commands.push(`L${x} ${y}`);
    }
    let right = true;
    for (const section of sections) {
      if (section === first && landscape) continue;
      const nextX = right ? width - bank : bank;
      const topPadding = parseFloat(getComputedStyle(section).paddingTop);
      const endY = section.offsetTop + topPadding - 48;
      const span = Math.max(1, endY - y);
      commands.push(`C${x} ${y + span * .52} ${nextX} ${endY - span * .52} ${nextX} ${endY}`);
      x = nextX;
      y = section.offsetTop + section.offsetHeight - parseFloat(getComputedStyle(section).paddingBottom) + 48;
      const bend = Math.min(16, gutter * .12) * (right ? -1 : 1);
      commands.push(`C${x + bend} ${endY + (y - endY) * .32} ${x - bend * .5} ${endY + (y - endY) * .68} ${x} ${y}`);
      right = !right;
    }
    commands.push(`C${x} ${y + 45} ${x} ${height - 30} ${x} ${height + 80}`);
    // Pixel geometry gives the fallback and live renderer the identical route.
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    route.setAttribute('d', commands.join(' '));
    svg.querySelectorAll('.rb-water-static').forEach(path => path.setAttribute('d', commands.join(' ')));
    root.dataset.waterLayout = 'continuous';
    const length = route.getTotalLength();
    routeLength = length;
    points = [];
    for (let i = 0; i <= SAMPLE_COUNT; i += 1) {
      const p = route.getPointAtLength(length * i / SAMPLE_COUNT);
      const across = Math.sin(Math.PI * clamp((p.x - bank) / (width - bank * 2), 0, 1));
      points.push({x:p.x, y:p.y, t:i / SAMPLE_COUNT, breadth:(.46 + .54 * across) * (.4 + .6 * clamp(length * i / SAMPLE_COUNT / 140, 0, 1))});
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
    root.dataset.waterWidth = String(Math.round(bands[0].width * waterScale()));
  }

  function screenPoints() {
    const ctm = route.getScreenCTM();
    if (!ctm) return [];
    // The advancing front stays visible, with a short eased catch-up after
    // scrolling. Page coordinates keep horizontal crossings in sync with content.
    const visible = points.filter(p => p.y <= state.frontier);
    state.reveal = visible.length ? visible[visible.length - 1].t : 0;
    return points.filter(p => p.t <= state.reveal).map(p => ({
      x: ctm.a * p.x + ctm.c * p.y + ctm.e,
      y: ctm.b * p.x + ctm.d * p.y + ctm.f,
      t: p.t, breadth:p.breadth
    }));
  }

  function shieldRects() {
    return [...root.querySelectorAll('[data-rb-water-shield], [data-rb-water-source]')].map(el => {
      const r = el.getBoundingClientRect();
      const padding = el.hasAttribute('data-rb-water-source') ? 0 : 16;
      return {left:r.left - padding, right:r.right + padding, top:r.top - padding, bottom:r.bottom + padding};
    });
  }

  function isShielded(point, shields) {
    return shields.some(r => point.x >= r.left && point.x <= r.right && point.y >= r.top && point.y <= r.bottom);
  }

  function rippleContribution(t, now) {
    let total = 0;
    for (const ripple of ripples) {
      const age = (now - ripple.born) / 1000;
      const spread = .008 + age * .015;
      const distance = t - ripple.t;
      const envelope = Math.exp(-(distance * distance) / (2 * spread * spread));
      const decay = Math.exp(-age * 2.8);
      total += ripple.amp * decay * envelope * Math.sin(age * 8 - Math.abs(distance) * 160);
    }
    return clamp(total, -4, 4);
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

  function surfacePoint(p, n, band, elapsed, now, side = 0) {
    const phase = p.t * 62 - elapsed * band.speed + band.phase + state.scrollPhase;
    const wave = band.amp * (Math.sin(phase) * .65 + Math.sin(phase * 1.73 + p.t * 19) * .35);
    const width = band.width * (.88 + .12 * Math.sin(p.t * 39 - elapsed * .8 + band.phase));
    const taper = clamp((state.reveal - p.t) * routeLength / 75, 0, 1);
    const offset = ((band.offset + wave + side * width * .5) * waterScale() + rippleContribution(p.t, now)) * p.breadth * taper;
    return {x:p.x + n.x * offset, y:p.y + n.y * offset};
  }

  function drawBand(list, band, elapsed, now) {
    // Closed filled banks give every current a changing cross-section.
    const banks = [-1, 1].map(side => list.map((p, i) =>
      surfacePoint(p, normalAt(list, i), band, elapsed, now, side)));
    ctx.beginPath();
    const outline = banks[0].concat(banks[1].reverse());
    const last = outline[outline.length - 1];
    ctx.moveTo((last.x + outline[0].x) / 2, (last.y + outline[0].y) / 2);
    for (let i = 0; i < outline.length; i++) {
      const p = outline[i], next = outline[(i + 1) % outline.length];
      ctx.quadraticCurveTo(p.x, p.y, (p.x + next.x) / 2, (p.y + next.y) / 2);
    }
    ctx.closePath();
    ctx.fillStyle = band.color;
    ctx.globalAlpha = band.alpha;
    ctx.fill();
  }

  function drawTexture(list, elapsed, now) {
    // Short, travelling filaments create flowing surface detail at several depths.
    ctx.lineCap = 'round';
    for (let lane = 0; lane < 17; lane++) {
      const band = bands[1 + lane % 4];
      ctx.beginPath();
      let drawing = false;
      for (let i = 0; i < list.length; i++) {
        const p = list[i];
        const phase = p.t * 175 - elapsed * (2.5 + lane % 3) + lane * 2.399;
        if (Math.sin(phase) < .35 || p.y < -100 || p.y > canvasHeight + 100) {
          drawing = false;
          continue;
        }
        const point = surfacePoint(p, normalAt(list, i), band, elapsed, now, Math.sin(lane * 4.7) * .8);
        if (!drawing) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
        drawing = true;
      }
      ctx.strokeStyle = lane % 4 === 0 ? '#073e64' : '#e4fcf7';
      ctx.globalAlpha = lane % 4 === 0 ? .22 : .27;
      ctx.lineWidth = (lane % 3 === 0 ? 1.5 : .7) * waterScale();
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function addSplash(point, count, strength = 1, glint = false) {
    const now = performance.now();
    for (let i = 0; i < count; i++) {
      droplets.push({
        x:point.x + window.scrollX + (Math.random() - .5) * 16,
        y:point.y + window.scrollY,
        vx:(Math.random() - .5) * 100 * strength,
        vy:-(35 + Math.random() * 90) * strength,
        radius:glint ? 1.2 + Math.random() * 2.1 : .6 + Math.random() * .8,
        born:now, life:glint ? 650 + Math.random() * 400 : 450 + Math.random() * 200, glint, strength
      });
    }
    if (droplets.length > 140) droplets.splice(0, droplets.length - 140);
    if (!glint) splashTotal += count;
    root.dataset.waterSplashTotal = String(splashTotal);
  }

  function drawSplashes(now, list, shields) {
    // Sparse surface glints keep the water luminous between pointer gestures.
    if (now - lastGlint > 180) {
      lastGlint = now;
      const visible = list.filter(p => p.y > 90 && p.y < canvasHeight - 30 && !isShielded(p, shields));
      if (visible.length) addSplash(visible[Math.floor(Math.random() * visible.length)], 1, .15, true);
    }
    droplets = droplets.filter(drop => now - drop.born < drop.life);
    ctx.save();
    ctx.shadowColor = '#a4edff';
    ctx.shadowBlur = 5;
    for (const drop of droplets) {
      const age = Math.max(0, now - drop.born) / 1000;
      const life = clamp((now - drop.born) / drop.life, 0, 1);
      const x = drop.x - window.scrollX + drop.vx * age;
      const y = drop.y - window.scrollY + drop.vy * age + (drop.glint ? 0 : 100 * drop.strength * age * age);
      const radius = drop.radius * Math.sin(Math.PI * life);
      ctx.globalAlpha = Math.min(1, (1 - life) * 1.6) * (drop.glint ? 1 : .5);
      ctx.fillStyle = drop.glint ? '#ffffff' : '#d8f8ff';
      ctx.beginPath();
      if (drop.glint || drop.radius > 2.5) {
        ctx.moveTo(x, y - radius * 2.5);
        ctx.lineTo(x + radius * .65, y - radius * .65);
        ctx.lineTo(x + radius * 2, y);
        ctx.lineTo(x + radius * .65, y + radius * .65);
        ctx.lineTo(x, y + radius * 2.5);
        ctx.lineTo(x - radius * .65, y + radius * .65);
        ctx.lineTo(x - radius * 2, y);
        ctx.lineTo(x - radius * .65, y - radius * .65);
        ctx.closePath();
      } else ctx.ellipse(x, y, radius * .65, radius * 1.5, -.3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    root.dataset.waterSplashCount = String(droplets.length);
  }

  function render(now) {
    if (!active) return;
    raf = requestAnimationFrame(render);
    frame += 1;
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    const rootRect = root.getBoundingClientRect();
    if (rootRect.bottom < 0 || rootRect.top > canvasHeight) return;

    const target = canvasHeight * .82 - rootRect.top;
    const dt = Math.min((now - lastFrameTime) / 1000 || .016, .1);
    lastFrameTime = now;
    if (state.frontier === null) state.frontier = target;
    else state.frontier += (target - state.frontier) * (1 - Math.exp(-dt * 9));
    const list = screenPoints();
    root.dataset.waterProgress = state.reveal.toFixed(3);
    if (list.length < 2) return;
    const shields = shieldRects();
    const elapsed = now / 1000;

    ctx.save();
    ctx.beginPath();
    ctx.rect(0, Math.max(0, rootRect.top), canvasWidth, Math.min(canvasHeight, rootRect.bottom) - Math.max(0, rootRect.top));
    ctx.clip();
    for (const band of bands) drawBand(list, band, elapsed, now);
    drawTexture(list, elapsed, now);
    drawSplashes(now, list, shields);
    // Mask the entire painted surface, including displaced edges and reflections.
    for (const shield of shields) ctx.clearRect(shield.left, shield.top, shield.right - shield.left, shield.bottom - shield.top);
    ctx.restore();
    root.dataset.waterWidth = String(Math.round(bands[0].width * waterScale()));

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
    if (now - lastMoveRipple > 220) {
      lastMoveRipple = now;
      addRipple(nearest.t, 2);
      addSplash(nearest, 2, .18);
    }
  }

  function onPointerDown(event) {
    if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
    const nearest = nearestVisiblePoint(event.clientX, event.clientY);
    if (nearest) {
      addRipple(nearest.t, 4);
      addSplash(nearest, 4, .25);
    }
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
    state.frontier = null;
    lastFrameTime = 0;
    const revealTween = ScrollTrigger.create({
      trigger: root, start: 'top bottom', end: 'bottom bottom',
      onRefresh: rebuildRoutePoints
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
      droplets = [];
      root.dataset.waterSplashCount = '0';
      hoverPoint = null;
    };
  });

  mm.add('(prefers-reduced-motion: reduce)', () => {
    rebuildRoutePoints();
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
  if (observer) {
    observer.observe(root);
    [...root.children].filter(el => el.matches('header, section')).forEach(el => observer.observe(el));
  }
  document.fonts?.ready.then(refresh);

  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    observer?.disconnect();
    cancelAnimationFrame(pending);
    cancelAnimationFrame(raf);
    mm.revert();
  });
})();
