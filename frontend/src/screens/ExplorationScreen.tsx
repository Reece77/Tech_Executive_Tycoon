import { Alert, Button, Modal, NumberInput, Progress, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Explain } from '../components/Explain';
import { Term } from '../components/Term';
import {
  useExploration,
  useExplorationAction,
  type Exploration,
  type ExplorationAction,
  type ExplorationProject,
  type GeoBlock,
  type StageName,
} from '../hooks/exploration';
import { formatGrade, formatRange } from '../lib/exploration';
import { formatMoneyWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const projectHelper = createColumnHelper<GameTableFeatures, ExplorationProject>();
const holeHelper = createColumnHelper<GameTableFeatures, ExplorationProject['holes'][number]>();

const BAND_COLOR: Record<string, string> = {
  high: 'var(--tst-accent)',
  medium: 'var(--tst-gold-bg)',
  low: 'var(--tst-track)',
};

/** Exploration (M18, formulas.md 34): the region map with heat-map bands and licences, desk
 * studies, and each project's pipeline, ranges, permit and sale. Only revealed values. */
export function ExplorationScreen() {
  const { saveId = '' } = useParams();
  const exploration = useExploration(saveId);
  if (exploration.isPending) return <Loading />;
  if (exploration.error) {
    return <LoadError title="Could not load exploration" error={exploration.error} />;
  }
  return <Body saveId={saveId} x={exploration.data} />;
}

function Body({ saveId, x }: { saveId: string; x: Exploration }) {
  const act = useExplorationAction(saveId);
  const [region, setRegion] = useState(x.regions[0]?.key ?? '');
  const [commodity, setCommodity] = useState(x.commodities[0]?.key ?? '');
  // An event's link opens its project (M23c): ?project=<id>
  const [params] = useSearchParams();
  const linked = Number(params.get('project'));
  const [selected, setSelected] = useState<number | null>(
    x.projects.some((p) => p.id === linked) ? linked : (x.projects[0]?.id ?? null),
  );
  const run = (a: ExplorationAction) => act.mutate(a);
  // M23c: clicking a free block asks first (cost, term, what you get) instead of buying it.
  const [confirm, setConfirm] = useState<GeoBlock | null>(null);
  const info = x.regions.find((r) => r.key === region);
  const blocks = x.blocks.filter((b) => b.region === region);
  const explorer = x.explorers[0];
  const project = x.projects.find((p) => p.id === selected) ?? x.projects[0] ?? null;
  const running = x.desk_studies.filter((s) => !s.done && s.region === region);
  return (
    <>
      <div style={{ display: 'flex', gap: 12, fontSize: 13 }}>
        <Link to={`/game/${saveId}/products`} style={{ textDecoration: 'none' }}>
          ← Products
        </Link>
        <Link
          to={`/game/${saveId}/products/mines`}
          style={{ textDecoration: 'none' }}
          data-testid="mines-link"
        >
          Mines
        </Link>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Exploration</h1>
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="explorer-line">
          {explorer
            ? `${explorer.name}: ${explorer.geologists} geologist${explorer.geologists === 1 ? '' : 's'}, ${explorer.busy} busy`
            : ''}
          {explorer && explorer.gate.length > 0 ? ` · ${explorer.gate.join('; ')}` : ''}
        </span>
        {x.gate_how && (
          <span className="tst-muted" style={{ fontSize: 12 }} data-testid="gate-how">
            How: {x.gate_how}
          </span>
        )}
        <span className="tst-muted" style={{ fontSize: 12 }}>
          Every <Term term="exploration.range">estimate</Term> is a range at{' '}
          {Math.round(x.confidence * 100)}% confidence; the truth is never shown.
        </span>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="exploration-error">
          {act.error.message}
        </Alert>
      )}
      <Panel
        title="Region map"
        testId="map-panel"
        action={
          <div style={{ display: 'flex', gap: 8 }}>
            <Select
              aria-label="Region"
              data-testid="region-select"
              size="xs"
              data={x.regions.map((r) => ({ value: r.key, label: r.label }))}
              value={region}
              onChange={(v) => v && setRegion(v)}
              allowDeselect={false}
            />
            <Select
              aria-label="Commodity"
              data-testid="commodity-select"
              size="xs"
              data={x.commodities.map((c) => ({ value: c.key, label: c.label }))}
              value={commodity}
              onChange={(v) => v && setCommodity(v)}
              allowDeselect={false}
            />
            <Button
              size="xs"
              data-testid="desk-study"
              loading={act.isPending}
              onClick={() => run({ kind: 'desk', region, commodity })}
            >
              Desk study · {formatMoneyWhole(x.desk_cost_cents)}
            </Button>
          </div>
        }
      >
        {info && (
          <p
            className="tst-muted"
            style={{ fontSize: 12, marginTop: 0 }}
            data-testid="region-facts"
          >
            Prospectivity for {humanize(commodity)}: {info.prospectivity[commodity]?.toFixed(2)} (
            {info.basis[commodity]}). Licence {formatMoneyWhole(info.licence_fee_cents)}, survey{' '}
            {formatMoneyWhole(info.survey_cost_cents)}, holes{' '}
            {formatMoneyWhole(info.hole_cost_low_cents)}–
            {formatMoneyWhole(info.hole_cost_high_cents)}, permits {info.permit_years_low}–
            {info.permit_years_high} years.
            {running.length > 0 && ` A desk study reports ${running.length > 1 ? 'soon' : 'soon'}.`}
          </p>
        )}
        <BlockGrid
          blocks={blocks}
          commodity={commodity}
          onLicence={(b) => setConfirm(b)}
          onOpen={(id) => setSelected(id)}
          busy={act.isPending}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          <Term term="exploration.band">Bands</Term>: high, medium, low from your latest desk study
          of the commodity. Click a free block to see its licence terms; a held block shows its
          holder; yours are outlined.
        </p>
        <StudiesList
          x={x}
          region={region}
          commodity={commodity}
          onShow={(r, c) => {
            setRegion(r);
            setCommodity(c);
          }}
        />
      </Panel>
      {confirm && info && (
        <LicenceDialog
          x={x}
          block={confirm}
          regionLabel={info.label}
          feeCents={info.licence_fee_cents}
          surveyCents={info.survey_cost_cents}
          onClose={() => setConfirm(null)}
          onConfirm={() => {
            run({ kind: 'licence', region: confirm.region, block: confirm.index });
            setConfirm(null);
          }}
        />
      )}
      <Panel title="Your blocks and projects" testId="projects-panel">
        <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
          Every block your group holds, across all regions, with its next step. Pick one to open it
          and show its region on the map.
        </p>
        <ProjectsTable
          projects={x.projects}
          regions={x.regions}
          onSelect={(id) => {
            setSelected(id);
            const p = x.projects.find((q) => q.id === id);
            if (p) setRegion(p.region);
          }}
        />
      </Panel>
      {project && (
        <ProjectPanel key={project.id} p={project} x={x} busy={act.isPending} onAct={run} />
      )}
    </>
  );
}

