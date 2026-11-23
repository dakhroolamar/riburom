// Read-only Render vs password-protected Cloudflare browser comparison.
// Produces screenshots and navigation metrics. Does not submit forms.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const folder = process.env.RUNNER_TEMP
  ? path.join(process.env.RUNNER_TEMP, 'riburom-browser-qa')
  : '/tmp/riburom-browser-qa';
fs.mkdirSync(folder, {recursive:true});
const stagingPassword = process.env.STAGING_ACCESS_PASSWORD;
if (!stagingPassword || stagingPassword.length < 16) {
  throw new Error('Staging access password is missing or too short');
}
const targets = [
  {key:'render', host:'https://riburomtours.com', protected:false},
  {key:'cloudflare', host:'https://riburom-application-staging.dakhroo.workers.dev', protected:true},
];
const routes = ['/', '/all_tours', '/about', '/marketplace', '/stories'];
const profiles = [
  {key:'desktop',width:1440,height:900,deviceScaleFactor:1,isMobile:false},
  {key:'mobile',width:390,height:844,deviceScaleFactor:1,isMobile:true,hasTouch:true},
];
const expectedTours = ['Adventure', 'TRUE COLOURS OF THE JAINTIA', 'Family Tour Plan', '7 Nights 8 Days'];

(async () => {
  const browser = await chromium.launch({headless:true});
  const observations=[];
  try {
    for (const device of profiles) {
      for (const target of targets) {
        const context = await browser.newContext({
          viewport:{width:device.width,height:device.height},
          deviceScaleFactor:device.deviceScaleFactor,
          isMobile:device.isMobile || false,
          hasTouch:device.hasTouch || false,
          ...(target.protected ? {httpCredentials:{username:'rehearsal',password:stagingPassword}} : {}),
        });
        for (const route of routes) {
          const slug = route==='/'?'home':route.slice(1).replace(/[^a-z0-9-]/g,'-');
          const page=await context.newPage();
          const failures=[];
          page.on('pageerror', error => failures.push(String(error.name||'PageError').slice(0,40)));
          await page.addInitScript(() => {
            window.__riburomQA = {lcp:0,cls:0};
            try {
              new PerformanceObserver(list => {
                for (const item of list.getEntries()) {
                  window.__riburomQA.lcp = item.startTime;
                  window.__riburomQA.lcpElement = item.element
                    ? {tag:item.element.tagName, className:String(item.element.className||'').slice(0,100)}
                    : null;
                  window.__riburomQA.lcpUrl = item.url ? new URL(item.url).hostname : null;
                }
              }).observe({type:'largest-contentful-paint', buffered:true});
              new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                  if (!entry.hadRecentInput) window.__riburomQA.cls += entry.value;
                }
              }).observe({type:'layout-shift', buffered:true});
            } catch (_) {}
          });
          const started=Date.now();
          const response=await page.goto(target.host+route,{waitUntil:'domcontentloaded',timeout:45000});
          try {await page.waitForLoadState('load',{timeout:10000});} catch (_){}
          await page.waitForTimeout(700);
          const result=await page.evaluate(() => {
            const nav=performance.getEntriesByType('navigation')[0];
            return {
              title:document.title,
              bodyCharacters:document.body?.innerText?.length||0,
              visibleTourHeadings:document.body?.innerText||'',
              lcpMs:Math.round(window.__riburomQA?.lcp||0),
              lcpElement:window.__riburomQA?.lcpElement||null,
              lcpHost:window.__riburomQA?.lcpUrl||null,
              cls:Number((window.__riburomQA?.cls||0).toFixed(4)),
              staticResourceCount:performance.getEntriesByType('resource').filter(e=>e.initiatorType==='img').length,
              slowestImageMs:Math.round(Math.max(0,...performance.getEntriesByType('resource').filter(e=>e.initiatorType==='img').map(e=>e.duration))),
              domContentLoadedMs:nav?Math.round(nav.domContentLoadedEventEnd):null,
              resourceRequests:performance.getEntriesByType('resource').length,
              brokenLoadedImages:[...document.images].filter(img=>img.complete && !img.naturalWidth).length,
              brokenImageSources:[...document.images]
                .filter(img=>img.complete && !img.naturalWidth)
                .slice(0,4)
                .map(img=>{try {const u=new URL(img.currentSrc||img.src); return u.host+u.pathname;} catch(_) {return 'invalid-image-url';}}),
            };
          });
          const screenshot=`${device.key}-${target.key}-${slug}.png`;
          await page.screenshot({path:path.join(folder,screenshot),fullPage:false,animations:'disabled'});
          const observed={
            device:device.key,host:target.key,route,
            httpStatus:response?.status()||0,
            navigationWallMs:Date.now()-started,
            lcpMs:result.lcpMs,lcpElement:result.lcpElement,lcpHost:result.lcpHost,
            slowestImageMs:result.slowestImageMs,staticResourceCount:result.staticResourceCount,
            cls:result.cls,
            domContentLoadedMs:result.domContentLoadedMs,
            bodyCharacters:result.bodyCharacters,resourceRequests:result.resourceRequests,
            brokenLoadedImages:result.brokenLoadedImages,
            brokenImageSources:result.brokenImageSources,
            pageErrorClasses:failures.slice(0,5),screenshot,title:result.title,
          };
          if (route==='/all_tours') {
            const lower=result.visibleTourHeadings.toLowerCase();
            observed.tourMatches=expectedTours.map(name=>lower.includes(name.toLowerCase()));
          }
          observations.push(observed);
          console.log(JSON.stringify({...observed,title:undefined}));
          if (observed.httpStatus!==200||observed.bodyCharacters<40) {
            throw new Error(`Invalid page for ${device.key}/${target.key}${route}: ${observed.httpStatus}`);
          }
          if (observed.tourMatches?.some(x=>!x)) {
            throw new Error(`Published tour missing on ${target.key}`);
          }
          await page.close();
        }
        await context.close();
      }
    }
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(folder,'comparison.json'),JSON.stringify({
      method:'Chromium from GitHub Actions hosted runner; one navigated page per host/route/device',
      limitations:['US runner rather than India','Single navigation not a stable Web Vitals benchmark',
                   'LCP and CLS observational; not field Core Web Vitals','Staging protected by HTTP Basic'],
      observations,
    },null,2));
  }
})().catch(error=>{console.error('Read-only browser QA failed:',String(error.message||error));process.exitCode=1;});
