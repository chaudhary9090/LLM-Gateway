import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/Inno/.gemini/antigravity/brain/ff84fa37-caea-4f97-abeb-76074862e7c4/screenshots';
const EDGE_PATH = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log('Launching browser via Edge...');
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();

  // 1. Overview Page
  console.log('Capturing 1: Overview...');
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle0' });
  await page.waitForTimeout ? page.waitForTimeout(1500) : new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'overview.png') });

  // 2. Playground Page & Interacting
  console.log('Capturing 2: Playground initial...');
  await page.goto('http://127.0.0.1:5173/playground', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'playground_initial.png') });

  // In Playground, type a message and send it
  console.log('Testing Playground chat interaction...');
  const textarea = await page.$('textarea');
  if (textarea) {
    await textarea.type('Explain quantum computing caching in one punchy sentence.');
    // Click submit button
    const submitBtn = await page.$('button[type="submit"]');
    if (submitBtn) {
      await submitBtn.click();
      // Wait for response to render
      await new Promise((r) => setTimeout(r, 2500));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'playground_with_response.png') });

      // Click submit again to trigger cache hit!
      console.log('Sending identical query for cache hit...');
      await textarea.type('Explain quantum computing caching in one punchy sentence.');
      await submitBtn.click();
      await new Promise((r) => setTimeout(r, 2000));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'playground_cached.png') });
    }
  }

  // 3. Providers Page
  console.log('Capturing 3: Providers...');
  await page.goto('http://127.0.0.1:5173/providers', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'providers.png') });

  // 4. Models Page
  console.log('Capturing 4: Models...');
  await page.goto('http://127.0.0.1:5173/models', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'models.png') });

  // 5. Logs Page
  console.log('Capturing 5: Logs...');
  await page.goto('http://127.0.0.1:5173/logs', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'logs.png') });

  // Click the first row in Logs table to open the detail drawer!
  const firstRow = await page.$('tbody tr');
  if (firstRow) {
    await firstRow.click();
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'logs_detail_drawer.png') });
  }

  // 6. Health & Metrics Page
  console.log('Capturing 6: Health & Metrics...');
  await page.goto('http://127.0.0.1:5173/health-metrics', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'health_metrics.png') });

  // Re-capture Overview with fresh stats after playground requests!
  console.log('Re-capturing Overview with live metrics...');
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'overview_active.png') });

  await browser.close();
  console.log('All screenshots captured successfully!');
}

run().catch((err) => {
  console.error('Error during screenshot capture:', err);
  process.exit(1);
});