function BlockGrid({
  blocks,
  commodity,
  onLicence,
  onOpen,
  busy,
}: {
  blocks: GeoBlock[];
  commodity: string;
  onLicence: (b: GeoBlock) => void;
  onOpen: (projectId: number) => void;
  busy: boolean;
}) {
  return (
    <div
      role="grid"
      aria-label="Blocks"
      style={{ display: 'grid', gridTemplateColumns: 'repeat(12, minmax(0, 1fr))', gap: 4 }}
    >
      {blocks.map((b) => {
        const band = b.bands[commodity];
        const mine = b.project_id !== null;
        const held = b.holder !== null;
        return (
          <button
            type="button"
            key={b.index}
            data-testid={`block-${b.index}`}
            data-band={band ?? 'none'}
            data-held={held ? 'true' : 'false'}
            disabled={busy || (held && !mine)}
            title={
              (band ? `${band} for ${humanize(commodity)}` : 'not studied') +
              (held ? ` · held by ${b.holder}` : ' · free')
            }
            onClick={() => (mine && b.project_id !== null ? onOpen(b.project_id) : onLicence(b))}
            style={{
              height: 34,
              fontSize: 11,
              border: mine ? '2px solid var(--tst-text)' : '1px solid var(--tst-border)',
              background: band ? BAND_COLOR[band] : 'transparent',
              color: band === 'high' ? 'var(--tst-bg)' : 'var(--tst-text)',
              opacity: held && !mine ? 0.45 : 1,
              cursor: held && !mine ? 'not-allowed' : 'pointer',
            }}
          >
            {b.index + 1}
            {held && !mine ? '·' : ''}
          </button>
        );
      })}
    </div>
  );
}

