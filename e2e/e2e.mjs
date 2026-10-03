#!/usr/bin/env node
// e2e: paywall, sign-in state, Stripe checkout display (/pricing?test=true), /account, JS sign-out.
// Run: cd ../app-site && node ../readingtime/e2e/e2e.mjs   (needs playwright; uses a throwaway SSO user)
import { chromium } from '/nvme0n1-disk/code/app-site/node_modules/playwright/index.mjs';
import { spawn, execFileSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';

const ROOT = '/nvme0n1-disk/code/readingtime';
const SSO = '/nvme0n1-disk/data/appnz-sso.db';
const PORT = process.env.E2E_PORT || '4398';
const BASE = `http://127.0.0.1:${PORT}`;
const sql = q => execFileSync('sqlite3', [SSO, q]).toString();

const uid = 'e2e-' + randomBytes(6).toString('hex');
const email = `${uid}@e2e.readingtime.test`;
const tok = randomBytes(24).toString('base64url');
const hash = createHash('sha256').update(tok).digest('base64url');
const now = new Date().toISOString().replace('T', ' ').slice(0, 19) + '+00:00';
const exp = new Date(Date.now() + 3600e3).toISOString().replace('T', ' ').slice(0, 19) + '+00:00';

const fails = [];
const check = (name, ok, extra = '') => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`); if (!ok) fails.push(name); };

sql(`INSERT INTO users (id,email,password_hash,salt,created_at) VALUES ('${uid}','${email}','x','x','${now}')`);
sql(`INSERT INTO sso_sessions (id,user_id,created_at,expires_at) VALUES ('${hash}','${uid}','${now}','${exp}')`);

const srv = spawn(`${ROOT}/readingtime`, [], {
  cwd: ROOT, stdio: 'ignore',
  env: { ...process.env, PORT, DEV: 'true', DB_PATH: `/nvme0n1-disk/tmp/rt-e2e-${PORT}.db`, STATIC_BASE_URL: '', SITE_BASE_URL: BASE },
});
for (let i = 0; i < 40; i++) { try { if ((await fetch(BASE + '/health')).ok) break; } catch {} await new Promise(r => setTimeout(r, 250)); }

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext();
  const errs = [];
  const watch = page => {
    page.on('console', m => { if (m.type() === 'error') errs.push(`${page.url()} console: ${m.text()}`); });
    page.on('pageerror', e => errs.push(`${page.url()} pageerror: ${e.message}`));
    page.on('requestfailed', r => { if (r.url().startsWith(BASE)) errs.push(`requestfailed ${r.url()}`); });
  };
  const page = await ctx.newPage(); watch(page);

  // anonymous
  let r = await page.goto(BASE + '/');
  check('home 200', r.status() === 200);
  check('home pitch', (await page.textContent('body')).includes('Read a book free'));
  r = await page.goto(BASE + '/book/alphabet'); check('first book free', r.status() === 200);
  errs.length = 0; // reveal.js noise is not part of this check
  r = await page.goto(BASE + '/book/at-the-zoo'); check('second book paywalled', r.status() === 402);
  check('paywall shows plans', (await page.textContent('body')).includes('$90'));
  r = await page.goto(BASE + '/pricing'); check('pricing 200', r.status() === 200);
  const login = await ctx.request.get(BASE + '/account', { maxRedirects: 0 });
  check('anon /account redirects to login', login.status() === 302 && /login/.test(login.headers().location || ''));

  // signed in
  await ctx.addCookies([{ name: 'appnz_session', value: tok, url: BASE }]);
  errs.length = 0;
  await page.goto(BASE + '/pricing');
  check('signed-in header shows account', (await page.content()).includes('href="/account"'));
  check('pricing no console errors', errs.length === 0, errs.join(' | '));

  // Stripe checkout via ?test=true
  const stripeErrs = [];
  const sp = page;
  await page.goto(BASE + '/pricing?test=true');
  await page.waitForURL(/checkout\.stripe\.com/, { timeout: 45000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  const body = await page.textContent('body');
  check('stripe checkout displayed', /checkout\.stripe\.com/.test(page.url()) && /\$9\.00|9\.00/.test(body), page.url().slice(0, 60));
  const own = errs.filter(e => !/stripe\.com|stripe\.network|stripecdn/.test(e));
  check('no console errors up to stripe', own.length === 0, own.join(' | '));
  if (errs.length > own.length) console.log(`note: ${errs.length - own.length} third-party stripe console message(s)`);

  // account + JS sign out
  errs.length = 0;
  await page.goto(BASE + '/account');
  await page.waitForFunction(() => document.getElementById('who')?.textContent.includes('@'));
  check('account shows email', (await page.textContent('#who')) === email);
  check('account shows free plan', (await page.textContent('#planBody')).includes('Free plan'));
  check('account no console errors', errs.length === 0, errs.join(' | '));
  await page.click('#signout');
  await page.waitForURL(BASE + '/');
  await page.waitForLoadState('networkidle');
  check('signed out header shows Sign in', (await page.textContent('.site-nav')).includes('Sign in'));
  const again = await ctx.request.get(BASE + '/account', { maxRedirects: 0 });
  check('signed out /account redirects', again.status() === 302);
  const me = await (await ctx.request.get(BASE + '/api/me')).json();
  check('api/me signed out', me.signedIn === false);

  // sign back in
  await ctx.addCookies([{ name: 'appnz_session', value: tok, url: BASE }]);
  const t2 = randomBytes(24).toString('base64url');
  const h2 = createHash('sha256').update(t2).digest('base64url');
  sql(`INSERT INTO sso_sessions (id,user_id,created_at,expires_at) VALUES ('${h2}','${uid}','${now}','${exp}')`);
  await ctx.addCookies([{ name: 'appnz_session', value: t2, url: BASE }]);
  const me2 = await (await ctx.request.get(BASE + '/api/me')).json();
  check('sign back in', me2.signedIn === true && me2.email === email);
  await page.goto(BASE + '/account');
  await page.waitForFunction(() => document.getElementById('who')?.textContent.includes('@'));
  check('account after re-login', true);
} catch (e) {
  fails.push('exception'); console.error(e);
} finally {
  await browser.close();
  srv.kill();
  sql(`DELETE FROM sso_sessions WHERE user_id='${uid}'; DELETE FROM users WHERE id='${uid}'`);
}
console.log(fails.length ? `\n${fails.length} FAILED: ${fails.join(', ')}` : '\nall passed');
process.exit(fails.length ? 1 : 0);
