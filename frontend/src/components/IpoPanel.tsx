import { Alert, Button } from '@mantine/core';
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import { Panel } from './ScreenState';
import { Term } from './Term';
import {
  useChooseEvent,
  useEvents,
  usePublic,
  usePublicAction,
  type Ipo,
  type PriceOption,
  type PublicCompany,
} from '../hooks/api';
import { formatMoney, formatMoneyShort, formatMoneyWhole } from '../lib/format';
import { formatShares } from '../lib/finance';
import { pct } from '../lib/org';
import { openIpoEvent, pctText } from '../lib/public';

const STEP_COLOR: Record<string, string> = {
  done: 'var(--tst-good)',
  now: 'var(--tst-accent)',
  next: 'var(--tst-muted)',
};

function Row({
  label,
  children,
  testId,
}: {
  label: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <div className="tst-row" data-testid={testId}>
      <span>{label}</span>
      <span className="tst-num">{children}</span>
    </div>
  );
}

/**
 * The IPO in Fundraising (M13, wireframe "IPO"): eligibility and the bank choice before banks
 * are hired; then the chain's progress strip, the offering and, at pricing, the pricing card.
 * The S-1, roadshow and pricing steps are events: the choice is made there.
 */
export function IpoPanel({ saveId }: { saveId: string }) {
  const data = usePublic(saveId);
  // From the scale-up stage (3), or once an IPO has begun; earlier it is only noise.
  if (!data.data || (data.data.stage < 3 && data.data.ipo === null)) return null;
  return <IpoBody saveId={saveId} p={data.data} />;
}

export function IpoBody({ saveId, p }: { saveId: string; p: PublicCompany }) {
  const ipo = p.ipo;
  const pulled = ipo?.status === 'pulled';
  return (
    <Panel
      title="Initial public offering"
      label="Initial public offering"
      testId="ipo-panel"
      action={
        ipo && !pulled ? (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="ipo.lead_underwriter">Lead bank</Term>: {ipo.bank} · fee{' '}
            {pctText(ipo.fee_pct)}
          </span>
        ) : undefined
      }
    >
      {(!ipo || pulled) && <HireBanks saveId={saveId} p={p} />}
      {ipo && <IpoProgress saveId={saveId} ipo={ipo} />}
    </Panel>
  );
}

function HireBanks({ saveId, p }: { saveId: string; p: PublicCompany }) {
  const [bank, setBank] = useState<string>(p.banks[0]?.key ?? '');
  const act = usePublicAction(saveId);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span className="tst-muted" style={{ fontSize: 13 }}>
        Going public takes about five months: hire the banks, file the{' '}
        <Term term="ipo.s1">S-1</Term>, take the <Term term="ipo.roadshow">roadshow</Term>, price
        the offering and list. Each step is an event to answer.
      </span>
      {p.problem ? (
        <Alert color="warn" data-testid="ipo-problem">
          Not yet: {p.problem}.
        </Alert>
      ) : (
        <span data-testid="ipo-problem" style={{ fontSize: 13, color: 'var(--tst-good)' }}>
          Eligible: banks will take you on now.
        </span>
      )}
      <div
        role="radiogroup"
        aria-label="Lead bank"
        style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
      >
        {p.banks.map((b) => (
          <label
            key={b.key}
            className="tst-row"
            style={{ cursor: 'pointer', gap: 10 }}
            data-testid={`bank-option-${b.key}`}
          >
            <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="radio"
                name="ipo-bank"
                value={b.key}
                checked={bank === b.key}
                onChange={() => setBank(b.key)}
              />
              <strong>{b.name}</strong>
              <span className="tst-muted">{b.reputation}</span>
            </span>
            <span className="tst-num">fee {pctText(b.fee_pct)}</span>
          </label>
        ))}
      </div>
      {act.error && (
        <Alert color="warn" data-testid="ipo-error">
          {act.error.message}
        </Alert>
      )}
      <Button
        h={44}
        style={{ alignSelf: 'flex-start' }}
        disabled={!p.eligible || bank === ''}
        loading={act.isPending}
        onClick={() => act.mutate({ kind: 'banks', bank })}
        data-testid="hire-banks"
      >
        Hire banks · {p.hire_energy} energy
      </Button>
    </div>
  );
}