function ProjectsTable({
  projects,
  regions,
  onSelect,
}: {
  projects: ExplorationProject[];
  regions: Exploration['regions'];
  onSelect: (id: number) => void;
}) {
  const columns = useMemo(
    () =>
      projectHelper.columns([
        projectHelper.accessor('label', {
          header: 'Block',
          cell: ({ row }) => (
            <Button variant="subtle" size="compact-xs" onClick={() => onSelect(row.original.id)}>
              {row.original.label}
            </Button>
          ),
        }),
        projectHelper.accessor('region', {
          header: 'Region',
          cell: ({ getValue }) => regions.find((r) => r.key === getValue())?.label ?? getValue(),
        }),
        projectHelper.accessor('status', { header: 'Status' }),
        projectHelper.accessor('commodity', {
          header: 'Commodity',
          cell: ({ getValue }) => (getValue() ? humanize(getValue() as string) : '—'),
        }),
        projectHelper.accessor('stage', {
          header: 'Stage',
          cell: ({ row }) => humanize(row.original.stage ?? row.original.level ?? '—'),
        }),
        projectHelper.accessor('category', {
          header: 'Category',
          meta: { term: 'exploration.category' },
          cell: ({ getValue }) => getValue() ?? '—',
        }),
        projectHelper.accessor('spent_cents', {
          header: 'Spent',
          meta: { term: 'field.spent_cents' },
          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
        projectHelper.accessor('npv_mid_cents', {
          header: 'NPV (mid)',
          meta: { term: 'field.npv_mid_cents' },
          cell: ({ getValue }) =>
            getValue() === null ? '—' : formatMoneyWhole(getValue() as number),
        }),
        projectHelper.accessor('next_step', {
          header: 'Next step',
          enableSorting: false,
          cell: ({ getValue }) => (
            <span className="tst-muted" style={{ fontSize: 12, whiteSpace: 'normal' }}>
              {getValue().replace(/^next: /, '') || '—'}
            </span>
          ),
        }),
      ]),
    [onSelect, regions],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: projects,
    getRowId: (p) => String(p.id),
  });
  return <DataTable table={table} label="Projects" rowTestId="project-row" />;
}

const NEXT_STAGES: StageName[] = [
  'survey',
  'sampling',
  'estimate',
  'scoping',
  'pre_feasibility',
  'definitive',
  'permitting',
];

function ProjectPanel({
  p,
  x,
  busy,
  onAct,
}: {
  p: ExplorationProject;
  x: Exploration;
  busy: boolean;
  onAct: (a: ExplorationAction) => void;
}) {
  const [holes, setHoles] = useState<number | string>(20);
  const unit = x.commodities.find((c) => c.key === p.commodity)?.grade_unit ?? 'pct';
  const grade = (v: number) => formatGrade(v, unit);
  const drill = p.options.find((o: { stage: string }) => o.stage === 'drilling');
  // the first greyed-out stage's way in, shown under the buttons (M23c)
  const blocked = NEXT_STAGES.map((s) => p.options.find((o) => o.stage === s)).find(
    (o) => o !== undefined && !o.allowed && o.how !== '',
  );
  return (
    <Panel title={`${p.label} · ${p.company}`} testId="project-panel">
      <div
        style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 16 }}
      >
        <div>
          <dl className="tst-facts" style={{ fontSize: 13, margin: 0 }} data-testid="project-facts">
            <Fact
              label="Status"
              value={`${p.status}${p.stage ? `, ${humanize(p.stage)} running` : ''}`}
            />
            <Fact label="Commodity" value={p.commodity ? humanize(p.commodity) : '—'} />
            <Fact
              label="Survey"
              term="exploration.reading"
              value={
                p.reading
                  ? `${p.reading} anomaly${p.kind ? `, ${humanize(p.kind)}` : ''} · ${Math.round((p.deposit_chance_low ?? 0) * 100)}–${Math.round((p.deposit_chance_high ?? 0) * 100)}% chance of a deposit`
                  : '—'
              }
            />
            <Fact
              label="Sample grade"
              value={p.sample_grade ? formatRange(p.sample_grade, grade) : '—'}
              testId="sample-range"
            />
            <Fact
              label={`Grade from ${p.holes.length} holes`}
              term="exploration.range"
              value={p.grade ? formatRange(p.grade, grade) : '—'}
              testId="grade-range"
            />
            <Fact
              label="Resource"
              term="exploration.category"
              value={
                p.category && p.est_tonnage_mt && p.est_grade
                  ? `${p.category}: ${formatRange(p.est_tonnage_mt, (v) => `${v.toFixed(1)} Mt`)} at ${formatRange(p.est_grade, grade)}`
                  : '—'
              }
            />
            <Fact
              label={p.level ? `${humanize(p.level)} study` : 'Feasibility'}
              value={
                p.npv_mid_cents !== null
                  ? `NPV ${formatMoneyWhole(p.npv_low_cents ?? 0)} to ${formatMoneyWhole(p.npv_high_cents ?? 0)} (mid ${formatMoneyWhole(p.npv_mid_cents)})${p.capex_usd ? `; capex $${(p.capex_usd.low / 1e6).toFixed(0)}–${(p.capex_usd.high / 1e6).toFixed(0)}M` : ''}`
                  : '—'
              }
              testId="npv-range"
            />
            {p.npv_mid_cents !== null && (
              <div style={{ fontSize: 12, paddingLeft: 178 }}>
                <Term term="npv">What NPV means</Term> · why this range?{' '}
                <Explain metric="mine_npv" entity={p.id} label="NPV" />
              </div>
            )}
            <Fact
              label="Permit"
              term="exploration.permit"
              value={
                p.permit_start !== null
                  ? `${p.status === 'permitted' ? 'granted' : p.status === 'refused' ? 'refused' : 'pending'}; typically ${p.permit_years_low}–${p.permit_years_high} years; protests ${p.protests}${p.benefit_agreement ? ', benefit agreement signed' : ''}${p.protest_open ? ' · a protest is open: answer it in the inbox' : ''}`
                  : '—'
              }
              testId="permit-status"
            />
            <Fact label="Spent" value={formatMoneyWhole(p.spent_cents)} />
            <Fact
              label="Sale"
              value={
                p.sold_to
                  ? `sold to ${p.sold_to} for ${formatMoneyWhole(p.sale_cents)}`
                  : p.sale_quote_cents > 0
                    ? `${p.buyer} would pay ${formatMoneyWhole(p.sale_quote_cents)}`
                    : 'no buyer at this stage'
              }
              testId="sale-quote"
            />
          </dl>
          <CategoryProgress p={p} />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
            {NEXT_STAGES.map((stage) => {
              const o = p.options.find((opt) => opt.stage === stage);
              if (!o) return null;
              return (
                <Button
                  key={stage}
                  size="xs"
                  variant="default"
                  data-testid={`stage-${stage}`}
                  disabled={busy || !o.allowed}
                  title={o.allowed ? undefined : `${o.reason}. How: ${o.how}`}
                  onClick={() => onAct({ kind: 'stage', projectId: p.id, stage })}
                >
                  {humanize(stage)}
                  {o.cost_cents > 0 ? ` · ${formatMoneyWhole(o.cost_cents)}` : ''}
                </Button>
              );
            })}
          </div>
          {blocked && (
            <p
              className="tst-muted"
              style={{ fontSize: 12, margin: '6px 0 0' }}
              data-testid="stage-how"
            >
              {humanize(blocked.stage)} is greyed out: {blocked.reason}. <strong>How:</strong>{' '}
              {blocked.how}.
            </p>
          )}
          <div style={{ display: 'flex', gap: 6, marginTop: 8, alignItems: 'center' }}>
            <NumberInput
              aria-label="Holes"
              data-testid="holes-input"
              size="xs"
              min={1}
              max={x.max_programme}
              value={holes}
              onChange={setHoles}
              style={{ width: 80 }}
            />
            <Button
              size="xs"
              data-testid="drill"
              disabled={busy || !drill?.allowed}
              title={drill && !drill.allowed ? `${drill.reason}. How: ${drill.how}` : undefined}
              onClick={() => onAct({ kind: 'drill', projectId: p.id, holes: Number(holes) || 1 })}
            >
              Drill holes
            </Button>
            <Button
              size="xs"
              variant="default"
              data-testid="renew"
              disabled={busy || !p.renewable}
              title={p.renewable ? undefined : `How: ${p.renew_how}`}
              onClick={() => onAct({ kind: 'renew', projectId: p.id })}
            >
              Renew licence
            </Button>
            <Button
              size="xs"
              color="green"
              data-testid="sell"
              disabled={
                busy ||
                p.sale_quote_cents <= 0 ||
                (p.status !== 'active' && p.status !== 'permitted')
              }
              title={
                p.sale_quote_cents > 0
                  ? undefined
                  : 'How: buyers bid once the project has a resource estimate; drill and estimate first'
              }
              onClick={() => onAct({ kind: 'sell', projectId: p.id })}
            >
              Sell project
            </Button>
            <Button
              size="xs"
              variant="subtle"
              color="red"
              data-testid="relinquish"
              disabled={busy || p.status !== 'active'}
              onClick={() => onAct({ kind: 'relinquish', projectId: p.id })}
            >
              Relinquish
            </Button>
          </div>
        </div>
        <HolesTable holes={p.holes} unit={unit} />
      </div>
    </Panel>
  );
}

