import {
  Alert,
  Button,
  Container,
  Group,
  NumberInput,
  Select,
  Stack,
  Switch,
  Tabs,
  TextInput,
  Title,
} from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import {
  useDataFile,
  useDataFiles,
  useDeleteMod,
  useMods,
  useSaveMod,
  type EditorFile,
  type ModChange,
} from '../hooks/mods';
import { asText, commentFor, identityField, parseInput, pathKey, type Spec } from '../lib/mods';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// The data editor (M25 section 3): rivals, entrants, categories, cities, scenarios and
// balance.yaml as forms generated from the loader's schemas, each field with its YAML comment.
// Edits save as a named mod (saves/mods/<name>.yaml, changed values only) that a new game can
// use; the server validates the merged data exactly as the loader does.

type Edits = Map<string, ModChange>;
type Row = Record<string, unknown>;

interface Ctx {
  file: EditorFile;
  edits: Edits;
  setEdit: (path: string[], value: unknown) => void;
}

const SCALARS = new Set(['number', 'integer', 'string', 'boolean', 'enum']);
const TABLE_COLUMNS = 4; // scalar fields shown as columns in a list's table

function current(ctx: Ctx, path: string[], value: unknown): unknown {
  const edit = ctx.edits.get(pathKey(ctx.file.file, path));
  return edit ? edit.value : value;
}

function label(name: string): string {
  return name.replace(/_/g, ' ');
}

function Hint({
  ctx,
  path,
  description,
}: {
  ctx: Ctx;
  path: string[];
  description?: string | null;
}) {
  const note = commentFor(ctx.file.comments, path) ?? description ?? null;
  return note ? (
    <div className="tst-muted" style={{ fontSize: 11, maxWidth: 520 }}>
      {note}
    </div>
  ) : null;
}

function ScalarField({
  ctx,
  path,
  spec,
  value,
  name,
  description,
}: {
  ctx: Ctx;
  path: string[];
  spec: Spec;
  value: unknown;
  name: string;
  description?: string | null;
}) {
  const shown = current(ctx, path, value);
  const edited = ctx.edits.has(pathKey(ctx.file.file, path));
  const testId = `field-${path.join('/')}`;
  const title = (
    <span style={{ fontWeight: edited ? 600 : 400 }}>
      {label(name)}
      {edited ? ' (changed)' : ''}
    </span>
  );
  let input;
  if (spec.kind === 'boolean') {
    input = (
      <Switch
        label={title}
        checked={Boolean(shown)}
        onChange={(e) => ctx.setEdit(path, e.currentTarget.checked)}
        data-testid={testId}
      />
    );
  } else if (spec.kind === 'enum') {
    input = (
      <Select
        label={title}
        data={spec.options ?? []}
        value={shown === null || shown === undefined ? null : String(shown)}
        onChange={(v) => ctx.setEdit(path, v)}
        data-testid={testId}
        w={260}
      />
    );
  } else if (spec.kind === 'number' || spec.kind === 'integer') {
    input = (
      <NumberInput
        label={title}
        value={typeof shown === 'number' ? shown : ''}
        allowDecimal={spec.kind === 'number'}
        onChange={(v) => {
          if (v === '' && !spec.nullable) return;
          ctx.setEdit(path, v === '' ? null : Number(v));
        }}
        data-testid={testId}
        w={260}
      />
    );
  } else {
    input = (
      <TextInput
        label={title}
        value={asText(shown)}
        onChange={(e) => ctx.setEdit(path, parseInput(e.currentTarget.value, spec))}
        data-testid={testId}
        w={spec.kind === 'list' ? 420 : 260}
      />
    );
  }
  return (
    <div>
      {input}
      <Hint ctx={ctx} path={path} description={description} />
    </div>
  );
}

function RecordList({
  ctx,
  path,
  spec,
  items,
  field,
}: {
  ctx: Ctx;
  path: string[];
  spec: Spec;
  items: Row[];
  field: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const pathText = path.join('/');
  const scalars = (spec.fields ?? [])
    .filter((f) => SCALARS.has(f.spec.kind) && f.name !== field)
    .slice(0, TABLE_COLUMNS);
  const helper = createColumnHelper<GameTableFeatures, Row>();
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor((r) => String(r[field]), {
          id: 'identity',
          header: label(field),
          meta: { term: 'editor.item' },
          cell: ({ getValue }) => <strong>{getValue()}</strong>,
        }),
        ...scalars.map((f) =>
          helper.accessor(
            (r) =>
              asText(current(ctx, [...path, `@${field}=${String(r[field])}`, f.name], r[f.name])),
            {
              id: f.name,
              header: label(f.name),
              meta: { term: 'editor.value' },
              cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
            },
          ),
        ),
        helper.display({
          id: 'edit',
          header: '',
          meta: { term: 'editor.edit' },
          cell: ({ row }) => {
            const id = String(row.original[field]);
            const item = [...path, `@${field}=${id}`];
            return (
              <Button
                size="compact-xs"
                variant={open === id ? 'filled' : 'default'}
                onClick={() => setOpen(open === id ? null : id)}
                data-testid={`open-${item.join('/')}`}
              >
                {open === id ? 'Close' : 'Edit'}
              </Button>
            );
          },
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [field, open, ctx.edits, pathText],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: items });
  const chosen = open === null ? null : items.find((i) => String(i[field]) === open);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <DataTable
        table={table}
        label={label(path[path.length - 1] ?? 'items')}
        rowTestId="editor-row"
      />
      {chosen && (
        <div style={{ borderLeft: '2px solid var(--tst-border)', paddingLeft: 12 }}>
          <Fields ctx={ctx} path={[...path, `@${field}=${open}`]} spec={spec} value={chosen} />
        </div>
      )}
    </div>
  );
}

