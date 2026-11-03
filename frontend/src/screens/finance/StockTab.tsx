import { Alert, Button, NumberInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState, type ReactNode } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DataTable } from '../../components/DataTable';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { Term } from '../../components/Term';
import { usePublic, usePublicAction, type GuidanceRow, type Stock } from '../../hooks/api';
import { formatMoney, formatMoneyShort } from '../../lib/format';
import { formatShares } from '../../lib/finance';
import { pct } from '../../lib/org';
import { pctText } from '../../lib/public';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, GuidanceRow>();
const right = { display: 'block', textAlign: 'right' } as const;

const MARK_COLOR: Record<string, string> = {
  listing: 'var(--tst-accent)',
  beat: 'var(--tst-good)',
  miss: 'var(--tst-warn)',
  inline: 'var(--tst-muted)',
};
const RESULT_TEXT: Record<string, string> = { beat: 'Beat', miss: 'Miss', inline: 'In line' };
const EFFECT_COLOR: Record<string, string> = {
  lifts: 'var(--tst-good)',
  'weighs on': 'var(--tst-warn)',
};

/** Finance · Stock (M13, wireframe "Stock"): the share price and chart since listing,
 * guidance against results, next quarter's guidance, analysts, capital actions, the board's
 * line on earnings, and what drives the price, in words. Shown once the company is public. */
export function StockTab({ saveId }: { saveId: string }) {
  const data = usePublic(saveId);
  if (data.isPending) return <Loading />;
  if (data.error) return <LoadError title="Could not load the stock" error={data.error} />;
  const stock = data.data.stock;
  if (!stock) {
    return (
      <Panel title="Stock">
        <p className="tst-muted" style={{ margin: 0 }} data-testid="not-listed">
          The company is not listed. Going public starts in Finance › Fundraising.
        </p>
      </Panel>
    );
  }
  return <StockBody saveId={saveId} stock={stock} />;
}

