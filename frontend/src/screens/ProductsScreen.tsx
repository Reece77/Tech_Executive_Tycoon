import { Alert, Button, Checkbox, Modal, NativeSelect, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { KpiTile } from '../components/KpiTile';
import { LifecycleChip } from '../components/LifecycleChip';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import {
  useCategories,
  useCreateProduct,
  usePortfolio,
  useProducts,
  useProductsMeta,
  type Category,
  type Portfolio,
  type Product,
  type ProductsMeta,
} from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../lib/format';
import {
  formatCount,
  formatScore,
  formatSignedPercent,
  paceText,
  REACH_TEXT,
  seriesScope,
} from '../lib/products';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { useTableViews } from '../hooks/useTableViews';

const helper = createColumnHelper<GameTableFeatures, Product>();

export function ProductsScreen() {
  const { saveId = '' } = useParams();
  const products = useProducts(saveId);
  const portfolio = usePortfolio(saveId);
  const meta = useProductsMeta();
  const [creating, setCreating] = useState(false);

  if (products.isPending || portfolio.isPending || meta.isPending) return <Loading />;
  if (products.error || portfolio.error || meta.error) {
    return (
      <LoadError
        title="Could not load your products"
        error={products.error ?? portfolio.error ?? meta.error}
      />
    );
  }
  return (
    <>
      <ScreenTitle
        aside={
          <>
            <Link
              to={`/game/${saveId}/products/markets`}
              style={{ fontSize: 13 }}
              data-testid="markets-link"
            >
              Markets
            </Link>
            <Link
              to={`/game/${saveId}/products/research`}
              style={{ fontSize: 13 }}
              data-testid="research-link"
            >
              Research
            </Link>
            <Button
              variant="default"
              style={{ marginLeft: 'auto' }}
              onClick={() => setCreating(true)}
              data-testid="new-product"
            >
              New product · {meta.data.energy_costs.create_product}
            </Button>
          </>
        }
      >
        Products
      </ScreenTitle>
      <PortfolioTiles portfolio={portfolio.data} />
      <PortfolioTable saveId={saveId} products={products.data} />
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Scores run 0–100. Development pace shows how fast the assigned team is working against the
        product&apos;s size: fast, steady or slow.
      </p>
      {creating && (
        <NewProductDialog saveId={saveId} meta={meta.data} onClose={() => setCreating(false)} />
      )}
    </>
  );
}

function PortfolioTiles({ portfolio: p }: { portfolio: Portfolio }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <KpiTile
        term="kpi.mrr"
        label="Monthly revenue (MRR)"
        value={formatMoneyWhole(p.mrr_cents)}
        note={
          p.mrr_change === null || p.previous_label === null
            ? 'Last closed month'
            : `${formatSignedPercent(p.mrr_change)} on ${p.previous_label}`
        }
        testId="kpi-mrr"
      />
      <KpiTile
        term="kpi.arr"
        label="Annual run rate (ARR)"
        value={formatMoneyShort(p.arr_cents)}
        note={p.stage_label}
        hint="12 × MRR; stage 2 from $1M, stage 3 from $20M"
        testId="kpi-arr"
      />
      <KpiTile
        term="kpi.customers"
        label="Paying customers"
        value={formatCount(p.paying_customers)}
        note={
          p.consumer_users > 0
            ? `plus ${formatCount(p.consumer_users)} consumer users`
            : 'Businesses across your products'
        }
        testId="kpi-customers"
      />
      <KpiTile
        term="kpi.product_costs"
        label="Hosting and marketing"
        value={formatMoneyWhole(p.product_costs_cents)}
        note={`this month: hosting ${formatMoneyWhole(p.hosting_cents)}, marketing ${formatMoneyWhole(p.marketing_cents)}`}
        testId="kpi-product-costs"
      />
    </div>
  );
}

function trend(p: Product) {
  if (p.status === 'in_development') {
    const text = p.launch.ready ? 'Ready to launch' : `Not ready: ${p.launch.missing.join('; ')}`;
    return (
      <span
        style={{
          fontSize: 13,
          color: p.launch.ready ? 'var(--tst-good)' : 'var(--tst-muted)',
          whiteSpace: 'normal',
        }}
      >
        {text}
      </span>
    );
  }
  if (p.customer_trend === null) return <span className="tst-muted">—</span>;
  const color =
    p.customer_trend > 0
      ? 'var(--tst-good)'
      : p.customer_trend < 0
        ? 'var(--tst-warn)'
        : 'var(--tst-muted)';
  return (
    <span className="tst-num" style={{ color }}>
      {formatSignedPercent(p.customer_trend)} a month
      {p.sells_abroad && <span className="tst-muted">{seriesScope(p)}</span>}
    </span>
  );
}

