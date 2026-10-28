import { test, expect, type Browser, type BrowserContext, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const password = process.env.APP_DEMO_PASSWORD;
const baseURL = process.env.APP_BASE_URL || 'http://127.0.0.1:8094';
const employeeState = '.local/e2e-employee.json';
const managerState = '.local/e2e-manager.json';
const secondState = '.local/e2e-second-manager.json';
type Row = { id: number; version: number; units: number; status: string; key: string };

async function login(page: Page, email: string) {
  if (!password) throw new Error('Set APP_DEMO_PASSWORD to the locally generated training password');
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email);
  await page.getByLabel('Kata sandi', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keluar', exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Tahun cuti', exact: true })).toBeEnabled();
}

async function actor(browser: Browser, state: string): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL, storageState: state, viewport: { width: 1440, height: 1000 }, timezoneId: 'Asia/Jakarta' });
  const page = await context.newPage(); await page.goto('/');
  await expect(page.getByRole('button', { name: 'Keluar', exact: true })).toBeVisible();
  return { context, page };
}

async function post(page: Page, path: string, body: unknown) {
  const auth = await page.request.get('/api/auth/me');
  const csrf = (await auth.json()).csrf_token;
  return page.request.post(path, { data: body, headers: { Origin: new URL(baseURL).origin, 'X-CSRF-Token': csrf } });
}

