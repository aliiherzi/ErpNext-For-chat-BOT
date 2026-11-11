const { chromium } = require('playwright');
const out = process.argv[2];
async function login(browser, user, pwd, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2, ...opts });
  const page = await ctx.newPage();
  page.on('pageerror', e => console.log('PAGEERROR', user, e.message));
  const r = await ctx.request.post('http://localhost:8080/api/method/login', { form: { usr: user, pwd: pwd } });
  if (!r.ok()) throw new Error('login failed ' + user + ' ' + r.status());
  await page.goto('http://localhost:8080/desk');
  await page.waitForTimeout(5000);
  return page;
}
(async () => {
  const browser = await chromium.launch();
  const admin = await login(browser, 'Administrator', 'admin');
  console.log('admin url', admin.url(), 'admin sees button:', await admin.locator('#xal-bot-button').count());
  await admin.screenshot({ path: out + '/admin.png' });
  const page = await login(browser, 'manager@example.com', 'Bot-test-12345');
  console.log('manager sees button:', await page.locator('#xal-bot-button').count());
  await page.click('#xal-bot-button');
  await page.click('text=New chat'); await page.waitForTimeout(500);
  const say = async t => { await page.fill('.xal-bot-input', t); await page.keyboard.press('Enter'); await page.waitForTimeout(3500); };
  await say('I sold 2 book to Ahmed for 5 dollars each');
  await page.screenshot({ path: out + '/1-confirm.png' });
  await page.click('.xal-bot-card .btn-primary'); await page.waitForTimeout(5000);
  await say('what is the balance of Ahmed');
  await page.screenshot({ path: out + '/2-done.png' });
  const href = await page.locator('a:has-text("PDF")').last().getAttribute('href');
  const resp = await page.request.get('http://localhost:8080' + href);
  console.log('pdf', href, resp.status(), resp.headers()['content-type'], (await resp.body()).length);
  console.log('open link', await page.locator('a:has-text("Open")').last().getAttribute('href'));
  console.log(await page.locator('.xal-bot-list').innerText());
  const phone = await login(browser, 'manager@example.com', 'Bot-test-12345', { viewport: { width: 390, height: 800 } });
  await phone.click('#xal-bot-button'); await phone.waitForTimeout(800);
  await phone.screenshot({ path: out + '/3-phone.png' });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
