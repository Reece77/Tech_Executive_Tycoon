import { Link, useNavigate, useParams } from 'react-router';
import { MarketTable } from '../components/MarketTable';
import { LoadError, Loading } from '../components/ScreenState';
import { useCategories, useMarket } from '../hooks/api';
import { useTableViews } from '../hooks/useTableViews';
import { segmentSummary } from '../lib/products';

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
  const key = category || categories.data?.[0]?.key || '';
  const market = useMarket(saveId, key);

  if (categories.isPending) return <Loading />;
  if (categories.error)
    return <LoadError title="Could not load the markets" error={categories.error} />;
  const growth = categories.data.find((c) => c.key === key)?.annual_growth;
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
        </div>
        {growth !== undefined && (
          <span className="tst-muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
            Growing about {Math.round(growth * 100)}% a year
          </span>
        )}
      </div>
      {market.error && <LoadError title="Could not load the market" error={market.error} />}
      {market.isPending && <Loading />}
      {market.data?.segments.map((s) => (
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
          </div>
          <MarketTable
            segment={s}
            productHref={(id) => `/game/${saveId}/products/${id}`}
            views={views}
          />
        </section>
      ))}
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Share of buyers counts only customers who use a product in this segment. Competitors&apos;
        scores are public. Until competitors start making decisions (M5) their products keep these
        scores.
      </p>
    </>
  );
}
