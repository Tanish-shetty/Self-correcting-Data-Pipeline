// Capture real browser screenshots of the live diagnostic Streamlit app.
const path = require('path');
const fs = require('fs');
const { chromium } = require('C:/Users/tanis/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const dir = path.resolve('artifacts/healing-report');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ headless: true,
    executablePath: 'C:/Users/tanis/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe' });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 1280 }, deviceScaleFactor: 1 });
    await page.goto('http://127.0.0.1:8502', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Run one correction pass', exact: true }).waitFor();
    await page.getByText('BEFORE CORRECTION: no automatic correction pass has run.', { exact: true }).waitFor();
    const mainClip = { x: 50, y: 95, width: 1000, height: 1030 };
    await page.getByTestId('stMain').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.join(dir, '01-before.png'), clip: mainClip });
    await page.getByRole('button', { name: 'Run one correction pass', exact: true }).click();
    await page.getByText('AFTER PASS 1: ALL DATA CHECKS PASS - ready for downstream duplicate checks.', { exact: true }).waitFor();
    await page.getByText('Rule audit from the actual execution', { exact: true }).waitFor();
    await page.getByTestId('stMain').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.join(dir, '02-safe-pass-one.png'), clip: mainClip });
    await page.getByTestId('stDataFrame').nth(1).screenshot({ path: path.join(dir, '02b-safe-audit.png') });
    await page.getByText('Unsafe values', { exact: true }).click();
    await page.getByText('BEFORE CORRECTION: no automatic correction pass has run.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Run one correction pass', exact: true }).click();
    await page.getByText('AFTER PASS 1: QUARANTINE REQUIRED - unsuccessful parsing is not guessed.', { exact: true }).waitFor();
    await page.getByText('Validation reasons', { exact: true }).click();
    await page.getByText('Unresolved reasons after revalidation', { exact: true }).waitFor();
    await page.getByTestId('stMain').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.join(dir, '03-unsafe-pass-one.png'), clip: mainClip });
    await page.getByTestId('stDataFrame').nth(1).screenshot({ path: path.join(dir, '03b-unsafe-reasons.png') });
    await page.getByText('Automated tests', { exact: true }).click();
    await page.getByText('Automated test results', { exact: true }).waitFor();
    await page.getByTestId('stMain').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.join(dir, '04-tests.png'), clip: { x: 50, y: 95, width: 1000, height: 760 } });
    console.log('Captured six live Streamlit screenshots in ' + dir);
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
