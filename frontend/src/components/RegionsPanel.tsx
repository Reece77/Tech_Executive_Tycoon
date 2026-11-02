import { Alert, Button, Modal, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import {
  useProductRegions,
  useRegionAction,
  type ProductRegion,
  type ProductRegions,
} from '../hooks/api';
import { formatMoneyWhole, parseDollars } from '../lib/format';
import { formatCount } from '../lib/products';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Panel } from './ScreenState';

const helper = createColumnHelper<GameTableFeatures, ProductRegion>();

/** The product profile's Regions panel (M9, formulas.md 19.5, 19.7): where it sells,
 * prices, customers and MRR by region, reach, launching, and the builders' spread. */
export function RegionsPanel({ saveId, productId }: { saveId: string; productId: number }) {
  const regions = useProductRegions(saveId, productId);
  if (!regions.data) return null;
  return <Body saveId={saveId} r={regions.data} />;
}

function Body({ saveId, r }: { saveId: string; r: ProductRegions }) {
  const act = useRegionAction(saveId, r.product_id);
  const [launching, setLaunching] = useState<ProductRegion | null>(null);
  const [splitting, setSplitting] = useState(false);
  // The region's key, not a copy: the dialog reads the fresh row after each price (M10b).
  const [pricingKey, setPricingKey] = useState<string | null>(null);
  const pricing = r.regions.find((x) => x.region === pricingKey) ?? null;
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', {
          header: 'Region',
          meta: { term: 'geo.region' },
          cell: ({ getValue }) => <span style={{ fontWeight: 600 }}>{getValue()}</span>,
        }),
        helper.accessor('status_label', {
          header: 'Status',
          meta: { term: 'geo.region_status' },
          cell: ({ row }) => (
            <span data-testid={`region-status-${row.original.region}`}>
              {row.original.status_label}
            </span>
          ),
        }),
        helper.display({
          id: 'prices',
          header: 'Prices',
          meta: { term: 'geo.region_prices' },
          cell: ({ row }) =>
            row.original.status === 'not_launched'
              ? '—'
              : row.original.segments
                  .map(
                    (s) =>
                      `${s.label} ${s.price_cents === null ? '—' : formatMoneyWhole(s.price_cents)}`,
                  )
                  .join(' · '),
        }),
        helper.accessor('customers', {
          header: 'Customers',
          meta: { term: 'geo.region_customers' },
          sortFn: 'basic',
          cell: ({ row }) =>
            row.original.status === 'not_launched' ? (
              <span className="tst-muted">{formatCount(row.original.addressable)} addressable</span>
            ) : (
              <span className="tst-num">{formatCount(row.original.customers)}</span>
            ),
        }),
        helper.accessor('mrr_cents', {
          header: 'MRR',
          meta: { term: 'geo.region_mrr' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        helper.display({
          id: 'marketing',
          header: 'Marketing',
          meta: { term: 'geo.region_marketing' },
          cell: ({ row }) =>
            row.original.marketing_share === null ? (
              '—'
            ) : (
              <span className="tst-num" data-testid={`region-marketing-${row.original.region}`}>
                {Math.round(row.original.marketing_share * 100)}%
                {row.original.awareness_factor !== null &&
                  ` · awareness ×${row.original.awareness_factor.toFixed(2)}`}
              </span>
            ),
        }),
        helper.display({
          id: 'reach',
          header: 'Reach',
          meta: { term: 'geo.reach' },
          cell: ({ row }) => (
            <span
              style={{
                color:
                  row.original.status === 'not_launched' ||
                  row.original.sellers_here + row.original.sellers_neighbour > 0 ||
                  row.original.local_presence
                    ? undefined
                    : 'var(--tst-warn)',
                fontSize: 13,
              }}
            >
              {row.original.reach_note}; sellers {row.original.sellers_here} here,{' '}
              {row.original.sellers_neighbour} in {row.original.neighbour_label}
            </span>
          ),
        }),
        helper.accessor('rivals', {
          header: 'Rivals',
          meta: { term: 'geo.region_rivals' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
        helper.display({
          id: 'act',
          header: '',
          cell: ({ row }) =>
            row.original.status === 'not_launched' ? (
              <Button
                size="xs"
                data-testid={`launch-${row.original.region}`}
                disabled={row.original.launch_problem !== null}
                title={row.original.launch_problem ?? undefined}
                onClick={() => setLaunching(row.original)}
              >
                Launch
              </Button>
            ) : row.original.status !== 'home' ? (
              <Button
                size="xs"
                variant="subtle"
                onClick={() => setPricingKey(row.original.region)}
                data-testid={`prices-${row.original.region}`}
              >
                Prices
              </Button>
            ) : null,
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
  return (
    <Panel title="Regions" testId="regions-panel">
      {act.error && (
        <Alert color="warn" data-testid="region-error">
          {act.error.message}
        </Alert>
      )}
      <DataTable table={table} label="Regions" rowTestId="region-row" />
      <ul
        className="tst-muted"
        style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}
        data-testid="region-rules"
      >
        {r.rules.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {r.regions.filter((x) => x.marketing_share !== null).length > 1 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Button
            size="xs"
            variant="default"
            onClick={() => setSplitting(true)}
            data-testid="marketing-split"
          >
            Split marketing
          </Button>
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {r.marketing_custom ? 'Your split' : 'Following revenue by region'} · energy{' '}
            {r.marketing_energy}
          </span>
        </div>
      )}
      {splitting && (
        <SplitDialog
          r={r}
          busy={act.isPending}
          onClose={() => setSplitting(false)}
          onSet={(shares) =>
            act.mutate({ kind: 'marketing', shares }, { onSuccess: () => setSplitting(false) })
          }
        />
      )}
      <p className="tst-muted" style={{ fontSize: 13 }} data-testid="team-spread">
        Builders: {r.team.map((t) => `${t.label} ${t.builders}`).join(', ') || 'none assigned'}
        {r.time_zone_factor < 1
          ? ` — working across regions costs output (×${r.time_zone_factor.toFixed(2)})`
          : ''}
      </p>
      {launching && (
        <Modal opened onClose={() => setLaunching(null)} title={`Launch in ${launching.label}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 14 }}>
            <div className="tst-row">
              <span>Localization, now</span>
              <span className="tst-num">{formatMoneyWhole(launching.launch_cost_cents ?? 0)}</span>
            </div>
            <div className="tst-row">
              <span>Goes live</span>
              <span>{launching.live_label}</span>
            </div>
            <div className="tst-row">
              <span>Addressable customers</span>
              <span className="tst-num">{formatCount(launching.addressable)}</span>
            </div>
            <div className="tst-row">
              <span>Local rivals</span>
              <span className="tst-num">{launching.rivals}</span>
            </div>
            <p className="tst-muted" style={{ margin: 0 }}>
              Prices start at the region&apos;s usual level. While localizing ({r.localize_months}{' '}
              months) new features come 10% slower. Energy {r.launch_energy}.
            </p>
            <Button
              data-testid="launch-confirm"
              loading={act.isPending}
              onClick={() =>
                act.mutate(
                  { kind: 'launch', region: launching.region },
                  { onSuccess: () => setLaunching(null) },
                )
              }
            >
              Launch
            </Button>
          </div>
        </Modal>
      )}
      {pricing && (
        <PriceDialog
          region={pricing}
          busy={act.isPending}
          onClose={() => setPricingKey(null)}
          onSet={(segment, priceCents) =>
            act.mutate({ kind: 'price', region: pricing.region, segment, priceCents })
          }
        />
      )}
    </Panel>
  );
}

function PriceDialog({
  region,
  busy,
  onClose,
  onSet,
}: {
  region: ProductRegion;
  busy: boolean;
  onClose: () => void;
  onSet: (segment: string, priceCents: number) => void;
}) {
  const [text, setText] = useState<Record<string, string>>({});
  return (
    <Modal opened onClose={onClose} title={`Prices in ${region.label}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {region.segments.map((s) => (
          <div key={s.segment} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <TextInput
              label={`${s.label}: now ${s.price_cents === null ? 'no price' : formatMoneyWhole(s.price_cents)} (usual ${formatMoneyWhole(s.default_price_cents)})`}
              data-testid={`region-price-${s.segment}`}
              placeholder={s.price_cents === null ? '' : formatMoneyWhole(s.price_cents)}
              value={text[s.segment] ?? ''}
              onChange={(e) => setText({ ...text, [s.segment]: e.currentTarget.value })}
            />
            <Button
              loading={busy}
              disabled={!(parseDollars(text[s.segment] ?? '') > 0)}
              onClick={() => {
                onSet(s.segment, parseDollars(text[s.segment] ?? ''));
                setText({ ...text, [s.segment]: '' });
              }}
            >
              Set
            </Button>
          </div>
        ))}
      </div>
    </Modal>
  );
}

/** The marketing split by region, in whole percent summing to 100 (23.5, M10b). */
function SplitDialog({
  r,
  busy,
  onClose,
  onSet,
}: {
  r: ProductRegions;
  busy: boolean;
  onClose: () => void;
  onSet: (shares: Record<string, number>) => void;
}) {
  const selling = r.regions.filter((x) => x.marketing_share !== null);
  const [text, setText] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      selling.map((x) => [x.region, String(Math.round((x.marketing_share ?? 0) * 100))]),
    ),
  );
  const percents = Object.fromEntries(
    selling.map((x) => [x.region, Number.parseInt(text[x.region] ?? '0', 10) || 0]),
  );
  const total = Object.values(percents).reduce((a, b) => a + b, 0);
  return (
    <Modal opened onClose={onClose} title="Split marketing by region">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {selling.map((x) => (
          <TextInput
            key={x.region}
            label={`${x.label} (%)`}
            value={text[x.region] ?? ''}
            onChange={(e) => setText({ ...text, [x.region]: e.currentTarget.value })}
            data-testid={`split-${x.region}`}
          />
        ))}
        <span className="tst-muted" style={{ fontSize: 13 }}>
          Total {total}%. A region with no marketing gets 70% of the usual awareness.
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            loading={busy}
            disabled={total !== 100}
            onClick={() =>
              onSet(Object.fromEntries(Object.entries(percents).map(([k, v]) => [k, v * 100])))
            }
            data-testid="split-confirm"
          >
            Set split
          </Button>
          <Button variant="default" loading={busy} onClick={() => onSet({})}>
            Follow revenue
          </Button>
        </div>
      </div>
    </Modal>
  );
}
