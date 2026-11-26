// Read-only Render vs password-protected Cloudflare browser comparison.
// Produces screenshots and navigation metrics. Does not submit forms.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const folder = process.env.RUNNER_TEMP
  ? path.join(process.env.RUNNER_TEMP, 'riburom-browser-qa')
  : '/tmp/riburom-browser-qa';
fs.mkdirSync(folder, {recursive:true});
const previewPassword = process.env.STAGING_ACCESS_PASSWORD;
if (!previewPassword || previewPassword.length < 16) {
  throw new Error('Preview access password is missing or too short');
}
const previewHosts = new Map([
  ['staging', 'https://riburom-application-staging.dakhroo.workers.dev'],
  ['production-candidate', 'https://riburom-production.dakhroo.workers.dev'],
]);
const previewHost = previewHosts.get(process.env.RIBUROM_BENCHMARK_PROFILE || 'staging');
if (!previewHost) throw new Error('Unsupported benchmark profile');
const targets = [
  {key:'render', host:'https://riburomtours.com', protected:false},
  {key:'cloudflare', host:previewHost, protected:true},
];
const repetitions = 5;
const routes = ['/', '/all_tours', '/about', '/marketplace', '/stories'];
const profiles = [
  {key:'desktop',width:1440,height:900,deviceScaleFactor:1,isMobile:false},
  {key:'mobile',width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true},
];
const expectedTours = ['Adventure', 'TRUE COLOURS OF THE JAINTIA', 'Family Tour Plan', '7 Nights 8 Days'];

