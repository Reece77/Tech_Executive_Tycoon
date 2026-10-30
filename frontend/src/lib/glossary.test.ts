/// <reference types="node" />
// M7b sub-task 4: every KPI label and table column header has a glossary definition. The test
// reads the component sources and backend/data/glossary.yaml, so a new KPI tile or column
// without an entry fails here, not as a silent missing tooltip.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..');
const DATA = resolve(__dirname, '../../../backend/data');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'api' ? [] : files(path);
    return /\.tsx?$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

function glossary(): Set<string> {
  const text = readFileSync(join(DATA, 'glossary.yaml'), 'utf8');
  return new Set([...text.matchAll(/^ {2}([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)?):/gm)].map((m) => m[1]));
}

interface Found {
  file: string;
  term: string | null; // null: a column whose id is computed and has no meta.term
  header: string;
}

/** Every column definition's glossary term: meta.term, else its id, else its accessor key. */
function columnTerms(file: string, source: string): Found[] {
  const starts = [...source.matchAll(/helper\.(accessor|display)\(/g)].map((m) => m.index);
  return starts.map((start, i) => {
    const chunk = source.slice(start, starts[i + 1] ?? start + 800);
    const header = /header:\s*('([^']*)'|"([^"]*)"|[^,\n]+)/.exec(chunk);
    const headerText = header ? (header[2] ?? header[3] ?? header[1]) : '';
    const meta = /meta:\s*\{\s*term:\s*'([^']+)'/.exec(chunk);
    const id = /\bid:\s*'([^']+)'/.exec(chunk);
    const accessor = /^helper\.accessor\(\s*'([^']+)'/.exec(chunk);
    return {
      file,
      term: meta?.[1] ?? id?.[1] ?? accessor?.[1] ?? null,
      header: headerText.trim(),
    };
  });
}

describe('glossary', () => {
  const terms = glossary();
  const sources = files(SRC).map((f) => [f.slice(SRC.length + 1), readFileSync(f, 'utf8')]);

  it('has a definition for every KPI tile', () => {
    const missing: string[] = [];
    let tiles = 0;
    for (const [file, source] of sources) {
      for (const m of source.matchAll(/<KpiTile\b[^>]*?\bterm="([^"]+)"/gs)) {
        tiles += 1;
        if (!terms.has(m[1])) missing.push(`${file}: ${m[1]}`);
      }
    }
    expect(tiles).toBeGreaterThan(30);
    expect(missing).toEqual([]);
  });

  it('has a definition for every table column header', () => {
    const problems: string[] = [];
    let columns = 0;
    for (const [file, source] of sources) {
      for (const col of columnTerms(file, source)) {
        if (col.header === "''" || col.header === '') continue; // no header text to explain
        columns += 1;
        if (col.term === null) problems.push(`${file}: a computed column id needs meta.term`);
        else if (!terms.has(col.term)) problems.push(`${file}: ${col.term} (${col.header})`);
      }
    }
    expect(columns).toBeGreaterThan(100);
    expect(problems).toEqual([]);
  });

  it('wraps every hand-built table header in a Term', () => {
    const bare: string[] = [];
    for (const [file, source] of sources) {
      for (const m of source.matchAll(/<th\b[^>]*>\s*([A-Za-z][^<{]*?)\s*<\/th>/g)) {
        bare.push(`${file}: ${m[1]}`);
      }
    }
    expect(bare).toEqual([]);
  });

  it('has a definition for every Term and statement line', () => {
    const missing: string[] = [];
    for (const [file, source] of sources) {
      for (const m of source.matchAll(/<Term term="([^"]+)"/g)) {
        if (!terms.has(m[1])) missing.push(`${file}: ${m[1]}`);
      }
    }
    for (const line of ['revenue', 'gross', 'opex', 'interest', 'tax', 'net']) {
      if (!terms.has(`line.${line}`)) missing.push(`line.${line}`);
    }
    const accounts = readFileSync(join(DATA, 'accounts.yaml'), 'utf8');
    for (const m of accounts.matchAll(
      /code: (\d{4}_[a-z_]+), name: [^,]+, type: (revenue|expense)/g,
    )) {
      if (!terms.has(`account.${m[1]}`)) missing.push(`account.${m[1]}`);
    }
    expect(missing).toEqual([]);
  });
});