function Node({
  ctx,
  path,
  spec,
  value,
  name,
  description,
}: {
  ctx: Ctx;
  path: string[];
  spec: Spec;
  value: unknown;
  name: string;
  description?: string | null;
}) {
  if (SCALARS.has(spec.kind) || spec.kind === 'any') {
    if (value !== null && typeof value === 'object') return null; // shown as JSON elsewhere
    return (
      <ScalarField
        ctx={ctx}
        path={path}
        spec={spec}
        value={value}
        name={name}
        description={description}
      />
    );
  }
  if (spec.kind === 'list') {
    const items = Array.isArray(value) ? value : [];
    const item = spec.item ?? { kind: 'any' };
    const field = item.kind === 'object' ? identityField(items) : null;
    if (field) {
      return (
        <details>
          <summary style={{ cursor: 'pointer' }}>
            {label(name)} <span className="tst-muted">({items.length})</span>
          </summary>
          <Hint ctx={ctx} path={path} description={description} />
          <RecordList ctx={ctx} path={path} spec={item} items={items as Row[]} field={field} />
        </details>
      );
    }
    if (items.every((i) => i === null || typeof i !== 'object')) {
      return (
        <ScalarField
          ctx={ctx}
          path={path}
          spec={spec}
          value={items}
          name={name}
          description={description}
        />
      );
    }
    return (
      <div className="tst-muted" style={{ fontSize: 12 }}>
        {label(name)}: a list of {items.length} records without names, edited in the YAML file.
      </div>
    );
  }
  if (spec.kind === 'map' && value && typeof value === 'object') {
    const entries = Object.entries(value as Row);
    const inner = spec.value ?? { kind: 'any' };
    return (
      <details>
        <summary style={{ cursor: 'pointer' }}>{label(name)}</summary>
        <Hint ctx={ctx} path={path} description={description} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, paddingLeft: 12 }}>
          {entries.map(([k, v]) => (
            <Node key={k} ctx={ctx} path={[...path, k]} spec={inner} value={v} name={k} />
          ))}
        </div>
      </details>
    );
  }
  if (spec.kind === 'object' && value && typeof value === 'object') {
    return (
      <details>
        <summary style={{ cursor: 'pointer' }}>{label(name)}</summary>
        <Hint ctx={ctx} path={path} description={description} />
        <div style={{ paddingLeft: 12 }}>
          <Fields ctx={ctx} path={path} spec={spec} value={value as Row} />
        </div>
      </details>
    );
  }
  return null;
}

function Fields({ ctx, path, spec, value }: { ctx: Ctx; path: string[]; spec: Spec; value: Row }) {
  const fields = (spec.fields ?? []).filter((f) => f.name in value);
  const scalars = fields.filter((f) => SCALARS.has(f.spec.kind) || f.spec.kind === 'any');
  const nested = fields.filter((f) => !scalars.includes(f));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {scalars.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {scalars.map((f) => (
            <Node
              key={f.name}
              ctx={ctx}
              path={[...path, f.name]}
              spec={f.spec}
              value={value[f.name]}
              name={f.name}
              description={f.description}
            />
          ))}
        </div>
      )}
      {nested.map((f) => (
        <Node
          key={f.name}
          ctx={ctx}
          path={[...path, f.name]}
          spec={f.spec}
          value={value[f.name]}
          name={f.name}
          description={f.description}
        />
      ))}
    </div>
  );
}

function FileForm({
  file,
  mod,
  spoilers,
  ctx,
}: {
  file: string;
  mod: string | null;
  spoilers: boolean;
  ctx: Omit<Ctx, 'file'>;
}) {
  const query = useDataFile(file, mod, spoilers);
  if (query.isPending) return <Loading />;
  if (query.error || !query.data)
    return <LoadError title="Could not load the file" error={query.error} />;
  const f = query.data;
  return (
    <div data-testid={`editor-form-${file}`}>
      <Fields ctx={{ ...ctx, file: f }} path={[]} spec={f.spec as Spec} value={f.value as Row} />
    </div>
  );
}

