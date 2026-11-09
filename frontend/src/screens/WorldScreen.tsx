import { Alert, Button } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Sparkline } from '../components/Sparkline';
import {
  useWorld,
  useWorldAction,
  type Licence,
  type ProductExposure,
  type Rule,
  type SupplyExposure,
  type World,
  type WorldAction,
} from '../hooks/geopolitics';
import { formatMoney } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const ruleHelper = createColumnHelper<GameTableFeatures, Rule>();
const licenceHelper = createColumnHelper<GameTableFeatures, Licence>();
const productHelper = createColumnHelper<GameTableFeatures, ProductExposure>();
const supplyHelper = createColumnHelper<GameTableFeatures, SupplyExposure>();

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`;

const STATUS: Record<string, string> = {
  in_force: 'In force',
  coming: 'Announced',
  ended: 'Ended',
  suspended: 'Suspended',
};

/** World (M22, formulas.md 39): blocs, US-China tension, the export rules announced so far,
 * licences, compliant variants, the entity list and the group's exposure. */
export function WorldScreen() {
  const { saveId = '' } = useParams();
  const world = useWorld(saveId);
  if (world.isPending) return <Loading />;
  if (world.error) return <LoadError title="Could not load the world" error={world.error} />;
  return <WorldBody saveId={saveId} w={world.data} />;
}

export function WorldBody({ saveId, w }: { saveId: string; w: World }) {
  const act = useWorldAction(saveId);
  const run = (a: WorldAction) => act.mutate(a);
  const current = w.rules.filter((r) => r.status !== 'ended');
  const past = w.rules.filter((r) => r.status === 'ended');
  const now = w.tension_history.at(-1);
  return (
    <>
      <Link to={`/game/${saveId}/competitors`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Competitors
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>World</h1>
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="tension">
          US-China tension {w.tension.toFixed(0)}/100 {now ? `(${now.label})` : ''}
        </span>
        <Sparkline values={w.tension_history.map((t) => t.value)} label="Tension history" />
      </div>
      {act.error && (
        <Alert color="warn" data-testid="world-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Your exposure" testId="exposure-panel">
        {w.products.length === 0 && w.supply.length === 0 && w.listings.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12 }} data-testid="no-exposure">
            No export control touches the group.
          </p>
        ) : (
          <>
            {w.products.length > 0 && (
              <ProductsTable products={w.products} busy={act.isPending} onAct={run} />
            )}
            {w.supply.length > 0 && <SupplyTable supply={w.supply} />}
          </>
        )}
        {w.listings.map((x) => (
          <Alert key={`${x.company_id}-${x.actor_label}`} color="red" data-testid="listing">
            {x.company} is on {x.actor_label}'s entity list since {x.since} ({x.reason}).
          </Alert>
        ))}
        {w.sites
          .filter((s) => s.partner_needed && !s.local_partner)
          .map((s) => (
            <div key={s.company_id} style={{ fontSize: 13 }}>
              {s.company} sits in {s.country_label}: cloud there needs a local partner.{' '}
              <Button
                size="compact-xs"
                disabled={act.isPending}
                onClick={() => run({ kind: 'partner', companyId: s.company_id })}
                data-testid="take-partner"
              >
                Take a local partner
              </Button>
            </div>
          ))}
      </Panel>
      <Panel title="Rules in force and announced" testId="rules-panel">
        <RulesTable rules={current} rowTestId="rule-row" />
      </Panel>
      {w.tariffs.length > 0 && (
        <Panel title="Tariffs this month" testId="tariffs-panel">
          {w.tariffs.map((t) => (
            <div key={t.key} style={{ fontSize: 13 }} data-testid="tariff-row">
              {t.title}: {pct(t.rate)} on {t.goods.join(', ')} made in {t.origin}, sold in{' '}
              {t.market} ({t.tag})
            </div>
          ))}
        </Panel>
      )}
      <Panel title="Licences" testId="licences-panel">
        {w.licences.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12 }}>
            No licence requested.
          </p>
        ) : (
          <LicencesTable licences={w.licences} />
        )}
        {w.variants.map((v) => (
          <div key={v.product_id} style={{ fontSize: 13 }} data-testid="variant-row">
            Compliant variant of {v.product}, launched {v.launched}
            {v.voided_by.length > 0 ? `: no longer accepted under ${v.voided_by.join(', ')}` : ''}
          </div>
        ))}
      </Panel>
      {past.length > 0 && (
        <Panel title="Earlier rules" testId="past-rules-panel">
          <RulesTable rules={past} rowTestId="past-rule-row" />
        </Panel>
      )}
    </>
  );
}

function RulesTable({ rules, rowTestId }: { rules: Rule[]; rowTestId: string }) {
  const columns = useMemo(
    () =>
      ruleHelper.columns([
        ruleHelper.accessor('month', { header: 'From' }),
        ruleHelper.accessor('title', { header: 'Rule' }),
        ruleHelper.accessor('actor_label', { header: 'By' }),
        ruleHelper.accessor((r) => r.goods.join(', '), { id: 'goods', header: 'Goods' }),
        ruleHelper.accessor((r) => r.destinations.join(', '), { id: 'to', header: 'To' }),
        ruleHelper.accessor('regime', {
          header: 'Regime',
          cell: ({ row }) =>
            row.original.regime === 'licence'
              ? `licence (${pct(row.original.approval)} base)`
              : row.original.regime === 'quota'
                ? `quota ${pct(row.original.quota)}`
                : 'ban',
        }),
        ruleHelper.accessor('status', {
          header: 'Status',
          cell: ({ row }) =>
            `${STATUS[row.original.status] ?? row.original.status}${
              row.original.suspended_until ? ` to ${row.original.suspended_until}` : ''
            }${row.original.effect === 'news' ? ' (news)' : ''}`,
        }),
        ruleHelper.accessor((r) => r.tag ?? '', { id: 'tag', header: 'Source' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rules,
    getRowId: (r) => r.key,
  });
  return <DataTable table={table} label="Rules" rowTestId={rowTestId} />;
}

function LicencesTable({ licences }: { licences: Licence[] }) {
  const columns = useMemo(
    () =>
      licenceHelper.columns([
        licenceHelper.accessor('product', { header: 'Product' }),
        licenceHelper.accessor('country_label', { header: 'To' }),
        licenceHelper.accessor('rule', { header: 'Rule' }),
        licenceHelper.accessor('status', { header: 'Status' }),
        licenceHelper.accessor('decision', { header: 'Decision' }),
        licenceHelper.accessor((x) => x.until ?? '', { id: 'until', header: 'Until' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: licences,
    getRowId: (x) => String(x.id),
  });
  return <DataTable table={table} label="Licences" rowTestId="licence-row" />;
}

function ProductsTable({
  products,
  busy,
  onAct,
}: {
  products: ProductExposure[];
  busy: boolean;
  onAct: (a: WorldAction) => void;
}) {
  const columns = useMemo(
    () =>
      productHelper.columns([
        productHelper.accessor('product', { header: 'Product' }),
        productHelper.accessor(
          (p) =>
            p.regions
              .map(
                (r) =>
                  `${r.region}: ${pct(r.blocked)} closed${r.variant ? `, ${pct(r.variant)} as variant` : ''}`,
              )
              .join('; '),
          { id: 'access', header: 'Markets' },
        ),
        productHelper.accessor('tariff_cents', {
          header: 'Tariffs',
          cell: ({ getValue }) => formatMoney(getValue()),
        }),
        productHelper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) => (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {row.original.licensable.map((c) => (
                <Button
                  key={c}
                  size="compact-xs"
                  disabled={busy}
                  onClick={() =>
                    onAct({ kind: 'licence', productId: row.original.product_id, country: c })
                  }
                  data-testid="request-licence"
                >
                  Request licence ({c})
                </Button>
              ))}
              {row.original.variant_possible && (
                <Button
                  size="compact-xs"
                  disabled={busy}
                  onClick={() => onAct({ kind: 'variant', productId: row.original.product_id })}
                  data-testid="launch-variant"
                >
                  {row.original.has_variant ? 'Relaunch' : 'Launch'} compliant variant
                </Button>
              )}
            </div>
          ),
        }),
      ]),
    [busy, onAct],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: products,
    getRowId: (p) => String(p.product_id),
  });
  return <DataTable table={table} label="Products" rowTestId="exposure-row" />;
}

function SupplyTable({ supply }: { supply: SupplyExposure[] }) {
  const columns = useMemo(
    () =>
      supplyHelper.columns([
        supplyHelper.accessor('company', { header: 'Company' }),
        supplyHelper.accessor('good_label', { header: 'Input' }),
        supplyHelper.accessor('exposed', {
          header: 'From the restricting country',
          cell: ({ getValue }) => pct(getValue()),
        }),
        supplyHelper.accessor('allocation', {
          header: 'Allocation',
          cell: ({ getValue }) => pct(getValue()),
        }),
        supplyHelper.accessor('price_premium', {
          header: 'Price premium',
          cell: ({ getValue }) => `+${pct(getValue())}`,
        }),
        supplyHelper.accessor((x) => x.rule ?? '', { id: 'rule', header: 'Rule' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: supply,
    getRowId: (x) => `${x.company_id}-${x.good}`,
  });
  return <DataTable table={table} label="Supply" rowTestId="supply-row" />;
}
