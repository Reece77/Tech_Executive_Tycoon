// Regulation (M34, formulas.md 48): regulators by region with their regimes' thresholds and
// duties, the player's position against each test, designations, duties, investigations with
// their visible stages, fines, structural warning signs and orders, and history's precedents.
// No game values are computed here: shares, money and months are formatted only.
import { Alert, Badge, Button, Group } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import { formatShare } from '../hooks/platforms';
import {
  useAnswerOrder,
  useComplyDuties,
  useRegulation,
  type Regulation,
  type RegulationCase,
  type RegulationDesignation,
  type RegulationDuty,
  type RegulationTest,
} from '../hooks/regulation';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const caseHelper = createColumnHelper<GameTableFeatures, RegulationCase>();
const dutyHelper = createColumnHelper<GameTableFeatures, RegulationDuty>();
const designationHelper = createColumnHelper<GameTableFeatures, RegulationDesignation>();
const testHelper = createColumnHelper<GameTableFeatures, RegulationTest>();

export function RegulationScreen() {
  const { saveId = '' } = useParams();
  const q = useRegulation(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load regulation" error={q.error} />;
  return <RegulationBody saveId={saveId} r={q.data} />;
}

export function RegulationBody({ saveId, r }: { saveId: string; r: Regulation }) {
  const comply = useComplyDuties(saveId);
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {r.running
              ? 'Regulators test, investigate and rule each month from January 2026.'
              : 'To 2025, designations, cases and fines follow the historical record.'}{' '}
            Fines to date: {formatMoneyWhole(r.fines_cents)}{' '}
            <Explain metric="regulation_fines" label="Fines" />
          </span>
        }
      >
        Regulation
      </ScreenTitle>
      {r.breaches.length > 0 && (
        <Alert color="red" title="Non-compliance" data-testid="breaches">
          {r.breaches.join('; ')}. Breaking a duty raises the risk of a case and doubles its fine.{' '}
          <Button
            size="xs"
            ml="sm"
            loading={comply.isPending}
            onClick={() => comply.mutate()}
            data-testid="comply-duties"
          >
            Comply with every duty
          </Button>
        </Alert>
      )}
      <Orders saveId={saveId} r={r} />
      <Watches r={r} />
      <Tests r={r} />
      <Cases r={r} />
      <Duties r={r} />
      <Designations r={r} />
      <Regulators r={r} />
      <Panel title="Precedents">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {r.precedents.map((p) => (
            <li key={p.label + p.month}>
              <strong>{p.label}</strong> ({p.month}): {p.note}
            </li>
          ))}
        </ul>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          {r.explain.structural} <Term term="regulation.structural_remedy">Structural remedy</Term>
        </p>
      </Panel>
    </>
  );
}

function Orders({ saveId, r }: { saveId: string; r: Regulation }) {
  const answer = useAnswerOrder(saveId);
  const mine = r.orders.filter((o) => o.player);
  if (mine.length === 0) return null;
  return (
    <Panel title="Structural orders" testId="orders">
      {mine.map((o) => (
        <div key={o.id} data-testid={`order-${o.id}`} style={{ marginBottom: 8 }}>
          <strong>{o.regulator_name}</strong> ordered the company to separate{' '}
          <strong>{o.unit}</strong> ({o.ordered}; warned from {o.warned_from}). Deadline{' '}
          {o.deadline}. <Badge>{o.status}</Badge>
          {o.status === 'open' && (
            <Group gap="xs" mt={4}>
              <Button
                size="xs"
                disabled={!o.can_sell}
                onClick={() => answer.mutate({ order_id: o.id, how: 'sell' })}
                data-testid="order-sell"
              >
                Sell it
              </Button>
              <Button
                size="xs"
                disabled={!o.can_spin_off}
                onClick={() => answer.mutate({ order_id: o.id, how: 'spin_off' })}
                data-testid="order-spin-off"
              >
                Spin it off
              </Button>
            </Group>
          )}
        </div>
      ))}
    </Panel>
  );
}

