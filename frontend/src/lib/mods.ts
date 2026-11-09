// The data editor's paths (M25 section 3): a change path is a list of segments, a key or
// `@<field>=<value>` for a list item. Display and form plumbing only; the server validates.

export type Spec = {
  kind: string;
  fields?: { name: string; description?: string | null; required?: boolean; spec: Spec }[];
  item?: Spec;
  value?: Spec;
  options?: string[];
  nullable?: boolean;
};

const IDENTITY = ['key', 'id', 'name', 'segment', 'region'] as const;

/** The field that identifies every item of a list of records, if one does. */
export function identityField(items: unknown[]): string | null {
  if (items.length === 0 || !items.every((i) => i !== null && typeof i === 'object')) return null;
  for (const field of IDENTITY) {
    const values = items.map((i) => (i as Record<string, unknown>)[field]);
    if (
      values.every((v) => v !== undefined && v !== null) &&
      new Set(values.map(String)).size === values.length
    )
      return field;
  }
  return null;
}

export function pathKey(file: string, path: string[]): string {
  return `${file}|${path.join('/')}`;
}

/** The comment for a path: its own inline comment, else the field's header note. */
export function commentFor(comments: Record<string, string>, path: string[]): string | null {
  const dotted = path.map((s) => (s.startsWith('@') ? '[]' : s)).join('.');
  const field = [...path].reverse().find((s) => !s.startsWith('@'));
  return comments[dotted] ?? (field ? (comments[`field:${field}`] ?? null) : null);
}

/** A typed value from an input's text, by the field's kind. */
export function parseInput(text: string, spec: Spec): unknown {
  if (text === '' && spec.nullable) return null;
  if (spec.kind === 'integer') return Number.parseInt(text, 10);
  if (spec.kind === 'number') return Number(text);
  if (spec.kind === 'list') {
    const parts = text
      .split(',')
      .map((p) => p.trim())
      .filter((p) => p !== '');
    return spec.item && (spec.item.kind === 'number' || spec.item.kind === 'integer')
      ? parts.map(Number)
      : parts;
  }
  return text;
}

export function asText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(String).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