function PortfolioTable({ saveId, products }: { saveId: string; products: Product[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Product',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <Link
              to={`/game/${saveId}/products/${row.original.product_id}`}
              style={{ fontWeight: 600, textDecoration: 'none' }}
            >
              {row.original.name}
            </Link>
          ),
        }),
        helper.accessor('category_label', {
          header: 'Category',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <span style={{ color: 'var(--tst-text-2)' }}>{getValue()}</span>,
        }),
        helper.accessor('status', {
          header: 'Status',
          sortFn: 'alphanumeric',
          cell: ({ row }) => <LifecycleChip product={row.original} />,
        }),
        helper.accessor('quality', {
          header: 'Quality',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="tst-num" style={{ width: 24 }}>
                {formatScore(getValue())}
              </span>
              <span
                aria-hidden="true"
                style={{ width: 70, height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
              >
                <span
                  style={{
                    display: 'block',
                    height: 6,
                    borderRadius: 3,
                    background: 'var(--tst-accent)',
                    width: `${Math.min(100, getValue())}%`,
                  }}
                />
              </span>
            </span>
          ),
        }),
        helper.accessor('feature_score', {
          header: 'Features',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatScore(getValue())}</span>,
        }),
        helper.accessor('brand', {
          header: 'Brand',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatScore(getValue())}</span>,
        }),
        helper.accessor('customers', {
          header: 'Customers',
          sortFn: 'basic',
          cell: ({ row }) =>
            row.original.status === 'in_development' ? (
              <span className="tst-muted">—</span>
            ) : (
              <span className="tst-num" data-testid="product-customers">
                {formatCount(row.original.customers)}
                {row.original.counts_users ? ' users' : ''}
              </span>
            ),
        }),
        helper.accessor('mrr_cents', {
          header: 'MRR',
          sortFn: 'basic',
          cell: ({ row }) =>
            row.original.status === 'in_development' ? (
              <span className="tst-muted">—</span>
            ) : (
              <span className="tst-num">{formatMoneyWhole(row.original.mrr_cents)}</span>
            ),
        }),
        helper.accessor((p) => p.customer_trend ?? undefined, {
          id: 'trend',
          header: 'Trend',
          sortFn: 'basic',
          sortUndefined: 'last',
          cell: ({ row }) => trend(row.original),
        }),
        helper.accessor((p) => paceText(p.pace, p.builders.length), {
          id: 'pace',
          header: 'Development',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span style={{ color: 'var(--tst-text-2)' }} data-testid="product-pace">
              {getValue()}
            </span>
          ),
        }),
      ]),
    [saveId],
  );
  const views = useTableViews('products');
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: products,
    getRowId: (p) => String(p.product_id),
    ...views.tableProps,
  });
  return (
    <DataTable
      views={views}
      table={table}
      label="Your products"
      rowTestId="product-row"
      empty="No products yet. Create one with New product."
    />
  );
}

function NewProductDialog({
  saveId,
  meta,
  onClose,
}: {
  saveId: string;
  meta: ProductsMeta;
  onClose: () => void;
}) {
  const categories = useCategories(saveId);
  const create = useCreateProduct(saveId);
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [categoryKey, setCategoryKey] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);

  const list = categories.data ?? [];
  const category: Category | undefined = list.find((c) => c.key === categoryKey) ?? list[0];
  const cost = meta.energy_costs.create_product;
  const ready = name.trim() !== '' && chosen.length > 0 && category !== undefined;

  const submit = () => {
    if (!category) return;
    create.mutate(
      { name: name.trim(), category: category.key, segments: chosen },
      { onSuccess: (out) => navigate(`/game/${saveId}/products/${out.product.product_id}`) },
    );
  };

  return (
    <Modal opened onClose={onClose} title="New product" centered size="lg">
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
        data-testid="new-product-dialog"
      >
        {categories.error && (
          <LoadError title="Could not load categories" error={categories.error} />
        )}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 12,
          }}
        >
          <TextInput
            label="Name"
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.currentTarget.value)}
            data-testid="new-product-name"
          />
          <NativeSelect
            label="Category"
            value={category?.key ?? ''}
            data={list.map((c) => ({ value: c.key, label: c.label }))}
            onChange={(e) => {
              setCategoryKey(e.currentTarget.value);
              setChosen([]);
            }}
            data-testid="product-category"
          />
        </div>
        {category && (category.note || category.launch_quality) && (
          <p className="tst-muted" style={{ margin: 0, fontSize: 13 }} data-testid="category-note">
            {category.note ? `${category.note}. ` : ''}
            {category.launch_quality ? `Launch needs quality ${category.launch_quality}.` : ''}
          </p>
        )}
        {category && (
          <fieldset
            style={{
              border: 0,
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <legend style={{ fontSize: 13, color: 'var(--tst-text-2)', padding: '0 0 8px' }}>
              Sell to
            </legend>
            {category.segments.map((s) => (
              <label
                key={s.segment}
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 12,
                  alignItems: 'center',
                  padding: '10px 12px',
                  border: '1px solid var(--tst-border)',
                  borderRadius: 8,
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                <Checkbox
                  checked={chosen.includes(s.segment)}
                  onChange={(e) => {
                    const on = e.currentTarget.checked;
                    setChosen((now) =>
                      on ? [...now, s.segment] : now.filter((key) => key !== s.segment),
                    );
                  }}
                  aria-label={s.label}
                  data-testid={`segment-${s.segment}`}
                />
                <span style={{ fontWeight: 600, minWidth: 110 }}>{s.label}</span>
                <span className="tst-muted" style={{ fontSize: 13 }}>
                  {REACH_TEXT[s.reach] ?? s.reach}
                </span>
                <span className="tst-num tst-muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
                  {formatCount(s.addressable)} {s.counts_users ? 'users' : 'businesses'} · ~
                  {formatMoneyWhole(s.reference_price_cents)} a month
                </span>
              </label>
            ))}
          </fieldset>
        )}
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          It starts in development at quality {formatScore(meta.start_quality)} with no features.
          Assign a unit to build it from the product page; it can launch once quality reaches{' '}
          {formatScore(meta.launch_min_quality)} and features {formatScore(meta.launch_min_feature)}
          . You set prices before launch.
        </p>
        {create.error && (
          <Alert color="red" title="Could not create the product">
            {create.error.message}
          </Alert>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Button
            size="md"
            disabled={!ready}
            loading={create.isPending}
            onClick={submit}
            data-testid="create-product"
          >
            Create · {cost} energy
          </Button>
          <Button variant="default" size="md" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
