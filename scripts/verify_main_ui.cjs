// Browser smoke check of the real main entry point and automatic local storage.
const path = require('path');
const fs = require('fs');
const assert = require('assert');
const { chromium } = require('C:/Users/tanis/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const out = path.resolve('artifacts/main-ui-verification');
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true,
    executablePath:'C:/Users/tanis/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
  let page;
  try {
    page = await browser.newPage({viewport:{width:1440,height:1320},deviceScaleFactor:1});
    await page.goto('http://127.0.0.1:8501', {waitUntil:'domcontentloaded'});
    await page.getByRole('button',{name:'Run one correction pass',exact:true}).waitFor();
    await page.screenshot({path:path.join(out,'01-main-before.png')});
    await page.getByRole('button',{name:'Run one correction pass',exact:true}).click();
    await page.getByText('AFTER PASS 1: ALL DATA CHECKS PASS - ready for downstream duplicate checks.',{exact:true}).waitFor();
    let metrics = await page.getByTestId('stMetricValue').allTextContents();
    assert.deepStrictEqual(metrics,['1','2','7','0']);
    await page.screenshot({path:path.join(out,'02-main-safe.png')});
    await page.getByTestId('stDataFrame').nth(1).screenshot({path:path.join(out,'03-main-audit.png')});
    await page.getByText('Unsafe values',{exact:true}).click();
    await page.getByRole('button',{name:'Run one correction pass',exact:true}).click();
    await page.getByText('AFTER PASS 1: QUARANTINE REQUIRED - unsuccessful parsing is not guessed.',{exact:true}).waitFor();
    metrics = await page.getByTestId('stMetricValue').allTextContents();
    assert.deepStrictEqual(metrics,['1','2','1','5']);
    await page.getByText('Validation reasons',{exact:true}).click();
    await page.getByText('Unresolved reasons after revalidation',{exact:true}).waitFor();
    await page.getByTestId('stMain').evaluate(el => {el.scrollTop=0;});
    await page.screenshot({path:path.join(out,'04-main-unsafe.png')});
    await page.getByRole('button',{name:'Reset this case',exact:true}).click();
    await page.getByText('BEFORE CORRECTION: no automatic correction pass has run.',{exact:true}).waitFor();
    assert.strictEqual((await page.getByTestId('stMetricValue').allTextContents())[0],'0');
    await page.getByText('Rules & profiles',{exact:true}).click();
    await page.getByRole('heading',{name:'Explicit rules and source profiles',exact:true}).waitFor();
    await page.getByText('Live correction',{exact:true}).click();
    await page.getByRole('button',{name:'Run one correction pass',exact:true}).waitFor();
    for (const [view, heading] of [['Upload','Upload sales CSV'], ['Batch history','Batch history'],
      ['Accepted records','Accepted sales'], ['Correction audit','Correction attempts'],
      ['Quarantine review','Quarantine review']]) {
      await page.getByText(view,{exact:true}).first().click();
      await page.getByRole('heading',{name:heading,exact:true}).waitFor();
      assert.strictEqual(await page.getByTestId('stException').count(),0);
      assert.strictEqual(await page.getByText('Could not open local storage.',{exact:false}).count(),0);
    }
    await page.getByText('Upload',{exact:true}).click();
    await page.getByRole('heading',{name:'Upload sales CSV',exact:true}).waitFor();
    await page.screenshot({path:path.join(out,'05-local-storage-upload.png')});
    console.log('Main UI verified: correction, audit, quarantine reasons, reset, rules, and all local storage views.');
    console.log('Screenshots: '+out);
  } catch(err) {
    if(page) {
      await page.screenshot({path:path.join(out,'99-failure.png')});
      console.log((await page.locator('body').innerText()).slice(-5000));
    }
    throw err;
  } finally { await browser.close(); }
})().catch(err=>{console.error(err);process.exit(1);});
