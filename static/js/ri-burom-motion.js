(function () {
  'use strict';

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Reveal sections as the visitor scrolls.
  const revealItems = document.querySelectorAll('[data-reveal]');
  if (reduceMotion) {
    revealItems.forEach((el) => el.classList.add('is-visible'));
  } else if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealItems.forEach((el) => observer.observe(el));
  } else {
    revealItems.forEach((el) => el.classList.add('is-visible'));
  }

  // Light stagger for card grids without JavaScript libraries.
  document.querySelectorAll('.rb-stagger').forEach((group) => {
    Array.from(group.children).forEach((child, index) => {
      child.style.setProperty('--rb-delay', `${Math.min(index, 6) * 90}ms`);
    });
  });

  // Give the sticky navigation a subtle change after scrolling.
  const nav = document.querySelector('.rb-site-nav');
  if (nav) {
    const syncNav = () => nav.classList.toggle('rb-scrolled', window.scrollY > 16);
    syncNav();
    window.addEventListener('scroll', syncNav, { passive: true });
  }

  // Keep the floating WhatsApp CTA fully visible on narrow screens.
  const whatsappCta = document.querySelector('.rb-floating-cta');
  if (whatsappCta) {
    Object.assign(whatsappCta.style, {
      right: '18px',
      left: 'auto',
      bottom: '18px',
      maxWidth: 'calc(100vw - 36px)',
      whiteSpace: 'normal',
      textAlign: 'center',
      boxSizing: 'border-box',
      zIndex: '1000'
    });
  }

  // Public enquiry confirmation: submit asynchronously so the visitor stays
  // in the same contact area, then show a prominent confirmation modal only
  // when the server's success message is present in the returned page.
  const enquiryForm = document.querySelector('form[action="/send_message"]');
  if (enquiryForm) {
    enquiryForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submitButton = enquiryForm.querySelector('button[type="submit"]');
      const originalLabel = submitButton ? submitButton.textContent : '';
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Sending…';
      }

      try {
        const response = await fetch(enquiryForm.action, {
          method: 'POST',
          body: new FormData(enquiryForm),
          credentials: 'same-origin',
          redirect: 'follow'
        });
        const html = await response.text();
        const success = response.ok && html.includes("Your message has been sent");

        if (success) {
          enquiryForm.reset();
          showEnquiryConfirmation();
        } else {
          // Let the server-rendered flash/error message remain authoritative.
          window.location.href = '/#contact';
        }
      } catch (_) {
        // Fall back to the ordinary form submission if JS/fetch is unavailable.
        enquiryForm.submit();
        return;
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = originalLabel;
        }
      }
    });
  }

  function showEnquiryConfirmation() {
    if (document.getElementById('rb-enquiry-confirmation')) return;

    const overlay = document.createElement('div');
    overlay.id = 'rb-enquiry-confirmation';
    Object.assign(overlay.style, {
      position: 'fixed', inset: '0', background: 'rgba(15,23,42,.70)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '20px', zIndex: '2000'
    });

    const card = document.createElement('div');
    Object.assign(card.style, {
      width: 'min(560px, 100%)', background: '#fff', borderRadius: '20px',
      padding: '30px', boxShadow: '0 25px 70px rgba(0,0,0,.28)',
      textAlign: 'center', color: '#1f2937'
    });

    const icon = document.createElement('div');
    icon.textContent = '✓';
    Object.assign(icon.style, {
      width: '62px', height: '62px', borderRadius: '50%', background: '#166534',
      color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: '34px', fontWeight: '800', margin: '0 auto 18px'
    });

    const title = document.createElement('h2');
    title.textContent = 'Your enquiry has been received';
    Object.assign(title.style, { margin: '0 0 12px', fontSize: '28px', fontWeight: '800', color: '#14532d' });

    const text = document.createElement('p');
    text.textContent = 'Thank you for contacting RI BUROM. Your message has been recorded successfully. Our representative will review your enquiry and get back to you by phone, WhatsApp, or email.';
    Object.assign(text.style, { margin: '0 auto 22px', lineHeight: '1.65', fontSize: '17px', maxWidth: '480px' });

    const note = document.createElement('p');
    note.textContent = 'You can safely close this message and continue exploring Meghalaya.';
    Object.assign(note.style, { margin: '0 0 22px', color: '#6b7280', fontSize: '14px' });

    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = 'Continue browsing';
    Object.assign(close.style, {
      border: '0', borderRadius: '999px', padding: '12px 22px', background: '#166534',
      color: '#fff', fontWeight: '800', cursor: 'pointer', fontSize: '15px'
    });
    close.addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (event) => { if (event.target === overlay) overlay.remove(); });
    document.addEventListener('keydown', function escHandler(event) {
      if (event.key === 'Escape') {
        overlay.remove();
        document.removeEventListener('keydown', escHandler);
      }
    });

    card.append(icon, title, text, note, close);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    close.focus();
  }

  // Apply CMS-managed section background images after the public theme loads.
  const sectionMap = {
    hero: '#rb-home-hero',
    home_about: '#rb-home-about',
    home_tours: '#rb-home-tours',
    home_why: '#rb-home-why',
    home_blog: '#rb-home-blog',
    home_contact: '#rb-home-contact',
    about_header: 'body > header:not(.rb-site-nav)',
    about_belief: '#about-belief',
    about_pillars: '#about-pillars',
    about_extra1: '#about-extra1',
    about_extra2: '#about-extra2',
    about_team: '#about-team',
    about_logo: '#about-logo',
    about_blog: '#about-blog',
    footer: '.rb-footer'
  };

  const applySectionBackgrounds = async () => {
    try {
      const response = await fetch('/api/public-section-backgrounds', { credentials: 'same-origin' });
      if (!response.ok) return;
      const payload = await response.json();
      const backgrounds = payload.backgrounds || {};
      const styles = payload.styles || {};

      Object.entries(backgrounds).forEach(([key, image]) => {
        const el = document.querySelector(sectionMap[key]);
        if (!el || !image) return;
        const style = styles[key] || {};
        const overlayColor = style.overlay_color || '#000000';
        const opacity = Number(style.overlay_opacity ?? 0) / 100;
        let overlay = overlayColor;
        const match = overlayColor.match(/^#([0-9a-f]{6})$/i);
        if (match) {
          const hex = match[1];
          overlay = `rgba(${parseInt(hex.slice(0, 2), 16)},${parseInt(hex.slice(2, 4), 16)},${parseInt(hex.slice(4, 6), 16)},${opacity})`;
        }
        el.style.backgroundImage = `linear-gradient(${overlay},${overlay}),url("${image}")`;
        el.style.backgroundSize = 'cover';
        el.style.backgroundPosition = 'center';
      });
    } catch (_) {
      // Background customization is optional; never block the public page if it fails.
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applySectionBackgrounds);
  } else {
    applySectionBackgrounds();
  }
})();
