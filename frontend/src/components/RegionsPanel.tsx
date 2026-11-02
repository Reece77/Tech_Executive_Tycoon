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
          id: 'reach',
          header: 'Reach',
          meta: { term: 'geo.reach' },
          cell: ({ row }) => (
            <span
              style={{
                color: row.original.local_presence ? undefined : 'var(--tst-warn)',
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
