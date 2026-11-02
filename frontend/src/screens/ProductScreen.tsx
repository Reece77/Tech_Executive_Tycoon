import { Alert, Button, Modal, NativeSelect, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { KpiTile } from '../components/KpiTile';
import { RegionsPanel } from '../components/RegionsPanel';
import { BreakdownTip } from '../components/Term';
import { LifecycleChip } from '../components/LifecycleChip';
import { ScoreBar, ScoreLegend, type ScoreBarItem } from '../components/ScoreBar';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { ActiveEffects } from '../components/ActiveEffects';
import { SegmentTable } from '../components/SegmentTable';
import {
  useCategories,
  useMarket,
  useOrg,
  usePricePreview,
  useProduct,
  useProductAction,
  useProductsMeta,
  useScaleup,
  useScaleupAction,
  type Market,
  type Product,
  type ProductAction,
  type ProductSegment,
  type ProductsMeta,
} from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole, parseDollars } from '../lib/format';
import {
  BRAND_TREND_TEXT,
  formatAppeal,
  formatCount,
  formatFlow,
  formatPercent,
  formatScore,
  formatSignedPercent,
  paceText,
  weightsText,
  seriesScope,
} from '../lib/products';

/** Cents as the price box shows them: 4000 -> "40", 35 -> "0.35". */
function priceText(cents: number | null): string {
  if (cents === null) return '';
  const rest = cents % 100;
  return rest === 0
    ? String(cents / 100)
    : `${Math.trunc(cents / 100)}.${String(rest).padStart(2, '0')}`;
}

export function ProductScreen() {
  const { saveId = '', productId = '' } = useParams();
  const id = Number(productId);
  const product = useProduct(saveId, id);
  const meta = useProductsMeta();
  if (product.isPending || meta.isPending) return <Loading />;
  if (product.error || meta.error) {
    return <LoadError title="Could not load the product" error={product.error ?? meta.error} />;
  }
  return <ProductBody saveId={saveId} product={product.data} meta={meta.data} />;
}

function ProductBody({
  saveId,
  product: p,
  meta,
}: {
  saveId: string;
  product: Product;
  meta: ProductsMeta;
}) {
  const market = useMarket(saveId, p.category);
  const act = useProductAction(saveId);
  const costs = meta.energy_costs;
  const run = (action: ProductAction, onSuccess?: () => void) =>
    act.mutate({ productId: p.product_id, action }, { onSuccess });
  const developing = p.status === 'in_development';

  // Price boxes: the text per segment; a box that differs from the price opens the preview.
  const [prices, setPrices] = useState<Record<string, string>>({});
  const current = useMemo(
    () => Object.fromEntries(p.segments.map((s) => [s.segment, priceText(s.price_cents)])),
    [p.segments],
  );
  const shown = { ...current, ...prices };
  const editing =
    Object.keys(prices).find((k) => prices[k] !== current[k] && parseDollars(prices[k]) > 0) ??
    null;
  const onPriceChange = useCallback(
    (segment: string, text: string) => setPrices((now) => ({ ...now, [segment]: text })),
    [],
  );
  const resetPrice = (segment: string) =>
    setPrices((now) => Object.fromEntries(Object.entries(now).filter(([k]) => k !== segment)));

  const firstSegment = p.segments[0]?.segment ?? '';
  const [segment, setSegment] = useState(firstSegment);
  const shownSegment = p.segments.some((s) => s.segment === segment) ? segment : firstSegment;

  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }} data-testid="product-name">
          {p.name}
        </h1>
        <span style={{ fontSize: 14, color: 'var(--tst-text-2)' }}>
          {p.category_label}
          {p.launched_label ? ` · launched ${p.launched_label}` : ''}
        </span>
        <LifecycleChip product={p} />
        <DivisionPicker saveId={saveId} p={p} />
        <Link
          to={`/game/${saveId}/products/markets/${p.category}`}
          style={{ fontSize: 13, marginLeft: 'auto' }}
          data-testid="market-link"
        >
          See the {p.category_label} market
        </Link>
      </div>
      {act.error && (
        <Alert color="red" title="Could not do that" data-testid="product-error">
          {act.error.message}
        </Alert>
      )}
      <Tiles p={p} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <Competition p={p} market={market.data} segment={shownSegment} onSegment={setSegment} />
        <TeamAndMarketing saveId={saveId} p={p} meta={meta} run={run} busy={act.isPending} />
      </div>
      {developing ? (
        <Readiness
          p={p}
          meta={meta}
          busy={act.isPending}
          onLaunch={() => run({ action: 'launch' })}
          cancelProduct={<CancelDevelopment saveId={saveId} p={p} meta={meta} />}
        >
          <SegmentTable
            segments={p.segments}
            price={{ prices: shown, editing, onChange: onPriceChange }}
            selling={false}
          />
        </Readiness>
      ) : (
        <section
          aria-label="Segments"
          style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
        >
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Segments</h2>
          <SegmentTable
            segments={p.segments}
            price={{ prices: shown, editing, onChange: onPriceChange }}
            selling
          />
          <AddSegments saveId={saveId} p={p} meta={meta} run={run} busy={act.isPending} />
          <RegionalPrices p={p} />
        </section>
      )}
      {developing && (
        <AddSegments saveId={saveId} p={p} meta={meta} run={run} busy={act.isPending} />
      )}
      <ActiveEffects saveId={saveId} effects={p.active_effects} />
      <RegionsPanel saveId={saveId} productId={p.product_id} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        {editing && (
          <PricePreview
            saveId={saveId}
            p={p}
            seg={p.segments.find((s) => s.segment === editing) as ProductSegment}
            priceCents={parseDollars(shown[editing])}
            cost={costs.set_price}
            busy={act.isPending}
            onSet={(cents) =>
              run({ action: 'price', segment: editing, price_cents: cents }, () =>
                resetPrice(editing),
              )
            }
            onCancel={() => resetPrice(editing)}
          />
        )}
        {!developing && <LastYear p={p} meta={meta} run={run} busy={act.isPending} />}
      </div>
    </>
  );
}

