export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function api<T>(path: string, options: { method?: string; body?: unknown; csrf?: string } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? 'GET', credentials: 'same-origin',
    headers: { ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(options.csrf ? { 'X-CSRF-Token': options.csrf } : {}) },
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login' && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('leaveflow:session-expired'));
    }
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    throw new ApiError(response.status, typeof detail === 'string' ? detail : response.status === 422 ? 'Periksa isian dan rentang tanggal, lalu coba lagi.' : `Permintaan gagal (${response.status}). Coba muat ulang.`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
