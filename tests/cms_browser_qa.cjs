const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const BASE = process.env.CMS_QA_BASE_URL || 'http://127.0.0.1:5055';
const OUT = process.env.CMS_QA_OUTPUT || '/tmp/riburom-cms-qa';
fs.mkdirSync(OUT, {recursive:true});
const river = '[data-rb-river-gallery]';
async function noOverflow(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'Horizontal overflow');
}
async function imageReady(page, selector) {
  await page.waitForFunction(sel => [...document.querySelectorAll(sel)].every(i => i.complete && i.naturalWidth > 0), selector);
}
async function changed(page, start, timeout=8500) {
  await page.waitForFunction(start => document.querySelector('[data-rb-river-gallery]').dataset.galleryIndex !== start, start, {timeout});
  await page.waitForTimeout(500);
  assert.equal(await page.locator(river+' figure.is-current').evaluate(el=>getComputedStyle(el).opacity),'1','The selected photograph must actually be visible');
  const hidden=await page.locator(river+' figure:not(.is-current)').evaluateAll(items=>items.every(el=>getComputedStyle(el).opacity==='0'));
  assert.ok(hidden,'Other photographs must not overlap the selected photograph');
}
async function visibleGallery(page) {
  await page.locator(river).evaluate(el=>el.scrollIntoView({block:'center',behavior:'instant'}));
  await page.waitForFunction(selector=>{
    const box=document.querySelector(selector).getBoundingClientRect();
    return (Math.min(box.bottom,innerHeight)-Math.max(box.top,0))/box.height>=.2;
  },river);
}
async function captureRealPhotoEvidence(page) {
  const source = 'https://riburomtours.com/api/public-section-backgrounds';
  const capturedProductionFallback = [
    {src:'https://res.cloudinary.com/gpxpatvk/image/upload/f_auto,q_auto,w_1200,c_limit/v1789490948/riburom/cq6nxuy3izhsk8zwhuzz.png', focal_x:50, focal_y:50},
    {src:'https://res.cloudinary.com/gpxpatvk/image/upload/f_auto,q_auto,w_1200,c_limit/v1789674265/riburom/piyz6gmoinvywqaeaq9q.jpg', focal_x:44, focal_y:49},
    {src:'https://res.cloudinary.com/gpxpatvk/image/upload/f_auto,q_auto,w_1200,c_limit/v1789625689/riburom/l7itacgglomuk98r6ayg.png', focal_x:50, focal_y:50},
    {src:'https://res.cloudinary.com/gpxpatvk/image/upload/f_auto,q_auto,w_1200,c_limit/v1789578684/riburom/fjca4qv7ue8wcnzpizag.jpg', focal_x:46, focal_y:68}
  ];
  try {
    let photos = [];
    let sourceMode = 'live-production-api';
    let sourceWarning = null;
    try {
      const response = await fetch(source, {headers:{'user-agent':'RI-BUROM-CMS-QA/1.0'}});
      if (!response.ok) throw new Error(`production media API returned ${response.status}`);
      const payload = await response.json();
      const raw = payload?.media_details?.home_gallery;
      photos = (Array.isArray(raw) ? raw : []).map(item => ({
        src: item?.src ? new URL(item.src, 'https://riburomtours.com').href : '',
        focal_x: Number.isFinite(Number(item?.focal_x)) ? Number(item.focal_x) : 50,
        focal_y: Number.isFinite(Number(item?.focal_y)) ? Number(item.focal_y) : 50
      })).filter(item => item.src).slice(0, 4);
      if (photos.length < 4) throw new Error(`expected four production gallery photos, found ${photos.length}`);
    } catch (error) {
      photos = capturedProductionFallback;
      sourceMode = 'captured-production-fallback';
      sourceWarning = error.message;
    }
    fs.writeFileSync(OUT+'/real-photo-evidence.json', JSON.stringify({
      source,
      source_mode:sourceMode,
      source_warning:sourceWarning,
      fallback_capture_date:'2026-09-18',
      photos
    }, null, 2));

    for (const viewport of [
      {label:'desktop', width:1440, height:1000},
      {label:'mobile-390', width:390, height:844}
    ]) {
      await page.setViewportSize({width:viewport.width, height:viewport.height});
      await page.goto(BASE+'/', {waitUntil:'networkidle'});
      await page.locator(river+'[data-gallery-ready="true"]').waitFor();
      await page.locator(river).scrollIntoViewIfNeeded();
      const pause = page.locator(river+' [data-gallery-pause]');
      if (await pause.isVisible()) {
        const pressed = await pause.getAttribute('aria-pressed');
        if (pressed !== 'true') await pause.click();
      }
      for (let index=0; index<photos.length; index++) {
        const photo = photos[index];
        await page.locator(river+' figure img').first().evaluate((img, value) => {
          img.removeAttribute('data-src');
          img.src = value.src;
          img.alt = 'Real production gallery photograph';
          img.style.objectPosition = value.focal_x+'% '+value.focal_y+'%';
        }, photo);
        await page.waitForFunction(sel => {
          const img = document.querySelector(sel);
          return !!img && img.complete && img.naturalWidth > 0;
        }, river+' figure img');
        await page.waitForTimeout(150);
        await page.locator(river).screenshot({path:OUT+`/final-real-photo-${viewport.label}-${index+1}.png`});
        if (index === 0) {
          await page.screenshot({path:OUT+`/final-real-photo-${viewport.label}.png`, fullPage:true});
        }
      }
    }
  } catch (error) {
    fs.writeFileSync(OUT+'/real-photo-evidence.txt', 'Real-photo evidence unavailable: '+error.message+'\n');
    console.warn('Real-photo evidence unavailable:', error.message);
  }
}