function Tiles({ p }: { p: Product }) {
  const noun = p.counts_users ? 'Users' : 'Customers';
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <KpiTile
        term="kpi.mrr"
        label="MRR"
        value={formatMoneyWhole(p.mrr_cents)}
        note={
          p.mrr_change === null
            ? 'At the current customers'
            : `${formatSignedPercent(p.mrr_change)} on last month${seriesScope(p)}`
        }
        testId="product-mrr"
      />
      <KpiTile
        term="kpi.customers"
        label={noun}
        value={formatCount(p.customers)}
        note={`${formatFlow(p.new_last_month, '+')} new, ${formatFlow(p.churned_last_month, '-')} lost${seriesScope(p)}`}
        testId="product-customers-total"
      />
      <KpiTile
        term="quality"
        label="Quality"
        value={formatScore(p.quality)}
        note={p.rotting ? 'Falling: nobody works on it' : `Pace: ${p.pace}`}
        warn={p.rotting}
        drivers={(v) => (
          <BreakdownTip breakdown={p.quality_breakdown} title="Quality" testId="quality-drivers">
            {v}
          </BreakdownTip>
        )}
        testId="product-quality"
      />
      <KpiTile
        term="kpi.hosting"
        label="Hosting"
        value={formatMoneyWhole(p.hosting_cents)}
        note="this month"
        testId="product-hosting"
      />
      <KpiTile
        term="kpi.development"
        label="Development"
        value={paceText(p.pace, p.builders.length)}
        small
        note={`${p.builders.length} ${p.builders.length === 1 ? 'builder' : 'builders'}${p.rotting ? ' · quality is falling' : ''}`}
        warn={p.rotting}
        testId="product-pace-tile"
      />
    </div>
  );
}

