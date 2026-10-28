// Person profile additions (M2b): unit and manager links, the morale breakdown, Raise and
// Promote dialogs with their previews, and Move to…. Every number comes from the API.
import { Alert, Button, Menu, Modal, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  useGiveRaise,
  useMoraleBreakdown,
  useOrg,
  useOrgMeta,
  usePayPreview,
  usePromote,
  type MoraleBreakdown,
  type Org,
  type OrgMeta,
  type Overview,
  type PayPreview,
  type Profile,
} from '../hooks/api';
import {
  formatBpPercent,
  formatMoneyWhole,
  formatRatio,
  formatRunway,
  formatWhole,
  humanize,
  parseDollars,
} from '../lib/format';
import { MANAGER_LABELS, POLICY_LABELS, signed } from '../lib/org';
import { ChangeDialog, type Pending } from './OrgChangeDialog';
import { Panel } from './ScreenState';

/** "Unit Platform (Engineering) · Manager Marcus Ode", linked. */
export function UnitManagerLine({ saveId, p }: { saveId: string; p: Profile }) {
  if (!p.org) return null;
  const o = p.org;
  return (
    <span style={{ fontSize: 14, color: 'var(--tst-text-2)' }} data-testid="profile-org">
      Unit{' '}
      <Link to={`/game/${saveId}/org`} data-testid="profile-unit">
        {o.unit_name}
      </Link>
      {o.parent_unit_name ? ` (${o.parent_unit_name})` : ''}
      {o.manager_id !== null && (
        <>
          {' · Manager '}
          <Link to={`/game/${saveId}/people/${o.manager_id}`} data-testid="profile-manager">
            {o.manager_name}
          </Link>
        </>
      )}
    </span>
  );
}

