import { describe, expect, it } from 'vitest';
import { formatMoney, formatMoneyShort, formatRunway } from './format';

describe('formatMoney', () => {
  it.each([
    [0, '$0.00'],
    [5, '$0.05'],
    [99, '$0.99'],
    [100, '$1.00'],
    [123_456, '$1,234.56'],
    [4_800_000, '$48,000.00'],
    [150_000_000, '$1,500,000.00'],
    [-150, '-$1.50'],
    [-200_000, '-$2,000.00'],
  ])('%i cents -> %s', (cents, text) => {
    expect(formatMoney(cents)).toBe(text);
  });

  it('rejects non-integer input', () => {
    expect(() => formatMoney(1.5)).toThrow(RangeError);
  });
});

describe('formatMoneyShort', () => {
  it.each([
    [4_800_000, '$48k'],
    [150_000_000, '$1.5M'],
    [5_000, '$50'],
    [-4_850_000, '-$48.5k'],
  ])('%i cents -> %s', (cents, text) => {
    expect(formatMoneyShort(cents)).toBe(text);
  });
});

describe('formatRunway', () => {
  it('formats months', () => {
    expect(formatRunway(24)).toBe('24 months');
    expect(formatRunway(1)).toBe('1 month');
    expect(formatRunway(null)).toBe('Not burning');
  });
});
