/// <reference types="node" />
// M7c sub-task 4: the playtest found a People column that showed "From M3" in every row, a
// placeholder from M1c that was never filled. No screen may show milestone placeholder text.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'api' ? [] : files(path);
    return /\.tsx$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

describe('placeholders', () => {
  it('no screen shows milestone placeholder text such as "From M3"', () => {
    const found = files(SRC).flatMap((f) =>
      [...readFileSync(f, 'utf8').matchAll(/>\s*(?:From|Coming in|Until) M\d+[a-z]?\s*</g)].map(
        (m) => `${f.slice(SRC.length + 1)}: ${m[0]}`,
      ),
    );
    expect(found).toEqual([]);
  });
});