(async () => {
  const browser = await chromium.launch({headless:true});
  const observations=[];
  try {
    for (let sample = 1; sample <= repetitions; sample++) {
      for (const device of profiles) {
        for (const target of (sample % 2 ? targets : [...targets].reverse())) {
          const context = await browser.newContext({
            viewport:{width:device.width,height:device.height},
            deviceScaleFactor:device.deviceScaleFactor,
            isMobile:device.isMobile || false,
            hasTouch:device.hasTouch || false,
            ...(target.protected ? {httpCredentials:{origin:target.host,username:'rehearsal',password:previewPassword}} : {}),
          });
          for (const route of (sample === 1 ? routes : ['/'])) {
            const slug = route==='/'?'home':route.slice(1).replace(/[^a-z0-9-]/g,'-');
            const page=await context.newPage();
            const network = await context.newCDPSession(page);
            await network.send('Network.enable');
            if (device.isMobile) {
              await network.send('Network.emulateNetworkConditions', {
                offline:false, latency:80, downloadThroughput:4_000_000/8, uploadThroughput:1_000_000/8,
              });
            }
            let transferredBytes = 0;
            network.on('Network.loadingFinished', event => { transferredBytes += event.encodedDataLength; });
            const failures=[];
            page.on('pageerror', error => failures.push(String(error.name||'PageError').slice(0,40)));
            await page.addInitScript(() => {
              window.__riburomQA = {lcp:0,cls:0,longTasks:[]};
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
              if (PerformanceObserver.supportedEntryTypes.includes('longtask')) {
                new PerformanceObserver(list => {
                  for (const entry of list.getEntries()) {
                    window.__riburomQA.longTasks.push([entry.startTime, entry.duration]);
                  }
                }).observe({type:'longtask', buffered:true});
              }
            });

            const response=await page.goto(target.host+route,{waitUntil:'domcontentloaded',timeout:45000});
            try {await page.waitForLoadState('load',{timeout:10000});} catch (_){}
            await page.waitForTimeout(700);
            const result=await page.evaluate(() => {
              const nav=performance.getEntriesByType('navigation')[0];
              const fcp = performance.getEntriesByName('first-contentful-paint')[0]?.startTime;
              const longTasks = window.__riburomQA.longTasks;
              // This measures blocking through the browser sample, ending 700 ms after the load wait.
              const blocking = fcp && PerformanceObserver.supportedEntryTypes.includes('longtask')
                ? longTasks.reduce((total, [start, duration]) => total + Math.max(0, start + duration - Math.max(fcp, start) - 50), 0)
                : null;
              return {
                title:document.title,
                ttfbMs:nav ? Math.round(nav.responseStart - nav.startTime) : null,
                loadMs:nav ? Math.round(nav.loadEventEnd) : null,
                fcpMs:fcp ? Math.round(fcp) : null,
                observedBlockingMs:blocking === null ? null : Math.round(blocking),
                landscapeWidthCandidate: document.querySelector('.rb-home-landscape-photo')?.currentSrc.match(/w_(\d+),c_limit/)?.[1] || null,
                landscapeLoaded: (() => {
                  const img = document.querySelector('.rb-home-landscape-photo');
                  return img ? Boolean(img.complete && img.naturalWidth) : null;
                })(),
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
                tourCardImages:document.querySelectorAll('img.rb-card-media').length,
                responsiveTourCards:[...document.querySelectorAll('img.rb-card-media')].filter(image => {
                  const srcset=image.getAttribute('srcset')||'';
                  return srcset.includes('w_360,c_limit') && srcset.includes('w_640,c_limit');
                }).length,
                invalidEmptyImageAttributes:[...document.images].filter(img=>img.hasAttribute('src') && !img.getAttribute('src')).length,
                brokenLoadedImages:[...document.images].filter(img=>img.complete && !img.naturalWidth && img.getAttribute('src')).length,
                brokenImageSources:[...document.images]
                  .filter(img=>img.complete && !img.naturalWidth && img.getAttribute('src'))
                  .slice(0,4)
                  .map(img=>{try {const u=new URL(img.currentSrc||img.src); return u.host+u.pathname;} catch(_) {return 'invalid-image-url';}}),
              };
            });
            const screenshot=`${device.key}-${target.key}-${slug}.png`;
            if (sample === 1) await page.screenshot({path:path.join(folder,screenshot),fullPage:false,animations:'disabled'});
            const observed={
              device:device.key,host:target.key,route,
              httpStatus:response?.status()||0,
              sample, transferredBytes, landscapeWidthCandidate:result.landscapeWidthCandidate,
              stagingErrorClass:response?.headers()['x-riburom-staging-error-class'] || null,
              ttfbMs:result.ttfbMs, loadMs:result.loadMs, landscapeLoaded:result.landscapeLoaded,
              fcpMs:result.fcpMs, observedBlockingMs:result.observedBlockingMs,
              lcpMs:result.lcpMs,lcpElement:result.lcpElement,lcpHost:result.lcpHost,
              slowestImageMs:result.slowestImageMs,staticResourceCount:result.staticResourceCount,
              cls:result.cls,
              domContentLoadedMs:result.domContentLoadedMs,
              bodyCharacters:result.bodyCharacters,resourceRequests:result.resourceRequests,
              tourCardImages:result.tourCardImages,responsiveTourCards:result.responsiveTourCards,
              brokenLoadedImages:result.brokenLoadedImages,
              invalidEmptyImageAttributes:result.invalidEmptyImageAttributes,
              brokenImageSources:result.brokenImageSources,
              pageErrorClasses:failures.slice(0,5),screenshot:sample === 1 ? screenshot : null,title:result.title,
            };
            if (route==='/all_tours') {
              const lower=result.visibleTourHeadings.toLowerCase();
              observed.tourMatches=expectedTours.map(name=>lower.includes(name.toLowerCase()));
            }
            observations.push(observed);
            console.log(JSON.stringify({...observed,title:undefined}));
            await page.close();
          }
          await context.close();
        }
      }
    }
    for (const device of profiles) {
      for (const target of targets) {
        const visits = observations.filter(r => r.device === device.key && r.host === target.key && r.route === '/');
        const rows = visits.filter(r => r.httpStatus === 200 && r.lcpMs > 0);
        const summary = {device:device.key, host:target.key, samples:rows.length, errors:visits.length-rows.length};
        for (const key of ['ttfbMs','fcpMs','lcpMs','loadMs','observedBlockingMs','transferredBytes','cls']) {
          const values = rows.map(r => r[key]).filter(value => Number.isFinite(value)).sort((a,b) => a-b);
          if (values.length) {
            const middle = Math.floor(values.length / 2);
            summary[key] = {median:values.length % 2 ? values[middle] : (values[middle-1] + values[middle]) / 2};
          }
        }
        console.log('Homepage summary', JSON.stringify(summary));
      }
    }
    if (observations.some(r => r.httpStatus !== 200 || r.bodyCharacters < 40 || r.pageErrorClasses.length ||
      r.tourMatches?.some(match => !match) || (r.host === 'cloudflare' && r.invalidEmptyImageAttributes) ||
      (r.host === 'cloudflare' && r.route === '/all_tours' && (!r.tourCardImages || r.responsiveTourCards !== r.tourCardImages)) ||
      (r.route === '/' && (!r.lcpMs || r.landscapeLoaded === false)))) {
      throw new Error('Public browser checks failed; inspect the per-page observations');
    }
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(folder,'comparison.json'),JSON.stringify({
      method:'Chromium from GitHub Actions hosted runner; five fresh browser contexts per host/device for homepage, then one visit to each additional page in the first session',
      limitations:['US runner rather than India','Small sample; mobile uses DPR 2 and synthetic 80 ms latency, 4 Mbps down and 1 Mbps up',
                   'LCP and CLS observational; not field Core Web Vitals','Staging protected by HTTP Basic'],
      observations,
    },null,2));
  }
})().catch(error=>{console.error('Read-only browser QA failed:',String(error.message||error));process.exitCode=1;});
