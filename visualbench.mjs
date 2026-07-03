#!/usr/bin/env node
// VisualBench for readingtime.app.nz — captures the key pages at desktop +
// mobile into ./visualbench (gitignored). Run from a dir where `playwright`
// resolves (e.g. ../app-site), e.g.:
//   cd ../app-site && BASE=http://127.0.0.1:4337 RT_SESSION=<token> \
//     node /nvme0n1-disk/code/readingtime/visualbench.mjs
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';

const BASE = process.env.BASE || 'http://127.0.0.1:4337';
const SESSION = process.env.RT_SESSION || '';
const STORY = process.env.RT_STORY || '';
const rootDir = '/nvme0n1-disk/code/readingtime/visualbench';

const pages = [
  { name: 'home', path: '/' },
  { name: 'author', path: '/author', auth: true },
  { name: 'reader', path: '/book/dive', settle: 1500 },
];
if (STORY) pages.push({ name: 'story', path: `/story/${STORY}`, settle: 1500 });

const viewports = [
  { suffix: 'desktop', width: 1440, height: 1100, deviceScaleFactor: 1 },
  { suffix: 'mobile', width: 390, height: 1200, deviceScaleFactor: 2, isMobile: true },
];

await mkdir(rootDir, { recursive: true });
const browser = await chromium.launch();
const host = new URL(BASE).hostname;
const artifacts = [];

for (const p of pages) {
  for (const vp of viewports) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: vp.deviceScaleFactor,
      isMobile: Boolean(vp.isMobile),
    });
    if (p.auth && SESSION) {
      await context.addCookies([
        { name: 'appnz_session', value: SESSION, domain: host, path: '/' },
      ]);
    }
    const page = await context.newPage();
    try {
      await page.goto(BASE + p.path, { waitUntil: 'networkidle', timeout: 60_000 });
    } catch { /* networkidle can flake on autoplay audio; screenshot anyway */ }
    if (p.settle) await page.waitForTimeout(p.settle);
    const name = `${p.name}-${vp.suffix}`;
    await page.screenshot({ path: `${rootDir}/${name}.png`, fullPage: !p.settle });
    artifacts.push({ name, file: `${name}.png`, url: BASE + p.path, ...vp });
    await context.close();
  }
}
await browser.close();

const capturedAt = new Date().toISOString();
await writeFile(`${rootDir}/manifest.json`, JSON.stringify({ capturedAt, base: BASE, artifacts }, null, 2));
await writeFile(`${rootDir}/index.html`, `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Reading Time VisualBench</title>
<style>body{margin:0;background:#0f1226;color:#fff;font:14px/1.5 system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:32px 18px}h1{font-size:30px;margin:0 0 6px}
p{color:#a7adda;margin:0 0 26px}.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
article{border:1px solid rgba(255,255,255,.12);border-radius:12px;overflow:hidden;background:rgba(255,255,255,.04)}
h2{font-size:15px;margin:0;padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.1)}
img{display:block;width:100%;height:auto;background:#050505}</style></head><body><main>
<h1>Reading Time — VisualBench</h1><p>Captured ${capturedAt} from ${BASE}</p><div class="grid">
${artifacts.map((a) => `<article><h2>${a.name}</h2><img src="./${a.file}" alt="${a.name}"></article>`).join('\n')}
</div></main></body></html>`);

console.log(`VisualBench captured ${artifacts.length} screenshots from ${BASE}`);
