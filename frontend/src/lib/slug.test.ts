import { describe, expect, it } from 'vitest';
import { toSaveSlug } from './slug';

describe('toSaveSlug', () => {
  it.each([
    ['Garage Test', 'garage-test'],
    ['  Acme, Inc.  ', 'acme-inc'],
    ['Café Ünicode', 'cafe-unicode'],
    ['!!!', ''],
    ['a'.repeat(70), 'a'.repeat(64)],
  ])('%s -> %s', (name, slug) => {
    expect(toSaveSlug(name)).toBe(slug);
  });
});