(async () => {
 const browser = await chromium.launch({headless:true});
 try {
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage(); const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {if(m.type()==='error') errors.push(m.text());});
  await page.goto(BASE+'/__visual/cms');
  await page.locator('[data-panel="content"]').click();
  await page.locator('#content-fields textarea').first().waitFor();
  await noOverflow(page);
  await page.screenshot({path:OUT+'/cms-main-desktop.png',fullPage:true});
  await page.locator('[data-section="home_gallery"]').click();
  await page.locator('#image-preview img').waitFor();
  assert.equal(await page.locator('#collection-items button').count(),3);
  await imageReady(page,'#image-preview img');
  await page.screenshot({path:OUT+'/cms-gallery-desktop.png',fullPage:true});
  await page.getByLabel('Caption (optional)',{exact:true}).fill('Meghalaya gallery QA');
  await page.getByRole('button',{name:'Later →',exact:true}).click();
  assert.match(await page.locator('#gallery-summary').textContent(),/Unsaved/);
  const saved=page.waitForResponse(r=>r.url().endsWith('/collections/home_gallery')&&r.request().method()==='POST');
  await page.locator('#save-collection').click(); assert.equal((await saved).status(),200);
  await page.getByText('Gallery and image details saved.',{exact:true}).waitFor();
  await page.reload(); await page.locator('[data-section="home_gallery"]').click();
  await page.locator('#image-preview img').waitFor();
  await page.locator('#choose-library').click();
  await page.locator('#picker-results .media-card').first().waitFor();
  await page.screenshot({path:OUT+'/cms-media-picker.png',fullPage:true});
  await page.locator('#picker-close').click();
  await page.locator('[data-panel="appearance"]').click();
  await page.locator('#gallery-design:not([hidden])').waitFor();
  await page.locator('#gallery-interval').selectOption('7000');
  await page.locator('#gallery-design button').click();
  await page.getByText('Gallery design saved.',{exact:true}).waitFor();
  await page.locator('#gallery-interval').selectOption('6000');
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/gallery-design/home_gallery')&&r.request().method()==='POST'), page.locator('#gallery-design button').click()]);

  await page.locator('[data-section="home_about_gallery"]').click();
  await page.locator('[data-panel="appearance"]').click();
  await page.locator('#design-fields input').first().waitFor();
  await page.locator('#design-fields input').first().fill('#ffffff');
  await page.locator('#section-design button').click();
  await page.getByText('Section design saved.',{exact:true}).waitFor();
  await page.screenshot({path:OUT+'/cms-design-desktop.png',fullPage:true});
  await page.goto(BASE+'/workspace/library');
  await page.locator('#library-results .media-card').first().waitFor();
  await noOverflow(page); await page.screenshot({path:OUT+'/cms-library-desktop.png',fullPage:true});
  await page.goto(BASE+'/');
  for (const state of ['', 'rb-hero-video-playing', 'rb-hero-video-complete', 'rb-hero-video-fallback']) {
    await page.locator('#rb-home-hero').evaluate((hero,state) => {
      hero.classList.remove('rb-hero-video-playing','rb-hero-video-complete','rb-hero-video-fallback');
      hero.classList.add('rb-hero-video-enabled');if(state)hero.classList.add(state);
    },state);
    assert.ok(await page.locator('#rb-home-hero h1').isVisible(),'Opening film never hides the hero title');
    assert.equal(await page.locator('#rb-home-hero h1').evaluate(el=>getComputedStyle(el).opacity),'1','Hero title is immediately opaque in every film state');
    const heroCopy = await page.locator('.rb-hero-content').evaluate(el => ({opacity:getComputedStyle(el).opacity,pointerEvents:getComputedStyle(el).pointerEvents}));
    assert.equal(heroCopy.opacity,'1','Opening film leaves hero content visible');
    assert.equal(heroCopy.pointerEvents,'auto','Opening film leaves journey actions interactive');
    assert.ok(await page.locator('.rb-hero-actions a').first().isVisible(),'Journey action remains visible during playback');
  }
  await page.locator('#rb-home-hero').evaluate(hero => hero.classList.remove('rb-hero-video-enabled','rb-hero-video-playing','rb-hero-video-complete','rb-hero-video-fallback'));
  assert.equal(await page.locator('.cms-hero-gallery').count(),0,'Fixture must match production with no optional Hero collection');
  await page.locator(river+'[data-gallery-ready="true"]').waitFor();
  await visibleGallery(page);
  await imageReady(page,river+' img'); await noOverflow(page);
  const bounds=await page.locator(river).boundingBox();
  const host=await page.locator('[data-rb-river-gallery-host]').evaluate(el=>{
    const box=el.getBoundingClientRect(),style=getComputedStyle(el);
    const left=parseFloat(style.paddingLeft)+parseFloat(style.borderLeftWidth);
    const right=parseFloat(style.paddingRight)+parseFloat(style.borderRightWidth);
    return {x:box.x+left,width:box.width-left-right};
  });
  assert.ok(host && bounds.width>=host.width-2 && bounds.width<=host.width+2,'Desktop gallery fills its editorial media column');
  assert.ok(bounds.x>=host.x-2 && bounds.x+bounds.width<=host.x+host.width+2,'Desktop gallery stays within its media column');
  assert.ok(bounds.x>=-2 && bounds.x+bounds.width<=1442,'Desktop gallery stays within the viewport without overflow');
  const start=await page.locator(river).getAttribute('data-gallery-index');
  await page.locator(river).hover();
  await page.waitForTimeout(6500);
  assert.equal(await page.locator(river).getAttribute('data-gallery-index'),start,'Hover pauses autoplay');
  await page.mouse.move(0,0);
  await page.screenshot({path:OUT+'/gallery-before-autoplay.png'});
  await changed(page,start);
  await page.screenshot({path:OUT+'/gallery-after-autoplay.png'});
  const auto=await page.locator(river).getAttribute('data-gallery-index');
  await page.locator(river+' [data-gallery-next]').click(); await changed(page,auto,2000);
  const manual=await page.locator(river).getAttribute('data-gallery-index');
  await page.waitForTimeout(6500);
  assert.equal(await page.locator(river).getAttribute('data-gallery-index'),manual,'Manual input must pause autoplay');
  await visibleGallery(page);
  await page.mouse.move(0,0);
  await changed(page,manual,7500);
  await page.locator(river+' [data-gallery-pause]').click();
  await page.mouse.move(0,0);
  const paused=await page.locator(river).getAttribute('data-gallery-index');
  await page.waitForTimeout(6500);
  assert.equal(await page.locator(river).getAttribute('data-gallery-index'),paused,'Explicit pause');
  await page.locator(river+' [data-gallery-pause]').click();
  await visibleGallery(page);
  await page.mouse.move(0,0); await changed(page,paused);
  await page.locator('#rb-home-contact').scrollIntoViewIfNeeded();
  const off=await page.locator(river).getAttribute('data-gallery-index'); await page.waitForTimeout(6500);
  assert.equal(await page.locator(river).getAttribute('data-gallery-index'),off,'Offscreen pause');
  await page.emulateMedia({reducedMotion:'reduce'}); await page.locator(river).scrollIntoViewIfNeeded();
  await page.waitForTimeout(6500); assert.equal(await page.locator(river).getAttribute('data-gallery-index'),off,'Reduced motion');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:390,height:844});
  await page.goto(BASE+'/workspace/pages/home#home_gallery'); await page.locator('#image-preview img').waitFor();
  await noOverflow(page); await page.screenshot({path:OUT+'/cms-mobile-390.png',fullPage:true});
  await page.goto(BASE+'/'); await page.locator(river+'[data-gallery-ready="true"]').waitFor();
  await page.locator(river).scrollIntoViewIfNeeded(); await noOverflow(page);
  const size=await page.locator(river+' figure').first().boundingBox();
  assert.ok(Math.abs(size.width/size.height-(4/3/0.7))<0.02,`Mobile gallery uses the configured reduced height: ${size.width} × ${size.height}`);
  await page.screenshot({path:OUT+'/gallery-mobile-390.png'});
  await page.locator(river+' .cms-gallery-track').focus();
  const beforeKey=await page.locator(river).getAttribute('data-gallery-index');
  await page.keyboard.press('ArrowRight'); await changed(page,beforeKey,2000);
  const beforePrevious=await page.locator(river).getAttribute('data-gallery-index');
  await page.locator(river+' [data-gallery-prev]').click(); await changed(page,beforePrevious,2000);
  const beforeNext=await page.locator(river).getAttribute('data-gallery-index');
  await page.locator(river+' [data-gallery-next]').click(); await changed(page,beforeNext,2000);
  assert.deepEqual(errors,[]);
  await captureRealPhotoEvidence(page);
  console.log('PASS: CMS content/media/design, saved ordering and metadata, picker, library, desktop/390px; production river autoplay, hover, manual resume, explicit pause, offscreen, reduced motion and keyboard.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
