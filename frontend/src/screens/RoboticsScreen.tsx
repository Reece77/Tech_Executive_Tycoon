// Robotics (M39, formulas.md 53.1-53.2): industrial robot installations, labour costs and density by
// region, the robot makers' lines and shares, the humanoid market (its era, announcements, adoption
// and actuators), the player's robot lines with their humanoid designs, and plant automation:
// robots installed in the player's assembly and vehicle plants with the conversion cost a unit
// before and after. No game values are computed here: figures are formatted.
import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  pct,
  useInstallRobots,
  useRobotics,
  useSetHumanoidSpec,
  type PlantAutomation,
  type RobotLine,
  type RobotMaker,
  type RobotRegion,
  type Robotics,
} from '../hooks/robotics';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const regionHelper = createColumnHelper<GameTableFeatures, RobotRegion>();
const makerHelper = createColumnHelper<GameTableFeatures, RobotMaker>();
const lineHelper = createColumnHelper<GameTableFeatures, RobotLine>();
const plantHelper = createColumnHelper<GameTableFeatures, PlantAutomation>();

const CATEGORY: Record<string, string> = {
  industrial_robots: 'Industrial',
  humanoid_robots: 'Humanoid',
};

export function RoboticsScreen() {
  const { saveId = '' } = useParams();
  const q = useRobotics(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load robotics" error={q.error} />;
  return <RoboticsBody saveId={saveId} r={q.data} />;
}

function RoboticsBody({ saveId, r }: { saveId: string; r: Robotics }) {
  const h = r.humanoids;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="robotics.scale">{r.scale_basis}</Term>
          </span>
        }
      >
        Robotics
      </ScreenTitle>
      <Panel title="Markets" testId="robotics-regions">
        <p style={{ margin: '0 0 8px' }}>
          A robot {formatMoney(Math.round(r.options.robot_cents))}, installed{' '}
          {formatMoney(Math.round(r.options.system_cents))} (2010 dollars).
        </p>
        <RegionTable r={r} />
      </Panel>
      <Panel title="Makers" testId="robotics-makers">
        <MakerTable r={r} />
      </Panel>
      <Panel title="Humanoids" testId="robotics-humanoids">
        <p data-testid="humanoid-era" style={{ margin: '0 0 8px' }}>
          The {h.era} era ({h.window}):{' '}
          {h.arrived ? `arrived ${h.arrived}` : 'not arrived yet; no humanoid sales before it'}.{' '}
          {h.open && (
            <>
              <Term term="robotics.actuators">Actuators</Term>{' '}
              {formatMoney(Math.round(h.actuator_cents))} a robot (index{' '}
              {h.actuator_index.toFixed(2)}
              ); best <Term term="robotics.capability">capability</Term>{' '}
              {h.best_capability.toFixed(0)}.{h.homes_open ? ' Homes buy humanoids now.' : ''}
            </>
          )}
        </p>
        {h.announcements.length > 0 && (
          <ul style={{ margin: 0 }}>
            {h.announcements.map((a) => (
              <li key={`${a.month}-${a.label}`}>
                {a.month}: {a.label}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Your robot lines" testId="robotics-lines">
        <LineTable saveId={saveId} r={r} />
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Make a robot line from Products (Industrial robots, or Humanoid robots once their era
          arrives) and assemble it in an assembly plant or under a contract from Hardware.
        </p>
      </Panel>
      <Panel title="Plant automation" testId="robotics-plants">
        <PlantTable saveId={saveId} r={r} />
      </Panel>
    </>
  );
}

function RegionTable({ r }: { r: Robotics }) {
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region' }),
        regionHelper.accessor('installations_year', {
          header: 'Robots a year',
          meta: { term: 'robotics.installations' },
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        regionHelper.accessor('game_installations_year', {
          header: 'In the game',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        regionHelper.accessor('density', {
          header: 'Density',
          meta: { term: 'robotics.density' },
          cell: (c) => (c.getValue() == null ? '—' : Math.round(c.getValue() ?? 0).toString()),
        }),
        regionHelper.accessor('labour_cents_hour', {
          header: 'Labour an hour',
          cell: (c) => formatMoney(Math.round(c.getValue())),
        }),
        regionHelper.accessor('humanoid_adoption', {
          header: 'Humanoid adoption',
          cell: (c) => (c.getValue() > 0 ? pct(c.getValue(), 2) : '—'),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.regions,
    getRowId: (x) => x.region,
  });
  return <DataTable table={table} label="Robot markets" rowTestId="robot-region-row" />;
}

function MakerTable({ r }: { r: Robotics }) {
  const columns = useMemo(
    () =>
      makerHelper.columns([
        makerHelper.accessor('company', { header: 'Maker' }),
        makerHelper.accessor('product', { header: 'Line' }),
        makerHelper.accessor('category', {
          header: 'Kind',
          cell: (c) => CATEGORY[c.getValue()] ?? c.getValue(),
        }),
        makerHelper.accessor('price_cents', {
          header: 'Price',
          cell: (c) => {
            const p = c.getValue();
            return p == null ? 'not selling' : formatMoneyShort(p);
          },
        }),
        makerHelper.accessor(
          (m) =>
            m.shares
              .filter((s) => s.share >= 0.005)
              .map((s) => `${s.region.replaceAll('_', ' ')} ${pct(s.share, 0)}`)
              .join(', ') || '—',
          { id: 'shares', header: 'Shares of served buyers' },
        ),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.makers,
    getRowId: (m) => String(m.company_id),
  });
  return <DataTable table={table} label="Robot makers" rowTestId="robot-maker-row" />;
}

function LineTable({ saveId, r }: { saveId: string; r: Robotics }) {
  const columns = useMemo(
    () =>
      lineHelper.columns([
        lineHelper.accessor('name', { header: 'Line' }),
        lineHelper.accessor('category', {
          header: 'Kind',
          cell: (c) => CATEGORY[c.getValue()] ?? c.getValue(),
        }),
        lineHelper.accessor('status', { header: 'Status' }),
        lineHelper.accessor('quality', { header: 'Quality', cell: (c) => c.getValue().toFixed(0) }),
        lineHelper.accessor('capability', {
          header: 'Capability',
          meta: { term: 'robotics.capability' },
          cell: (c) => (c.getValue() == null ? '—' : (c.getValue() ?? 0).toFixed(0)),
        }),
        lineHelper.accessor('customers', {
          header: 'Customers',
          cell: (c) => c.getValue().toFixed(0),
        }),
        lineHelper.accessor('unit_cost_cents', {
          header: 'Materials a unit',
          cell: (c) => formatMoney(Math.round(c.getValue())),
        }),
        lineHelper.display({
          id: 'design',
          header: 'Design',
          cell: (c) =>
            c.row.original.category === 'humanoid_robots' ? (
              <HumanoidDesign saveId={saveId} r={r} line={c.row.original} />
            ) : (
              '—'
            ),
        }),
      ]),
    [saveId, r],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.lines,
    getRowId: (l) => String(l.product_id),
  });
  if (r.lines.length === 0) return <p className="tst-muted">You make no robots yet.</p>;
  return <DataTable table={table} label="Your robot lines" rowTestId="robot-line-row" />;
}

function HumanoidDesign({ saveId, r, line }: { saveId: string; r: Robotics; line: RobotLine }) {
  const set = useSetHumanoidSpec(saveId);
  const none = { value: '', label: 'Licensed' };
  const [ai, setAi] = useState('');
  const [chip, setChip] = useState('');
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <Select
        aria-label="AI model"
        size="xs"
        data={[
          none,
          ...r.options.ai_models.map((p) => ({ value: String(p.product_id), label: p.name })),
        ]}
        value={ai}
        onChange={(x) => setAi(x ?? '')}
      />
      <Select
        aria-label="Chips"
        size="xs"
        data={[
          { value: '', label: 'Bought' },
          ...r.options.accelerators.map((p) => ({ value: String(p.product_id), label: p.name })),
        ]}
        value={chip}
        onChange={(x) => setChip(x ?? '')}
      />
      <Button
        size="compact-xs"
        variant="light"
        disabled={set.isPending}
        onClick={() =>
          set.mutate({
            productId: line.product_id,
            body: {
              ai_product_id: ai ? Number(ai) : null,
              chip_product_id: chip ? Number(chip) : null,
            },
          })
        }
      >
        Set
      </Button>
    </span>
  );
}

function PlantTable({ saveId, r }: { saveId: string; r: Robotics }) {
  const columns = useMemo(
    () =>
      plantHelper.columns([
        plantHelper.accessor('name', { header: 'Plant' }),
        plantHelper.accessor('region', {
          header: 'Region',
          cell: (c) => c.getValue().replaceAll('_', ' '),
        }),
        plantHelper.accessor('robots', {
          header: 'Robots',
          cell: (c) =>
            `${c.getValue().toLocaleString()} of ${c.row.original.max_robots.toLocaleString()}`,
        }),
        plantHelper.accessor('level', {
          header: 'Automation',
          meta: { term: 'robotics.automation' },
          cell: (c) => pct(c.getValue(), 0),
        }),
        plantHelper.accessor((p) => p.cost_without.total_cents, {
          id: 'without',
          header: 'Cost a unit, no robots',
          cell: (c) => formatMoney(Math.round(c.getValue())),
        }),
        plantHelper.accessor((p) => p.cost_with.total_cents, {
          id: 'with',
          header: 'With robots',
          cell: (c) => (
            <span data-testid={`plant-unit-cost-${c.row.original.facility_id}`}>
              {formatMoney(Math.round(c.getValue()))}{' '}
              <Explain
                metric="automation_saving"
                entity={c.row.original.facility_id}
                label="automation saving"
              />
            </span>
          ),
        }),
        plantHelper.display({
          id: 'install',
          header: 'Install',
          cell: (c) => <Install saveId={saveId} r={r} plant={c.row.original} />,
        }),
      ]),
    [saveId, r],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: r.plants,
    getRowId: (p) => String(p.facility_id),
  });
  if (r.plants.length === 0)
    return <p className="tst-muted">You own no assembly or vehicle plants to automate.</p>;
  return <DataTable table={table} label="Plant automation" rowTestId="plant-automation-row" />;
}

function Install({ saveId, r, plant }: { saveId: string; r: Robotics; plant: PlantAutomation }) {
  const install = useInstallRobots(saveId);
  const left = Math.max(0, plant.max_robots - plant.robots);
  const [n, setN] = useState<number>(
    Math.min(left, Math.max(1, Math.round(plant.max_robots * 0.75))),
  );
  const [source, setSource] = useState('');
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <NumberInput
        aria-label="Robots"
        data-testid={`robots-count-${plant.facility_id}`}
        size="xs"
        min={1}
        max={Math.max(1, left)}
        value={n}
        onChange={(x) => setN(Number(x) || 1)}
        style={{ width: 90 }}
      />
      <Select
        aria-label="Robot source"
        size="xs"
        data={[
          { value: '', label: 'Bought' },
          ...r.options.own_robot_lines.map((p) => ({ value: String(p.product_id), label: p.name })),
        ]}
        value={source}
        onChange={(x) => setSource(x ?? '')}
      />
      <Button
        size="compact-xs"
        data-testid={`install-robots-${plant.facility_id}`}
        disabled={install.isPending || left === 0}
        onClick={() =>
          install.mutate({
            facilityId: plant.facility_id,
            body: { robots: n, product_id: source ? Number(source) : null },
          })
        }
      >
        Install
      </Button>
      {install.error && <Alert color="red">{String(install.error.message ?? install.error)}</Alert>}
    </span>
  );
}
