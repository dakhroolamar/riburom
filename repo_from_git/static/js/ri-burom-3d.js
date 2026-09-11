/**
 * RI BUROM 3D Rendering Layer
 * Three.js-powered 3D backgrounds and interactive elements
 * Designed for performance, accessibility, and graceful degradation
 */
(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isLowEndDevice = navigator.hardwareConcurrency && navigator.hardwareConcurrency < 4;
  const THREE_URL = '/static/js/three.module.js';

  let THREE = null;
  let scenes = new Map();
  let animationId = null;

  async function loadThreeJS() {
    if (window.THREE) {
      THREE = window.THREE;
      return THREE;
    }
    if (THREE) {
      return THREE;
    }
    try {
      const module = await import(THREE_URL);
      THREE = module;
      window.THREE = module;
      return THREE;
    } catch (e) {
      console.warn('[RI BUROM 3D] Failed to load Three.js module:', e);
      throw e;
    }
  }

  function createParticleGeometry(count, radius, positions) {
    const geometry = new THREE.BufferGeometry();
    const positionArray = new Float32Array(count * 3);
    const colorArray = new Float32Array(count * 3);
    const sizeArray = new Float32Array(count);
    const velocityArray = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = radius * (0.5 + Math.random() * 0.5);

      positionArray[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positionArray[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positionArray[i * 3 + 2] = r * Math.cos(phi);

      const color = new THREE.Color();
      color.setHSL(0.3 + Math.random() * 0.1, 0.6, 0.4 + Math.random() * 0.2);
      colorArray[i * 3] = color.r;
      colorArray[i * 3 + 1] = color.g;
      colorArray[i * 3 + 2] = color.b;

      sizeArray[i] = 1.5 + Math.random() * 3;
      velocityArray[i * 3] = (Math.random() - 0.5) * 0.002;
      velocityArray[i * 3 + 1] = (Math.random() - 0.5) * 0.002;
      velocityArray[i * 3 + 2] = (Math.random() - 0.5) * 0.002;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positionArray, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizeArray, 1));
    geometry.setAttribute('velocity', new THREE.BufferAttribute(velocityArray, 3));
    return geometry;
  }

  function createParticleMaterial() {
    return new THREE.PointsMaterial({
      size: 2.5,
      vertexColors: true,
      transparent: true,
      opacity: 0.7,
      sizeAttenuation: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
  }

  class Hero3DScene {
    constructor(container, options = {}) {
      this.container = container;
      this.options = Object.assign({
        particleCount: prefersReducedMotion || isLowEndDevice ? 500 : 2000,
        sphereRadius: 80,
        rotationSpeed: 0.0003,
        interactionStrength: 0.5,
        colors: ['#14532d', '#166534', '#f3c969', '#d97706']
      }, options);

      this.scene = null;
      this.camera = null;
      this.renderer = null;
      this.particles = null;
      this.mouse = { x: 0, y: 0 };
      this.targetRotation = { x: 0, y: 0 };
      this.currentRotation = { x: 0, y: 0 };
      this.time = 0;
      this.isInitialized = false;
    }

    async init() {
      if (this.isInitialized) return;
      try {
        await loadThreeJS();
        this.setupScene();
        this.setupRenderer();
        this.createParticles();
        this.setupEvents();
        this.animate();
        this.isInitialized = true;
        scenes.set(this.container, this);
      } catch (e) {
        console.warn('[RI BUROM 3D] Failed to initialize:', e);
        this.fallback();
      }
    }

    setupScene() {
      const rect = this.container.getBoundingClientRect();
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(45, rect.width / rect.height, 0.1, 1000);
      this.camera.position.z = this.options.sphereRadius * 2.5;
    }

    setupRenderer() {
      const rect = this.container.getBoundingClientRect();
      this.renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: !isLowEndDevice,
        powerPreference: 'high-performance'
      });
      this.renderer.setSize(rect.width, rect.height);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.setClearColor(0x000000, 0);
      this.container.appendChild(this.renderer.domElement);
      this.renderer.domElement.style.position = 'absolute';
      this.renderer.domElement.style.inset = '0';
      this.renderer.domElement.style.zIndex = '0';
      this.renderer.domElement.style.pointerEvents = 'none';
    }

    createParticles() {
      const geometry = createParticleGeometry(
        this.options.particleCount,
        this.options.sphereRadius
      );
      const material = createParticleMaterial();
      this.particles = new THREE.Points(geometry, material);
      this.scene.add(this.particles);

      const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
      this.scene.add(ambientLight);

      const directionalLight = new THREE.DirectionalLight(0xf3c969, 0.4);
      directionalLight.position.set(100, 100, 100);
      this.scene.add(directionalLight);
    }

    setupEvents() {
      const handleMove = (e) => {
        const rect = this.container.getBoundingClientRect();
        this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        this.targetRotation.y = this.mouse.x * this.options.interactionStrength * 0.3;
        this.targetRotation.x = this.mouse.y * this.options.interactionStrength * 0.2;
      };

      this.container.addEventListener('mousemove', handleMove);
      this.container.addEventListener('touchmove', (e) => {
        if (e.touches[0]) handleMove(e.touches[0]);
      }, { passive: true });

      window.addEventListener('resize', () => this.onResize());
    }

    onResize() {
      const rect = this.container.getBoundingClientRect();
      this.camera.aspect = rect.width / rect.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(rect.width, rect.height);
    }

    animate() {
      this.animationId = requestAnimationFrame(() => this.animate());
      this.time += 0.01;

      this.currentRotation.x += (this.targetRotation.x - this.currentRotation.x) * 0.05;
      this.currentRotation.y += (this.targetRotation.y - this.currentRotation.y) * 0.05;

      if (this.particles) {
        this.particles.rotation.y += this.options.rotationSpeed;
        this.particles.rotation.x += this.options.rotationSpeed * 0.5;

        const positions = this.particles.geometry.attributes.position.array;
        const velocities = this.particles.geometry.attributes.velocity.array;
        for (let i = 0; i < positions.length; i += 3) {
          positions[i] += velocities[i];
          positions[i + 1] += velocities[i + 1];
          positions[i + 2] += velocities[i + 2];

          const dist = Math.sqrt(positions[i] ** 2 + positions[i + 1] ** 2 + positions[i + 2] ** 2);
          if (dist > this.options.sphereRadius * 1.2) {
            const scale = this.options.sphereRadius / dist;
            positions[i] *= scale;
            positions[i + 1] *= scale;
            positions[i + 2] *= scale;
          }
        }
        this.particles.geometry.attributes.position.needsUpdate = true;
      }

      this.camera.position.x += (this.currentRotation.y * 20 - this.camera.position.x) * 0.02;
      this.camera.position.y += (this.currentRotation.x * 20 - this.camera.position.y) * 0.02;
      this.camera.lookAt(0, 0, 0);

      this.renderer.render(this.scene, this.camera);
    }

    fallback() {
      this.container.classList.add('rb-3d-fallback');
    }

    dispose() {
      if (this.animationId) cancelAnimationFrame(this.animationId);
      if (this.renderer) {
        this.renderer.dispose();
        if (this.renderer.domElement.parentNode) {
          this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
        }
      }
      if (this.particles) {
        this.particles.geometry.dispose();
        this.particles.material.dispose();
      }
      scenes.delete(this.container);
      this.isInitialized = false;
    }
  }

  class Card3DScene {
    constructor(cardElement, imageUrl) {
      this.card = cardElement;
      this.imageUrl = imageUrl;
      this.scene = null;
      this.camera = null;
      this.renderer = null;
      this.mesh = null;
      this.isHovered = false;
      this.targetRotation = { x: 0, y: 0 };
      this.currentRotation = { x: 0, y: 0 };
      this.isInitialized = false;
    }

    async init() {
      if (this.isInitialized || prefersReducedMotion) return;
      try {
        await loadThreeJS();
        this.setupScene();
        this.setupRenderer();
        await this.createCardMesh();
        this.setupEvents();
        this.animate();
        this.isInitialized = true;
        scenes.set(this.card, this);
      } catch (e) {
        console.warn('[RI BUROM 3D Card] Failed to initialize:', e);
      }
    }

    setupScene() {
      const rect = this.card.getBoundingClientRect();
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(50, rect.width / rect.height, 0.1, 100);
      this.camera.position.z = 3;
    }

    setupRenderer() {
      const rect = this.card.getBoundingClientRect();
      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      this.renderer.setSize(rect.width, rect.height);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.setClearColor(0x000000, 0);
      this.renderer.domElement.style.position = 'absolute';
      this.renderer.domElement.style.inset = '0';
      this.renderer.domElement.style.zIndex = '0';
      this.renderer.domElement.style.pointerEvents = 'none';
      this.renderer.domElement.classList.add('rb-card-3d-canvas');
      this.card.style.position = 'relative';
      this.card.insertBefore(this.renderer.domElement, this.card.firstChild);
    }

    createCardMesh() {
      return new Promise((resolve) => {
        const loader = new THREE.TextureLoader();
        loader.load(this.imageUrl, (texture) => {
          texture.wrapS = THREE.ClampToEdgeWrapping;
          texture.wrapT = THREE.ClampToEdgeWrapping;
          texture.minFilter = THREE.LinearFilter;

          const geometry = new THREE.PlaneGeometry(2.5, 1.6, 32, 20);
          const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false
          });

          this.mesh = new THREE.Mesh(geometry, material);
          this.scene.add(this.mesh);

          const ambientLight = new THREE.AmbientLight(0xffffff, 1);
          this.scene.add(ambientLight);
          resolve();
        }, undefined, () => resolve());
      });
    }

    setupEvents() {
      this.card.addEventListener('mouseenter', () => { this.isHovered = true; });
      this.card.addEventListener('mouseleave', () => {
        this.isHovered = false;
        this.targetRotation = { x: 0, y: 0 };
      });
      this.card.addEventListener('mousemove', (e) => {
        if (!this.isHovered) return;
        const rect = this.card.getBoundingClientRect();
        this.targetRotation.y = ((e.clientX - rect.left) / rect.width - 0.5) * 0.4;
        this.targetRotation.x = (0.5 - (e.clientY - rect.top) / rect.height) * 0.3;
      });

      window.addEventListener('resize', () => this.onResize());
    }

    onResize() {
      const rect = this.card.getBoundingClientRect();
      this.camera.aspect = rect.width / rect.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(rect.width, rect.height);
    }

    animate() {
      this.animationId = requestAnimationFrame(() => this.animate());

      this.currentRotation.x += (this.targetRotation.x - this.currentRotation.x) * 0.1;
      this.currentRotation.y += (this.targetRotation.y - this.currentRotation.y) * 0.1;

      if (this.mesh) {
        this.mesh.rotation.x = this.currentRotation.x;
        this.mesh.rotation.y = this.currentRotation.y;

        if (!this.isHovered) {
          this.mesh.rotation.z = Math.sin(Date.now() * 0.0005) * 0.02;
        }
      }

      this.renderer.render(this.scene, this.camera);
    }

    dispose() {
      if (this.animationId) cancelAnimationFrame(this.animationId);
      if (this.renderer) {
        this.renderer.dispose();
        if (this.renderer.domElement.parentNode) {
          this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
        }
      }
      if (this.mesh) {
        this.mesh.geometry.dispose();
        if (this.mesh.material.map) this.mesh.material.map.dispose();
        this.mesh.material.dispose();
      }
      scenes.delete(this.card);
      this.isInitialized = false;
    }
  }

  function initHero3D() {
    const hero = document.getElementById('rb-home-hero');
    if (!hero || hero.querySelector('[data-rb-3d-hero]')) return;

    const canvasContainer = document.createElement('div');
    canvasContainer.dataset.rb3dHero = 'true';
    canvasContainer.style.position = 'absolute';
    canvasContainer.style.inset = '0';
    canvasContainer.style.zIndex = '1';
    canvasContainer.style.pointerEvents = 'none';
    hero.insertBefore(canvasContainer, hero.firstChild);

    const scene = new Hero3DScene(canvasContainer);
    scene.init();
  }

  function initCard3D() {
    const cards = document.querySelectorAll('.rb-card[data-3d-enabled]');
    cards.forEach((card) => {
      const imageUrl = card.dataset.imageUrl;
      if (!imageUrl) return;

      const existing = card.querySelector('.rb-card-3d-canvas');
      if (existing) return;

      const scene = new Card3DScene(card, imageUrl);
      scene.init();
    });
  }

  function initAll3D() {
    if (prefersReducedMotion) {
      document.documentElement.classList.add('rb-3d-reduced');
      return;
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        initHero3D();
        initCard3D();
      });
    } else {
      initHero3D();
      initCard3D();
    }
  }

  // Initialize immediately if document is already loaded, otherwise wait for DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll3D);
  } else {
    initAll3D();
  }
  window.RiBurom3D = { Hero3DScene, Card3DScene, initHero3D, initCard3D, initAll3D, scenes };

  /* ===== Horizontal Scroll Carousel (White Desert Style) ===== */
  function initToursCarousel() {
    const carousels = document.querySelectorAll('.rb-tours-carousel');
    carousels.forEach((carousel) => {
      const track = carousel.querySelector('.rb-tours-track');
      const prevBtn = carousel.querySelector('.rb-tours-carousel-prev');
      const nextBtn = carousel.querySelector('.rb-tours-carousel-next');

      if (!track) return;

      let isDragging = false;
      let startX = 0;
      let scrollLeft = 0;

      function updateNavButtons() {
        if (!prevBtn || !nextBtn) return;
        const maxScroll = track.scrollWidth - track.clientWidth;
        prevBtn.style.opacity = track.scrollLeft <= 10 ? '0.4' : '1';
        prevBtn.style.pointerEvents = track.scrollLeft <= 10 ? 'none' : 'auto';
        nextBtn.style.opacity = track.scrollLeft >= maxScroll - 10 ? '0.4' : '1';
        nextBtn.style.pointerEvents = track.scrollLeft >= maxScroll - 10 ? 'none' : 'auto';
      }

      function scrollByCard(direction) {
        const card = track.querySelector('.rb-tour-carousel-card');
        if (!card) return;
        const cardWidth = card.offsetWidth + 24; // card + gap
        track.scrollBy({ left: direction * cardWidth, behavior: 'smooth' });
      }

      if (prevBtn) prevBtn.addEventListener('click', () => scrollByCard(-1));
      if (nextBtn) nextBtn.addEventListener('click', () => scrollByCard(1));

      track.addEventListener('scroll', updateNavButtons, { passive: true });
      track.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.pageX - track.offsetLeft;
        scrollLeft = track.scrollLeft;
        track.style.cursor = 'grabbing';
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX) * 1.5;
        track.scrollLeft = scrollLeft - walk;
      });

      window.addEventListener('mouseup', () => {
        isDragging = false;
        track.style.cursor = 'grab';
      });

      track.addEventListener('touchstart', (e) => {
        isDragging = true;
        startX = e.touches[0].pageX - track.offsetLeft;
        scrollLeft = track.scrollLeft;
      }, { passive: true });

      track.addEventListener('touchmove', (e) => {
        if (!isDragging) return;
        const x = e.touches[0].pageX - track.offsetLeft;
        const walk = (x - startX) * 1.5;
        track.scrollLeft = scrollLeft - walk;
      }, { passive: true });

      track.addEventListener('touchend', () => { isDragging = false; });

      updateNavButtons();
      window.addEventListener('resize', updateNavButtons);

      // Keyboard navigation
      track.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') { e.preventDefault(); scrollByCard(-1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); scrollByCard(1); }
      });

      // Scroll hint animation - hide after first scroll
      let hintHidden = false;
      track.addEventListener('scroll', () => {
        if (!hintHidden && track.scrollLeft > 50) {
          const hint = carousel.querySelector('.rb-tours-scroll-hint');
          if (hint) {
            hint.style.opacity = '0';
            hint.style.pointerEvents = 'none';
            hintHidden = true;
          }
        }
      });
    });
  }

  /* ===== How It Works Modal ===== */
  function initHowItWorksModal() {
    const triggers = document.querySelectorAll('.rb-how-it-works-trigger');
    const modal = document.getElementById('rb-how-it-works-modal');
    if (!modal || triggers.length === 0) return;

    const closeBtn = modal.querySelector('.rb-how-it-works-close');
    const panel = modal.querySelector('.rb-how-it-works-panel');

    function openModal() {
      modal.classList.add('is-open');
      document.body.style.overflow = 'hidden';
      panel.focus();
      trapFocus(panel);
    }

    function closeModal() {
      modal.classList.remove('is-open');
      document.body.style.overflow = '';
    }

    function trapFocus(element) {
      const focusable = element.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      element.addEventListener('keydown', function handler(e) {
        if (e.key !== 'Tab') return;
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      });
    }

    triggers.forEach((trigger) => {
      trigger.addEventListener('click', (e) => {
        e.preventDefault();
        openModal();
      });
    });

    closeBtn?.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('is-open')) {
        closeModal();
      }
    });
  }

  /* ===== Initialize All New Components ===== */
  function initNewComponents() {
    initToursCarousel();
    initHowItWorksModal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNewComponents);
  } else {
    initNewComponents();
  }

  window.RiBurom3D = { Hero3DScene, Card3DScene, initHero3D, initCard3D, initAll3D, scenes, initToursCarousel, initHowItWorksModal };
})();