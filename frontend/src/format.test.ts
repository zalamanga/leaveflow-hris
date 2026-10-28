import { describe, expect, it } from 'vitest';
import { dateLabel, monthCells, nextWorkingDate } from './format';
describe('office date presentation', () => {
  it('keeps a plain calendar date without local timezone shifts', () => { expect(dateLabel('2026-11-02')).toBe('2 Nov 2026'); });
  it('starts Monday-first calendars with blank cells before Sunday', () => { const cells = monthCells(2026, 11); expect(cells.slice(0, 6)).toEqual(Array(6).fill(null)); expect(cells[6]).toBe('2026-11-01'); expect(cells.at(-1)).toBe('2026-11-30'); });
  it('includes leap-day and preserves Monday as column one', () => { expect(monthCells(2024, 2).at(-1)).toBe('2024-02-29'); expect(monthCells(2026, 6)[0]).toBe('2026-06-01'); });
  it('advances weekend suggestions across a year boundary', () => { expect(nextWorkingDate('2022-12-31')).toBe('2023-01-02'); });
});
