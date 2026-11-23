// Pharmaceuticals (M42, formulas.md 55): the pipeline by stage with readouts, efficacy estimates
// and chances as ranges, filings, exclusivity and Explain's chance to approval and rNPV; marketed
// drugs' prices, patients and revenue; plants and contract manufacturers; assets for licence and
// deals; rivals' drugs and approvals; dated rules. Programme and plant pages open from the tables.
// No game values are computed here: ranges, money and months come from the API and are formatted.
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Select,
  TextInput,
} from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { OpenNegotiation } from '../components/NegotiationPanel';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  formatBand,
  formatScore,
  useBuildPharmaPlant,
  useChooseCmo,
  useFileDrug,
  useLicenseAsset,
  usePharma,
  usePharmaPlantQuality,
  useSetDrugPrice,
  useStartProgramme,
  useStartTrial,
  useStopProgramme,
  type Pharma,
  type RxAsset,
  type RxDrug,
  type RxProgramme,
  type RxRival,
} from '../hooks/pharma';
import { formatMoneyWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const progHelper = createColumnHelper<GameTableFeatures, RxProgramme>();
const drugHelper = createColumnHelper<GameTableFeatures, RxDrug>();
const assetHelper = createColumnHelper<GameTableFeatures, RxAsset>();
const rivalHelper = createColumnHelper<GameTableFeatures, RxRival>();

const STAGE_WORDS: Record<string, string> = {
  discovery: 'Discovery',
  preclinical: 'Preclinical',
  phase1: 'Phase I',
  phase2: 'Phase II',
  phase3: 'Phase III',
  submission: 'Filed',
  approved: 'Approved',
};
const STAGE_TERMS: Record<string, string> = {
  phase1: 'pharma.phase_1',
  phase2: 'pharma.phase_2',
  phase3: 'pharma.phase_3',
};

function stageWord(stage: string): string {
  return STAGE_WORDS[stage] ?? humanize(stage);
}

function usePharmaQuery() {
  const { saveId = '' } = useParams();
  return { saveId, q: usePharma(saveId) };
}

export function PharmaScreen() {
  const { saveId, q } = usePharmaQuery();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load pharmaceuticals" error={q.error} />;
  return <PharmaBody saveId={saveId} m={q.data} />;
}

export function PharmaBody({ saveId, m }: { saveId: string; m: Pharma }) {
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Discovery {m.in_discovery}/{m.discovery_slots} · {m.researchers} research staff · AI
            discovery {m.ai_ready ? 'ready' : 'not available'}
          </span>
        }
      >
        Pharma
      </ScreenTitle>
      <StartForm saveId={saveId} m={m} />
      <Pipeline saveId={saveId} m={m} />
      <Drugs saveId={saveId} m={m} />
      <Manufacturing saveId={saveId} m={m} />
      <Assets saveId={saveId} m={m} />
      {m.deals.length > 0 && (
        <Panel title="Deals" testId="deals">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {m.deals.map((x) => (
              <li key={x.id}>
                {humanize(x.kind)} with {x.counterparty}
                {x.programme ? ` (${x.programme})` : ''}, {x.signed}: upfront{' '}
                {formatMoneyWhole(x.upfront_cents)}
                {x.royalty > 0 ? `, royalty ${Math.round(x.royalty * 100)}%` : ''}
                {x.fee_cents > 0 ? `, ${formatMoneyWhole(x.fee_cents)} a month` : ''}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {(m.inspections.length > 0 || m.recalls.length > 0) && (
        <Panel title="Inspections and recalls" testId="pharma-quality">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {m.inspections.map((i) => (
              <li key={i.month + i.regulator}>
                {i.month}: {i.regulator}, {humanize(i.finding)}
                {i.until ? ` (until ${i.until})` : ''}
                {i.fine_cents > 0 ? `, ${formatMoneyWhole(i.fine_cents)}` : ''}
              </li>
            ))}
            {m.recalls.map((r) => (
              <li key={r.month + r.programme}>
                {r.month}: recall of {r.programme}, {formatMoneyWhole(r.cost_cents)}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <Rivals m={m} />
      <Panel title="Regulators, rules and history">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {m.regulators.map((r) => (
            <li key={r.key}>
              <strong>{r.name}</strong> ({r.region}): {r.application}, standard {r.standard}
              {r.priority ? `, priority ${r.priority}` : ''}
            </li>
          ))}
        </ul>
        <ul style={{ marginTop: 8, paddingLeft: 18 }} data-testid="pharma-rules">
          {m.rules.map((r) => (
            <li key={`${r.year}${r.text}`}>
              {r.year}: {r.text}
            </li>
          ))}
          {m.facts.map((f) => (
            <li key={f.month + f.text}>
              {f.month}: {f.text}
            </li>
          ))}
        </ul>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          <Term term="pharma.phase_1">Phase I</Term> · <Term term="pharma.phase_2">Phase II</Term> ·{' '}
          <Term term="pharma.phase_3">Phase III</Term> · <Term term="pharma.nda_bla">NDA/BLA</Term>{' '}
          · <Term term="pharma.loe">LOE</Term> · <Term term="pharma.biosimilar">Biosimilar</Term> ·{' '}
          <Term term="pharma.orphan">Orphan</Term> ·{' '}
          <Term term="pharma.priority_review">Priority review</Term> ·{' '}
          <Term term="pharma.ira">IRA</Term> · <Term term="pharma.hta">HTA</Term> ·{' '}
          <Term term="pharma.rnpv">rNPV</Term>
        </p>
      </Panel>
    </>
  );
}

function StartForm({ saveId, m }: { saveId: string; m: Pharma }) {
  const start = useStartProgramme(saveId);
  const [name, setName] = useState('');
  const [indication, setIndication] = useState<string | null>(m.indications[0]?.key ?? null);
  const [modality, setModality] = useState<string | null>('small_molecule');
  const [ai, setAi] = useState(false);
  const full = m.in_discovery >= m.discovery_slots;
  return (
    <Panel title="Start a programme" testId="pharma-start">
      <Group gap="xs" align="end">
        <TextInput
          label="Name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          data-testid="rx-name"
          w={160}
        />
        <Select
          label="Indication"
          data={m.indications.map((i) => ({
            value: i.key,
            label: `${i.label} (${i.area_label}${i.orphan ? ', orphan' : ''})`,
          }))}
          value={indication}
          onChange={setIndication}
          allowDeselect={false}
          data-testid="rx-indication"
          w={320}
        />
        <Select
          label="Modality"
          data={m.modalities.map((x) => ({ value: x, label: humanize(x) }))}
          value={modality}
          onChange={setModality}
          allowDeselect={false}
          data-testid="rx-modality"
          w={180}
        />
        <Checkbox
          label="AI discovery"
          checked={ai}
          disabled={!m.ai_ready}
          onChange={(e) => setAi(e.currentTarget.checked)}
          data-testid="rx-ai"
        />
        <Button
          disabled={!indication || !modality || name.trim() === '' || full}
          title={full ? 'Discovery is full: hire research scientists' : undefined}
          loading={start.isPending}
          onClick={() =>
            indication &&
            modality &&
            start.mutate({
              name,
              indication,
              modality: modality as 'small_molecule' | 'biologic' | 'cell_and_gene',
              ai,
            })
          }
          data-testid="rx-start"
        >
          Start discovery
        </Button>
      </Group>
      {start.error && <Alert color="red">{start.error.message}</Alert>}
    </Panel>
  );
}

function ProgrammeActions({
  saveId,
  p,
  regulators,
}: {
  saveId: string;
  p: RxProgramme;
  regulators: Pharma['regulators'];
}) {
  const trial = useStartTrial(saveId);
  const stop = useStopProgramme(saveId);
  const file = useFileDrug(saveId);
  const [design, setDesign] = useState<string | null>('standard');
  const trialable = p.next_stage !== null || p.status === 'failed';
  const active = !['stopped', 'marketed', 'out', 'withdrawn'].includes(p.status);
  return (
    <Group gap={4} wrap="nowrap">
      {trialable && (
        <>
          <Select
            size="xs"
            data={['lean', 'standard', 'large']}
            value={design}
            onChange={setDesign}
            allowDeselect={false}
            w={100}
            data-testid={`rx-design-${p.id}`}
          />
          <Button
            size="xs"
            loading={trial.isPending}
            onClick={() =>
              trial.mutate({
                programme_id: p.id,
                design: (design ?? 'standard') as 'lean' | 'standard' | 'large',
              })
            }
            data-testid={p.status === 'failed' ? `rx-redesign-${p.id}` : `rx-trial-${p.id}`}
          >
            {p.status === 'failed' ? 'Redesign' : `Start ${stageWord(p.next_stage ?? '')}`}
          </Button>
        </>
      )}
      {p.can_file.map((key) => (
        <Button
          key={key}
          size="xs"
          variant="light"
          loading={file.isPending}
          onClick={() => file.mutate({ programme_id: p.id, regulator: key })}
          data-testid={`rx-file-${p.id}-${key}`}
        >
          File {regulators.find((r) => r.key === key)?.application ?? key}
        </Button>
      ))}
      {active && p.status !== 'marketed' && (
        <Button
          size="xs"
          color="red"
          variant="subtle"
          loading={stop.isPending}
          onClick={() => stop.mutate({ programme_id: p.id })}
          data-testid={`rx-stop-${p.id}`}
        >
          Stop
        </Button>
      )}
      {(trial.error || file.error || stop.error) && (
        <span style={{ color: 'var(--mantine-color-red-6)', fontSize: 12 }}>
          {(trial.error ?? file.error ?? stop.error)?.message}
        </span>
      )}
    </Group>
  );
}

function Pipeline({ saveId, m }: { saveId: string; m: Pharma }) {
  const columns = useMemo(
    () =>
      progHelper.columns([
        progHelper.accessor('name', {
          header: 'Programme',
          cell: (c) => (
            <Link
              to={`programme/${c.row.original.id}`}
              data-testid={`rx-link-${c.row.original.id}`}
            >
              {c.getValue()}
            </Link>
          ),
        }),
        progHelper.accessor('indication_label', { header: 'Indication' }),
        progHelper.accessor((p) => `${stageWord(p.stage)} · ${p.status}`, {
          id: 'stage',
          header: 'Stage',
          cell: (c) => (
            <span data-testid={`rx-stage-${c.row.original.id}`}>
              <Term term={STAGE_TERMS[c.row.original.stage] ?? 'pharma.rnpv'}>{c.getValue()}</Term>
              {c.row.original.ai && (
                <Badge ml={4} size="xs" color="grape">
                  AI
                </Badge>
              )}
            </span>
          ),
        }),
        progHelper.accessor((p) => formatScore(p.efficacy), {
          id: 'efficacy',
          header: 'Efficacy (estimate)',
        }),
        progHelper.accessor((p) => (p.next_chance ? formatBand(p.next_chance) : '—'), {
          id: 'next',
          header: 'Next chance',
          cell: (c) => <span data-testid={`rx-next-${c.row.original.id}`}>{c.getValue()}</span>,
        }),
        progHelper.accessor('planned_end', { header: 'Planned end' }),
        progHelper.accessor((p) => (p.value ? formatBand(p.value.to_approval) : '—'), {
          id: 'value',
          header: 'To approval · rNPV',
          cell: (c) => {
            const v = c.row.original.value;
            if (!v) return '—';
            return (
              <span title={v.explain}>
                {c.getValue()} · {formatMoneyWhole(v.rnpv_lo_cents)} to{' '}
                {formatMoneyWhole(v.rnpv_hi_cents)}{' '}
                <Explain metric="pharma_value" entity={c.row.original.id} label="Expected value" />
              </span>
            );
          },
        }),
        progHelper.display({
          id: 'act',
          header: '',
          cell: (c) => (
            <ProgrammeActions saveId={saveId} p={c.row.original} regulators={m.regulators} />
          ),
        }),
      ]),
    [saveId, m.regulators],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.programmes,
    getRowId: (p) => String(p.id),
  });
  return (
    <Panel title="Pipeline" testId="pipeline">
      {m.programmes.length === 0 ? (
        <Alert color="blue" data-testid="no-programmes">
          No programmes yet: start one above, or license one from a biotech below.
        </Alert>
      ) : (
        <DataTable table={table} label="Programmes" rowTestId="rx-row" />
      )}
    </Panel>
  );
}

function PriceForm({ saveId, d }: { saveId: string; d: RxDrug }) {
  const price = useSetDrugPrice(saveId);
  const [dollars, setDollars] = useState<number | string>(Math.round(d.list_cents / 100));
  const [support, setSupport] = useState<number | string>(d.support);
  return (
    <Group gap={4} wrap="nowrap">
      <NumberInput
        size="xs"
        value={dollars}
        onChange={setDollars}
        w={110}
        prefix="$"
        thousandSeparator
      />
      <NumberInput
        size="xs"
        value={support}
        onChange={setSupport}
        w={70}
        step={0.1}
        min={0}
        max={2}
      />
      <Button
        size="xs"
        loading={price.isPending}
        onClick={() =>
          price.mutate({
            programme_id: d.programme_id,
            list_cents: Math.round(Number(dollars) * 100),
            support: Number(support),
          })
        }
        data-testid={`rx-price-${d.programme_id}`}
      >
        Set
      </Button>
      {price.error && (
        <span style={{ color: 'var(--mantine-color-red-6)' }}>{price.error.message}</span>
      )}
    </Group>
  );
}

function Drugs({ saveId, m }: { saveId: string; m: Pharma }) {
  const columns = useMemo(
    () =>
      drugHelper.columns([
        drugHelper.accessor('name', { header: 'Drug' }),
        drugHelper.accessor('indication_label', { header: 'Indication' }),
        drugHelper.accessor('patients', {
          header: 'Patients',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        drugHelper.accessor('revenue_cents', {
          header: 'Last month',
          cell: (c) => (
            <span data-testid={`rx-revenue-${c.row.original.programme_id}`}>
              {formatMoneyWhole(c.getValue())}
            </span>
          ),
        }),
        drugHelper.accessor('year_cents', {
          header: '12 months',
          cell: (c) => formatMoneyWhole(c.getValue()),
        }),
        drugHelper.accessor((d) => (d.generic ? 'generics' : 'exclusive'), {
          id: 'loe',
          header: 'Exclusivity',
          meta: { term: 'pharma.loe' },
          cell: (c) => (
            <Badge
              color={c.row.original.generic ? 'red' : 'teal'}
              data-testid={`rx-loe-${c.row.original.programme_id}`}
            >
              {c.getValue()}
            </Badge>
          ),
        }),
        drugHelper.accessor((d) => d.ira ?? '—', {
          id: 'ira',
          header: 'Medicare',
          meta: { term: 'pharma.ira' },
        }),
        drugHelper.display({
          id: 'price',
          header: 'US list a year · support',
          cell: (c) => <PriceForm saveId={saveId} d={c.row.original} />,
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.drugs,
    getRowId: (d) => String(d.programme_id),
  });
  if (m.drugs.length === 0) return null;
  return (
    <Panel title="Marketed drugs" testId="drugs">
      <DataTable table={table} label="Drugs" rowTestId="rx-drug-row" />
      {m.drugs.map((d) => (
        <details key={d.programme_id} data-testid={`rx-history-${d.programme_id}`}>
          <summary>{d.name}: revenue by month</summary>
          <ul style={{ margin: 0, paddingLeft: 18, columns: 3, fontSize: 12 }}>
            {d.history.map((h) => (
              <li key={h.month} data-testid="rx-month">
                {h.month}: {formatMoneyWhole(h.revenue_cents)}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </Panel>
  );
}

function Manufacturing({ saveId, m }: { saveId: string; m: Pharma }) {
  const build = useBuildPharmaPlant(saveId);
  const cmo = useChooseCmo(saveId);
  const [kind, setKind] = useState<string | null>('api');
  const [region, setRegion] = useState<string | null>('north_america');
  return (
    <Panel title="Manufacturing" testId="pharma-plants">
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {m.plants.map((p) => (
          <li key={p.id}>
            <Link to={`plant/${p.id}`} data-testid={`rx-plant-${p.id}`}>
              {p.label}
            </Link>{' '}
            ({p.region}): {p.live ? 'running' : `ready ${p.ready}`}, quality {p.quality}
          </li>
        ))}
        {m.cmos.map((c) => (
          <li key={c.name}>
            <Term term="pharma.cmo">{c.name}</Term> ({c.region}, {c.kinds.join(' and ')}, quality{' '}
            {c.quality})
            {c.chosen_for.length > 0 ? ` — makes your ${c.chosen_for.join(' and ')}` : ''}
            {c.kinds
              .filter((k) => !c.chosen_for.includes(k))
              .map((k) => (
                <Button
                  key={k}
                  size="compact-xs"
                  variant="subtle"
                  ml={4}
                  onClick={() => cmo.mutate({ kind: k as 'api' | 'biologics', cmo: c.name })}
                >
                  Use for {k}
                </Button>
              ))}
          </li>
        ))}
      </ul>
      <Group gap="xs" align="end" mt="xs">
        <Select
          label="Plant"
          data={['api', 'biologics']}
          value={kind}
          onChange={setKind}
          w={130}
          allowDeselect={false}
        />
        <Select
          label="Region"
          data={['north_america', 'europe', 'east_asia', 'south_southeast_asia', 'latin_america']}
          value={region}
          onChange={setRegion}
          w={200}
          allowDeselect={false}
        />
        <Button
          loading={build.isPending}
          onClick={() =>
            kind && region && build.mutate({ kind: kind as 'api' | 'biologics', region })
          }
          data-testid="rx-build"
        >
          Build plant
        </Button>
      </Group>
      {(build.error || cmo.error) && (
        <Alert color="red">{(build.error ?? cmo.error)?.message}</Alert>
      )}
    </Panel>
  );
}

function Assets({ saveId, m }: { saveId: string; m: Pharma }) {
  const take = useLicenseAsset(saveId);
  const columns = useMemo(
    () =>
      assetHelper.columns([
        assetHelper.accessor('name', { header: 'Asset' }),
        assetHelper.accessor('indication_label', { header: 'Indication' }),
        assetHelper.accessor((a) => stageWord(a.stage), { id: 'stage', header: 'Stage' }),
        assetHelper.accessor((a) => formatScore(a.efficacy), {
          id: 'eff',
          header: 'Efficacy (estimate)',
        }),
        assetHelper.accessor('upfront_cents', {
          header: 'Upfront · royalty',
          cell: (c) =>
            `${formatMoneyWhole(c.getValue())} · ${Math.round(c.row.original.royalty * 100)}%`,
        }),
        assetHelper.display({
          id: 'take',
          header: '',
          cell: (c) => (
            <Group gap={4} wrap="nowrap">
              <Button size="xs" onClick={() => take.mutate({ asset_id: c.row.original.id })}>
                License
              </Button>
              <Button
                size="xs"
                variant="light"
                onClick={() => take.mutate({ asset_id: c.row.original.id, acquire: true })}
              >
                Acquire ({formatMoneyWhole(c.row.original.acquire_cents)})
              </Button>
              <OpenNegotiation
                saveId={saveId}
                kind="licence_in"
                params={{ asset_id: c.row.original.id }}
              />
            </Group>
          ),
        }),
      ]),
    [take, saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.assets,
    getRowId: (a) => String(a.id),
  });
  if (m.assets.length === 0) return null;
  return (
    <Panel title="Biotech assets for licence" testId="assets">
      <DataTable table={table} label="Assets" rowTestId="rx-asset-row" />
      {take.error && <Alert color="red">{take.error.message}</Alert>}
    </Panel>
  );
}

function Rivals({ m }: { m: Pharma }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', { header: 'Company' }),
        rivalHelper.accessor('year_cents', {
          header: '12 months',
          cell: (c) => formatMoneyWhole(c.getValue()),
        }),
        rivalHelper.accessor(
          (r) => r.drugs.map((d) => `${d.name} (US LOE ${d.loe_us})`).join(', ') || '—',
          {
            id: 'drugs',
            header: 'Key drugs',
          },
        ),
        rivalHelper.accessor((r) => r.pipeline.join(', ') || '—', {
          id: 'pipeline',
          header: 'Late pipeline',
        }),
        rivalHelper.accessor(
          (r) => r.approvals.map((a) => `${a.name} ${a.month}`).join(', ') || '—',
          {
            id: 'approvals',
            header: 'Recent approvals',
          },
        ),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.rivals,
    getRowId: (r) => String(r.id),
  });
  return (
    <Panel title="Rivals" testId="pharma-rivals">
      <DataTable table={table} label="Pharma rivals" rowTestId="rx-rival-row" />
    </Panel>
  );
}

// --- programme and plant pages ------------------------------------------------------------------

export function PharmaProgrammeScreen() {
  const { saveId, q } = usePharmaQuery();
  const { programmeId = '' } = useParams();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load the programme" error={q.error} />;
  const p = q.data.programmes.find((x) => String(x.id) === programmeId);
  if (!p) return <Alert color="red">No such programme.</Alert>;
  const preclinical =
    p.preclinical_months < p.preclinical_months_without_ai
      ? `${p.preclinical_months} months with AI discovery (${p.preclinical_months_without_ai} without)`
      : `${p.preclinical_months} months`;
  return (
    <>
      <ScreenTitle aside={<Link to="../..">Back to Pharma</Link>}>{p.name}</ScreenTitle>
      <Panel title={`${p.indication_label} · ${humanize(p.modality)}`} testId="rx-programme">
        <Group gap="xs" mb="xs">
          <Badge>{stageWord(p.stage)}</Badge>
          <Badge color="gray">{p.status}</Badge>
          {p.ai && <Badge color="grape">AI discovery</Badge>}
          {p.breakthrough && (
            <Badge color="teal">
              <Term term="pharma.breakthrough">Breakthrough</Term>
            </Badge>
          )}
          {p.accelerated && (
            <Badge color="teal">
              <Term term="pharma.accelerated_approval">Accelerated</Term>
            </Badge>
          )}
          {p.orphan && (
            <Badge color="indigo">
              <Term term="pharma.orphan">Orphan</Term>
            </Badge>
          )}
          {p.partner && <Badge color="gray">with {p.partner}</Badge>}
        </Group>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>
            Efficacy estimate {formatScore(p.efficacy)} after {p.readouts} readout(s): the true
            value is never known.
          </li>
          <li data-testid="rx-preclinical">Preclinical work: {preclinical}</li>
          <li>
            This stage: {p.patients > 0 ? `${p.patients} patients, ` : ''}
            {formatMoneyWhole(p.cost_cents)} ({formatMoneyWhole(p.spent_cents)} spent), {p.started}{' '}
            to {p.planned_end} <Explain metric="trial_cost" entity={p.id} label="Trial cost" />
          </li>
          {p.next_stage && (
            <li>
              Next: {stageWord(p.next_stage)}, chance {formatBand(p.next_chance)},{' '}
              {formatMoneyWhole(p.next_cost_cents ?? 0)} over {p.next_months} months
            </li>
          )}
          {p.redesign_cost_cents && <li>Redesign: {formatMoneyWhole(p.redesign_cost_cents)}</li>}
          {p.value && (
            <li data-testid="rx-value">
              Chance to approval {formatBand(p.value.to_approval)}, rNPV{' '}
              {formatMoneyWhole(p.value.rnpv_lo_cents)} to {formatMoneyWhole(p.value.rnpv_hi_cents)}{' '}
              <Explain metric="pharma_value" entity={p.id} label="Expected value" />
            </li>
          )}
        </ul>
        <div style={{ marginTop: 8 }}>
          <ProgrammeActions saveId={saveId} p={p} regulators={q.data.regulators} />
        </div>
      </Panel>
      <Panel title="Readouts" testId="rx-readouts">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {p.history.map((r) => (
            <li key={r.month + r.stage} data-testid="rx-readout">
              {r.month}: {stageWord(r.stage)} ({r.design}) {r.success ? 'succeeded' : 'failed'};
              shown chance was {formatBand(r.shown)}
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Filings and exclusivity">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {p.reviews.map((r) => (
            <li key={r.regulator + r.filed}>
              {r.regulator_name}: {r.application} filed {r.filed}, {r.status}
              {r.priority ? ' (priority)' : ''}; decision {r.expected}
              {r.adcom ? `; committee voted ${r.adcom}` : ''}
            </li>
          ))}
          {p.approvals.length > 0 && <li>Approved: {p.approvals.join(', ')}</li>}
          {p.exclusivity
            .filter((e) => e.ends)
            .map((e) => (
              <li key={e.region}>
                {e.region_label}: exclusivity {e.ended ? 'ended' : 'ends'} {e.ends}
              </li>
            ))}
        </ul>
      </Panel>
    </>
  );
}

export function PharmaPlantScreen() {
  const { saveId, q } = usePharmaQuery();
  const { plantId = '' } = useParams();
  const quality = usePharmaPlantQuality(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load the plant" error={q.error} />;
  const p = q.data.plants.find((x) => String(x.id) === plantId);
  if (!p) return <Alert color="red">No such plant.</Alert>;
  return (
    <>
      <ScreenTitle aside={<Link to="../..">Back to Pharma</Link>}>{p.label}</ScreenTitle>
      <Panel title={p.region} testId="rx-plant">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>
            Ordered {p.ordered}, {p.live ? 'running' : `ready ${p.ready}`}; capex{' '}
            {formatMoneyWhole(p.capex_cents)}
          </li>
          <li>Makes {p.patient_years_k.toLocaleString()} thousand patient-years a year</li>
        </ul>
        <Group gap="xs" mt="xs">
          {(['low', 'standard', 'high'] as const).map((level) => (
            <Button
              key={level}
              size="xs"
              variant={p.quality === level ? 'filled' : 'light'}
              onClick={() => quality.mutate({ plant_id: p.id, level })}
            >
              {humanize(level)} quality
            </Button>
          ))}
        </Group>
        {quality.error && <Alert color="red">{quality.error.message}</Alert>}
      </Panel>
    </>
  );
}
