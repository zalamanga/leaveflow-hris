import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api';
import { dateLabel, monthCells, nextWorkingDate } from './format';
import type { Auth, Balance, Calendar, Context, Detail, Estimate, Queue, Status, Summary } from './types';

const statusNames: Record<Status, string> = { pending: 'Menunggu', approved: 'Disetujui', rejected: 'Ditolak', withdrawn: 'Ditarik', cancelled: 'Dibatalkan' };
const months = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
const message = (error: unknown) => error instanceof Error ? error.message : 'Koneksi terputus. Coba lagi.';
const stamp = (value: string) => new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Jakarta' }).format(new Date(value));

function Login({ onAuth }: { onAuth: (auth: Auth) => void }) {
  const [email, setEmail] = useState('employee@leaveflow.test');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onAuth(await api<Auth>('/api/auth/login', { method: 'POST', body: { email, password } })); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  return <main className="login-page"><div className="login-story"><a className="brand" href="#main">LeaveFlow<span>Cuti tahunan</span></a><p className="eyebrow">Ruang kerja karyawan</p><h1>Rencanakan jeda.<br />Jaga pekerjaan tetap terarah.</h1><p>Lihat saldo, ajukan tanggal cuti, lalu ikuti keputusan manajer dalam satu riwayat.</p><div className="policy-note"><strong>Aturan contoh yang terbuka</strong><p>Kuota latihan 12 hari per tahun. Hari Sabtu, Minggu, dan libur kantor yang dikonfigurasi tidak mengurangi kuota.</p></div></div><section className="login-form" id="main"><h2>Masuk ke ruang kerja</h2><p>Gunakan akun yang disiapkan administrator.</p><form onSubmit={login}><label>Email<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} /></label><label>Kata sandi<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required maxLength={128} /></label>{error && <p role="alert" className="error">{error}</p>}<button className="primary" disabled={busy}>{busy ? 'Memeriksa akun...' : 'Masuk'}</button></form><details className="training-help"><summary>Akun latihan lokal</summary><p>Karyawan: <code>employee@leaveflow.test</code><br />Manajer: <code>manager@leaveflow.test</code></p><p>Kata sandi unik tersedia di <code>.local/LOCAL-CREDENTIALS.txt</code> setelah menjalankan Start.ps1.</p></details></section></main>;
}

function StatusTag({ status }: { status: Status }) { return <span className={`status ${status}`}>{statusNames[status]}</span>; }