async function futureDay(page: Page, offset = 35) {
  const context = await (await page.request.get('/api/leave/context')).json();
  const date = new Date(context.today + 'T00:00:00Z');
  date.setUTCDate(date.getUTCDate() + offset);
  while (date.getUTCDay() === 0 || date.getUTCDay() === 6) date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

async function create(page: Page, day: string, reason = 'Browser training request for planned family time'): Promise<Row> {
  const year = Number(day.slice(0, 4));
  const allowance = await (await page.request.get(`/api/leave/balance?year=${year}`)).json();
  const response = await post(page, '/api/leave/requests', { start_date: day, end_date: day, reason, expected_version: allowance.version });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

async function chooseAll(page: Page, year: number) {
  await page.getByRole('combobox', { name: 'Tahun cuti', exact: true }).selectOption(String(year));
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('');
  await expect(page.getByRole('combobox', { name: 'Tahun cuti', exact: true })).toBeEnabled();
}

async function open(page: Page, row: Row) {
  await page.getByRole('button', { name: new RegExp(row.key) }).click();
  await expect(page.getByText(`Versi ${row.version}`, { exact: true })).toBeVisible();
}

test.beforeAll(async ({ browser }) => {
  await mkdir('.local', { recursive: true });
  for (const [email, state] of [['employee@leaveflow.test', employeeState], ['manager@leaveflow.test', managerState], ['manager2@leaveflow.test', secondState]]) {
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    await login(page, email); await context.storageState({ path: state }); await context.close();
  }
});

test('login page has working labels and rejects a wrong password', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill('employee@leaveflow.test');
  await page.getByLabel('Kata sandi', { exact: true }).fill('IncorrectTrainingPassword42!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('incorrect');
});

test('employee previews, submits and withdraws with a restored reservation', async ({ browser }) => {
  const { context, page } = await actor(browser, employeeState);
  const day = await futureDay(page);
  const year = Number(day.slice(0, 4));
  const before = await (await page.request.get(`/api/leave/balance?year=${year}`)).json();
  await chooseAll(page, year);
  await page.getByLabel('Tanggal mulai', { exact: true }).fill(day);
  await page.getByLabel('Tanggal selesai', { exact: true }).fill(day);
  await page.getByRole('textbox', { name: 'Alasan cuti', exact: true }).fill('UI training: family time arranged in advance');
  await page.getByRole('button', { name: 'Hitung hari kerja', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Kirim permintaan', exact: true })).toBeEnabled();
  const saved = page.waitForResponse(response => response.url().endsWith('/api/leave/requests') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Kirim permintaan', exact: true }).click();
  const response = await saved; expect(response.status()).toBe(201);
  const row: Row = await response.json();
  await expect(page.getByRole('button', { name: 'Tarik permintaan', exact: true })).toBeEnabled();
  expect((await (await page.request.get(`/api/leave/balance?year=${year}`)).json()).available).toBe(before.available - 1);
  await page.getByRole('button', { name: 'Tarik permintaan', exact: true }).click();
  await expect(page.locator('.success[role="status"]')).toContainText(`${row.key}: ditarik`);
  expect((await (await page.request.get(`/api/leave/balance?year=${year}`)).json()).available).toBe(before.available);
  await context.close();
});

test('manager approves, sees calendar then cancels with an audit reason', async ({ browser }) => {
  const employee = await actor(browser, employeeState);
  const manager = await actor(browser, managerState);
  const day = await futureDay(employee.page, 42);
  const row = await create(employee.page, day);
  const year = Number(day.slice(0, 4));
  await chooseAll(manager.page, year); await open(manager.page, row);
  await manager.page.getByRole('button', { name: 'Setujui cuti', exact: true }).click();
  await expect(manager.page.locator('.success[role="status"]')).toContainText('disetujui');
  await expect(manager.page.getByRole('button', { name: 'Batalkan persetujuan', exact: true })).toBeVisible();
  await manager.page.getByRole('button', { name: 'Kalender cuti', exact: true }).click();
  await manager.page.getByRole('combobox', { name: 'Bulan', exact: true }).selectOption(String(Number(day.slice(5, 7))));
  await expect(manager.page.getByRole('heading', { name: 'Ringkasan bulan ini', exact: true })).toBeVisible();
  await expect(manager.page.locator('.calendar-agenda')).toContainText('Training Ayu');
  await expect(manager.page.locator('.calendar-agenda')).not.toContainText('family time');
  await manager.page.getByRole('button', { name: /Persetujuan cuti/ }).click();
  await manager.page.getByRole('textbox', { name: 'Catatan keputusan', exact: true }).fill('Training: employee has changed the travel dates');
  await manager.page.getByRole('button', { name: 'Batalkan persetujuan', exact: true }).click();
  await expect(manager.page.locator('.success[role="status"]')).toContainText('dibatalkan');
  await expect(manager.page.locator('.timeline')).toContainText('changed the travel dates');
  await employee.context.close(); await manager.context.close();
});

test('stale manager decision preserves the draft and reloads latest state', async ({ browser }) => {
  const employee = await actor(browser, employeeState);
  const manager = await actor(browser, managerState);
  const day = await futureDay(employee.page, 49);
  const row = await create(employee.page, day);
  await chooseAll(manager.page, Number(day.slice(0, 4))); await open(manager.page, row);
  await manager.page.getByRole('textbox', { name: 'Catatan keputusan', exact: true }).fill('Draft note must survive a stale decision');
  expect((await post(manager.page, `/api/leave/requests/${row.id}/approve`, { expected_version: row.version })).status()).toBe(200);
  await manager.page.getByRole('button', { name: 'Tolak permintaan', exact: true }).click();
  await expect(manager.page.locator('.success[role="status"]')).toContainText('Catatan tetap disimpan');
  await expect(manager.page.getByText('Versi 2', { exact: true })).toBeVisible();
  await expect(manager.page.getByRole('textbox', { name: 'Catatan keputusan', exact: true })).toHaveValue('Draft note must survive a stale decision');
  await expect(manager.page.getByRole('button', { name: 'Batalkan persetujuan', exact: true })).toBeEnabled();
  await manager.page.getByRole('button', { name: 'Batalkan persetujuan', exact: true }).click();
  await expect(manager.page.locator('.success[role="status"]')).toContainText('dibatalkan');
  await employee.context.close(); await manager.context.close();
});

test('second manager cannot read another team through details search counts or CSV', async ({ browser }) => {
  const employee = await actor(browser, employeeState);
  const stranger = await actor(browser, secondState);
  const day = await futureDay(employee.page, 56);
  const marker = `private-browser-case-${Date.now()}`;
  const row = await create(employee.page, day, marker);
  const year = Number(day.slice(0, 4));
  expect((await stranger.page.request.get(`/api/leave/requests/${row.id}`)).status()).toBe(404);
  const result = await (await stranger.page.request.get(`/api/leave/requests?year=${year}&q=${marker}`)).json();
  expect(result.total).toBe(0); expect(result.items).toEqual([]);
  expect(await (await stranger.page.request.get(`/api/leave/requests/export.csv?year=${year}&q=${marker}`)).text()).not.toContain(marker);
  expect((await post(employee.page, `/api/leave/requests/${row.id}/withdraw`, { expected_version: row.version })).status()).toBe(200);
  await employee.context.close(); await stranger.context.close();
});

test('empty filters, mobile widths and keyboard focus remain usable', async ({ browser }) => {
  const { context, page } = await actor(browser, employeeState);
  await page.getByRole('searchbox', { name: 'Cari alasan', exact: true }).fill('no-matching-training-case-unique');
  await page.getByRole('button', { name: 'Cari', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Belum ada permintaan di daftar ini', exact: true })).toBeVisible();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByRole('textbox', { name: 'Alasan cuti', exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Hitung hari kerja', exact: true })).toBeFocused();
  await context.close();
});

test('fresh reload failure disables mutation and keeps the retry control usable', async ({ browser }) => {
  const { context, page } = await actor(browser, employeeState);
  await page.route('**/api/leave/requests?**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Training simulated outage' }) }));
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('rejected');
  await expect(page.getByRole('alert')).toContainText('Training simulated outage');
  await expect(page.getByRole('button', { name: 'Kirim permintaan', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Muat ulang data', exact: true })).toBeEnabled();
  await page.unroute('**/api/leave/requests?**');
  await page.getByRole('button', { name: 'Muat ulang data', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Tahun cuti', exact: true })).toBeEnabled();
  await context.close();
});

test('a revoked session returns to the login form on the next read', async ({ browser }) => {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await login(page, 'employee@leaveflow.test');
  expect((await post(page, '/api/auth/logout', undefined)).status()).toBe(204);
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('rejected');
  await expect(page.getByRole('heading', { name: 'Masuk ke ruang kerja', exact: true })).toBeVisible();
  await context.close();
});

test('@review-actions manager expands working dates, rejects and downloads CSV', async ({browser}) => {
  const employee=await actor(browser,employeeState);
  const manager=await actor(browser,managerState);
  const day=await futureDay(employee.page,63);
  const row=await create(employee.page,day);
  await chooseAll(manager.page,Number(day.slice(0,4)));
  await open(manager.page,row);
  await manager.page.getByText('Lihat 1 tanggal kerja',{exact:true}).click();
  await expect(manager.page.locator('.working-dates[open]')).toBeVisible();
  await manager.page.getByRole('textbox',{name:'Catatan keputusan',exact:true}).fill('Training: kebutuhan tim telah diperiksa dan pengajuan ditolak.');
  await manager.page.getByRole('button',{name:'Tolak permintaan',exact:true}).click();
  await expect(manager.page.locator('.success[role="status"]')).toContainText('ditolak');
  const next=manager.page.getByRole('button',{name:'Berikutnya',exact:true});
  if(await next.count()&&await next.isEnabled()){
    await next.click();
    await expect(manager.page.getByText(/Halaman 2/)).toBeVisible();
    await manager.page.getByRole('button',{name:'Sebelumnya',exact:true}).click();
    await expect(manager.page.getByText(/Halaman 1/)).toBeVisible();
  }
  const download=manager.page.waitForEvent('download');
  await manager.page.getByRole('button',{name:'Ekspor CSV',exact:true}).click();
  expect((await download).suggestedFilename()).toBe(`leaveflow-${day.slice(0,4)}.csv`);
  await manager.page.getByRole('button',{name:'Keluar',exact:true}).click();
  await expect(manager.page.getByRole('textbox',{name:'Email',exact:true})).toBeVisible();
  await employee.context.close();await manager.context.close();
});

test('@capture employee manager calendar and mobile screenshots', async ({ browser }) => {
  await mkdir('docs/screenshots', { recursive: true });
  const employee = await actor(browser, employeeState);
  await expect(employee.page.getByRole('combobox', { name: 'Tahun cuti', exact: true })).toBeEnabled();
  await employee.page.screenshot({ path: 'docs/screenshots/employee-desktop.png' });
  await employee.page.setViewportSize({ width: 390, height: 844 });
  await employee.page.screenshot({ path: 'docs/screenshots/employee-mobile.png' });
  await employee.context.close();
  const manager = await actor(browser, managerState);
  await expect(manager.page.getByRole('combobox', { name: 'Tahun cuti', exact: true })).toBeEnabled();
  const first = manager.page.locator('.request-row').first();
  if (await first.count()) await first.click();
  await expect(manager.page.locator('.request-detail')).toHaveAttribute('aria-busy', 'false');
  await manager.page.screenshot({ path: 'docs/screenshots/manager-desktop.png' });
  await manager.page.getByRole('button', { name: 'Kalender cuti', exact: true }).click();
  const currentYear = await manager.page.getByRole('combobox', { name: 'Tahun cuti', exact: true }).inputValue();
  const approved = await (await manager.page.request.get(`/api/leave/requests?year=${currentYear}&status=approved`)).json();
  if (approved.items.length) await manager.page.getByRole('combobox', { name: 'Bulan', exact: true }).selectOption(String(Number(approved.items[0].start_date.slice(5, 7))));
  await expect(manager.page.getByRole('combobox', { name: 'Bulan', exact: true })).toBeEnabled();
  await manager.page.screenshot({ path: 'docs/screenshots/calendar-desktop.png' });
  await manager.context.close();
});
