/* Run against python -m tests.cms_review_preview. Local synthetic data only. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const BASE = 'http://127.0.0.1:5055';
const OUT = process.env.CMS_QA_OUTPUT || path.join(require('node:os').tmpdir(), 'riburom-seven-fixes-browser');
fs.mkdirSync(OUT, {recursive:true});
(async () => {
  const browser = await chromium.launch({headless:true});
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({viewport:{width, height:900}, reducedMotion:'reduce'});
      await context.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(BASE + '/__qa/session/owner');
      await page.getByRole('button', {name:/^Select (QA shared photograph|Saved before delay \d+)$/}).click();
      const title = page.locator('#cr-media-inspector input[name="title"]');
      await title.fill('Saved before delay ' + width);
      let release, entered;
      const intercepted = new Promise(resolve => {entered = resolve;});
      const gate = new Promise(resolve => {release = resolve;});
      await page.route('**/workspace/control/media/metadata/*', async route => {
        entered(); await gate; await route.continue();
      });
      await page.getByRole('button', {name:'Save Metadata', exact:true}).click();
      await intercepted;
      assert.ok(await title.isDisabled(), 'Inputs must lock during the pending save');
      await page.getByRole('button', {name:'Select QA second photograph', exact:true}).click();
      assert.equal(await title.inputValue(), 'Saved before delay ' + width, 'Selection must stay with the pending save');
      release();
      await page.waitForFunction(() => document.querySelector('#cr-media-inspector input[name="title"]')?.disabled === false);
      assert.equal(await title.inputValue(), 'Saved before delay ' + width);
      await title.fill('Unsaved after response ' + width);
      await page.waitForTimeout(200);
      assert.equal(await title.inputValue(), 'Unsaved after response ' + width);
      await title.fill('Saved before delay ' + width);
      const usedResponse = page.waitForResponse(response => response.url().includes('/media/videos?') && response.url().includes('usage=used'));
      await page.locator('#cr-media-usage').selectOption('used');
      await usedResponse;
      await page.getByRole('button', {name:'Select QA second photograph', exact:true}).waitFor({state:'hidden'});
      await page.getByRole('button', {name:'Select QA live opening film', exact:true}).waitFor();
      assert.equal(await page.getByRole('button', {name:'Select QA live opening film', exact:true}).count(), 1);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({path:path.join(OUT, `media-${width}.png`), fullPage:false});
      for (const role of ['media', 'content']) {
        await page.goto(BASE + '/__qa/session/' + role);
        await page.goto(BASE + '/workspace/pages');
        if (role === 'media') {
          await page.locator('[data-panel="appearance"]').click();
          await page.locator('#section-design input[type="color"]').first().waitFor();
          assert.ok(await page.locator('#section-design').isVisible());
        } else {
          assert.equal(await page.locator('#section-design').count(), 0);
        }
        await page.screenshot({path:path.join(OUT, `${role}-appearance-${width}.png`), fullPage:false});
      }
      assert.deepEqual(errors, [], 'No JavaScript runtime errors');
      results.push({width, delayedSave:'passed', liveFilmUsedFilter:'passed', roleAppearance:'passed', runtimeErrors:errors});
      await context.close();
    }
    fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify({passed:results.length * 3, results, output:OUT}, null, 2));
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
