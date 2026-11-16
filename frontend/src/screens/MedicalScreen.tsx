// Medical devices (M41, formulas.md 50): the pipeline of the player's devices with their class,
// route and evidence; submissions by regulator with their stages and review ranges; studies;
// coverage and clinicians' adoption by region; recalls; plants' quality systems; inspections;
// rivals' shares; and dated rules. No game values are computed here: ranges, shares, money and
// months come from the API and are formatted only.
import { Alert, Badge, Button, Checkbox, Group, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import { formatShare } from '../hooks/platforms';
import {
  useDesignDevice,
  useMedical,
  useMedicalSupport,
  usePlantQuality,
  useRequestCoverage,
  useStartStudy,
  useSubmitDevice,
  type Medical,
  type MedicalDevice,
  type MedicalRegion,
  type MedicalRival,
  type MedicalRoute,
  type MedicalStudy,
} from '../hooks/medical';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const routeHelper = createColumnHelper<GameTableFeatures, MedicalRoute>();
const studyHelper = createColumnHelper<GameTableFeatures, MedicalStudy>();
const regionHelper = createColumnHelper<GameTableFeatures, MedicalRegion>();
const rivalHelper = createColumnHelper<GameTableFeatures, MedicalRival>();

const STATUS_WORDS: Record<MedicalRoute['status'], string> = {
  not_filed: 'not filed',
  review: 'under review',
  information_requested: 'more information requested',
  cleared: 'cleared',
  refused: 'refused',
};
const STUDY_WORDS: Record<string, string> = {
  feasibility: 'Feasibility',
  pivotal: 'Pivotal',
  post_market: 'Post-market',
};

export function MedicalScreen() {
  const { saveId = '' } = useParams();
  const q = useMedical(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load medical devices" error={q.error} />;
  return <MedicalBody saveId={saveId} m={q.data} />;
}

export function MedicalBody({ saveId, m }: { saveId: string; m: Medical }) {
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Create a product in a medical category on the Products screen, choose its intended use
            here, then file it with each regulator.
          </span>
        }
      >
        Medical
      </ScreenTitle>
      {m.devices.length === 0 && (
        <Alert color="blue" title="No medical devices yet" data-testid="no-devices">
          Wearables and diagnostics, imaging, surgical robots, implants and diagnostic software are
          medical categories: a product in one is a device that needs clearance before it sells.
        </Alert>
      )}
      {m.devices.map((d) => (
        <Device key={d.product_id} saveId={saveId} m={m} d={d} />
      ))}
      <Plants saveId={saveId} m={m} />
      {m.inspections.length > 0 && (
        <Panel title="Inspections" testId="inspections">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {m.inspections.map((i) => (
              <li key={i.turn + i.regulator + i.finding}>
                {i.turn}: {i.regulator}, {i.finding}
                {i.until ? ` (until ${i.until})` : ''}
                {i.fine_cents > 0 ? `, ${formatMoneyWhole(i.fine_cents)}` : ''}
                {i.for_cause ? ' — for cause' : ''}
              </li>
            ))}
          </ul>
          <p className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="medical.inspection">Inspections</Term> read the plants' quality systems.
          </p>
        </Panel>
      )}
      <Rivals m={m} />
      <Panel title="Regulators and dated rules">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {m.regulators.map((r) => (
            <li key={r.key}>
              <strong>{r.name}</strong> — {r.region_label} ({formatShare(r.share)} of its people)
            </li>
          ))}
        </ul>
        <ul style={{ marginTop: 8, paddingLeft: 18 }}>
          {m.precedents.map((p) => (
            <li key={p.label}>
              <strong>{p.label}</strong> ({p.at}): {p.note}
            </li>
          ))}
        </ul>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          <Term term="medical.510k">510(k)</Term> · <Term term="medical.de_novo">De Novo</Term> ·{' '}
          <Term term="medical.pma">PMA</Term> · <Term term="medical.predicate">Predicate</Term> ·{' '}
          <Term term="medical.mdr">MDR</Term> ·{' '}
          <Term term="medical.notified_body">Notified body</Term> ·{' '}
          <Term term="medical.samd">SaMD</Term>
        </p>
      </Panel>
    </>
  );
}