export function DataEditorScreen() {
  // "Show spoiler fields" (PM ruling 2026-11-08): off by default; on, the editor shows and
  // edits the data files' fields that the game keeps hidden in play.
  const [spoilers, setSpoilers] = useState(false);
  const mods = useMods(spoilers);
  const files = useDataFiles();
  const save = useSaveMod();
  const remove = useDeleteMod();
  const [name, setName] = useState('');
  const [loaded, setLoaded] = useState<string | null>(null); // the mod the edits started from
  const [description, setDescription] = useState('');
  const [edits, setEdits] = useState<Edits>(new Map());
  const [file, setFile] = useState<string | null>(null);
  const tab = file ?? files.data?.[0]?.file ?? null;

  const open = (modName: string | null) => {
    const m = mods.data?.find((x) => x.name === modName);
    setLoaded(m ? m.name : null);
    setName(m ? m.name : '');
    setDescription(m?.description ?? '');
    setEdits(new Map((m?.changes ?? []).map((c) => [pathKey(c.file, c.path), c])));
    save.reset();
  };
  const setEdit = (path: string[], value: unknown) => {
    if (!tab) return;
    setEdits((prev) => new Map(prev).set(pathKey(tab, path), { file: tab, path, value }));
  };
  const valid = /^[a-z0-9][a-z0-9_-]{0,47}$/.test(name);

  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={2}>Data editor</Title>
          <Button component={Link} to="/" variant="default">
            Main menu
          </Button>
        </Group>
        <Alert color="blue">
          Edit rivals, markets, cities, scenarios and balance values, then save them as a named mod.
          A new game can start with a mod; the save keeps its own copy, so editing the mod later
          never changes it. Modded games earn no achievements and are flagged on the Saves list and
          in the Hall of Fame. Values the game keeps hidden in play are shown only with Show spoiler
          fields on.
        </Alert>
        <Panel title="Mod" testId="mod-panel">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
            <Select
              label="Open a mod"
              placeholder="A new mod"
              data={(mods.data ?? []).map((m) => m.name)}
              value={loaded}
              onChange={open}
              clearable
              data-testid="mod-open"
              w={220}
            />
            <TextInput
              label="Name"
              description="Lower-case letters, digits, - and _"
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              error={name !== '' && !valid ? 'Not a valid name' : undefined}
              data-testid="mod-name-input"
              w={220}
            />
            <TextInput
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
              data-testid="mod-description-input"
              w={320}
            />
            <Button
              disabled={!valid}
              loading={save.isPending}
              onClick={() =>
                save.mutate(
                  { name, description, changes: [...edits.values()], spoilers },
                  { onSuccess: (m) => setLoaded(m.name) },
                )
              }
              data-testid="mod-save"
            >
              Save mod
            </Button>
            <Switch
              label="Show spoiler fields"
              description="Values the game keeps hidden in play"
              checked={spoilers}
              onChange={(e) => setSpoilers(e.currentTarget.checked)}
              data-testid="spoiler-toggle"
            />
            {loaded && (
              <Button
                variant="default"
                color="warn"
                onClick={() => remove.mutate(loaded, { onSuccess: () => open(null) })}
                data-testid="mod-delete"
              >
                Delete mod
              </Button>
            )}
          </div>
          {save.error && (
            <Alert color="red" mt="sm" title="The mod was not saved" data-testid="mod-error">
              {save.error.message}
            </Alert>
          )}
          {save.isSuccess && !save.isPending && (
            <Alert color="green" mt="sm" data-testid="mod-saved">
              Saved {save.data.name}: {save.data.changes.length} changed value
              {save.data.changes.length === 1 ? '' : 's'}.
            </Alert>
          )}
          <div
            className="tst-muted"
            style={{ fontSize: 12, marginTop: 8 }}
            data-testid="mod-changes"
          >
            {edits.size} change{edits.size === 1 ? '' : 's'}
            {edits.size > 0 && (
              <>
                {': '}
                {[...edits.values()]
                  .map((c) => `${c.file} ${c.path.join(' › ')} = ${asText(c.value)}`)
                  .join('; ')}{' '}
                <Button size="compact-xs" variant="subtle" onClick={() => setEdits(new Map())}>
                  Clear
                </Button>
              </>
            )}
          </div>
        </Panel>
        {files.isPending ? (
          <Loading />
        ) : files.error || !files.data ? (
          <LoadError title="Could not load the data files" error={files.error} />
        ) : (
          <Tabs value={tab} onChange={setFile} keepMounted={false}>
            <Tabs.List>
              {files.data.map((f) => (
                <Tabs.Tab key={f.file} value={f.file} data-testid={`editor-file-${f.file}`}>
                  {f.label}
                </Tabs.Tab>
              ))}
            </Tabs.List>
            {files.data.map((f) => (
              <Tabs.Panel key={f.file} value={f.file} pt="md">
                <FileForm file={f.file} mod={loaded} spoilers={spoilers} ctx={{ edits, setEdit }} />
              </Tabs.Panel>
            ))}
          </Tabs>
        )}
      </Stack>
    </Container>
  );
}