function Watches({ r }: { r: Regulation }) {
  if (r.watches.length === 0) return null;
  return (
    <Panel title="Warning signs of a break-up" testId="watches">
      {r.watches.map((w) => (
        <div key={w.regulator + w.market} style={{ marginBottom: 6 }}>
          <strong>{w.regulator_name}</strong>, {w.market}: since {w.since} ({w.months} of the{' '}
          {w.needed_months} months an order needs).
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
            {w.signs.map((s) => (
              <li key={s.kind + s.month} data-testid="warning-sign">
                {s.month}: {s.label}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Panel>
  );
}

function Tests({ r }: { r: Regulation }) {
  const columns = useMemo(
    () =>
      testHelper.columns([
        testHelper.accessor('regime_name', {
          header: 'Regime',
          meta: { term: 'regulation.gatekeeper' },
        }),
        testHelper.accessor('users', {
          header: 'Users',
          meta: { term: 'regulation.thresholds' },
          cell: (c) =>
            `${formatShare(c.getValue())} of ${
              c.row.original.users_needed === null ? '—' : formatShare(c.row.original.users_needed)
            }`,
        }),
        testHelper.accessor('turnover_cents', {
          header: 'Turnover',
          meta: { term: 'regulation.thresholds' },
          cell: (c) =>
            c.row.original.turnover_needed_cents === null
              ? 'no test'
              : `${formatMoneyWhole(c.getValue())} of ${formatMoneyWhole(c.row.original.turnover_needed_cents)}`,
        }),
        testHelper.accessor('ratio', {
          header: 'Test',
          meta: { term: 'regulation.thresholds' },
          cell: (c) => (
            <>
              {formatShare(c.getValue())}{' '}
              <Explain
                metric="designation_thresholds"
                entity={c.row.original.regime}
                label="Designation test"
              />
            </>
          ),
        }),
        testHelper.accessor(
          (t) => (t.designated ? 'designated' : t.warned ? `warned ${t.warned}` : '—'),
          { id: 'status', header: 'Status', meta: { term: 'regulation.gatekeeper' } },
        ),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.tests,
    getRowId: (t) => t.regime,
  });
  return (
    <Panel title="Your position against the thresholds" testId="tests">
      <DataTable table={table} label="Designation tests" rowTestId="test-row" />
      <p className="tst-muted" style={{ fontSize: 13 }}>
        {r.explain.thresholds}
      </p>
    </Panel>
  );
}

function Cases({ r }: { r: Regulation }) {
  const columns = useMemo(
    () =>
      caseHelper.columns([
        caseHelper.accessor('company', { header: 'Company' }),
        caseHelper.accessor('regulator_name', { header: 'Regulator' }),
        caseHelper.accessor('title', {
          header: 'Case',
          meta: { term: 'regulation.statement_of_objections' },
        }),
        caseHelper.accessor('opened', { header: 'Opened' }),
        caseHelper.accessor(
          (c) =>
            c.outcome === 'open'
              ? `${c.stage}${c.stage_window ? ` (${c.stage_window})` : ''}`
              : c.outcome,
          { id: 'stage', header: 'Stage', meta: { term: 'regulation.statement_of_objections' } },
        ),
        caseHelper.accessor('fine_cents', {
          header: 'Fine',
          meta: { term: 'regulation.fine' },
          cell: (c) => {
            const final = c.row.original.final_cents;
            const fine = c.getValue() > 0 ? formatMoneyWhole(c.getValue()) : '—';
            return final !== null && final !== c.getValue()
              ? `${fine} (${formatMoneyWhole(final)} after appeal)`
              : fine;
          },
        }),
        caseHelper.accessor((c) => c.remedy ?? '—', {
          id: 'remedy',
          header: 'Remedy',
          meta: { term: 'regulation.behavioural_remedy' },
        }),
        caseHelper.accessor((c) => c.odds ?? '', {
          id: 'odds',
          header: 'Odds',
          meta: { term: 'regulation.odds' },
        }),
        caseHelper.accessor((c) => c.steps.map((s) => `${s.stage} ${s.month}`).join(' → '), {
          id: 'steps',
          header: 'Steps',
        }),
      ]),
    [],
  );
  const rows = useMemo(
    () => [...r.cases].sort((a, b) => Number(b.player) - Number(a.player)),
    [r.cases],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (c) => (c.id === null ? (c.key ?? '') : String(c.id)),
  });
  return (
    <Panel title="Investigations and rulings" testId="cases">
      <DataTable table={table} label="Investigations" rowTestId="case-row" />
      <p className="tst-muted" style={{ fontSize: 13 }}>
        {r.explain.fine}
      </p>
    </Panel>
  );
}

function Duties({ r }: { r: Regulation }) {
  const columns = useMemo(
    () =>
      dutyHelper.columns([
        dutyHelper.accessor('company', { header: 'Company' }),
        dutyHelper.accessor('regulator_name', { header: 'Regulator' }),
        dutyHelper.accessor('label', { header: 'Duty', meta: { term: 'regulation.duty' } }),
        dutyHelper.accessor('since', { header: 'Since' }),
        dutyHelper.accessor('source', { header: 'From' }),
        dutyHelper.accessor((d) => (d.breached ? 'breached' : ''), {
          id: 'breached',
          header: '',
        }),
      ]),
    [],
  );
  const rows = useMemo(
    () => [...r.duties].sort((a, b) => Number(b.player) - Number(a.player)),
    [r.duties],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (d) => String(d.id),
  });
  if (r.duties.length === 0) return null;
  return (
    <Panel title="Duties in force" testId="duties">
      <DataTable table={table} label="Duties" rowTestId="duty-row" />
    </Panel>
  );
}

function Designations({ r }: { r: Regulation }) {
  const columns = useMemo(
    () =>
      designationHelper.columns([
        designationHelper.accessor('company', { header: 'Company' }),
        designationHelper.accessor('regime_name', {
          header: 'Regime',
          meta: { term: 'regulation.gatekeeper' },
        }),
        designationHelper.accessor('since', { header: 'Designated' }),
        designationHelper.accessor('duties_from', { header: 'Duties from' }),
        designationHelper.accessor((d) => d.services.join(', '), {
          id: 'services',
          header: 'Services',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.designations,
    getRowId: (d) => `${d.regime}-${d.company}-${d.since}`,
  });
  return (
    <Panel title="Gatekeeper designations" testId="designations">
      <DataTable table={table} label="Designations" rowTestId="designation-row" />
    </Panel>
  );
}

function Regulators({ r }: { r: Regulation }) {
  return (
    <Panel title="Regulators by region" testId="regulators">
      {r.regulators.map((g) => (
        <div key={g.key} style={{ marginBottom: 8 }} data-testid="regulator">
          <strong>{g.name}</strong> ({g.region_label}
          {g.part ? `, ${g.part.replace('_', ' ')}` : ''})
          {g.structural ? ' · may order a break-up' : ''}
          {g.regime && (
            <div className="tst-muted" style={{ fontSize: 13 }}>
              {g.regime.name}, in force {g.regime.in_force}:{' '}
              {g.regime.users_share !== null && `${formatShare(g.regime.users_share)} of users; `}
              {g.regime.turnover_cents !== null &&
                `turnover ${formatMoneyWhole(g.regime.turnover_cents)}${
                  g.regime.turnover_scope === 'world' ? ' worldwide' : ' there'
                }; `}
              {g.regime.market_value_cents !== null &&
                `or market value ${formatMoneyWhole(g.regime.market_value_cents)}; `}
              duties after {g.regime.comply_months} months: {g.regime.duties.join(', ')}. Fines up
              to {formatShare(g.regime.max_fine_share)} of turnover.
            </div>
          )}
        </div>
      ))}
    </Panel>
  );
}
