/* GSAP 3.12.5 + ScrollTrigger 3.12.5, vendored; complete static art on failure. */
(() => {
  'use strict';

  const root = document.querySelector('[data-rb-waterfall]');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';

  const svg = root.querySelector('.rb-waterfall');
  if (!svg) return;

  const reveal = svg.querySelector('.rb-water-reveal');
  const route = svg.querySelector('.rb-water-base');
  const cursorRipple = svg.querySelector('[data-rb-water-cursor]');
  const waypoints = [...svg.querySelectorAll('.rb-water-waypoint')];
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;

  // The static SVG remains complete if animation dependencies are unavailable.
  if (!gsap || !ScrollTrigger || !reveal || !route) return;

  gsap.registerPlugin(ScrollTrigger);
  const mm = gsap.matchMedia();

  mm.add('(prefers-reduced-motion: no-preference)', () => {
    const length = reveal.getTotalLength();
    gsap.set(reveal, {strokeDasharray: length, strokeDashoffset: length});

    const journey = gsap.timeline({scrollTrigger: {
      trigger: root,
      start: 'top 70%',
      end: 'bottom 90%',
      scrub: 1,
      invalidateOnRefresh: true
    }});

    journey.to(reveal, {strokeDashoffset: 0, duration: 1, ease: 'none'}, 0);

    // Waypoints pulse only as the revealed water reaches their part of the story.
    waypoints.forEach((drop, index) => {
      journey.fromTo(
        drop,
        {opacity: .14, scale: .7, transformOrigin: 'center'},
        {opacity: .72, scale: 1.4, duration: .06, repeat: 1, yoyo: true},
        .2 + index * .25
      );
    });

    const roots = root.querySelector('[data-rb-roots]');
    if (roots) {
      gsap.fromTo(roots, {y: -8}, {y: 8, ease: 'none', scrollTrigger: {
        trigger: roots, start: 'top bottom', end: 'bottom top', scrub: 1
      }});
    }

    // Fine-pointer interaction: snap a soft ripple to the nearest visible point
    // on the stream. The listener exits immediately when the pointer is far away.
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    let pointerFrame = 0;
    let pendingPointer = null;

    const hideCursor = () => {
      svg.classList.remove('is-cursor-near');
      cursorRipple?.classList.remove('is-active');
    };

    const nearestRoutePoint = (clientX, clientY) => {
      const svgRect = svg.getBoundingClientRect();
      if (
        clientX < svgRect.left - 40 ||
        clientX > svgRect.right + 110 ||
        clientY < svgRect.top ||
        clientY > svgRect.bottom
      ) return null;

      const ctm = route.getScreenCTM();
      if (!ctm) return null;

      const routeLength = route.getTotalLength();
      let nearest = null;
      let nearestDistance = Infinity;
      const samples = 72;

      for (let i = 0; i <= samples; i += 1) {
        const point = route.getPointAtLength(routeLength * i / samples);
        const screenPoint = new DOMPoint(point.x, point.y).matrixTransform(ctm);
        const dx = screenPoint.x - clientX;
        const dy = screenPoint.y - clientY;
        const distance = Math.hypot(dx, dy);
        if (distance < nearestDistance) {
          nearestDistance = distance;
          nearest = point;
        }
      }

      return nearestDistance <= 86 ? nearest : null;
    };

    const renderPointer = () => {
      pointerFrame = 0;
      if (!pendingPointer || !finePointer.matches || !cursorRipple) {
        hideCursor();
        return;
      }

      const nearest = nearestRoutePoint(pendingPointer.x, pendingPointer.y);
      if (!nearest) {
        hideCursor();
        return;
      }

      cursorRipple.setAttribute('cx', nearest.x.toFixed(2));
      cursorRipple.setAttribute('cy', nearest.y.toFixed(2));
      svg.classList.add('is-cursor-near');
      cursorRipple.classList.add('is-active');
    };

    const onPointerMove = event => {
      if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
      pendingPointer = {x: event.clientX, y: event.clientY};
      if (!pointerFrame) pointerFrame = requestAnimationFrame(renderPointer);
    };

    const onPointerLeave = () => {
      pendingPointer = null;
      if (pointerFrame) cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      hideCursor();
    };

    root.addEventListener('pointermove', onPointerMove, {passive: true});
    root.addEventListener('pointerleave', onPointerLeave, {passive: true});

    return () => {
      root.removeEventListener('pointermove', onPointerMove);
      root.removeEventListener('pointerleave', onPointerLeave);
      if (pointerFrame) cancelAnimationFrame(pointerFrame);
      hideCursor();
      reveal.style.removeProperty('stroke-dasharray');
      reveal.style.removeProperty('stroke-dashoffset');
    };
  });

  mm.add('(prefers-reduced-motion: reduce)', () => {
    gsap.set(reveal, {strokeDasharray: 'none', strokeDashoffset: 0});
    svg.classList.remove('is-cursor-near');
    cursorRipple?.classList.remove('is-active');
  });

  // CMS visibility/order, late media and resize can change the journey height.
  let pending;
  const refresh = () => {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => ScrollTrigger.refresh());
  };
  const observer = 'ResizeObserver' in window ? new ResizeObserver(refresh) : null;
  if (observer) observer.observe(root);
  else window.addEventListener('resize', refresh, {passive: true});

  window.addEventListener('pagehide', event => {
    if (event.persisted) return; // Keep the animation context for back/forward cache.
    if (observer) observer.disconnect();
    else window.removeEventListener('resize', refresh);
    cancelAnimationFrame(pending);
    mm.revert();
  });
})();