function Device({ saveId, m, d }: { saveId: string; m: Medical; d: MedicalDevice }) {
  const sub = m.subcategories.find((s) => s.key === d.category);
  return (
    <Panel title={`${d.name} — ${d.category_label}`} testId={`device-${d.product_id}`}>
      <Group gap="xs" mb="xs">
        <Badge>{d.status}</Badge>
        {d.use_label && <Badge color="gray">{d.use_label}</Badge>}
        {d.us_class && <Badge color="teal">US class {d.us_class}</Badge>}
        {d.eu_class && <Badge color="teal">EU class {d.eu_class}</Badge>}
        <Badge color="grape">evidence {formatShare(d.evidence)}</Badge>
        <Badge color="gray">quality system: {d.quality_level}</Badge>
        {d.pccp && <Badge color="indigo">change control plan</Badge>}
      </Group>
      {d.update_needed && (
        <Alert color="yellow" mb="xs" data-testid="update-needed">
          The software has changed past its US clearance: file a new 510(k), or clear the next
          version with a change control plan.
        </Alert>
      )}
      {sub && <DesignForm saveId={saveId} d={d} sub={sub} />}
      {d.use && <Routes saveId={saveId} d={d} />}
      {d.use && <Studies saveId={saveId} m={m} d={d} />}
      {d.use && <Regions saveId={saveId} d={d} />}
      {d.use && <Support saveId={saveId} d={d} />}
      {d.recalls.length > 0 && (
        <div data-testid="recalls">
          <strong>
            <Term term="medical.class_i_recall">Recalls</Term>
          </strong>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {d.recalls.map((r) => (
              <li key={r.turn + r.klass}>
                {r.turn}: class {r.klass}, {r.units.toLocaleString()} units,{' '}
                {formatMoneyWhole(r.cost_cents)}
                {r.caught_early ? ' (caught early by surveillance)' : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}

function DesignForm({
  saveId,
  d,
  sub,
}: {
  saveId: string;
  d: MedicalDevice;
  sub: Medical['subcategories'][number];
}) {
  const design = useDesignDevice(saveId);
  const [use, setUse] = useState<string | null>(d.use ?? sub.uses[0]?.key ?? null);
  const [pccp, setPccp] = useState(d.pccp);
  const chosen = sub.uses.find((u) => u.key === use);
  return (
    <Group gap="xs" mb="xs" align="end">
      <Select
        label="Intended use"
        data={sub.uses.map((u) => ({ value: u.key, label: u.label }))}
        value={use}
        onChange={setUse}
        allowDeselect={false}
        data-testid="device-use"
        w={260}
      />
      {sub.software && (
        <Checkbox
          label="Predetermined change control plan"
          checked={pccp}
          onChange={(e) => setPccp(e.currentTarget.checked)}
          data-testid="device-pccp"
        />
      )}
      <Button
        size="xs"
        loading={design.isPending}
        disabled={use === null}
        onClick={() => use && design.mutate({ product_id: d.product_id, use, pccp })}
        data-testid="device-design"
      >
        {d.use ? 'Update design' : 'Set intended use'}
      </Button>
      {chosen && (
        <span className="tst-muted" style={{ fontSize: 13 }}>
          US class {chosen.us_class} ({chosen.us_route}), EU class {chosen.eu_class}
        </span>
      )}
      {design.error && <Alert color="red">{design.error.message}</Alert>}
    </Group>
  );
}

function Routes({ saveId, d }: { saveId: string; d: MedicalDevice }) {
  const submit = useSubmitDevice(saveId);
  const columns = useMemo(
    () =>
      routeHelper.columns([
        routeHelper.accessor('regulator_name', { header: 'Regulator' }),
        routeHelper.accessor('label', { header: 'Route', meta: { term: 'medical.510k' } }),
        routeHelper.accessor('review', {
          header: 'Review',
          cell: (c) => (
            <span title={c.row.original.explain} data-testid={`review-${c.row.original.regulator}`}>
              {c.getValue()}{' '}
              <Explain
                metric="medical_review"
                entity={`${d.product_id}:${c.row.original.regulator}`}
                label="Review range"
              />
            </span>
          ),
        }),
        routeHelper.accessor((r) => STATUS_WORDS[r.status], {
          id: 'status',
          header: 'Stage',
          cell: (c) => {
            const r = c.row.original;
            const when = r.filed
              ? ` (filed ${r.filed}${r.months_in !== null && r.months_in !== undefined ? `, ${r.months_in} months in` : ''})`
              : '';
            return (
              <span data-testid={`stage-${r.regulator}`}>
                {c.getValue()}
                {when}
              </span>
            );
          },
        }),
        routeHelper.accessor('fee_cents', {
          header: 'Fee',
          cell: (c) => (c.getValue() > 0 ? formatMoneyWhole(c.getValue()) : '—'),
        }),
        routeHelper.display({
          id: 'file',
          header: '',
          cell: (c) => {
            const r = c.row.original;
            if (r.status === 'review' || r.status === 'information_requested') return null;
            if (r.status === 'cleared' && !r.blocker) return null;
            return (
              <Button
                size="xs"
                disabled={r.blocker !== null && r.blocker !== undefined}
                title={r.blocker ?? undefined}
                loading={submit.isPending}
                onClick={() => submit.mutate({ product_id: d.product_id, regulator: r.regulator })}
                data-testid={`file-${r.regulator}`}
              >
                File
              </Button>
            );
          },
        }),
      ]),
    [d.product_id, submit],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: d.routes,
    getRowId: (r) => r.regulator,
  });
  return (
    <>
      <DataTable table={table} label="Submissions" rowTestId="route-row" />
      {d.routes
        .filter((r) => r.blocker && r.status === 'not_filed')
        .slice(0, 1)
        .map((r) => (
          <p key={r.regulator} className="tst-muted" style={{ fontSize: 13 }}>
            {r.regulator_name}: {r.blocker}.
          </p>
        ))}
      {submit.error && <Alert color="red">{submit.error.message}</Alert>}
    </>
  );
}

function Studies({ saveId, m, d }: { saveId: string; m: Medical; d: MedicalDevice }) {
  const start = useStartStudy(saveId);
  const [kind, setKind] = useState<string | null>('pivotal');
  const [patients, setPatients] = useState<number | string>('');
  const range = m.study_kinds.find((k) => k.kind === kind);
  const columns = useMemo(
    () =>
      studyHelper.columns([
        studyHelper.accessor((s) => STUDY_WORDS[s.kind] ?? s.kind, {
          id: 'kind',
          header: 'Study',
          meta: { term: 'medical.pivotal_study' },
        }),
        studyHelper.accessor('patients', { header: 'Patients' }),
        studyHelper.accessor('readout', { header: 'Readout' }),
        studyHelper.accessor('cost_cents', {
          header: 'Cost',
          cell: (c) => (
            <span title={c.row.original.explain}>
              {formatMoneyWhole(c.getValue())}{' '}
              <Explain metric="study_cost" entity={c.row.original.id} label="Study cost" />
            </span>
          ),
        }),
        studyHelper.accessor(
          (s) =>
            s.status === 'running'
              ? `running (${s.success_range ?? ''})`
              : s.status === 'succeeded'
                ? 'met its endpoint'
                : 'missed its endpoint',
          {
            id: 'status',
            header: 'Result',
          },
        ),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: d.studies,
    getRowId: (s) => String(s.id),
  });
  const running = d.studies.some((s) => s.status === 'running');
  return (
    <div style={{ marginTop: 8 }}>
      {d.studies.length > 0 && <DataTable table={table} label="Studies" rowTestId="study-row" />}
      {!running && (
        <Group gap="xs" align="end" mt={4}>
          <Select
            label="Study"
            data={m.study_kinds.map((k) => ({
              value: k.kind,
              label: STUDY_WORDS[k.kind] ?? k.kind,
            }))}
            value={kind}
            onChange={setKind}
            allowDeselect={false}
            data-testid="study-kind"
            w={160}
          />
          <NumberInput
            label={range ? `Patients (${range.patients[0]}-${range.patients[1]})` : 'Patients'}
            value={patients}
            onChange={setPatients}
            min={1}
            w={170}
            data-testid="study-patients"
          />
          <Button
            size="xs"
            loading={start.isPending}
            onClick={() =>
              kind &&
              start.mutate({
                product_id: d.product_id,
                kind: kind as 'feasibility' | 'pivotal' | 'post_market',
                patients: typeof patients === 'number' ? patients : null,
              })
            }
            data-testid="start-study"
          >
            Start study
          </Button>
        </Group>
      )}
      {start.error && <Alert color="red">{start.error.message}</Alert>}
    </div>
  );
}

function Regions({ saveId, d }: { saveId: string; d: MedicalDevice }) {
  const ask = useRequestCoverage(saveId);
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region' }),
        regionHelper.accessor('cleared', { header: 'Cleared by' }),
        regionHelper.accessor('coverage', {
          header: 'Coverage',
          meta: { term: 'medical.coverage' },
          cell: (c) => {
            const r = c.row.original;
            const label =
              r.coverage === 'not_needed'
                ? 'paid by buyers'
                : r.coverage === 'none'
                  ? `not asked (${r.coverage_window ?? ''})`
                  : r.coverage === 'pending'
                    ? `pending (${r.coverage_window ?? ''})`
                    : r.coverage;
            const can =
              (r.coverage === 'none' || r.coverage === 'denied') && r.cleared !== 'not cleared';
            return (
              <Group gap={4}>
                <span data-testid={`coverage-${r.region}`}>{label}</span>
                {can && (
                  <Button
                    size="compact-xs"
                    onClick={() => ask.mutate({ product_id: d.product_id, region: r.region })}
                    data-testid={`ask-coverage-${r.region}`}
                  >
                    Ask
                  </Button>
                )}
              </Group>
            );
          },
        }),
        regionHelper.accessor(
          (r) => (r.adoption === null || r.adoption === undefined ? '—' : formatShare(r.adoption)),
          {
            id: 'adoption',
            header: 'Clinicians using it',
          },
        ),
        regionHelper.accessor((r) => formatShare(r.sells_share), {
          id: 'sells',
          header: 'Demand open to it',
        }),
      ]),
    [ask, d.product_id],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: d.regions,
    getRowId: (r) => r.region,
  });
  return (
    <div style={{ marginTop: 8 }}>
      <DataTable table={table} label="Regions" rowTestId="region-row" />
      {ask.error && <Alert color="red">{ask.error.message}</Alert>}
    </div>
  );
}

function Support({ saveId, d }: { saveId: string; d: MedicalDevice }) {
  const set = useMedicalSupport(saveId);
  const [training, setTraining] = useState<number | string>(d.training_cents / 100);
  const [surveillance, setSurveillance] = useState(d.surveillance);
  return (
    <Group gap="xs" align="end" mt={8}>
      <NumberInput
        label="Clinical education a month a region ($)"
        value={training}
        onChange={setTraining}
        min={0}
        step={10000}
        thousandSeparator=","
        w={260}
        data-testid="training"
      />
      <Checkbox
        label="Post-market surveillance"
        checked={surveillance}
        onChange={(e) => setSurveillance(e.currentTarget.checked)}
        data-testid="surveillance"
      />
      <Button
        size="xs"
        loading={set.isPending}
        onClick={() =>
          set.mutate({
            product_id: d.product_id,
            training_cents: Math.round((typeof training === 'number' ? training : 0) * 100),
            surveillance,
          })
        }
        data-testid="save-support"
      >
        Save
      </Button>
    </Group>
  );
}

function Plants({ saveId, m }: { saveId: string; m: Medical }) {
  const set = usePlantQuality(saveId);
  if (m.plants.length === 0) return null;
  return (
    <Panel title="Plants' quality systems" testId="plants">
      {m.plants.map((p) => (
        <Group key={p.facility_id} gap="xs" mb={4}>
          <span>
            Plant {p.facility_id} ({p.region.replace(/_/g, ' ')}): {formatMoneyWhole(p.cents_month)}{' '}
            a month
          </span>
          <Select
            data={Object.keys(m.quality_levels).map((k) => ({
              value: k,
              label: `${k} (${formatMoneyWhole(m.quality_levels[k] ?? 0)} a month)`,
            }))}
            value={p.level}
            onChange={(v) =>
              v &&
              set.mutate({ facility_id: p.facility_id, level: v as 'low' | 'standard' | 'high' })
            }
            allowDeselect={false}
            w={240}
            data-testid={`plant-quality-${p.facility_id}`}
          />
        </Group>
      ))}
      <p className="tst-muted" style={{ fontSize: 13 }}>
        <Term term="medical.quality_system">A quality system</Term> costs more at best practice and
        cuts defects, and so recalls, and inspection findings.
      </p>
    </Panel>
  );
}

function Rivals({ m }: { m: Medical }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('category', { header: 'Sub-category' }),
        rivalHelper.accessor('company', { header: 'Company' }),
        rivalHelper.accessor('product', { header: 'Product' }),
        rivalHelper.accessor((r) => formatShare(r.share), { id: 'share', header: 'Share' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.rivals,
    getRowId: (r) => r.company + r.product,
  });
  return (
    <Panel title="Rivals" testId="medical-rivals">
      <DataTable table={table} label="Medical rivals" rowTestId="rival-row" />
    </Panel>
  );
}