const STATUS_TEXT: Record<string, string> = {
  filing: 'Filing the S-1',
  roadshow: 'On the roadshow',
  pricing: 'Pricing: decide in the pricing event',
  listed: 'Listed',
  pulled: 'Pulled',
};

function IpoProgress({ saveId, ipo }: { saveId: string; ipo: Ipo }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
      <ol
        aria-label="IPO progress"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {ipo.steps.map((s) => (
          <li
            key={s.key}
            data-testid={`ipo-step-${s.key}`}
            data-state={s.state}
            style={{
              flex: '1 1 140px',
              border: `1px solid ${s.state === 'now' ? 'var(--tst-accent)' : 'var(--tst-border)'}`,
              borderRadius: 8,
              padding: '8px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <span style={{ fontWeight: 600, color: STEP_COLOR[s.state] }}>{s.label}</span>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {s.state === 'now' ? 'now · ' : ''}
              {s.detail}
            </span>
          </li>
        ))}
      </ol>
      <span data-testid="ipo-status" data-status={ipo.status} style={{ fontSize: 14 }}>
        {STATUS_TEXT[ipo.status] ?? ipo.status}
        {ipo.status === 'listed' && ipo.listed && ` ${ipo.listed}`}
        {ipo.status === 'listed' && ipo.first_day_pct !== null && (
          <> · first day {pct(ipo.first_day_pct)}</>
        )}
        {ipo.status === 'pulled' && ipo.pulled && ` ${ipo.pulled}`}
        {ipo.status === 'listed' && (
          <>
            {' '}
            · <Link to={`/game/${saveId}/finance/stock`}>see the Stock tab</Link>
          </>
        )}
        {ipo.status !== 'listed' && ipo.status !== 'pulled' && (
          <>
            {' '}
            · <Link to={`/game/${saveId}/inbox`}>open events</Link>
          </>
        )}
      </span>
      {ipo.demand && (
        <span data-testid="ipo-demand" style={{ fontSize: 14 }}>
          <Term term="ipo.book_demand">The book</Term> is <strong>{ipo.demand}</strong>.
        </span>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        {ipo.status === 'pricing' && (
          <div style={{ flex: '3 1 360px' }}>
            <PricingCard saveId={saveId} ipo={ipo} choose />
          </div>
        )}
        {ipo.status !== 'pulled' && (
          <div style={{ flex: '2 1 300px' }}>
            <Offering ipo={ipo} />
          </div>
        )}
      </div>
    </div>
  );
}

/** The offering (wireframe "IPO"): new shares, shares after, implied cap, your stake after. */
export function Offering({ ipo }: { ipo: Ipo }) {
  const atPrice = ipo.price_cents ? ` at ${formatMoney(ipo.price_cents)}` : '';
  return (
    <section aria-label="The offering" data-testid="ipo-offering">
      <h3 className="tst-ptitle">The offering</h3>
      <Row label="New shares">
        {ipo.new_shares > 0
          ? `${formatShares(ipo.new_shares)}${ipo.share_sold_pct !== null ? ` (${pctText(ipo.share_sold_pct)})` : ''}`
          : 'set on the roadshow'}
      </Row>
      <Row label="Shares after listing">{formatShares(ipo.shares_after)}</Row>
      <Row label={<Term term="public.market_cap">Implied market cap{atPrice}</Term>}>
        {ipo.implied_cap_cents > 0 ? formatMoneyShort(ipo.implied_cap_cents) : 'set at pricing'}
      </Row>
      <Row label="Price-to-sales">
        {ipo.price_to_sales !== null ? `${ipo.price_to_sales.toFixed(1)}× ARR` : '—'}
      </Row>
      <Row label={<Term term="ipo.dual_class">Dual-class shares</Term>}>
        {ipo.dual_class === null ? 'decided on the roadshow' : ipo.dual_class ? 'Yes' : 'No'}
      </Row>
      <Row label="Your stake after listing">
        {pctText(ipo.stake_pct_after)}
        {ipo.stake_value_cents > 0 && ` · ${formatMoneyShort(ipo.stake_value_cents)}`}
      </Row>
    </section>
  );
}

/**
 * Pricing night (critical, wireframe "IPO"): the book in words, the bank's suggestion and each
 * choice with what it raises before and after fees and the likely first day. With `choose`,
 * the available options answer the open pricing event: they are its choices in order.
 */
export function PricingCard({
  saveId,
  ipo,
  choose = false,
}: {
  saveId: string;
  ipo: Ipo;
  choose?: boolean;
}) {
  const events = useEvents(saveId);
  const answer = useChooseEvent(saveId);
  const event = choose ? openIpoEvent(events.data?.open) : undefined;
  const available = ipo.options.filter((o) => o.available);
  const keyOf = (o: PriceOption): string | null => {
    if (!event || event.choices.length !== available.length) return null;
    const i = available.indexOf(o);
    return i < 0 ? null : (event.choices[i]?.key ?? null);
  };
  return (
    <section
      aria-label="Price the offering"
      data-testid="pricing-card"
      style={{
        border: '1px solid var(--tst-warn)',
        borderRadius: 10,
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <h3 style={{ margin: 0, fontSize: 16 }}>
        <span style={{ color: 'var(--tst-warn)', fontSize: 12, marginRight: 8 }}>CRITICAL</span>
        Price the offering
      </h3>
      <span style={{ fontSize: 14 }}>
        <Term term="ipo.book_demand">The book</Term> is <strong>{ipo.demand ?? 'not in'}</strong>.{' '}
        {ipo.bank} suggests{' '}
        <span className="tst-num">{ipo.price_cents ? formatMoney(ipo.price_cents) : '—'}</span> a
        share for {formatShares(ipo.new_shares)} new shares.
      </span>
      {ipo.options.map((o) => {
        const key = keyOf(o);
        return (
          <div
            key={o.choice}
            className="tst-row"
            data-testid={`price-option-${o.choice}`}
            data-available={o.available}
            style={{ opacity: o.available ? 1 : 0.55, gap: 10, flexWrap: 'wrap' }}
          >
            <span style={{ flex: '1 1 220px' }}>
              <strong>{o.label}</strong>
              {o.price_cents > 0 && (
                <span className="tst-num"> · {formatMoney(o.price_cents)}</span>
              )}
              <span className="tst-muted" style={{ display: 'block', fontSize: 12 }}>
                {o.first_day}
                {o.note && ` · ${o.note}`}
              </span>
            </span>
            <span className="tst-num" style={{ fontSize: 13 }}>
              {o.choice === 'pull'
                ? `costs ${formatMoneyWhole(-o.net_cents)}`
                : `raises ${formatMoneyShort(o.gross_cents)} (${formatMoneyShort(o.net_cents)} after fees)`}
            </span>
            {choose && key !== null && event && (
              <Button
                size="compact-sm"
                variant="default"
                disabled={answer.isPending}
                onClick={() => answer.mutate({ eventId: event.event_id, choice: key })}
                data-testid={`price-choose-${o.choice}`}
              >
                Choose
              </Button>
            )}
          </div>
        );
      })}
      {answer.error && <Alert color="warn">{answer.error.message}</Alert>}
      {choose && !event && (
        <span className="tst-muted" style={{ fontSize: 12 }}>
          Decide in the pricing event (<Link to={`/game/${saveId}/inbox`}>Inbox</Link>).
        </span>
      )}
    </section>
  );
}

/** The pricing card beside a critical IPO event's choices, read only (the event decides). */
export function IpoEventPricing({ saveId }: { saveId: string }) {
  const data = usePublic(saveId);
  const ipo = data.data?.ipo;
  if (!ipo || ipo.status !== 'pricing' || ipo.options.length === 0) return null;
  return <PricingCard saveId={saveId} ipo={ipo} />;
}
