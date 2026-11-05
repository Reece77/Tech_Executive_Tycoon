// M14 (formulas.md 28): what a company is worth to you and how to buy it, on the Rival screen.
// The value is a listed company's market cap or a private one's range (narrower after
// diligence); findings, people and product ranges arrive with diligence. The offer's answer
// comes back as messages; nothing here computes a game value (CLAUDE.md section 7).
import { Alert, Button, Checkbox, NumberInput, SegmentedControl } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import { useMna, useMnaAction, type MnaActionResult, type MnaTarget } from '../hooks/api';
import { formatMoneyWhole, humanize } from '../lib/format';
import { Panel } from './ScreenState';

export function RivalDealPanel({ saveId, companyId }: { saveId: string; companyId: number }) {
  const mna = useMna(saveId);
  const target = mna.data?.targets.find((t) => t.company_id === companyId);
  if (!mna.data) return null;
  const deal = mna.data.deals.find((d) => d.target_id === companyId && d.status !== 'closed');
  if (!target) {
    const owned = mna.data.acquisitions.find((a) => a.company_id === companyId);
    return owned ? (
      <Panel title="Acquisition">
        <p data-testid="deal-status" style={{ margin: 0 }}>
          You own {owned.name} ({owned.mode === 'brand' ? 'kept as a brand' : 'integrated'}).{' '}
          <Link to={`/game/${saveId}/finance/deals`}>Deals</Link>
        </p>
      </Panel>
    ) : null;
  }
  return <DealBody saveId={saveId} t={target} listed={mna.data.listed} dealStatus={deal?.status} />;
}

function valueText(t: MnaTarget): string {
  if (t.listed && t.market_cap_cents != null)
    return `Market cap ${formatMoneyWhole(t.market_cap_cents)}`;
  return `Estimated value ${formatMoneyWhole(t.value_low_cents ?? 0)} to ${formatMoneyWhole(
    t.value_high_cents ?? 0,
  )}`;
}

function DealBody({
  saveId,
  t,
  listed,
  dealStatus,
}: {
  saveId: string;
  t: MnaTarget;
  listed: boolean;
  dealStatus: string | undefined;
}) {
  const act = useMnaAction(saveId);
  const [price, setPrice] = useState<number | string>('');
  const [cash, setCash] = useState<number | string>(100);
  const [mode, setMode] = useState<'integrate' | 'brand'>('integrate');
  const [hostile, setHostile] = useState(false);
  const [result, setResult] = useState<MnaActionResult | null>(null);
  const done = (r: MnaActionResult) => setResult(r);
  const bid = () =>
    act.mutate(
      {
        kind: 'bid',
        companyId: t.company_id,
        priceCents: Math.round(Number(price) * 100),
        cashShare: Number(cash) / 100,
        hostile,
        mode,
      },
      { onSuccess: done },
    );
  return (
    <Panel title="Value and deal">
      <p data-testid="target-value" style={{ margin: '0 0 6px' }}>
        {valueText(t)}
        {t.diligence === 'done' ? ' (after diligence)' : ''}
      </p>
      {t.counter_cents != null && (
        <p data-testid="target-counter" style={{ margin: '0 0 6px' }}>
          They countered at {formatMoneyWhole(t.counter_cents)}.
        </p>
      )}
      {t.talks_closed_months != null && (
        <p className="tst-muted" style={{ margin: '0 0 6px' }}>
          Talks are closed for {t.talks_closed_months} more months.
        </p>
      )}
      <p data-testid="diligence-status" className="tst-muted" style={{ margin: '0 0 6px' }}>
        Diligence: {humanize(t.diligence)}
        {t.diligence === 'done'
          ? `. Findings: ${t.findings.map(humanize).join(', ') || 'no hidden problems'}.`
          : ''}
      </p>
      {t.diligence === 'none' && (
        <Button
          size="xs"
          variant="light"
          data-testid="start-diligence"
          loading={act.isPending}
          onClick={() =>
            act.mutate({ kind: 'diligence', companyId: t.company_id }, { onSuccess: done })
          }
        >
          Diligence ({formatMoneyWhole(t.diligence_cost_cents)}, two months)
        </Button>
      )}
      {t.diligence === 'done' && t.products.some((p) => p.quality_low != null) && (
        <ul
          data-testid="target-products"
          style={{ margin: '6px 0', paddingLeft: 18, fontSize: 13 }}
        >
          {t.products.map((p) => (
            <li key={p.product_id}>
              {p.name}: quality {p.quality_low}-{p.quality_high}, features {p.feature_low}-
              {p.feature_high}
            </li>
          ))}
        </ul>
      )}
      {dealStatus ? (
        <p data-testid="deal-status" style={{ margin: '8px 0 0' }}>
          Deal {humanize(dealStatus)}. <Link to={`/game/${saveId}/finance/deals`}>Deals</Link>
        </p>
      ) : (
        <div
          style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'end', marginTop: 10 }}
        >
          <NumberInput
            label="Offer ($)"
            data-testid="offer-price"
            value={price}
            onChange={setPrice}
            min={1}
            thousandSeparator=","
            style={{ width: 180 }}
          />
          {listed && (
            <NumberInput
              label="Cash (%)"
              data-testid="offer-cash"
              value={cash}
              onChange={setCash}
              min={0}
              max={100}
              style={{ width: 100 }}
            />
          )}
          <SegmentedControl
            size="xs"
            data-testid="offer-mode"
            value={mode}
            onChange={(v) => setMode(v as 'integrate' | 'brand')}
            data={[
              { value: 'integrate', label: 'Integrate' },
              { value: 'brand', label: 'Keep as a brand' },
            ]}
          />
          {t.listed && (
            <Checkbox
              label="Hostile tender"
              checked={hostile}
              onChange={(e) => setHostile(e.currentTarget.checked)}
            />
          )}
          <Button
            size="xs"
            data-testid="make-offer"
            disabled={!Number(price)}
            loading={act.isPending}
            onClick={bid}
          >
            Make an offer
          </Button>
        </div>
      )}
      {act.error && (
        <Alert color="red" mt={8} data-testid="offer-error">
          {act.error.message}
        </Alert>
      )}
      {result?.messages.map((m) => (
        <Alert key={m.title} mt={8} data-testid="offer-answer" title={m.title}>
          {m.detail}
        </Alert>
      ))}
    </Panel>
  );
}