export function StockBody({ saveId, stock }: { saveId: string; stock: Stock }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="stock-tab">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>
        <PriceBlock stock={stock} />
        <Panel title="Share price since listing" style={{ flex: '3 1 420px', minWidth: 0 }}>
          <StockChart stock={stock} />
        </Panel>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <div
          style={{
            flex: '3 1 520px',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <Panel title="Guidance and results" label="Guidance and results">
            <GuidanceTable rows={stock.guidance} />
          </Panel>
          <GuidanceForm key={stock.next_guidance.quarter} saveId={saveId} stock={stock} />
          <Drivers stock={stock} />
        </div>
        <div
          style={{
            flex: '2 1 320px',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <Analysts stock={stock} />
          <Capital saveId={saveId} stock={stock} />
          <Panel title="The board" label="The board on earnings">
            <p style={{ margin: 0, fontSize: 13 }} data-testid="board-line">
              {stock.board_line}
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Line2({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="tst-row">
      <span className="tst-muted">{label}</span>
      <span className="tst-num">{children}</span>
    </div>
  );
}

export function PriceBlock({ stock }: { stock: Stock }) {
  const change = stock.change_pct;
  return (
    <Panel title="Share price" style={{ flex: '2 1 280px' }} label="Share price">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <span data-testid="stock-ticker" style={{ fontWeight: 700, letterSpacing: '.04em' }}>
          {stock.ticker}
        </span>
        <span
          className="tst-num"
          style={{ fontSize: 28, fontWeight: 600 }}
          data-testid="stock-price"
        >
          {formatMoney(stock.price_cents)}
        </span>
        {change !== null && (
          <span
            className="tst-num"
            style={{ color: change < 0 ? 'var(--tst-warn)' : 'var(--tst-good)' }}
            data-testid="stock-change"
          >
            {pct(change)} this month
          </span>
        )}
      </div>
      <Line2 label={<Term term="public.market_cap">Market cap</Term>}>
        {formatMoneyShort(stock.market_cap_cents)}
      </Line2>
      <Line2 label="Listed">
        at {formatMoney(stock.listing_price_cents)} ({stock.listed})
        {stock.dual_class ? ' · dual class' : ''}
      </Line2>
      <Line2 label="Your stake">
        <span data-testid="stock-stake">
          {pctText(stock.stake_pct)} · {formatShares(stock.stake_shares)} shares ·{' '}
          {formatMoneyShort(stock.stake_value_cents)}
        </span>
      </Line2>
    </Panel>
  );
}

export function StockChart({ stock }: { stock: Stock }) {
  const marks = stock.history.filter((p) => p.mark !== '');
  const first = stock.history[0];
  const last = stock.history[stock.history.length - 1];
  return (
    <div
      role="img"
      data-testid="stock-chart"
      aria-label={
        first && last
          ? `Share price from ${formatMoney(first.price_cents)} in ${first.label} to ${formatMoney(last.price_cents)} in ${last.label}; ${marks
              .filter((m) => m.mark === 'beat' || m.mark === 'miss')
              .map((m) => `${m.mark} in ${m.label}`)
              .join(', ')}`
          : 'No share price yet'
      }
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={stock.history} margin={{ top: 16, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
          />
          <YAxis
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(v: number) => formatMoneyShort(v)}
            width={64}
            domain={['auto', 'auto']}
          />
          <Tooltip
            formatter={(v) => formatMoney(Number(v))}
            contentStyle={{
              background: 'var(--tst-panel)',
              border: '1px solid var(--tst-border)',
              fontFamily: 'var(--tst-font-mono)',
            }}
          />
          <Line
            type="linear"
            dataKey="price_cents"
            name="Share price"
            stroke="var(--tst-accent)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {marks.map((m) => (
            <ReferenceDot
              key={m.turn}
              x={m.label}
              y={m.price_cents}
              r={5}
              fill={MARK_COLOR[m.mark] ?? 'var(--tst-muted)'}
              stroke="none"
              label={{ value: m.mark, position: 'top', fontSize: 11, fill: 'var(--tst-text-2)' }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div
        style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 12 }}
        className="tst-muted"
      >
        {marks.map((m) => (
          <span key={m.turn} data-testid="stock-mark" data-mark={m.mark}>
            <span style={{ color: MARK_COLOR[m.mark] }}>●</span> {m.label} {m.mark}
          </span>
        ))}
      </div>
    </div>
  );
}

export function GuidanceTable({ rows }: { rows: GuidanceRow[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('quarter', {
          header: 'Quarter',
          meta: { term: 'public.guidance' },
          cell: (c) => (
            <span>
              {c.getValue()}
              {!c.row.original.by_player && (
                <span className="tst-muted" style={{ display: 'block', fontSize: 12 }}>
                  no guidance: the consensus
                </span>
              )}
            </span>
          ),
        }),
        helper.accessor('revenue_cents', {
          header: () => <span style={right}>Guided revenue</span>,
          meta: { term: 'public.guided_revenue' },
          cell: (c) => (
            <span className="tst-num" style={right}>
              {formatMoneyShort(c.getValue())}
            </span>
          ),
        }),
        helper.accessor((r) => r.actual_revenue_cents ?? undefined, {
          id: 'actual',
          header: () => <span style={right}>Actual</span>,
          meta: { term: 'public.actual_revenue' },
          sortUndefined: 'last',
          cell: (c) => {
            const v = c.getValue();
            return (
              <span className="tst-num" style={right}>
                {v === undefined ? '—' : formatMoneyShort(v)}
              </span>
            );
          },
        }),
        helper.accessor('margin_pct', {
          header: 'Margin (guided / actual)',
          meta: { term: 'public.margin' },
          cell: (c) => {
            const a = c.row.original.actual_margin_pct;
            return (
              <span className="tst-num">
                {pctText(c.getValue())} / {a === null ? '—' : pctText(a)}
              </span>
            );
          },
        }),
        helper.accessor((r) => r.result ?? undefined, {
          id: 'result',
          header: 'Result',
          meta: { term: 'public.beat_miss' },
          sortUndefined: 'last',
          cell: (c) => {
            const r = c.row.original;
            if (!r.result) return <span className="tst-muted">reported at the quarter end</span>;
            return (
              <span
                data-testid="guidance-result"
                data-result={r.result}
                style={{ color: MARK_COLOR[r.result] }}
              >
                {RESULT_TEXT[r.result] ?? r.result}
                {r.price_before_cents !== null && r.price_after_cents !== null && (
                  <span className="tst-num" style={{ display: 'block', fontSize: 12 }}>
                    {formatMoney(r.price_before_cents)} → {formatMoney(r.price_after_cents)}
                  </span>
                )}
              </span>
            );
          },
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    data: rows,
    columns,
    getRowId: (r) => r.quarter,
  });
  return (
    <div data-testid="guidance-table">
      <DataTable
        table={table}
        label="Guidance and results"
        rowTestId="guidance-row"
        empty="No quarter reported yet. Results come at each quarter's end."
      />
    </div>
  );
}

function GuidanceForm({ saveId, stock }: { saveId: string; stock: Stock }) {
  const g = stock.next_guidance;
  const [dollars, setDollars] = useState<number>(
    Math.round((g.set_revenue_cents ?? g.consensus_revenue_cents) / 100),
  );
  const [margin, setMargin] = useState<number>(g.set_margin_pct ?? g.consensus_margin_pct);
  const act = usePublicAction(saveId);
  return (
    <Panel title={`Set ${g.quarter} guidance`} label="Set guidance">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          <Term term="public.consensus">Consensus</Term>: revenue{' '}
          <span className="tst-num">{formatMoneyShort(g.consensus_revenue_cents)}</span>, margin{' '}
          <span className="tst-num">{pctText(g.consensus_margin_pct)}</span>. Guidance must lie
          within {pctText(g.band_pct, 0)} of it.
          {g.set_revenue_cents !== null && g.set_margin_pct !== null && (
            <span data-testid="guidance-set">
              {' '}
              Guided: {formatMoneyShort(g.set_revenue_cents)}, {pctText(g.set_margin_pct)}.
            </span>
          )}
        </span>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <NumberInput
            label="Revenue for the quarter"
            prefix="$"
            thousandSeparator=","
            allowDecimal={false}
            allowNegative={false}
            value={dollars}
            onChange={(v) => setDollars(typeof v === 'number' ? v : 0)}
            classNames={{ input: 'tst-num' }}
            disabled={!g.can_set}
            data-testid="guidance-revenue"
          />
          <NumberInput
            label="Operating margin"
            suffix="%"
            decimalScale={2}
            min={-100}
            max={100}
            value={margin}
            onChange={(v) => setMargin(typeof v === 'number' ? v : 0)}
            classNames={{ input: 'tst-num' }}
            disabled={!g.can_set}
            data-testid="guidance-margin"
          />
        </div>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {g.hint}
        </span>
        {g.problem && (
          <Alert color="warn" data-testid="guidance-problem">
            {g.problem}
          </Alert>
        )}
        {act.error && (
          <Alert color="warn" data-testid="guidance-error">
            {act.error.message}
          </Alert>
        )}
        <Button
          h={44}
          style={{ alignSelf: 'flex-start' }}
          disabled={!g.can_set || dollars <= 0}
          loading={act.isPending}
          onClick={() =>
            act.mutate({
              kind: 'guidance',
              revenueCents: dollars * 100,
              marginBp: Math.round(margin * 100),
            })
          }
          data-testid="guidance-submit"
        >
          Set guidance · {g.energy} energy
        </Button>
      </div>
    </Panel>
  );
}

export function Analysts({ stock }: { stock: Stock }) {
  return (
    <Panel title={`Analysts (${stock.analysts.length})`} label="Analysts" testId="analysts-panel">
      <div style={{ display: 'flex', gap: 16, fontSize: 14 }}>
        <span>
          <Term term="public.analyst_rating">Buy</Term>{' '}
          <strong className="tst-num" data-testid="analysts-buy">
            {stock.buys}
          </strong>
        </span>
        <span>
          Hold <strong className="tst-num">{stock.holds}</strong>
        </span>
        <span>
          Sell <strong className="tst-num">{stock.sells}</strong>
        </span>
      </div>
      <Line2 label={<Term term="public.price_target">Average target</Term>}>
        {stock.average_target_cents === null ? '—' : formatMoney(stock.average_target_cents)}
      </Line2>
      {stock.analysts.map((a) => (
        <div className="tst-row" key={a.firm} style={{ fontSize: 13 }} data-testid="analyst">
          <span>{a.firm}</span>
          <span className="tst-num">
            {a.rating} · {formatMoney(a.target_cents)}
          </span>
        </div>
      ))}
    </Panel>
  );
}

function Capital({ saveId, stock }: { saveId: string; stock: Stock }) {
  const c = stock.capital;
  const act = usePublicAction(saveId);
  const [buyback, setBuyback] = useState<number>(0);
  const [dividend, setDividend] = useState<number>(0);
  const [shares, setShares] = useState<number>(0);
  return (
    <Panel title="Capital" label="Capital actions">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <NumberInput
            label={<Term term="public.buyback">Buy back shares</Term>}
            description={`At ${formatMoney(c.buyback_price_cents)} a share, up to ${formatShares(c.buyback_max_shares)} shares`}
            inputWrapperOrder={['label', 'input', 'description', 'error']}
            prefix="$"
            thousandSeparator=","
            allowDecimal={false}
            allowNegative={false}
            value={buyback}
            onChange={(v) => setBuyback(typeof v === 'number' ? v : 0)}
            classNames={{ input: 'tst-num' }}
            data-testid="buyback-amount"
          />
          <Button
            variant="default"
            style={{ alignSelf: 'flex-start' }}
            disabled={buyback <= 0}
            loading={act.isPending && act.variables?.kind === 'buyback'}
            onClick={() => act.mutate({ kind: 'buyback', amountCents: buyback * 100 })}
            data-testid="buyback-submit"
          >
            Buy back · {c.buyback_energy} energy
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <NumberInput
            label={<Term term="public.dividend">Pay a dividend, a share</Term>}
            description={
              c.dividend_declared_cents > 0
                ? `Declared: ${formatMoney(c.dividend_declared_cents)} a share, paid at month end`
                : `Paid at month end on ${formatShares(c.shares_outstanding)} shares`
            }
            inputWrapperOrder={['label', 'input', 'description', 'error']}
            prefix="$"
            decimalScale={2}
            allowNegative={false}
            value={dividend}
            onChange={(v) => setDividend(typeof v === 'number' ? v : 0)}
            classNames={{ input: 'tst-num' }}
            data-testid="dividend-amount"
          />
          <Button
            variant="default"
            style={{ alignSelf: 'flex-start' }}
            disabled={dividend <= 0}
            loading={act.isPending && act.variables?.kind === 'dividend'}
            onClick={() =>
              act.mutate({ kind: 'dividend', perShareCents: Math.round(dividend * 100) })
            }
            data-testid="dividend-submit"
          >
            Declare · {c.dividend_energy} energy
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <NumberInput
            label={<Term term="public.secondary">Secondary offering, new shares</Term>}
            description={`At ${formatMoney(c.secondary_price_cents)} a share, up to ${formatShares(c.secondary_max_shares)}; fee ${pctText(c.secondary_fee_pct)}`}
            inputWrapperOrder={['label', 'input', 'description', 'error']}
            thousandSeparator=","
            allowDecimal={false}
            allowNegative={false}
            value={shares}
            onChange={(v) => setShares(typeof v === 'number' ? v : 0)}
            classNames={{ input: 'tst-num' }}
            data-testid="secondary-shares"
          />
          <Button
            variant="default"
            style={{ alignSelf: 'flex-start' }}
            disabled={shares <= 0}
            loading={act.isPending && act.variables?.kind === 'secondary'}
            onClick={() => act.mutate({ kind: 'secondary', shares })}
            data-testid="secondary-submit"
          >
            Sell shares · {c.secondary_energy} energy
          </Button>
        </div>
        {act.error && (
          <Alert color="warn" data-testid="capital-error">
            {act.error.message}
          </Alert>
        )}
      </div>
    </Panel>
  );
}

export function Drivers({ stock }: { stock: Stock }) {
  return (
    <Panel title="What moves the share price" label="Share price drivers" testId="price-drivers">
      {stock.drivers.map((d) => (
        <div className="tst-row" key={d.label} data-testid="price-driver" style={{ fontSize: 13 }}>
          <span>{d.label}</span>
          <span>
            <span style={{ color: EFFECT_COLOR[d.effect] ?? 'var(--tst-muted)' }}>{d.effect}</span>
            <span className="tst-muted"> · {d.detail}</span>
          </span>
        </div>
      ))}
      <p className="tst-muted" style={{ margin: '6px 0 0', fontSize: 12 }}>
        Fundamentals set what the shares are worth; the market&apos;s mood and your earnings move
        the price around it.
      </p>
    </Panel>
  );
}
