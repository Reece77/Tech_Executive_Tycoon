import {
  Alert,
  Button,
  Checkbox,
  Container,
  Group,
  NativeSelect,
  NumberInput,
  Stack,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import {
  exportCustom,
  openStart,
  useCheck,
  useCustomScenarios,
  useDifficulty,
  useEditorOptions,
  useImportCustom,
  usePreview,
  useSaveCustom,
  useStartCustomGame,
  useStartDifficulty,
  type CustomSpec,
  type EditorOptions,
} from '../hooks/editor';
import { formatMoneyWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// The scenario editor (M52, formulas.md 66.1-66.2, ADR-0026): open a blank start or any
// scenario, change the company, rivals, markets, world and rules, and save it as a custom
// scenario file (saves/scenarios). Every field shows its range from balance.yaml's editor.*,
// and the server's refusals are shown with their reasons. No game value is computed here:
// the preview and the difficulty estimate are the server's.

type Ranges = EditorOptions['ranges'];
type Overrides = NonNullable<CustomSpec['overrides']>;
type Rival = NonNullable<Overrides['rivals']>[string];
type Market = NonNullable<Overrides['markets']>[string];

const rangeText = (ranges: Ranges, key: string, unit = '') => {
  const r = ranges[key];
  return r ? `Range ${r.lo.toLocaleString()} to ${r.hi.toLocaleString()}${unit}` : undefined;
};

function Num({
  label,
  value,
  onChange,
  ranges,
  range,
  step,
  testId,
  disabled,
  unit,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  ranges: Ranges;
  range: string;
  step?: number;
  testId?: string;
  disabled?: boolean;
  unit?: string;
}) {
  return (
    <NumberInput
      label={label}
      size="xs"
      value={value ?? ''}
      step={step}
      decimalScale={step !== undefined && step < 1 ? 3 : undefined}
      description={rangeText(ranges, range, unit)}
      onChange={(v) => onChange(v === '' ? null : Number(v))}
      disabled={disabled}
      data-testid={testId}
      style={{ width: 200 }}
    />
  );
}

function Cell({
  value,
  onChange,
  step,
  testId,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  testId?: string;
}) {
  return (
    <NumberInput
      size="xs"
      value={value}
      step={step}
      decimalScale={step !== undefined && step < 1 ? 3 : undefined}
      onChange={(v) => onChange(v === '' ? 0 : Number(v))}
      data-testid={testId}
      style={{ width: 110 }}
    />
  );
}

type Staff = NonNullable<CustomSpec['staff']>[number];
type Product = NonNullable<CustomSpec['products']>[number];
type Lead = NonNullable<CustomSpec['research']>[number];
const staffHelper = createColumnHelper<GameTableFeatures, Staff>();
const productHelper = createColumnHelper<GameTableFeatures, Product>();
const leadHelper = createColumnHelper<GameTableFeatures, Lead>();
type RivalRow = { name: string; categories: string; o: Rival };
const rivalHelper = createColumnHelper<GameTableFeatures, RivalRow>();
type MarketRow = { key: string; label: string; editable: boolean; o: Market };
const marketHelper = createColumnHelper<GameTableFeatures, MarketRow>();

function CompanySection({
  spec,
  set,
  opts,
}: {
  spec: CustomSpec;
  set: (s: CustomSpec) => void;
  opts: EditorOptions;
}) {
  const r = opts.ranges;
  const staff = spec.staff ?? [];
  const products = spec.products ?? [];
  const leads = spec.research ?? [];
  const setStaff = (i: number, patch: Partial<Staff>) =>
    set({ ...spec, staff: staff.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const setProduct = (i: number, patch: Partial<Product>) =>
    set({ ...spec, products: products.map((p, j) => (j === i ? { ...p, ...patch } : p)) });
  const setLead = (i: number, lead: number) =>
    set({ ...spec, research: leads.map((l, j) => (j === i ? { ...l, lead } : l)) });
  const staffColumns = useMemo(
    () =>
      staffHelper.columns([
        staffHelper.accessor('role', { header: 'Role', meta: { term: 'editor.role' } }),
        staffHelper.accessor('level', { header: 'Level', meta: { term: 'editor.level' } }),
        staffHelper.accessor('unit', {
          header: 'Team',
          meta: { term: 'editor.team' },
          cell: ({ row }) => row.original.unit ?? '—',
        }),
        staffHelper.accessor('count', {
          header: 'People',
          meta: { term: 'editor.people' },
          cell: ({ row }) => (
            <Cell
              value={row.original.count}
              onChange={(v) => setStaff(row.index, { count: v })}
              testId={`staff-count-${row.index}`}
            />
          ),
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec],
  );
  const productColumns = useMemo(
    () =>
      productHelper.columns([
        productHelper.accessor('name', { header: 'Product', meta: { term: 'editor.product' } }),
        productHelper.accessor('category', {
          header: 'Category',
          meta: { term: 'editor.category' },
        }),
        productHelper.accessor('quality', {
          header: 'Quality',
          meta: { term: 'editor.quality' },
          cell: ({ row }) => (
            <Cell
              value={row.original.quality}
              onChange={(v) => setProduct(row.index, { quality: v })}
              testId={`product-quality-${row.index}`}
            />
          ),
        }),
        productHelper.accessor('features', {
          header: 'Features',
          meta: { term: 'editor.features' },
          cell: ({ row }) => (
            <Cell
              value={row.original.features}
              onChange={(v) => setProduct(row.index, { features: v })}
            />
          ),
        }),
        productHelper.accessor('brand', {
          header: 'Brand',
          meta: { term: 'editor.brand' },
          cell: ({ row }) => (
            <Cell
              value={row.original.brand}
              onChange={(v) => setProduct(row.index, { brand: v })}
            />
          ),
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec],
  );
  const leadColumns = useMemo(
    () =>
      leadHelper.columns([
        leadHelper.accessor('domain', { header: 'Domain', meta: { term: 'editor.domain' } }),
        leadHelper.accessor('lead', {
          header: 'Lead',
          meta: { term: 'editor.lead' },
          cell: ({ row }) => (
            <Cell value={row.original.lead} onChange={(v) => setLead(row.index, v)} />
          ),
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec],
  );
  const staffTable = useTable({
    features: gameTableFeatures,
    columns: staffColumns,
    data: staff,
    getRowId: (x, i) => `${x.role}-${x.level}-${i}`,
  });
  const productTable = useTable({
    features: gameTableFeatures,
    columns: productColumns,
    data: products,
    getRowId: (x) => x.name,
  });
  const leadTable = useTable({
    features: gameTableFeatures,
    columns: leadColumns,
    data: leads,
    getRowId: (x) => x.domain,
  });
  const debt = (spec.loans ?? []).reduce((t, l) => t + l.principal_dollars, 0);
  return (
    <Panel title="Company" testId="editor-company">
      <Group align="flex-start" wrap="wrap">
        <TextInput
          size="xs"
          label="Company name"
          value={spec.overrides?.company?.name ?? ''}
          onChange={(e) =>
            set({
              ...spec,
              overrides: {
                ...spec.overrides,
                company: { name: e.currentTarget.value || null },
              },
            })
          }
          maxLength={80}
          style={{ width: 220 }}
          data-testid="editor-company-name"
        />
        <Num
          label="Start year"
          value={spec.year}
          onChange={(v) => set({ ...spec, year: v ?? spec.year })}
          ranges={r}
          range="start_years"
          testId="editor-year"
        />
        <Num
          label="Cash ($)"
          value={spec.cash_dollars}
          onChange={(v) => set({ ...spec, cash_dollars: v ?? 0 })}
          ranges={r}
          range="cash_dollars"
          testId="editor-cash"
        />
        <Num
          label="Founder's age"
          value={spec.founder_age}
          onChange={(v) => set({ ...spec, founder_age: v })}
          ranges={r}
          range="founder_age"
        />
        <NativeSelect
          size="xs"
          label="Home city"
          value={spec.hq_city ?? ''}
          onChange={(e) => set({ ...spec, hq_city: e.currentTarget.value || null })}
          data={[
            { value: '', label: 'Default' },
            ...opts.cities.map((c) => ({ value: c.key, label: c.label })),
          ]}
          style={{ width: 200 }}
        />
      </Group>
      <p className="tst-muted" style={{ fontSize: 12 }} data-testid="editor-debt">
        Debt {formatMoneyWhole(debt * 100)} · {rangeText(r, 'debt_dollars', ' dollars')}
      </p>
      <h3 className="tst-ptitle">Staff · {rangeText(r, 'staff_count', ' a line')}</h3>
      <DataTable table={staffTable} label="Staff" />
      <h3 className="tst-ptitle">Products · quality {rangeText(r, 'quality')}</h3>
      <DataTable table={productTable} label="Products" />
      <h3 className="tst-ptitle">Research · {rangeText(r, 'research_lead', ' points')}</h3>
      <DataTable table={leadTable} label="Research" />
      {(spec.fabs ?? []).length > 0 && (
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Fabs running at the start:{' '}
          {(spec.fabs ?? []).map((f) => `${f.node} in ${humanize(f.region)}`).join(', ')}
        </p>
      )}
    </Panel>
  );
}

function RivalsSection({
  spec,
  set,
  opts,
}: {
  spec: CustomSpec;
  set: (s: CustomSpec) => void;
  opts: EditorOptions;
}) {
  const [all, setAll] = useState(false);
  const r = opts.ranges;
  const mine = new Set((spec.products ?? []).map((p) => p.category));
  const rivals = spec.overrides?.rivals ?? {};
  const setRival = (name: string, patch: Partial<Rival>) => {
    const next = { ...(rivals[name] ?? {}), ...patch };
    set({ ...spec, overrides: { ...spec.overrides, rivals: { ...rivals, [name]: next } } });
  };
  const rows: RivalRow[] = opts.incumbents
    .filter((i) => all || i.categories.some((c) => mine.has(c)) || rivals[i.name])
    .map((i) => ({ name: i.name, categories: i.categories.join(', '), o: rivals[i.name] ?? {} }));
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', { header: 'Incumbent', meta: { term: 'editor.incumbent' } }),
        rivalHelper.accessor('categories', {
          header: 'Categories',
          meta: { term: 'editor.categories' },
        }),
        rivalHelper.display({
          id: 'present',
          header: 'Present',
          meta: { term: 'editor.present' },
          cell: ({ row }) => (
            <Checkbox
              checked={row.original.o.present ?? true}
              onChange={(e) => setRival(row.original.name, { present: e.currentTarget.checked })}
              data-testid={`rival-present-${row.original.name}`}
            />
          ),
        }),
        rivalHelper.display({
          id: 'cash',
          header: 'Cash ×',
          meta: { term: 'editor.rival_cash' },
          cell: ({ row }) => (
            <Cell
              value={row.original.o.cash_mult ?? 1}
              step={0.05}
              onChange={(v) => setRival(row.original.name, { cash_mult: v })}
            />
          ),
        }),
        rivalHelper.display({
          id: 'quality',
          header: 'Quality +',
          meta: { term: 'editor.rival_quality' },
          cell: ({ row }) => (
            <Cell
              value={row.original.o.quality_delta ?? 0}
              onChange={(v) => setRival(row.original.name, { quality_delta: v })}
            />
          ),
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (x) => x.name,
  });
  return (
    <Panel
      title="Rivals"
      testId="editor-rivals"
      action={
        <Checkbox
          label="Every incumbent"
          checked={all}
          onChange={(e) => setAll(e.currentTarget.checked)}
        />
      }
    >
      <p className="tst-muted" style={{ fontSize: 12 }}>
        Cash × {rangeText(r, 'rival_cash_mult_range')}; quality +{' '}
        {rangeText(r, 'rival_quality_range', ' points')}. An incumbent gone by the start year is
        left as it is.
      </p>
      <DataTable table={table} label="Rivals" />
    </Panel>
  );
}

function MarketsSection({
  spec,
  set,
  opts,
}: {
  spec: CustomSpec;
  set: (s: CustomSpec) => void;
  opts: EditorOptions;
}) {
  const r = opts.ranges;
  const markets = spec.overrides?.markets ?? {};
  const setMarket = (key: string, patch: Partial<Market>) =>
    set({
      ...spec,
      overrides: {
        ...spec.overrides,
        markets: { ...markets, [key]: { ...(markets[key] ?? {}), ...patch } },
      },
    });
  const rows: MarketRow[] = opts.categories.map((c) => ({
    key: c.key,
    label: c.label,
    editable: c.market_editable,
    o: markets[c.key] ?? {},
  }));
  const columns = useMemo(
    () =>
      marketHelper.columns([
        marketHelper.accessor('label', { header: 'Category', meta: { term: 'editor.category' } }),
        marketHelper.display({
          id: 'mult',
          header: 'Market ×',
          meta: { term: 'editor.market_mult' },
          cell: ({ row }) =>
            row.original.editable ? (
              <Cell
                value={row.original.o.market_mult ?? 1}
                step={0.05}
                onChange={(v) => setMarket(row.original.key, { market_mult: v })}
                testId={`market-mult-${row.original.key}`}
              />
            ) : (
              <span className="tst-muted">its own data</span>
            ),
        }),
        marketHelper.display({
          id: 'growth',
          header: 'Growth +',
          meta: { term: 'editor.growth_delta' },
          cell: ({ row }) =>
            row.original.editable ? (
              <Cell
                value={row.original.o.growth_delta ?? 0}
                step={0.01}
                onChange={(v) => setMarket(row.original.key, { growth_delta: v })}
              />
            ) : (
              '—'
            ),
        }),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (x) => x.key,
  });
  return (
    <Panel title="Markets" testId="editor-markets">
      <p className="tst-muted" style={{ fontSize: 12 }}>
        Market × {rangeText(r, 'market_mult_range')}; growth +{' '}
        {rangeText(r, 'growth_delta_range', ' a year')}.
      </p>
      <DataTable table={table} label="Markets" />
    </Panel>
  );
}

function WorldRulesSection({
  spec,
  set,
  opts,
}: {
  spec: CustomSpec;
  set: (s: CustomSpec) => void;
  opts: EditorOptions;
}) {
  const r = opts.ranges;
  const world = spec.overrides?.world ?? {};
  const rules = spec.overrides?.rules ?? {};
  const macro = spec.year >= opts.macro_from_year;
  const goal = spec.goal;
  const setWorld = (patch: Partial<typeof world>) =>
    set({ ...spec, overrides: { ...spec.overrides, world: { ...world, ...patch } } });
  const chosen = rules.challenges ?? [];
  const toggle = (key: string) =>
    set({
      ...spec,
      overrides: {
        ...spec.overrides,
        rules: {
          challenges: chosen.includes(key) ? chosen.filter((c) => c !== key) : [...chosen, key],
        },
      },
    });
  return (
    <Panel title="World and rules" testId="editor-world">
      <Group align="flex-start" wrap="wrap">
        <NativeSelect
          size="xs"
          label="Eras"
          value={world.eras ?? 'historical'}
          onChange={(e) => setWorld({ eras: e.currentTarget.value as 'historical' | 'seeded' })}
          data={['historical', 'seeded']}
          style={{ width: 160 }}
        />
        <Num
          label="Consumer confidence"
          value={world.confidence}
          onChange={(v) => setWorld({ confidence: v })}
          ranges={r}
          range="confidence"
          disabled={!macro}
        />
        <Num
          label="Base rate (%)"
          value={world.policy_rate_pct}
          onChange={(v) => setWorld({ policy_rate_pct: v })}
          ranges={r}
          range="policy_rate_pct"
          step={0.25}
          disabled={!macro}
        />
        <NativeSelect
          size="xs"
          label="Campaign length"
          value={spec.length ?? 'standard'}
          onChange={(e) =>
            set({ ...spec, length: e.currentTarget.value as 'standard' | 'dynasty' | 'endless' })
          }
          data={opts.lengths.map((l) => ({
            value: l,
            label: l === 'endless' ? 'Sandbox, no end' : humanize(l),
          }))}
          style={{ width: 180 }}
          data-testid="editor-length"
        />
      </Group>
      {!macro && (
        <p className="tst-muted" style={{ fontSize: 12 }}>
          The macro and commodity prices are history before {opts.macro_from_year}: editable for a
          later start.
        </p>
      )}
      <h3 className="tst-ptitle">Challenges</h3>
      <Group>
        {opts.challenges.map((c) => (
          <Checkbox
            key={c.key}
            label={c.label}
            checked={chosen.includes(c.key)}
            onChange={() => toggle(c.key)}
          />
        ))}
      </Group>
      <h3 className="tst-ptitle">Goal</h3>
      {goal ? (
        <Group align="flex-end">
          <TextInput
            size="xs"
            label="Goal"
            value={goal.text}
            onChange={(e) => set({ ...spec, goal: { ...goal, text: e.currentTarget.value } })}
            style={{ width: 320 }}
          />
          <Num
            label="Deadline year"
            value={spec.deadline?.[0]}
            onChange={(v) => set({ ...spec, deadline: [v ?? spec.year, spec.deadline?.[1] ?? 12] })}
            ranges={r}
            range="deadline_years"
            unit=" years after the start"
          />
          <Button
            size="xs"
            variant="default"
            onClick={() => set({ ...spec, goal: null, deadline: null })}
            data-testid="editor-no-goal"
          >
            No goal
          </Button>
        </Group>
      ) : (
        <p className="tst-muted" style={{ fontSize: 13 }}>
          No goal: open play.
        </p>
      )}
    </Panel>
  );
}

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/yaml' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Section({ children }: { children: ReactNode }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>;
}

export function EditorScreen() {
  const opts = useEditorOptions();
  const saved = useCustomScenarios();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [spec, setSpec] = useState<CustomSpec | null>(null);
  const [existing, setExisting] = useState(false); // loaded from a saved file
  const [startKey, setStartKey] = useState(
    params.get('custom') ?? params.get('start') ?? 'blank_2010',
  );
  const [openError, setOpenError] = useState<string | null>(null);
  const [saveAs, setSaveAs] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [company, setCompany] = useState('');
  const [seed, setSeed] = useState<number | ''>('');
  const [jobId, setJobId] = useState<string | null>(null);
  const check = useCheck(spec);
  const save = useSaveCustom();
  const imp = useImportCustom();
  const preview = usePreview();
  const startDifficulty = useStartDifficulty();
  const difficulty = useDifficulty(jobId);
  const startGame = useStartCustomGame();
  const fileInput = useRef<HTMLInputElement>(null);

  const open = async (key: string, fromFile: boolean) => {
    setOpenError(null);
    setMessage(null);
    try {
      const s = await openStart(key, fromFile);
      setSpec(s);
      setExisting(fromFile);
      setSaveAs(s.key);
      setCompany(s.overrides?.company?.name ?? '');
      setJobId(null);
      preview.reset();
      setParams(fromFile ? { custom: key } : { start: key }, { replace: true });
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : String(e));
    }
  };
  // The start the URL names, opened once; an edit or another Open replaces it.
  const initialCustom = params.get('custom');
  const initial = useQuery({
    queryKey: ['editor', 'initial', initialCustom, params.get('start')],
    queryFn: () =>
      openStart(initialCustom ?? params.get('start') ?? 'blank_2010', initialCustom !== null),
    staleTime: Infinity,
    enabled: spec === null,
  });
  if (spec === null && initial.data) {
    setSpec(initial.data);
    setExisting(initialCustom !== null);
    setSaveAs(initial.data.key);
    setCompany(initial.data.overrides?.company?.name ?? '');
  }

  if (opts.isPending || saved.isPending) return <Loading />;
  if (opts.error || saved.error) {
    return <LoadError title="Could not load the editor" error={opts.error ?? saved.error} />;
  }
  const o = opts.data;
  const customKeys = new Set(saved.data.map((c) => c.slug));
  const reasons = check.data?.reasons ?? [];
  const valid = check.data?.valid === true && !check.isPlaceholderData;

  const doSave = (asNew: boolean) => {
    if (!spec) return;
    const body = asNew ? { ...spec, key: saveAs } : spec;
    save.mutate(
      { spec: body, existing: existing && !asNew },
      {
        onSuccess: (s) => {
          setSpec(s as CustomSpec);
          setExisting(true);
          setMessage(`Saved as ${s.key}`);
          setParams({ custom: s.key }, { replace: true });
        },
      },
    );
  };
  const onImport = async (file: File) => {
    const text = await file.text();
    // saved under the file's own name (rename the file to import a copy beside the original)
    const slug = file.name
      .replace(/\.ya?ml$/i, '')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')
      .slice(0, 48);
    imp.mutate(
      { text, slug: slug || null },
      {
        onSuccess: (s) => {
          void open(s.key, true).then(() => setMessage(`Imported ${s.key}`));
        },
      },
    );
  };
  const error =
    save.error ?? imp.error ?? startGame.error ?? preview.error ?? startDifficulty.error;
  const slug = (company || spec?.label || 'custom')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);

  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={2}>Scenario editor</Title>
          <Group>
            <Button component={Link} to="/scenarios" variant="default">
              Scenarios
            </Button>
            <Button component={Link} to="/" variant="default">
              Main menu
            </Button>
          </Group>
        </Group>
        <Panel title="Open" testId="editor-open">
          <Group align="flex-end">
            <NativeSelect
              size="xs"
              label="Start from"
              value={startKey}
              onChange={(e) => setStartKey(e.currentTarget.value)}
              data={[
                ...o.starts.map((s) => ({ value: s.key, label: `${s.label} (${s.year})` })),
                ...saved.data.map((c) => ({ value: c.slug, label: `Custom: ${c.label}` })),
              ]}
              style={{ width: 320 }}
              data-testid="editor-start"
            />
            <Button
              size="xs"
              onClick={() => void open(startKey, customKeys.has(startKey))}
              data-testid="editor-open-button"
            >
              Open
            </Button>
            <Button size="xs" variant="default" onClick={() => fileInput.current?.click()}>
              Import a file
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept=".yaml,.yml"
              style={{ display: 'none' }}
              data-testid="editor-import-file"
              onChange={(e) => {
                const f = e.currentTarget.files?.[0];
                if (f) void onImport(f);
                e.currentTarget.value = '';
              }}
            />
          </Group>
          {openError && <Alert color="red">{openError}</Alert>}
        </Panel>
        {!spec ? (
          <Loading />
        ) : (
          <Section>
            <Panel title="Scenario" testId="editor-scenario">
              <Group align="flex-start">
                <TextInput
                  size="xs"
                  label="Label"
                  value={spec.label}
                  onChange={(e) => setSpec({ ...spec, label: e.currentTarget.value })}
                  style={{ width: 320 }}
                  data-testid="editor-label"
                />
                <TextInput
                  size="xs"
                  label="File name"
                  value={spec.key}
                  readOnly
                  description={existing ? 'saved' : 'not saved yet'}
                  style={{ width: 200 }}
                />
                <Textarea
                  size="xs"
                  label="Brief"
                  value={spec.description ?? ''}
                  onChange={(e) => setSpec({ ...spec, description: e.currentTarget.value })}
                  style={{ flex: '1 1 300px' }}
                  autosize
                  minRows={2}
                />
              </Group>
            </Panel>
            <CompanySection spec={spec} set={setSpec} opts={o} />
            <RivalsSection spec={spec} set={setSpec} opts={o} />
            <MarketsSection spec={spec} set={setSpec} opts={o} />
            <WorldRulesSection spec={spec} set={setSpec} opts={o} />
            {reasons.length > 0 && (
              <Alert color="red" title="Refused" data-testid="editor-refusals">
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {reasons.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </Alert>
            )}
            <Panel title="Save and share" testId="editor-save">
              <Group align="flex-end">
                <Button
                  size="xs"
                  disabled={!valid || !existing || save.isPending}
                  onClick={() => doSave(false)}
                  data-testid="editor-save-button"
                >
                  Save
                </Button>
                <TextInput
                  size="xs"
                  label="Save as"
                  value={saveAs}
                  onChange={(e) => setSaveAs(e.currentTarget.value)}
                  style={{ width: 200 }}
                  data-testid="editor-save-as-name"
                />
                <Button
                  size="xs"
                  disabled={!valid || save.isPending || saveAs === ''}
                  onClick={() => doSave(true)}
                  data-testid="editor-save-as"
                >
                  Save as
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  disabled={!existing}
                  onClick={() =>
                    void exportCustom(spec.key).then((x) => {
                      download(x.filename, x.text);
                      setMessage(`Exported ${x.filename}`);
                    })
                  }
                  data-testid="editor-export"
                >
                  Export
                </Button>
              </Group>
              {message && (
                <p style={{ fontSize: 13 }} data-testid="editor-message">
                  {message}
                </p>
              )}
              {error && <Alert color="red">{error.message}</Alert>}
            </Panel>
            <Panel title="Preview" testId="editor-preview">
              <Group>
                <Button
                  size="xs"
                  variant="default"
                  disabled={!valid || preview.isPending}
                  loading={preview.isPending}
                  onClick={() => preview.mutate(spec)}
                  data-testid="editor-preview-button"
                >
                  Preview the start
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  disabled={!valid || startDifficulty.isPending}
                  onClick={() =>
                    startDifficulty.mutate(spec, { onSuccess: (j) => setJobId(j.job_id) })
                  }
                  data-testid="editor-difficulty-button"
                >
                  Estimate the difficulty
                </Button>
              </Group>
              {preview.data && (
                <div style={{ fontSize: 13, marginTop: 8 }} data-testid="editor-preview-summary">
                  <div>
                    {preview.data.start_label} · cash{' '}
                    <span className="tst-num" data-testid="preview-cash">
                      {formatMoneyWhole(preview.data.cash_cents)}
                    </span>{' '}
                    · debt {formatMoneyWhole(preview.data.debt_cents)} · staff{' '}
                    {Object.values(preview.data.staff).reduce((a, b) => a + b, 0)}
                  </div>
                  <div className="tst-muted">
                    Rivals:{' '}
                    {preview.data.rivals
                      .map((x) => `${x.name}${x.added ? ' (added)' : ''}`)
                      .join(', ') || 'none'}
                    {preview.data.removed.length > 0 &&
                      ` · removed ${preview.data.removed.join(', ')}`}
                  </div>
                </div>
              )}
              {difficulty.data && (
                <p style={{ fontSize: 13 }} data-testid="editor-difficulty">
                  {difficulty.data.status === 'running'
                    ? `Playing seeds ${difficulty.data.seeds.join(', ')}… ${difficulty.data.results.length} done`
                    : difficulty.data.status === 'failed'
                      ? `The estimate failed: ${difficulty.data.error ?? ''}`
                      : `${difficulty.data.difficulty ?? 'no goal'} · ${difficulty.data.wins} of ${difficulty.data.seeds.length} won · scores ${difficulty.data.results.map((x) => x.score ?? '—').join(', ')}`}
                </p>
              )}
            </Panel>
            <Panel title="Start a game" testId="editor-start-game">
              <Group align="flex-end">
                <TextInput
                  size="xs"
                  label="Company name"
                  value={company}
                  onChange={(e) => setCompany(e.currentTarget.value)}
                  maxLength={80}
                  style={{ width: 220 }}
                  data-testid="editor-game-company"
                />
                <NumberInput
                  size="xs"
                  label="Seed"
                  value={seed}
                  onChange={(v) => setSeed(v === '' ? '' : Number(v))}
                  description="Blank for a random seed"
                  style={{ width: 160 }}
                />
                <Button
                  size="xs"
                  disabled={!existing || !valid || company.trim() === '' || startGame.isPending}
                  loading={startGame.isPending}
                  onClick={() =>
                    startGame.mutate(
                      {
                        slug: spec.key,
                        name: slug,
                        company: company.trim(),
                        seed: seed === '' ? null : seed,
                      },
                      { onSuccess: (s) => void navigate(`/game/${s.save_id}`) },
                    )
                  }
                  data-testid="editor-start-game-button"
                >
                  Start the game
                </Button>
              </Group>
              {!existing && (
                <p className="tst-muted" style={{ fontSize: 12 }}>
                  Save the scenario first: a game keeps its own copy of the saved file.
                </p>
              )}
            </Panel>
          </Section>
        )}
      </Stack>
    </Container>
  );
}
