export function dateLabel(value: string): string {
  return new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value + 'T00:00:00Z'));
}
export function monthCells(year: number, month: number): (string | null)[] {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const prefix = (first.getUTCDay() + 6) % 7;
  const length = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return [...Array<null>(prefix).fill(null), ...Array.from({ length }, (_, i) => `${year}-${String(month).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`)];
}
export function nextWorkingDate(day: string): string {
  const date = new Date(day + 'T00:00:00Z');
  while (date.getUTCDay() === 0 || date.getUTCDay() === 6) date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}
