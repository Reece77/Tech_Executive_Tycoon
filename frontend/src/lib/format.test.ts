import { describe, expect, it } from 'vitest';
import {
  formatBpPercent,
  formatMoney,
  formatMoneyShort,
  formatMoneyWhole,
  formatMonths,
  formatRatio,
  formatRunway,
  humanize,
  parseDollars,
} from './format';

describe('display helpers', () => {
  it('formats whole dollars', () => {
    expect(formatMoneyWhole(25_140_000)).toBe('$251,400');
    expect(formatMoneyWhole(983_350)).toBe('$9,834');
    expect(formatMoneyWhole(-150)).toBe('-$2');
  });

  it('formats basis points, ratios and months', () => {
    expect(formatBpPercent(50)).toBe('0.50%');
    expect(formatBpPercent(1000)).toBe('10.00%');
    expect(formatRatio(1.0438)).toBe('1.04×');
    expect(formatMonths(1)).toBe('1 month');
    expect(formatMonths(4)).toBe('4 months');
    expect(humanize('job_post')).toBe('Job post');
  });
});

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

describe('parseDollars', () => {
  it.each([
    ['40', 4000],
    ['$1,000.5', 100050],
    ['0.35', 35],
    [' 12 ', 1200],
    ['abc', 0],
    ['1.234', 0],
    ['', 0],
  ])('%s -> %i cents', (text, cents) => {
    expect(parseDollars(text)).toBe(cents);
  });
});