function Workspace({ auth, logout }: { auth: Auth; logout: () => Promise<void> }) {
  const manager = auth.user.role === 'manager';
  const [context, setContext] = useState<Context | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [tab, setTab] = useState<'requests' | 'calendar'>('requests');
  const [month, setMonth] = useState(1);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [calendar, setCalendar] = useState<Calendar | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [status, setStatus] = useState<Status | ''>(manager ? 'pending' : '');
  const [search, setSearch] = useState(''); const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false); const [detailLoading, setDetailLoading] = useState(false); const [freshReady, setFreshReady] = useState(false);
  const [busy, setBusy] = useState(false); const [fatal, setFatal] = useState(''); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [reason, setReason] = useState(''); const [reviewReason, setReviewReason] = useState('');
  const [estimate, setEstimate] = useState<Estimate | null>(null); const [estimateKey, setEstimateKey] = useState('');
  const [estimating, setEstimating] = useState(false);
  const serial = useRef(0);
  const today = context?.today ?? '';
  const blocked = busy || loading || detailLoading || !freshReady;
  const fresh = estimateKey === `${start}/${end}`;

  useEffect(() => { let active = true; api<Context>('/api/leave/context').then(value => { if (!active) return; setContext(value); setYear(value.year); setMonth(Number(value.today.slice(5, 7))); const day = nextWorkingDate(value.today); setStart(day); setEnd(day); }).catch(e => { if (active) setFatal(message(e)); }); return () => { active = false; }; }, []);
  useEffect(() => {
    if (year === null) return;
    let active = true; const current = ++serial.current; setLoading(true); setFreshReady(false);
    const params = new URLSearchParams({ year: String(year), q: query, page: String(page), page_size: '12', ...(status ? { status } : {}) });
    Promise.all([api<Queue>(`/api/leave/requests?${params}`), manager ? Promise.resolve(null) : api<Balance>(`/api/leave/balance?year=${year}`), api<Calendar>(`/api/leave/calendar?year=${year}&month=${month}`)])
      .then(([rows, allowance, dates]) => { if (!active || current !== serial.current) return; setQueue(rows); setBalance(allowance); setCalendar(dates); setFreshReady(true); })
      .catch(e => { if (active) setError(message(e)); })
      .finally(() => { if (active && current === serial.current) setLoading(false); });
    return () => { active = false; };
  }, [year, manager, query, status, page, refresh, month]);
  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    let active = true; setDetailLoading(true);
    api<Detail>(`/api/leave/requests/${selected}`).then(value => { if (active) setDetail(value); }).catch(e => { if (active) { setError(message(e)); setDetail(null); } }).finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selected, refresh]);

  async function preview(event: FormEvent) {
    event.preventDefault(); setEstimating(true); setError('');
    const key = `${start}/${end}`;
    try { const data = await api<Estimate>(`/api/leave/estimate?start_date=${start}&end_date=${end}`); setEstimate(data); setEstimateKey(key); }
    catch (e) { setError(message(e)); setEstimate(null); }
    finally { setEstimating(false); }
  }
  async function submit() {
    if (!balance?.version) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const row = await api<Detail>('/api/leave/requests', { method: 'POST', csrf: auth.csrf_token, body: { start_date: start, end_date: end, reason, expected_version: balance.version } });
      setSelected(row.id); setDetail(row); setReason(''); setEstimate(null); setStatus(''); setPage(1); setNotice('Permintaan dikirim. Hari cuti direservasi sambil menunggu keputusan manajer.'); setRefresh(value => value + 1);
    } catch (e) { setError(message(e)); if (e instanceof ApiError && e.status === 409) { setNotice('Isian tetap disimpan. Data terbaru sedang dimuat.'); setRefresh(value => value + 1); } }
    finally { setBusy(false); }
  }
  async function action(name: 'withdraw' | 'approve' | 'reject' | 'cancel') {
    if (!detail) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const row = await api<Detail>(`/api/leave/requests/${detail.id}/${name}`, { method: 'POST', csrf: auth.csrf_token, body: { expected_version: detail.version, ...(name !== 'withdraw' ? { reason: reviewReason } : {}) } });
      setDetail(row); setReviewReason(''); setNotice(`Permintaan ${row.key}: ${statusNames[row.status].toLowerCase()}.`); setRefresh(value => value + 1);
    } catch (e) { setError(message(e)); if (e instanceof ApiError && e.status === 409) { setNotice('Catatan tetap disimpan. Tinjau versi terbaru sebelum mencoba lagi.'); setRefresh(value => value + 1); } }
    finally { setBusy(false); }
  }
  function select(row: Summary) { setSelected(row.id); setDetail(null); setReviewReason(''); setError(''); }
  function chooseYear(value: number) { setYear(value); setPage(1); setSelected(null); if (!manager && !reason) { const day = nextWorkingDate(value === context?.year ? today : `${value}-01-01`); setStart(day); setEnd(day); setEstimate(null); } }
  async function exportCsv() {
    setBusy(true); setError('');
    try {
      const params = new URLSearchParams({ year: String(year), q: query, ...(status ? { status } : {}) });
      const response = await fetch(`/api/leave/requests/export.csv?${params}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('Ekspor gagal. Persempit filter atau masuk kembali.');
      const url = URL.createObjectURL(await response.blob()); const a = document.createElement('a'); a.href = url; a.download = `leaveflow-${year}.csv`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  if (fatal) return <main className="startup"><h1>Ruang kerja belum dapat dimuat</h1><p role="alert">{fatal}</p><button onClick={() => window.location.reload()}>Coba lagi</button></main>;
  if (!context) return <main className="startup" aria-busy="true"><p role="status">Memuat tanggal kantor dan kebijakan...</p></main>;

  return <div className="shell"><a className="skip-link" href="#main">Lewati ke isi</a><aside className="sidebar"><a className="brand" href="#main">LeaveFlow<span>Cuti tahunan</span></a><p className="workspace-label">{manager ? 'Ruang manajer' : 'Ruang karyawan'}</p><nav aria-label="Ruang kerja"><button className={tab === 'requests' ? 'active' : ''} aria-current={tab === 'requests' ? 'page' : undefined} onClick={() => setTab('requests')}>{manager ? 'Persetujuan cuti' : 'Permintaan saya'}{manager && queue && <span className="nav-count">{queue.counts.pending}</span>}</button><button className={tab === 'calendar' ? 'active' : ''} aria-current={tab === 'calendar' ? 'page' : undefined} onClick={() => setTab('calendar')}>Kalender cuti</button></nav><div className="sidebar-foot"><p>Asia/Jakarta</p><span>Hari kerja Senin-Jumat</span><p className="small">Libur kantor mengikuti konfigurasi administrator.</p></div></aside><div className="workspace"><header className="topbar"><span>{dateLabel(today)}</span><div className="user-menu"><div><strong>{auth.user.name}</strong><span>{manager ? 'Manajer' : 'Karyawan'}</span></div><button disabled={busy} onClick={() => { setBusy(true); logout().catch(e => { setError(message(e)); setBusy(false); }); }}>Keluar</button></div></header>{auth.demo_mode && <div className="demo-banner">Mode latihan. Semua akun dan permintaan awal adalah data sintetis. Kebijakan ini bukan ketentuan hukum.</div>}<main id="main" className="content"><div className="page-heading"><div><p className="eyebrow">{manager ? 'Tim langsung Anda' : 'Cuti tahunan Anda'}</p><h1>{tab === 'calendar' ? 'Kalender cuti' : manager ? 'Tinjau rencana cuti tim' : 'Rencanakan waktu istirahat'}</h1><p>{tab === 'calendar' ? manager ? 'Hanya cuti disetujui dari karyawan yang melapor langsung kepada Anda.' : 'Kalender menampilkan cuti Anda yang telah disetujui.' : manager ? 'Periksa tanggal dan ketersediaan tim sebelum mengambil keputusan.' : 'Permintaan menunggu mengurangi saldo tersedia sampai ditinjau atau ditarik.'}</p></div><label className="year-control">Tahun<select aria-label="Tahun cuti" value={year ?? context.year} onChange={e => chooseYear(Number(e.target.value))} disabled={blocked}>{[context.year, context.year + 1].map(value => <option key={value}>{value}</option>)}</select></label></div>
      {error && <div role="alert" className="error notice">{error}<button onClick={() => { setError(''); setRefresh(value => value + 1); }} disabled={busy || loading || detailLoading}>Muat ulang data</button></div>}{notice && <p role="status" className="success notice">{notice}</p>}
      {tab === 'requests' && <>
        {!manager && balance && <section className="balance-panel" aria-labelledby="balance-heading"><div className="balance-main"><p id="balance-heading">Saldo tersedia {year}</p><strong>{balance.available}<span>hari kerja</span></strong><p>{balance.configured ? `Dari kuota ${balance.granted} hari per tahun` : 'Kuota belum dikonfigurasi administrator'}</p></div><div className="balance-breakdown"><div><span>Disetujui</span><strong>{balance.approved} hari</strong></div><div><span>Menunggu</span><strong>{balance.pending} hari</strong></div><div className="balance-track" role="img" aria-label={`${balance.approved} hari disetujui dan ${balance.pending} hari menunggu dari kuota ${balance.granted}`}><span style={{ width: `${balance.granted ? balance.approved / balance.granted * 100 : 0}%` }} /><span style={{ width: `${balance.granted ? balance.pending / balance.granted * 100 : 0}%` }} /></div><p>Reservasi menunggu dilepas jika ditolak atau ditarik.</p></div></section>}
        <div className={`work-grid ${manager ? 'manager-grid' : ''}`}>
          {!manager && <section className="panel request-form" aria-labelledby="new-heading"><div className="section-heading"><span className="section-number">01</span><div><h2 id="new-heading">Ajukan cuti</h2><p>Hitung hari kerja sebelum mengirim.</p></div></div><form onSubmit={preview}><div className="date-fields"><label>Tanggal mulai<input type="date" value={start} min={today} onChange={e => { setStart(e.target.value); setEstimate(null); }} required disabled={blocked || estimating} /></label><label>Tanggal selesai<input type="date" value={end} min={start || today} onChange={e => { setEnd(e.target.value); setEstimate(null); }} required disabled={blocked || estimating} /></label></div><label>Alasan cuti<textarea value={reason} minLength={10} maxLength={2000} rows={3} onChange={e => setReason(e.target.value)} placeholder="Tuliskan rencana dan informasi yang dibutuhkan manajer." required disabled={blocked} /></label><p className="field-help">10-2.000 karakter. Alasan hanya terlihat oleh Anda dan manajer langsung.</p><button type="submit" disabled={blocked || estimating || !start || !end}>{estimating ? 'Menghitung...' : 'Hitung hari kerja'}</button></form>{estimate && fresh && <div className="estimate" role="status"><strong>{estimate.units} hari kerja</strong><p>{dateLabel(start)} s.d. {dateLabel(end)}</p>{estimate.excluded_days.length > 0 && <details><summary>{estimate.excluded_days.length} tanggal tidak dihitung</summary><ul>{estimate.excluded_days.map(day => <li key={day.date}>{dateLabel(day.date)}: {day.reason}</li>)}</ul></details>}<p className="small">Tanggal kerja dihitung ulang dan disimpan oleh server saat pengajuan.</p></div>}<button className="primary submit-request" type="button" onClick={submit} disabled={blocked || estimating || !estimate || !fresh || reason.trim().length < 10 || !balance?.configured || estimate.units > (balance?.available ?? 0) || Number(start.slice(0, 4)) !== year}>{busy ? 'Mengirim...' : 'Kirim permintaan'}</button>{Number(start.slice(0, 4)) !== year && <p className="field-help">Pilih tahun yang sama dengan tanggal permintaan.</p>}<p className="policy-caption">Kuota latihan 12 hari/tahun, tanpa carry-over. Permintaan harus berada dalam satu tahun kalender.</p></section>}
          <section className="panel request-list" aria-labelledby="list-heading"><div className="section-heading"><span className="section-number">{manager ? '01' : '02'}</span><div><h2 id="list-heading">{manager ? 'Permintaan tim' : 'Riwayat permintaan'}</h2><p>{manager ? `${queue?.counts.pending ?? 0} permintaan menunggu keputusan pada ${year}` : 'Tanggal terbaru ditampilkan lebih dahulu'}</p></div></div><form className="filters" onSubmit={e => { e.preventDefault(); setQuery(search); setPage(1); }}><label>Cari {manager ? 'nama atau alasan' : 'alasan'}<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder={manager ? 'Nama karyawan atau alasan' : 'Cari alasan cuti'} maxLength={200} /></label><label>Status<select value={status} onChange={e => { setStatus(e.target.value as Status | ''); setPage(1); }}><option value="">Semua status</option>{Object.entries(statusNames).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label><button type="submit" disabled={blocked}>Cari</button>{manager && <button type="button" onClick={exportCsv} disabled={blocked}>Ekspor CSV</button>}</form><div className="request-rows" aria-busy={loading}>{loading && <p role="status" className="loading-line">Memuat permintaan terbaru...</p>}{!loading && queue?.items.length === 0 && <div className="empty"><h3>Belum ada permintaan di daftar ini</h3><p>{query || status ? 'Ubah pencarian atau status untuk melihat permintaan lain.' : manager ? 'Permintaan karyawan langsung Anda akan muncul di sini.' : 'Ajukan tanggal pertama melalui formulir di samping.'}</p></div>}{queue?.items.map(row => <button key={row.id} type="button" className={`request-row ${selected === row.id ? 'selected' : ''}`} onClick={() => select(row)} disabled={blocked} aria-pressed={selected === row.id}><div className="row-top"><span className="request-key">{row.key}</span><StatusTag status={row.status} /></div><strong>{manager ? row.employee.name : `${dateLabel(row.start_date)}${row.start_date !== row.end_date ? ` - ${dateLabel(row.end_date)}` : ''}`}</strong><div className="row-bottom"><span>{manager ? `${dateLabel(row.start_date)} - ${dateLabel(row.end_date)}` : `Diajukan ${stamp(row.created_at)}`}</span><b>{row.units} hari</b></div></button>)}</div>{queue && queue.total > 12 && <div className="pagination"><button disabled={blocked || page === 1} onClick={() => setPage(value => value - 1)}>Sebelumnya</button><span>Halaman {page} / {Math.ceil(queue.total / 12)}</span><button disabled={blocked || page * 12 >= queue.total} onClick={() => setPage(value => value + 1)}>Berikutnya</button></div>}</section>
          <section className="panel request-detail" aria-labelledby="detail-heading" aria-busy={detailLoading}><div className="section-heading"><span className="section-number">{manager ? '02' : '03'}</span><div><h2 id="detail-heading">Detail permintaan</h2><p>{detail?.key ?? 'Pilih permintaan dari daftar'}</p></div></div>{detailLoading && <p role="status">Memuat detail terbaru...</p>}{!selected && <div className="empty detail-empty"><div className="date-mark" aria-hidden="true">31</div><h3>Tanggal dan keputusan, dalam satu tempat</h3><p>Pilih satu permintaan untuk melihat rincian hari kerja dan jejak persetujuannya.</p></div>}{detail && <><div className="detail-title"><StatusTag status={detail.status} /><span>Versi {detail.version}</span></div><h3>{detail.employee.name}</h3><p className="detail-dates">{dateLabel(detail.start_date)} - {dateLabel(detail.end_date)}</p><p className="unit-label">{detail.units} hari kerja</p><h4>Alasan pengajuan</h4><p className="preserve">{detail.reason}</p><details className="working-dates"><summary>Lihat {detail.working_days.length} tanggal kerja</summary><ul>{detail.working_days.map(day => <li key={day}>{dateLabel(day)}</li>)}</ul></details>{!manager && detail.status === 'pending' && <div className="action-block"><p>Menarik permintaan langsung melepaskan reservasi saldo.</p><button onClick={() => action('withdraw')} disabled={blocked}>Tarik permintaan</button></div>}{manager && ['pending', 'approved'].includes(detail.status) && <div className="action-block"><label>Catatan keputusan<textarea rows={3} maxLength={2000} value={reviewReason} onChange={e => setReviewReason(e.target.value)} disabled={blocked} placeholder="Alasan wajib minimal 10 karakter untuk menolak atau membatalkan." /></label><div className="action-buttons">{detail.status === 'pending' ? <><button className="primary" onClick={() => action('approve')} disabled={blocked}>Setujui cuti</button><button className="danger" onClick={() => action('reject')} disabled={blocked || reviewReason.trim().length < 10}>Tolak permintaan</button></> : <button className="danger" onClick={() => action('cancel')} disabled={blocked || reviewReason.trim().length < 10}>Batalkan persetujuan</button>}</div><p className="field-help">{detail.status === 'pending' ? 'Persetujuan memakai saldo yang sudah direservasi.' : 'Pembatalan mengembalikan saldo dan tercatat pada riwayat.'}</p></div>}<h4>Jejak permintaan</h4><ol className="timeline">{detail.events.map(event => <li key={event.id}><strong>{event.actor}</strong><p>{event.note}</p><time dateTime={event.created_at}>{stamp(event.created_at)} WIB</time></li>)}</ol></>}</section>
        </div></>}
      {tab === 'calendar' && <section className="panel calendar-panel" aria-labelledby="calendar-heading"><div className="calendar-toolbar"><div><h2 id="calendar-heading">{months[month - 1]} {year}</h2><p>{manager ? 'Nama dan tanggal cuti disetujui. Alasan tidak ditampilkan di kalender.' : 'Permintaan menunggu belum muncul di kalender.'}</p></div><label>Bulan<select value={month} onChange={e => setMonth(Number(e.target.value))} disabled={blocked}>{months.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label></div>{loading && <p role="status">Memuat kalender?</p>}<div className="calendar-grid" role="group" aria-label={`Kalender ${months[month - 1]} ${year}`}><div className="calendar-week" aria-hidden="true">{['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'].map(day => <div key={day}>{day}</div>)}</div><div className="calendar-days">{monthCells(year!, month).map((day, index) => <div className={`calendar-cell ${day === today ? 'today' : ''} ${day ? '' : 'outside'}`} key={day ?? `blank${index}`}>{day && <><span className="day-number">{Number(day.slice(-2))}</span>{calendar?.items.filter(item => item.working_days.includes(day)).map(item => <div className="calendar-leave" key={item.id}><span>{manager ? item.employee.name : 'Cuti Anda'}</span></div>)}</>}</div>)}</div></div>{calendar?.items.length === 0 && !loading && <p className="calendar-empty">Belum ada cuti disetujui pada bulan ini.</p>}<div className="calendar-agenda"><h3>Ringkasan bulan ini</h3>{calendar?.items.map(item => <div key={item.id}><strong>{item.employee.name}</strong><span>{dateLabel(item.start_date)} - {dateLabel(item.end_date)} | {item.units} hari kerja</span></div>)}<p className="small">Blok kalender hanya menandai tanggal kerja pada snapshot pengajuan.</p></div></section>}
      <footer className="content-footer">LeaveFlow | Cuti tahunan | Kuota dan libur kantor adalah konfigurasi latihan</footer></main></div></div>;
}

export default function App() {
  const [auth, setAuth] = useState<Auth | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => {
    const expired = () => { setAuth(null); setError(''); };
    window.addEventListener('leaveflow:session-expired', expired);
    return () => window.removeEventListener('leaveflow:session-expired', expired);
  }, []);
  useEffect(() => { let active = true; setLoading(true); api<Auth>('/api/auth/me').then(value => { if (active) setAuth(value); }).catch(e => { if (active && (!(e instanceof ApiError) || e.status !== 401)) setError(message(e)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [retry]);
  const logout = useCallback(async () => { if (!auth) return; await api<void>('/api/auth/logout', { method: 'POST', csrf: auth.csrf_token }); setAuth(null); }, [auth]);
  if (loading) return <main className="startup" aria-busy="true"><p role="status">Memeriksa sesi LeaveFlow...</p></main>;
  if (error && !auth) return <main className="startup"><h1>Server belum dapat dihubungi</h1><p role="alert">{error}</p><button onClick={() => { setError(''); setRetry(value => value + 1); }}>Coba lagi</button></main>;
  return auth ? <Workspace key={auth.user.id} auth={auth} logout={logout} /> : <Login onAuth={setAuth} />;
}