/** Give a raise, Promote and Move to…, each opening its preview before it is applied. */
export function PersonActions({ saveId, p }: { saveId: string; p: Profile }) {
  const meta = useOrgMeta();
  const org = useOrg(saveId);
  const [dialog, setDialog] = useState<'raise' | 'promote' | null>(null);
  const [raiseTo, setRaiseTo] = useState<number | null>(null);
  const [move, setMove] = useState<Pending | null>(null);
  if (!p.employment || p.is_founder || !meta.data || !org.data) return null;
  const costs = meta.data.energy_costs;
  const first = p.name.split(' ')[0];
  const leads = p.org?.leads_unit_id ?? null;
  const destinations = org.data.units.filter((u) => u.unit_id !== (p.org?.unit_id ?? null));
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, flexBasis: '100%' }}>
      <Button variant="default" h={36} data-testid="give-raise" onClick={() => setDialog('raise')}>
        Give a raise · {costs.give_raise}
      </Button>
      <Button variant="default" h={36} data-testid="promote" onClick={() => setDialog('promote')}>
        Promote · {costs.promote}
      </Button>
      <Menu>
        <Menu.Target>
          <Button
            variant="default"
            h={36}
            data-testid="profile-move"
            disabled={leads !== null}
            title={leads !== null ? 'Replace or remove them as leader first' : undefined}
          >
            Move to… · {costs.move_person}
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          {destinations.map((d) => (
            <Menu.Item
              key={d.unit_id ?? 'root'}
              onClick={() =>
                setMove({
                  change: { change: 'move_person', person_id: p.person_id, unit_id: d.unit_id },
                  title: `Move ${p.name} to ${d.name}?`,
                  confirmLabel: `Move ${first}`,
                  note: 'Their manager changes, so their monthly morale and growth follow the new manager from next month.',
                })
              }
            >
              {d.name}
            </Menu.Item>
          ))}
        </Menu.Dropdown>
      </Menu>
      {dialog === 'raise' && (
        <RaiseDialog
          saveId={saveId}
          p={p}
          meta={meta.data}
          initialCents={raiseTo ?? p.employment.salary_cents}
          onClose={() => {
            setDialog(null);
            setRaiseTo(null);
          }}
        />
      )}
      {dialog === 'promote' && (
        <PromoteDialog
          saveId={saveId}
          p={p}
          onClose={() => setDialog(null)}
          onPromoteAndRaise={(newMarketCents) => {
            setRaiseTo(newMarketCents);
            setDialog('raise');
          }}
        />
      )}
      {move && <ChangeDialog saveId={saveId} pending={move} onDone={() => setMove(null)} />}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' }) {
  return (
    <div className="tst-row">
      <span>{label}</span>
      <span
        className="tst-num"
        style={{
          color:
            tone === 'pos' ? 'var(--tst-good)' : tone === 'neg' ? 'var(--tst-warn)' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}

const tone = (v: number) => (v > 0 ? 'pos' : v < 0 ? 'neg' : undefined);

export function RaiseFacts({ pv, roleText }: { pv: PayPreview; roleText: string }) {
  const change = pv.salary_change_bp;
  return (
    <div data-testid="raise-facts">
      <p className="tst-muted" style={{ margin: '0 0 6px', fontSize: 12 }}>
        {change >= 0 ? 'Up' : 'Down'} {formatBpPercent(Math.abs(change))} from{' '}
        {formatMoneyWhole(pv.salary_cents)}. {roleText} market rate{' '}
        {formatMoneyWhole(pv.new_market_rate_cents)}: this is {formatRatio(pv.new_market_ratio)}.
      </p>
      <Row label="One-off morale" value={signed(pv.morale_change)} tone={tone(pv.morale_change)} />
      <Row
        label="Monthly cost"
        value={`${pv.monthly_cost_change_cents >= 0 ? '+' : '-'}${formatMoneyWhole(
          Math.abs(pv.monthly_cost_change_cents),
        )}`}
      />
      <Row label="Energy" value={String(pv.energy_cost)} />
    </div>
  );
}

function RaiseDialog({
  saveId,
  p,
  meta,
  initialCents,
  onClose,
}: {
  saveId: string;
  p: Profile;
  meta: OrgMeta;
  initialCents: number;
  onClose: () => void;
}) {
  const [text, setText] = useState(String(Math.round(initialCents / 100)));
  const [debounced] = useDebouncedValue(text, 250);
  const cents = parseDollars(debounced);
  const preview = usePayPreview(saveId, p.person_id, 'raise', cents, true);
  const raise = useGiveRaise(saveId);
  const pv = preview.data;
  const first = p.name.split(' ')[0];
  const roleText = `${humanize(p.employment?.level ?? '')} ${(p.role_label ?? '').toLowerCase()}`;
  return (
    <Modal opened onClose={onClose} title={`Give ${first} a raise`} centered>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="raise-dialog">
        <TextInput
          label="New annual salary"
          leftSection="$"
          value={text}
          data-testid="raise-salary"
          onChange={(e) => setText(e.currentTarget.value)}
        />
        {cents === 0 && <span className="tst-muted">Enter a salary in dollars.</span>}
        {pv && cents > 0 && <RaiseFacts pv={pv} roleText={roleText} />}
        {pv && !pv.allowed && <Alert color="warn">{pv.problem}</Alert>}
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          Raises of {formatBpPercent(meta.raise_threshold_bp)} or more lift morale by{' '}
          {formatWhole(meta.raise_morale)} once every {meta.raise_cooldown_turns} months. A pay cut
          costs {formatWhole(Math.abs(meta.pay_cut_morale))} morale. The new salary applies from the
          next payroll.
        </p>
        {raise.error && <Alert color="red">{raise.error.message}</Alert>}
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="md"
            data-testid="confirm-raise"
            disabled={!pv?.allowed || cents === 0 || preview.isPlaceholderData}
            loading={raise.isPending}
            onClick={() =>
              raise.mutate({ personId: p.person_id, salaryCents: cents }, { onSuccess: onClose })
            }
          >
            Confirm raise
          </Button>
          <Button size="md" variant="default" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function PromoteDialog({
  saveId,
  p,
  onClose,
  onPromoteAndRaise,
}: {
  saveId: string;
  p: Profile;
  onClose: () => void;
  onPromoteAndRaise: (newMarketCents: number) => void;
}) {
  const preview = usePayPreview(saveId, p.person_id, 'promote', 0, true);
  const promote = usePromote(saveId);
  const pv = preview.data;
  const first = p.name.split(' ')[0];
  return (
    <Modal
      opened
      onClose={onClose}
      title={pv ? `Promote ${first} to ${humanize(pv.new_level)}` : `Promote ${first}`}
      centered
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        data-testid="promote-dialog"
      >
        {!pv && <span className="tst-muted">Checking the promotion…</span>}
        {pv && !pv.allowed && <Alert color="warn">{pv.problem}</Alert>}
        {pv && pv.allowed && (
          <div data-testid="promote-facts">
            <Row label="Level" value={`${humanize(pv.level)} → ${humanize(pv.new_level)}`} />
            <Row
              label="Market rate"
              value={`${formatMoneyWhole(pv.market_rate_cents)} → ${formatMoneyWhole(
                pv.new_market_rate_cents,
              )}`}
            />
            <Row
              label={`${first}'s salary against it`}
              value={formatRatio(pv.new_market_ratio)}
              tone={pv.below_market ? 'neg' : undefined}
            />
            <Row
              label="One-off morale"
              value={signed(pv.morale_change)}
              tone={tone(pv.morale_change)}
            />
            <Row label="Energy" value={String(pv.energy_cost)} />
          </div>
        )}
        {pv?.below_market && (
          <Alert color="warn" data-testid="below-market">
            At {formatMoneyWhole(pv.salary_cents)} {first} would be paid below a {pv.new_level}
            &apos;s market rate, and pay would weigh on morale from next month. Promote and raise
            together.
          </Alert>
        )}
        {promote.error && <Alert color="red">{promote.error.message}</Alert>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Button
            size="md"
            data-testid="confirm-promote"
            disabled={!pv?.allowed}
            loading={promote.isPending}
            onClick={() => promote.mutate(p.person_id, { onSuccess: onClose })}
          >
            Promote
          </Button>
          <Button
            size="md"
            variant="default"
            data-testid="promote-and-raise"
            disabled={!pv?.allowed}
            onClick={() =>
              pv &&
              promote.mutate(p.person_id, {
                onSuccess: () => onPromoteAndRaise(pv.new_market_rate_cents),
              })
            }
          >
            Promote and raise…
          </Button>
          <Button size="md" variant="default" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// --- Morale breakdown ---------------------------------------------------------------------------

/** One-line notes for each term, from values the profile, org and overview already carry. */
function termNote(
  key: string,
  p: Profile,
  b: MoraleBreakdown,
  org: Org | undefined,
  overview: Overview,
): string {
  if (key === 'base') return 'Everyone starts here';
  if (key === 'pay' && p.employment?.market_rate_cents != null) {
    return `${formatMoneyWhole(p.employment.salary_cents)} against a ${formatMoneyWhole(
      p.employment.market_rate_cents,
    )} market rate`;
  }
  if (key === 'runway') {
    return overview.runway_months === null
      ? 'Profitable'
      : `${formatRunway(overview.runway_months)} of cash`;
  }
  if (key === 'manager' && b.manager_id !== null) {
    const m = org?.managers.find((x) => x.person_id === b.manager_id);
    if (!m) return b.manager_name ?? '';
    const label = (MANAGER_LABELS[m.label] ?? m.label).toLowerCase();
    return `${b.manager_name} is ${label} (${m.reports.length} reports)`;
  }
  if (key === 'remote') {
    const unit = org?.units.find((u) => u.unit_id === (p.org?.unit_id ?? null));
    return unit ? (POLICY_LABELS[unit.effective_policy] ?? unit.effective_policy) : '';
  }
  if (key === 'other') return 'Things you do not know yet';
  return '';
}

export function MoraleBreakdownPanel({
  saveId,
  p,
  overview,
}: {
  saveId: string;
  p: Profile;
  overview: Overview;
}) {
  const enabled = !!p.employment && !p.is_founder;
  const breakdown = useMoraleBreakdown(saveId, p.person_id, enabled);
  const org = useOrg(saveId);
  if (!enabled) return null;
  const first = p.name.split(' ')[0];
  const b = breakdown.data;
  return (
    <Panel
      title={`Why ${first}'s morale is moving`}
      style={{ flex: '1 1 360px', display: 'flex', flexDirection: 'column', gap: 4 }}
    >
      {!b && <span className="tst-muted">Loading…</span>}
      {b &&
        b.terms.map((t) => (
          <div key={t.key} className="tst-row" data-testid={`term-${t.key}`}>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <span>{t.key === 'base' ? 'Starting point' : t.label}</span>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {termNote(t.key, p, b, org.data, overview)}
              </span>
            </span>
            <span
              className="tst-num"
              style={{
                color:
                  t.key === 'base'
                    ? undefined
                    : t.value > 0
                      ? 'var(--tst-good)'
                      : t.value < 0
                        ? 'var(--tst-warn)'
                        : 'var(--tst-muted)',
              }}
            >
              {t.key === 'base' ? formatWhole(t.value) : signed(t.value)}
            </span>
          </div>
        ))}
      {b && (
        <div className="tst-row" style={{ borderBottom: 0, fontWeight: 600 }}>
          <span>Where {first}&apos;s morale is heading</span>
          <span className="tst-num" data-testid="morale-target">
            {formatWhole(b.target)}
          </span>
        </div>
      )}
      <p className="tst-muted" style={{ margin: '4px 0 0', fontSize: 12, lineHeight: 1.5 }}>
        Morale moves part of the way toward this each month. &quot;Other&quot; covers everything you
        cannot see yet, such as traits you have not noticed and month-to-month mood.
      </p>
    </Panel>
  );
}
