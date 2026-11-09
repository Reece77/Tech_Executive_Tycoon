import { Explain } from '../components/Explain';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { components } from '../api/schema';
import { EraTimeline } from '../components/EraTimeline';
import { MacroStrip } from '../components/MacroStrip';
import { MarketTable } from '../components/MarketTable';
import { NodeTimeline } from '../components/NodeTimeline';
import { LoadError, Loading } from '../components/ScreenState';
import { useCategories, useEras, useMarket } from '../hooks/api';
import { useNodes } from '../hooks/fabs';
import { useTableViews } from '../hooks/useTableViews';
import { CommoditiesTab } from './CommoditiesTab';
import { formatMoneyShort } from '../lib/format';
import { formatCount, segmentSummary } from '../lib/products';

type Market = components['schemas']['MarketOut'];

const COMMODITIES = 'commodities'; // the Commodities tab's slot in the category route (M17)
const NODES = 'nodes'; // the process-node timeline's slot (M21, 38.1)

/** The category's size a year and its customers by month, with era arrivals marked (27.3,
 * 27.4). Display only: every number comes from the API. */
function MarketDemand({ m }: { m: Market }) {
  return (
    <section
      aria-label="Market size"
      data-testid="market-size"
      style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>
          Market size {formatMoneyShort(m.size_cents_year ?? 0)} a year
          <Explain metric="market_size" entity={m.category} label="Market size" />
          <Explain metric="market_customers" entity={m.category} label="Market customers" />
        </h2>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          customers × typical price × 12, growing about {Math.round(m.annual_growth * 100)}% a year
        </span>
      </div>
      {(m.history ?? []).length > 1 && (
        <div role="img" aria-label="Customers in this market by month">
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={m.history} margin={{ top: 14, right: 8, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
              <XAxis
                dataKey="date_label"
                stroke="var(--tst-muted)"
                fontSize={11}
                fontFamily="var(--tst-font-mono)"
              />
              <YAxis
                stroke="var(--tst-muted)"
                fontSize={11}
                fontFamily="var(--tst-font-mono)"
                tickFormatter={(v: number) => formatCount(v)}
                width={56}
              />
              <Tooltip
                formatter={(v) => formatCount(Number(v))}
                contentStyle={{
                  background: 'var(--tst-panel)',
                  border: '1px solid var(--tst-border)',
                  fontFamily: 'var(--tst-font-mono)',
                }}
              />
              {(m.era_marks ?? []).map((e) => (
                <ReferenceLine
                  key={e.label}
                  x={e.date_label}
                  stroke="var(--tst-warn)"
                  strokeDasharray="3 3"
                  label={{ value: e.label, fontSize: 10, fill: 'var(--tst-warn)', position: 'top' }}
                />
              ))}
              <Line
                type="linear"
                dataKey="customers"
                name="Customers"
                stroke="var(--tst-accent)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {(m.era_marks ?? []).length > 0 && (
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }} data-testid="market-era-marks">
          Eras:{' '}
          {(m.era_marks ?? [])
            .map((e) => `${e.label} (${e.date_label}${e.caused_by ? `, ${e.caused_by}` : ''})`)
            .join(' · ')}
        </p>
      )}
    </section>
  );
}