function Competition({
  p,
  market,
  segment,
  onSegment,
}: {
  p: Product;
  market: Market | undefined;
  segment: string;
  onSegment: (segment: string) => void;
}) {
  const mine = p.segments.find((s) => s.segment === segment);
  const seg = market?.segments.find((s) => s.segment === segment);
  const rivals = (seg?.products ?? []).filter((r) => r.product_id !== p.product_id);
  const items = (pick: (r: (typeof rivals)[number]) => [number, string], own: [number, string]) => [
    { key: String(p.product_id), name: p.name, value: own[0], text: own[1], mine: true },
    ...rivals.map((r): ScoreBarItem => ({
      key: String(r.product_id),
      name: r.name.startsWith(r.company_name) ? r.name : `${r.company_name} ${r.name}`,
      value: pick(r)[0],
      text: pick(r)[1],
      mine: r.is_player,
    })),
  ];
  const score = (v: number): [number, string] => [v, formatScore(v)];
  const ownPrice: [number, string] =
    mine?.price_cents != null && mine.price_score !== null
      ? [
          mine.price_score,
          `${formatMoneyWhole(mine.price_cents)} · ${formatScore(mine.price_score)}`,
        ]
      : [0, 'No price'];
  const ownAppeal: [number, string] =
    mine?.appeal != null ? [mine.appeal, formatAppeal(mine.appeal)] : [0, '—'];
  const legend = items((r) => score(r.quality), score(p.quality));
  return (
    <Panel
      title="Against the competition"
      label="Against the competition"
      style={{ flex: '3 1 520px', display: 'flex', flexDirection: 'column', gap: 12 }}
      action={
        p.segments.length > 1 && (
          <div role="group" aria-label="Segment" className="tst-toggle">
            {p.segments.map((s) => (
              <button
                key={s.segment}
                type="button"
                aria-pressed={s.segment === segment}
                onClick={() => onSegment(s.segment)}
                data-testid={`competition-${s.segment}`}
              >
                {s.label}
              </button>
            ))}
          </div>
        )
      }
    >
      {!seg ? (
        <p className="tst-muted" style={{ margin: 0 }}>
          Loading the market…
        </p>
      ) : (
        <>
          <ScoreLegend items={legend} />
          <ScoreBar label="Quality" items={legend} />
          <ScoreBar
            label="Features"
            items={items((r) => score(r.feature_score), score(p.feature_score))}
          />
          <ScoreBar label="Brand" items={items((r) => score(r.brand), score(p.brand))} />
          <ScoreBar
            label="Price"
            items={items(
              (r) => [
                r.price_score,
                `${formatMoneyWhole(r.price_cents)} · ${formatScore(r.price_score)}`,
              ],
              ownPrice,
            )}
          />
          <ScoreBar
            label="Appeal"
            strong
            items={items((r) => [r.appeal, formatAppeal(r.appeal)], ownAppeal)}
          />
          <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
            Appeal weighs {weightsText(seg.weights)} in {seg.label}. Price scores 50 at the
            segment&apos;s typical price ({formatMoneyWhole(seg.reference_price_cents)}) and 100 at
            half of it.
          </p>
        </>
      )}
    </Panel>
  );
}

