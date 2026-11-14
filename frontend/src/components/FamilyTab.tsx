// The founder profile's Family tab (M36, formulas.md 45.5-45.6): a link to the Family screen,
// succession (an heir, whom the player then plays, or a professional CEO) and estate planning
// (the estate-tax quote, gifts to heirs, the family trust and shares to the foundation).
// Every number comes from the API; percentages are its basis points shown as %.
import { Alert, Button, Modal, NativeSelect, NumberInput } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  useFamily,
  useFoundationShares,
  useFundTrust,
  useGiftShares,
  useNameSuccessor,
  type Estate,
  type Family,
} from '../hooks/family';
import { formatShares } from '../lib/finance';
import { formatBpPercent, formatMoney, formatMoneyWhole } from '../lib/format';
import { Explain } from './Explain';
import { Panel } from './ScreenState';
import { Term } from './Term';

const COL = { display: 'flex', flexDirection: 'column', gap: 8 } as const;

const OPEN_TEXT: Record<string, string> = {
  choice: 'You chose to step back: name your successor.',
  health: 'On health grounds, it is time to name your successor.',
  board: 'The board wants a new leader: name your successor, or the company goes on without you.',
};

function Line({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span className="tst-muted">{label}</span>
      <span className="tst-num" data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

function Problem({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <Alert color="orange" role="alert" data-testid="family-error">
      {error.message}
    </Alert>
  );
}

export function FamilyTab({ saveId }: { saveId: string }) {
  const q = useFamily(saveId);
  if (!q.data) return null;
  return <FamilyTabBody saveId={saveId} family={q.data} />;
}

function FamilyTabBody({ saveId, family }: { saveId: string; family: Family }) {
  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
      data-testid="founder-family-tab"
    >
      <Link to={`/game/${saveId}/people/family`} style={{ fontSize: 13 }} data-testid="family-link">
        Open the Family screen
      </Link>
      {!family.exists ? (
        <span className="tst-muted">No family in this game (Family was set to none).</span>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          <SuccessionPanel saveId={saveId} family={family} />
          {family.estate && <EstatePanel saveId={saveId} family={family} e={family.estate} />}
        </div>
      )}
    </div>
  );
}

function SuccessionPanel({ saveId, family }: { saveId: string; family: Family }) {
  const name = useNameSuccessor(saveId);
  const names = new Map(family.children.map((c) => [c.person_id, c.name]));
  const [heir, setHeir] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const heirId = heir ?? (family.heirs[0] !== undefined ? String(family.heirs[0]) : '');
  const heirName = names.get(Number(heirId)) ?? '';
  const head = family.head_name ?? 'your founder';
  return (
    <Panel title="Succession" style={{ ...COL, flex: '1 1 300px' }} testId="succession-panel">
      {family.succession_open && (
        <Alert color="yellow" data-testid="succession-open">
          {OPEN_TEXT[family.succession_open] ?? 'Name your successor.'}
        </Alert>
      )}
      {family.step_back_open && (
        <Alert color="yellow" data-testid="step-back-open">
          Your health asks you to step back: answer it in the inbox.
        </Alert>
      )}
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Hand the company to an heir, and you play as them; or appoint a professional CEO and stay on
        as head of the family. Heirs are listed by <Term term="family.readiness">readiness</Term>,
        readiest first.
      </span>
      {family.heirs.length === 0 ? (
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="no-heirs">
          No child can succeed yet: an heir must be old enough and work in the group.
        </span>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <NativeSelect
            label="Heir"
            value={heirId}
            onChange={(e) => setHeir(e.currentTarget.value)}
            data={family.heirs.map((id) => ({
              value: String(id),
              label: names.get(id) ?? `Person ${id}`,
            }))}
            data-testid="succession-heir-select"
          />
          <Button
            onClick={() => setConfirming(true)}
            disabled={!heirId}
            data-testid="succession-hand-over"
          >
            Hand over
          </Button>
        </div>
      )}
      <Button
        variant="default"
        onClick={() => name.mutate({ professional: true })}
        loading={name.isPending && !confirming}
        data-testid="succession-ceo"
      >
        Appoint a professional CEO
      </Button>
      <Problem error={name.error} />
      {confirming && (
        <Modal opened onClose={() => setConfirming(false)} title="Hand over the company" centered>
          <p style={{ marginTop: 0 }} data-testid="succession-confirm-text">
            You will play as {heirName}; {head} joins the board as adviser.
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="default" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              loading={name.isPending}
              onClick={() =>
                name.mutate({ heir_id: Number(heirId) }, { onSettled: () => setConfirming(false) })
              }
              data-testid="succession-confirm"
            >
              Hand over to {heirName}
            </Button>
          </div>
        </Modal>
      )}
    </Panel>
  );
}

function EstatePanel({ saveId, family, e }: { saveId: string; family: Family; e: Estate }) {
  const gift = useGiftShares(saveId);
  const trust = useFundTrust(saveId);
  const foundation = useFoundationShares(saveId);
  const kids = family.children;
  const [giftTo, setGiftTo] = useState<string | null>(null);
  const [giftShares, setGiftShares] = useState<number | string>('');
  const [trustShares, setTrustShares] = useState<number | string>('');
  const [foundationShares, setFoundationShares] = useState<number | string>('');
  const giftId = giftTo ?? (kids[0] ? String(kids[0].person_id) : '');
  const keepsControl = e.family_bp_after >= e.control_bp;
  return (
    <Panel title="Estate planning" style={{ ...COL, flex: '2 1 380px' }} testId="estate-panel">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }} data-testid="estate-quote">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <strong>
            <Term term="family.estate_tax">Estate tax</Term> if the company passed on today
          </strong>
          <Explain metric="estate_tax" label="Estate tax" />
        </div>
        <Line
          label={`Rate (${e.region.replace(/_/g, ' ')})`}
          value={`${Math.round(e.rate * 1000) / 10}%`}
        />
        <Line label="Estate" value={formatMoneyWhole(e.estate_cents)} testId="estate-value" />
        <Line
          label="  Shares"
          value={`${formatShares(e.shares)} at ${formatMoney(e.share_price_cents)}`}
        />
        <Line label="  Cash" value={formatMoneyWhole(e.cash_cents)} />
        <Line label="  Other" value={formatMoneyWhole(e.other_cents)} />
        <Line
          label="Exemption (used by gifts)"
          value={`${formatMoneyWhole(e.exemption_cents)} (${formatMoneyWhole(e.used_exemption_cents)})`}
        />
        <Line label="Taxable" value={formatMoneyWhole(e.taxable_cents)} />
        <Line label="Tax" value={formatMoneyWhole(e.tax_cents)} testId="estate-tax" />
        <Line
          label="Shares to sell"
          value={formatShares(e.shares_to_sell)}
          testId="estate-shares-to-sell"
        />
        <Line
          label="Family holds now → after"
          value={`${formatBpPercent(e.family_bp_now)} → ${formatBpPercent(e.family_bp_after)}`}
          testId="estate-family-pct"
        />
        <Line label="Control needs" value={formatBpPercent(e.control_bp)} />
        <span
          style={{ fontSize: 13, color: keepsControl ? 'var(--tst-accent)' : 'var(--tst-warn)' }}
          data-testid="estate-control"
        >
          {keepsControl ? 'The family would keep control.' : 'The family would lose control.'}
        </span>
      </div>

      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="family.gift">Gifts</Term>, the trust and the foundation take shares out of the
        estate.
      </span>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <NativeSelect
          label="Gift shares to"
          value={giftId}
          onChange={(ev) => setGiftTo(ev.currentTarget.value)}
          data={kids.map((k) => ({ value: String(k.person_id), label: k.name }))}
          data-testid="gift-heir-select"
        />
        <NumberInput
          label="Shares"
          value={giftShares}
          onChange={setGiftShares}
          min={1}
          allowDecimal={false}
          thousandSeparator=","
          data-testid="gift-shares-input"
        />
        <Button
          onClick={() => gift.mutate({ heir_id: Number(giftId), shares: Number(giftShares) })}
          disabled={!giftId || !Number(giftShares)}
          loading={gift.isPending}
          data-testid="gift-shares"
        >
          Gift
        </Button>
      </div>
      <Problem error={gift.error} />

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <NumberInput
          label="Shares into the trust"
          value={trustShares}
          onChange={setTrustShares}
          min={1}
          allowDecimal={false}
          thousandSeparator=","
          data-testid="trust-shares-input"
        />
        <Button
          onClick={() => trust.mutate(Number(trustShares))}
          disabled={!Number(trustShares)}
          loading={trust.isPending}
          data-testid="fund-trust"
        >
          Fund the trust
        </Button>
      </div>
      <span style={{ fontSize: 13 }} data-testid="trust-status">
        <Term term="family.trust">Family trust</Term>:{' '}
        {family.trust_since
          ? `since ${family.trust_since}, ${formatShares(e.trust_shares)} shares`
          : 'none yet'}
      </span>
      <Problem error={trust.error} />

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <NumberInput
          label="Shares to the foundation"
          value={foundationShares}
          onChange={setFoundationShares}
          min={1}
          allowDecimal={false}
          thousandSeparator=","
          data-testid="foundation-shares-input"
        />
        <Button
          onClick={() => foundation.mutate(Number(foundationShares))}
          disabled={!Number(foundationShares)}
          loading={foundation.isPending}
          data-testid="foundation-shares"
        >
          Give to the foundation
        </Button>
      </div>
      <Problem error={foundation.error} />

      <Line
        label="Lifetime gifts"
        value={formatMoneyWhole(e.lifetime_gifts_cents)}
        testId="lifetime-gifts"
      />
      <Line
        label={e.gift_tax ? 'Gift tax paid' : 'Gift tax paid (none in your region)'}
        value={formatMoneyWhole(e.gift_tax_paid_cents)}
      />
      <Line label="Estate tax paid" value={formatMoneyWhole(e.estate_tax_paid_cents)} />
    </Panel>
  );
}