/** Every product in a category's market, segment by segment, incumbents included. */
export function MarketScreen() {
  // One set of views for every segment's table: they share their columns (M7b).
  const views = useTableViews('market', {
    sorting: [{ id: 'appeal', desc: true }],
    columnVisibility: {},
    columnOrder: [],
  });
  const { saveId = '', category = '' } = useParams();
  const navigate = useNavigate();
  const categories = useCategories(saveId);
  const nodes = category === NODES; // M21: the node timeline (38.1)
  const commodities = category === COMMODITIES || nodes; // M17: the Commodities tab (33)
  const key = commodities ? '' : category || categories.data?.[0]?.key || '';
  const [region, setRegion] = useState<string | null>(null); // null: the home region (M9)
  const market = useMarket(saveId, key, region);
  const shown = commodities ? undefined : market.data; // a disabled query keeps its last data
  const regions = shown?.regions ?? [];

  if (categories.isPending) return <Loading />;
  if (categories.error)
    return <LoadError title="Could not load the markets" error={categories.error} />;
  const growth = shown?.annual_growth ?? categories.data.find((c) => c.key === key)?.annual_growth;
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Markets</h1>
        <div role="group" aria-label="Category" className="tst-toggle">
          {categories.data.map((c) => (
            <button
              key={c.key}
              type="button"
              aria-pressed={c.key === key}
              onClick={() => navigate(`/game/${saveId}/products/markets/${c.key}`)}
              data-testid={`category-${c.key}`}
            >
              {c.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => navigate(`/game/${saveId}/products/markets/${COMMODITIES}`)}
            aria-pressed={category === COMMODITIES}
            data-testid="category-commodities"
          >
            Commodities
          </button>
          <button
            type="button"
            aria-pressed={nodes}
            onClick={() => navigate(`/game/${saveId}/products/markets/${NODES}`)}
            data-testid="category-nodes"
          >
            Process nodes
          </button>
          {!commodities && <MarketEras saveId={saveId} />}
        </div>
        {regions.length > 0 && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
            Region
            <select
              aria-label="Region"
              data-testid="market-region"
              value={shown?.region ?? ''}
              onChange={(e) => {
                const picked = regions.find((r) => r.key === e.target.value);
                setRegion(picked === undefined || picked.home ? null : picked.key);
              }}
            >
              {regions.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                  {r.home ? ' (home)' : ''}
                </option>
              ))}
            </select>
          </label>
        )}
        {growth !== undefined && (
          <span className="tst-muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
            Growing about {Math.round(growth * 100)}% a year
          </span>
        )}
      </div>
      <MacroStrip saveId={saveId} />
      {commodities && !nodes && <CommoditiesTab saveId={saveId} />}
      {nodes && <MarketNodes saveId={saveId} />}
      {!commodities && market.error && (
        <LoadError title="Could not load the market" error={market.error} />
      )}
      {!commodities && market.isPending && <Loading />}
      {shown && <MarketDemand m={shown} />}
      {shown?.segments.map((s) => (
        <section
          key={s.segment}
          aria-label={s.label}
          data-testid={`market-${s.segment}`}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>{s.label}</h2>
            <span className="tst-muted" style={{ fontSize: 13 }}>
              {segmentSummary(s)}
            </span>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="segment-size">
              size {formatMoneyShort(s.size_cents_year ?? 0)} a year
            </span>
          </div>
          <MarketTable
            segment={s}
            productHref={(id) => `/game/${saveId}/products/${id}`}
            views={views}
          />
        </section>
      ))}
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }} hidden={commodities}>
        Share of buyers counts only customers who use a product in this segment. Competitors&apos;
        scores are public. Until competitors start making decisions (M5) their products keep these
        scores.
      </p>
    </>
  );
}

/** The process-node timeline on Market (M21, formulas.md 38.1, 38.3). */
function MarketNodes({ saveId }: { saveId: string }) {
  const nodes = useNodes(saveId);
  if (nodes.isPending) return <Loading />;
  if (nodes.error) return <LoadError title="Could not load the nodes" error={nodes.error} />;
  return (
    <section aria-label="Process nodes" data-testid="market-nodes">
      <h2 style={{ margin: '8px 0', fontSize: 17, fontWeight: 600 }}>Process nodes</h2>
      <NodeTimeline nodes={nodes.data} />
    </section>
  );
}

/** The era timeline on Market (M11, formulas.md 21.4): what is coming and who caused what. */
function MarketEras({ saveId }: { saveId: string }) {
  const eras = useEras(saveId);
  if (!eras.data) return null;
  return (
    <section aria-label="Eras" data-testid="market-eras">
      <h2 style={{ margin: '8px 0', fontSize: 17, fontWeight: 600 }}>Eras</h2>
      <EraTimeline eras={eras.data} />
    </section>
  );
}