function TeamAndMarketing({
  saveId,
  p,
  meta,
  run,
  busy,
}: {
  saveId: string;
  p: Product;
  meta: ProductsMeta;
  run: (action: ProductAction, onSuccess?: () => void) => void;
  busy: boolean;
}) {
  const costs = meta.energy_costs;
  const [assigning, setAssigning] = useState(false);
  const [draft, setDraft] = useState<string | null>(null); // null: show the saved budget
  const budget = draft ?? priceText(p.marketing_budget_cents);
  const budgetCents = budget.trim() === '' ? 0 : parseDollars(budget);
  const validBudget = budget.trim() === '' || budget.trim() === '0' || budgetCents > 0;
  const people = (label: string, list: Product['builders']) => (
    <>
      <span className="tst-muted" style={{ fontSize: 13 }}>
        {label}
      </span>
      <span
        style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
        data-testid={`team-${label.toLowerCase()}`}
      >
        {list.length === 0 ? (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            None
          </span>
        ) : (
          list.map((m) => (
            <Link
              key={m.person_id}
              to={`/game/${saveId}/people/${m.person_id}`}
              className="tst-chip"
            >
              {m.name}
            </Link>
          ))
        )}
      </span>
    </>
  );
  return (
    <Panel
      title="Who works on it"
      label="Team and marketing"
      style={{ flex: '2 1 340px', display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      {p.assigned_units.length === 0 && (
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }} data-testid="no-team">
          No unit works on it{p.status === 'in_development' ? '; it cannot develop' : ''}. Assign
          one below.
        </p>
      )}
      {p.assigned_units.map((u) => (
        <div key={u.unit_id ?? 'root'} className="tst-row" data-testid="assigned-unit">
          <Link to={`/game/${saveId}/org`}>{u.name}</Link>
          <Button
            size="compact-sm"
            variant="default"
            disabled={busy}
            onClick={() => run({ action: 'unassign', unit_id: u.unit_id })}
            data-testid="unassign"
          >
            Unassign · {costs.unassign_unit}
          </Button>
        </div>
      ))}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {people('Builders', p.builders)}
        {people('Sellers', p.sellers)}
        {people('Marketers', p.marketers)}
      </div>
      <Button
        variant="default"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => setAssigning(true)}
        data-testid="assign-unit"
      >
        Assign a unit · {costs.assign_unit}
      </Button>
      <h2 className="tst-ptitle" style={{ margin: '8px 0 0' }}>
        Marketing
      </h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 10 }}>
        <TextInput
          label="Monthly budget ($)"
          w={140}
          value={budget}
          onChange={(e) => setDraft(e.currentTarget.value)}
          error={validBudget ? undefined : 'Dollars, e.g. 10000'}
          data-testid="marketing-budget"
          styles={{ input: { fontFamily: 'var(--tst-font-mono)' } }}
        />
        <Button
          variant="default"
          disabled={busy || !validBudget || budgetCents === p.marketing_budget_cents}
          onClick={() =>
            run({ action: 'marketing', budget_cents: budgetCents }, () => setDraft(null))
          }
          data-testid="save-marketing"
        >
          Save · {costs.set_marketing}
        </Button>
      </div>
      <span className="tst-muted" style={{ fontSize: 12 }} data-testid="brand-trend">
        Brand {formatScore(p.brand)} {BRAND_TREND_TEXT[p.brand_trend] ?? ''}. Brand decides how many
        self-serve buyers hear of {p.name}; with no budget or marketers it drifts toward 0.
      </span>
      {assigning && (
        <AssignDialog
          saveId={saveId}
          p={p}
          cost={costs.assign_unit}
          busy={busy}
          onAssign={(unitId) =>
            run({ action: 'assign', unit_id: unitId }, () => setAssigning(false))
          }
          onClose={() => setAssigning(false)}
        />
      )}
    </Panel>
  );
}