function Fact({
  label,
  value,
  term,
  testId,
}: {
  label: string;
  value: string;
  term?: string;
  testId?: string;
}) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
      <dt className="tst-muted" style={{ width: 170, flexShrink: 0 }}>
        {term ? <Term term={term}>{label}</Term> : label}
      </dt>
      <dd style={{ margin: 0 }} data-testid={testId}>
        {value}
      </dd>
    </div>
  );
}

function HolesTable({ holes, unit }: { holes: ExplorationProject['holes']; unit: string }) {
  const columns = useMemo(
    () =>
      holeHelper.columns([
        holeHelper.accessor('n', { header: 'Hole', meta: { term: 'field.n' } }),
        holeHelper.accessor('assay', {
          header: 'Assay',
          meta: { term: 'field.assay' },
          cell: ({ getValue }) => formatGrade(getValue(), unit),
        }),
        holeHelper.accessor('cost_cents', {
          header: 'Cost',

          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
      ]),
    [unit],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: holes,
    getRowId: (h) => String(h.n),
  });
  return <DataTable table={table} label="Drill holes" rowTestId="hole-row" />;
}

/** The progress line toward the next resource category (M23c): holes drilled against the
 * holes the next estimate needs, and what to do when it is reached. */
function CategoryProgress({ p }: { p: ExplorationProject }) {
  if (!p.next_category || !p.holes_for_next || p.commodity === null) return null;
  const pct = Math.min(100, (100 * p.holes_drilled) / p.holes_for_next);
  const left = Math.max(0, p.holes_for_next - p.holes_drilled);
  return (
    <div style={{ marginTop: 10, fontSize: 12 }} data-testid="category-progress">
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>
          Toward <Term term="exploration.category">{p.next_category}</Term>:{' '}
          <span className="tst-num">
            {p.holes_drilled}/{p.holes_for_next}
          </span>{' '}
          holes
        </span>
        <span className="tst-muted">
          {left > 0
            ? `${left} more, then re-estimate`
            : `enough holes: run the estimate to reach ${p.next_category}`}
        </span>
      </div>
      <Progress value={pct} size="sm" mt={4} aria-label={`Holes toward ${p.next_category}`} />
    </div>
  );
}

/** A licence asks first (M23c, playtest 5: "bought several by accident"). */
function LicenceDialog({
  x,
  block,
  regionLabel,
  feeCents,
  surveyCents,
  onClose,
  onConfirm,
}: {
  x: Exploration;
  block: GeoBlock;
  regionLabel: string;
  feeCents: number;
  surveyCents: number;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const bands = Object.entries(block.bands);
  return (
    <Modal opened onClose={onClose} title="Licence this block?" data-testid="licence-dialog">
      <dl className="tst-facts" style={{ fontSize: 13, margin: 0 }}>
        <Fact label="Block" value={`${regionLabel} block ${block.index + 1}`} />
        <Fact label="Licence fee" value={formatMoneyWhole(feeCents)} testId="licence-fee" />
        <Fact
          label="Term"
          value={`${x.licence_years} years, renewable ${x.licence_renewals} time${x.licence_renewals === 1 ? '' : 's'} for the same fee`}
          testId="licence-term"
        />
        <Fact
          label="Desk study bands"
          value={
            bands.length
              ? bands.map(([c, b]) => `${humanize(c)} ${b}`).join(', ')
              : 'not studied yet: a desk study shows its bands'
          }
        />
      </dl>
      <p style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>
        You get the sole right to explore this block for the term: survey it (
        {formatMoneyWhole(surveyCents)}), sample, drill, estimate a resource, study it and apply for
        a permit. Nothing is found yet; the fee is spent whatever the block holds. You can
        relinquish or sell it later.
      </p>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <Button variant="default" size="xs" onClick={onClose} data-testid="licence-cancel">
          Cancel
        </Button>
        <Button size="xs" onClick={onConfirm} data-testid="licence-confirm">
          Licence for {formatMoneyWhole(feeCents)}
        </Button>
      </div>
    </Modal>
  );
}

/** Desk studies kept per region and commodity (M23c): each one is listed, and showing it
 * switches the map to that region and commodity, so a new study never recolours the map you
 * were looking at. */
function StudiesList({
  x,
  region,
  commodity,
  onShow,
}: {
  x: Exploration;
  region: string;
  commodity: string;
  onShow: (region: string, commodity: string) => void;
}) {
  const latest = new Map<string, Exploration['desk_studies'][number]>();
  for (const s of x.desk_studies) latest.set(`${s.region}|${s.commodity}`, s);
  const studies = [...latest.values()].sort((a, b) => b.start_turn - a.start_turn);
  if (studies.length === 0) return null;
  const label = (key: string) => x.regions.find((r) => r.key === key)?.label ?? key;
  return (
    <div
      style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', fontSize: 12 }}
      data-testid="desk-studies"
    >
      <span className="tst-muted">Your desk studies:</span>
      {studies.map((s) => {
        const current = s.region === region && s.commodity === commodity;
        return (
          <Button
            key={`${s.region}|${s.commodity}`}
            size="compact-xs"
            variant={current ? 'filled' : 'default'}
            disabled={!s.done}
            data-testid="desk-study-chip"
            onClick={() => onShow(s.region, s.commodity)}
            title={s.done ? 'Show it on the map' : 'Still running'}
          >
            {label(s.region)} · {humanize(s.commodity)}
            {s.done ? '' : ' (running)'}
          </Button>
        );
      })}
    </div>
  );
}