function AssignDialog({
  saveId,
  p,
  cost,
  busy,
  onAssign,
  onClose,
}: {
  saveId: string;
  p: Product;
  cost: number;
  busy: boolean;
  onAssign: (unitId: number | null) => void;
  onClose: () => void;
}) {
  const org = useOrg(saveId);
  const free = (org.data?.units ?? []).filter((u) => u.product_id == null);
  const [choice, setChoice] = useState<string>('');
  const value = choice || (free[0] ? String(free[0].unit_id ?? 'root') : '');
  const busyUnits = (org.data?.units ?? []).filter(
    (u) => u.product_id != null && u.product_id !== p.product_id,
  );
  return (
    <Modal opened onClose={onClose} title={`Assign a unit to ${p.name}`} centered>
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        data-testid="assign-dialog"
      >
        {org.isPending && <Loading />}
        {free.length === 0 && !org.isPending ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            Every unit already works on a product. Unassign one first.
          </p>
        ) : (
          <NativeSelect
            label="Unit"
            value={value}
            onChange={(e) => setChoice(e.currentTarget.value)}
            data={free.map((u) => ({
              value: String(u.unit_id ?? 'root'),
              label: `${u.name} (${u.headcount} ${u.headcount === 1 ? 'person' : 'people'})`,
            }))}
            data-testid="assign-unit-select"
          />
        )}
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          Everyone in the unit works on {p.name}: builders develop it, sellers close mid-market and
          enterprise customers, marketers build its brand. Members of teams below it follow their
          own team. The company is you and whoever reports to you directly.
          {busyUnits.length > 0 &&
            ` Busy: ${busyUnits.map((u) => `${u.name} on ${u.product_name}`).join(', ')}.`}
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="md"
            disabled={!value || busy}
            loading={busy}
            onClick={() => onAssign(value === 'root' ? null : Number(value))}
            data-testid="assign-confirm"
          >
            Assign · {cost} energy
          </Button>
          <Button variant="default" size="md" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function Readiness({
  p,
  meta,
  busy,
  onLaunch,
  cancelProduct,
  children,
}: {
  p: Product;
  meta: ProductsMeta;
  busy: boolean;
  onLaunch: () => void;
  cancelProduct: ReactNode;
  children: ReactNode;
}) {
  const row = (label: string, value: number, need: number) => (
    <div className="tst-row">
      <span>{label}</span>
      <span
        className="tst-num"
        style={{ color: value >= need ? 'var(--tst-good)' : 'var(--tst-text-2)' }}
      >
        {formatScore(value)} of {formatScore(need)}
      </span>
    </div>
  );
  return (
    <section
      className="tst-panel"
      aria-label="Launch readiness"
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <h2 className="tst-ptitle" style={{ margin: 0 }}>
        Launch readiness
      </h2>
      <div style={{ maxWidth: 420 }}>
        {row('Quality', p.quality, meta.launch_min_quality)}
        {row('Feature score', p.feature_score, meta.launch_min_feature)}
      </div>
      {children}
      <p
        style={{
          margin: 0,
          fontSize: 13,
          color: p.launch.ready ? 'var(--tst-good)' : 'var(--tst-text-2)',
        }}
        data-testid="launch-missing"
      >
        {p.launch.ready ? 'Ready to launch.' : `Still needs: ${p.launch.missing.join('; ')}.`}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Button
          size="md"
          disabled={!p.launch.ready || busy}
          onClick={onLaunch}
          data-testid="launch"
        >
          Launch · {meta.energy_costs.launch_product}
        </Button>
        {cancelProduct}
      </div>
    </section>
  );
}

function CancelDevelopment({
  saveId,
  p,
  meta,
}: {
  saveId: string;
  p: Product;
  meta: ProductsMeta;
}) {
  const [open, setOpen] = useState(false);
  const act = useProductAction(saveId);
  const navigate = useNavigate();
  const cost = meta.energy_costs.cancel_product;
  return (
    <>
      <Button
        size="md"
        variant="default"
        style={{ color: 'var(--tst-warn)', borderColor: '#6A4426' }}
        onClick={() => setOpen(true)}
        data-testid="cancel-development"
      >
        Cancel development… · {cost}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={`Cancel ${p.name}?`} centered>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ margin: 0 }} data-testid="cancel-confirm-text">
            {p.name} is retired at once and its units are free to work on something else. Its
            progress is lost and this cannot be undone. Costs {cost} energy.
          </p>
          {act.error && (
            <Alert color="red" title="Could not cancel">
              {act.error.message}
            </Alert>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              size="md"
              color="orange"
              loading={act.isPending}
              onClick={() =>
                act.mutate(
                  { productId: p.product_id, action: { action: 'cancel' } },
                  { onSuccess: () => navigate(`/game/${saveId}/products`) },
                )
              }
              data-testid="cancel-confirm"
            >
              Cancel {p.name}
            </Button>
            <Button variant="default" size="md" onClick={() => setOpen(false)}>
              Keep developing
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

function AddSegments({
  saveId,
  p,
  meta,
  run,
  busy,
}: {
  saveId: string;
  p: Product;
  meta: ProductsMeta;
  run: (action: ProductAction) => void;
  busy: boolean;
}) {
  const categories = useCategories(saveId);
  if (p.status === 'sunset') return null;
  const have = new Set(p.segments.map((s) => s.segment));
  const missing =
    categories.data
      ?.find((c) => c.key === p.category)
      ?.segments.filter((s) => !have.has(s.segment)) ?? [];
  if (missing.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {missing.map((s) => (
        <Button
          key={s.segment}
          variant="default"
          disabled={busy}
          onClick={() => run({ action: 'segment', segment: s.segment })}
          data-testid={`add-segment-${s.segment}`}
        >
          Add {s.label} · {meta.energy_costs.add_segment}
        </Button>
      ))}
    </div>
  );
}

function PricePreview({
  saveId,
  p,
  seg,
  priceCents,
  cost,
  busy,
  onSet,
  onCancel,
}: {
  saveId: string;
  p: Product;
  seg: ProductSegment;
  priceCents: number;
  cost: number;
  busy: boolean;
  onSet: (cents: number) => void;
  onCancel: () => void;
}) {
  const [debounced] = useDebouncedValue(priceCents, 300);
  const preview = usePricePreview(saveId, p.product_id, seg.segment, debounced, true);
  const pv = preview.data;
  const arrow = (before: string | null, after: string) =>
    before === null ? after : `${before} → ${after}`;
  const better =
    pv && pv.current_choice_share !== null && pv.choice_share > pv.current_choice_share;
  return (
    <section
      aria-label="Price preview"
      data-testid="price-preview"
      className="tst-panel"
      style={{
        flex: '1 1 380px',
        borderColor: '#3B5A80',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>
        {seg.price_cents === null ? 'Set' : 'Change'} the {seg.label} price to{' '}
        {formatMoneyWhole(priceCents)}?
      </h2>
      {preview.error && (
        <Alert color="warn" title="Cannot preview this price">
          {preview.error.message}
        </Alert>
      )}
      {pv && (
        <>
          <div className="tst-row">
            <span>Price score</span>
            <span className="tst-num" data-testid="preview-price-score">
              {arrow(
                pv.current_price_score === null ? null : formatScore(pv.current_price_score),
                formatScore(pv.price_score),
              )}
            </span>
          </div>
          <div className="tst-row">
            <span>Appeal</span>
            <span className="tst-num" data-testid="preview-appeal">
              {arrow(
                pv.current_appeal === null ? null : formatAppeal(pv.current_appeal),
                formatAppeal(pv.appeal),
              )}
            </span>
          </div>
          <div className="tst-row">
            <span>Chance a buyer in play picks {p.name}</span>
            <span
              className="tst-num"
              style={{ color: better ? 'var(--tst-good)' : undefined }}
              data-testid="preview-share"
            >
              {arrow(
                pv.current_choice_share === null ? null : formatPercent(pv.current_choice_share),
                formatPercent(pv.choice_share),
              )}
            </span>
          </div>
          {pv.revenue_per_customer_change !== null && (
            <div className="tst-row">
              <span>Revenue per customer</span>
              <span
                className="tst-num"
                style={{
                  color: pv.revenue_per_customer_change < 0 ? 'var(--tst-warn)' : 'var(--tst-good)',
                }}
                data-testid="preview-revenue"
              >
                {formatSignedPercent(pv.revenue_per_customer_change)}
              </span>
            </div>
          )}
        </>
      )}
      <p className="tst-muted" style={{ margin: 0, fontSize: 12, lineHeight: 1.5 }}>
        Against this month&apos;s competitors, before brand awareness. How many customers you win
        depends on next month&apos;s market. Existing customers pay the new price from next month.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Button
          size="md"
          disabled={busy || !pv || debounced !== priceCents}
          onClick={() => onSet(priceCents)}
          data-testid="set-price"
        >
          Set {formatMoneyWhole(priceCents)} · {cost} energy
        </Button>
        <Button variant="default" size="md" onClick={onCancel} data-testid="cancel-price">
          Cancel
        </Button>
      </div>
    </section>
  );
}

function LastYear({
  p,
  meta,
  run,
  busy,
}: {
  p: Product;
  meta: ProductsMeta;
  run: (action: ProductAction, onSuccess?: () => void) => void;
  busy: boolean;
}) {
  const [confirm, setConfirm] = useState(false);
  const cost = meta.energy_costs.sunset_product;
  const months = p.monthly;
  return (
    <Panel
      title={p.sells_abroad ? `Last 12 months · ${p.series_label}` : 'Last 12 months'}
      style={{ flex: '1 1 380px', display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      {months.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0, fontSize: 14 }}>
          No month has closed since launch.
        </p>
      ) : (
        <div
          role="img"
          aria-label={`MRR and ${p.counts_users ? 'users' : 'customers'}, ${months[0].date_label} to ${months[months.length - 1].date_label}`}
        >
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
              <XAxis
                dataKey="date_label"
                stroke="var(--tst-muted)"
                fontSize={11}
                fontFamily="var(--tst-font-mono)"
                tickFormatter={(label: string) => label.split(' ')[0]}
              />
              <YAxis
                yAxisId="mrr"
                stroke="var(--tst-muted)"
                fontSize={11}
                fontFamily="var(--tst-font-mono)"
                tickFormatter={(v: number) => formatMoneyShort(v)}
                width={56}
              />
              <YAxis
                yAxisId="customers"
                orientation="right"
                stroke="var(--tst-muted)"
                fontSize={11}
                fontFamily="var(--tst-font-mono)"
                tickFormatter={(v: number) => formatCount(v)}
                width={56}
              />
              <Tooltip
                formatter={(v, name) =>
                  name === 'MRR' ? formatMoneyWhole(Number(v)) : formatCount(Number(v))
                }
                contentStyle={{
                  background: 'var(--tst-panel)',
                  border: '1px solid var(--tst-border)',
                  fontFamily: 'var(--tst-font-mono)',
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                yAxisId="mrr"
                type="linear"
                dataKey="revenue_cents"
                name="MRR"
                stroke="var(--tst-accent)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                yAxisId="customers"
                type="linear"
                dataKey="customers"
                name={p.counts_users ? 'Users' : 'Customers'}
                stroke="#D5DBE3"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {p.status === 'live' && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            <Button
              variant="default"
              style={{ color: 'var(--tst-warn)', borderColor: '#6A4426' }}
              onClick={() => setConfirm(true)}
              data-testid="sunset"
            >
              Sunset {p.name}… · {cost}
            </Button>
          </div>
          <Modal
            opened={confirm}
            onClose={() => setConfirm(false)}
            title={`Sunset ${p.name}?`}
            centered
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p style={{ margin: 0 }} data-testid="sunset-confirm-text">
                {p.name} takes no new customers, and existing customers leave three times faster
                until none remain. This cannot be undone. Costs {cost} energy.
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  size="md"
                  color="orange"
                  disabled={busy}
                  onClick={() => run({ action: 'sunset' }, () => setConfirm(false))}
                  data-testid="sunset-confirm"
                >
                  Sunset {p.name}
                </Button>
                <Button variant="default" size="md" onClick={() => setConfirm(false)}>
                  Keep selling
                </Button>
              </div>
            </div>
          </Modal>
        </>
      )}
      {p.status === 'sunset' && (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--tst-warn)' }}>
          Being sunset: no new customers; it retires when the last one leaves.
        </p>
      )}
    </Panel>
  );
}

/** The owning division with a picker (M8, energy 1); shown once divisions exist. */
function DivisionPicker({ saveId, p }: { saveId: string; p: Product }) {
  const scaleup = useScaleup(saveId);
  const act = useScaleupAction(saveId);
  const divisions = scaleup.data?.divisions ?? [];
  if (divisions.length === 0 && p.division_id === null) return null;
  return (
    <NativeSelect
      aria-label="Division"
      size="xs"
      data-testid="product-division"
      value={p.division_id === null ? '' : String(p.division_id)}
      data={[
        { value: '', label: 'Corporate' },
        ...divisions.map((d) => ({ value: String(d.unit_id), label: d.name })),
      ]}
      onChange={(e) => {
        const value = e.currentTarget.value;
        act.mutate({
          action: 'product_division',
          product_id: p.product_id,
          division_id: value === '' ? null : Number(value),
        });
      }}
    />
  );
}

/** Prices in other regions (M10b): set in the Regions panel, shown here beside home's. */
function RegionalPrices({ p }: { p: Product }) {
  if (p.regional_prices.length === 0) return null;
  return (
    <div data-testid="regional-prices" style={{ fontSize: 14 }}>
      <h3 style={{ margin: '4px 0', fontSize: 15, fontWeight: 600 }}>Prices in other regions</h3>
      {p.regional_prices.map((r) => (
        <div
          key={`${r.region}-${r.segment}`}
          className="tst-row"
          data-testid={`regional-price-${r.region}-${r.segment}`}
        >
          <span>
            {r.region_label} · {r.segment_label}
            {r.live ? '' : ' (localizing)'}
          </span>
          <span className="tst-num">
            {r.price_cents === null ? '—' : formatMoneyWhole(r.price_cents)}
            <span className="tst-muted"> usual {formatMoneyWhole(r.default_price_cents)}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
