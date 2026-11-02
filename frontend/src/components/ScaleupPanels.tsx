import { Alert, Button, Modal, NumberInput } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  useOrgMeta,
  useScaleup,
  useScaleupAction,
  useSeatCandidates,
  type Division,
  type Org,
  type Scaleup,
  type Seat,
} from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../lib/format';
import { pct } from '../lib/org';
import { Panel } from './ScreenState';

/**
 * The Org screen's scale-up panels (M8, from stage 3): divisions with their president,
 * shared services and P&L, support coverage, cross-division work, and the executive team.
 */
export function ScaleupPanels({ saveId, org }: { saveId: string; org: Org }) {
  const scaleup = useScaleup(saveId);
  if (!scaleup.data || !scaleup.data.in_play) return null;
  return <Body saveId={saveId} org={org} s={scaleup.data} />;
}

function Body({ saveId, org, s }: { saveId: string; org: Org; s: Scaleup }) {
  const act = useScaleupAction(saveId);
  const meta = useOrgMeta();
  const costs = meta.data?.energy_costs ?? {};
  const [seat, setSeat] = useState<string | null>(null);
  const [authorityKey, setAuthorityKey] = useState<string | null>(null);
  const setAuthority = (x: Seat) => setAuthorityKey(x.seat);
  const authority = s.seats.find((x) => x.seat === authorityKey) ?? null;
  const corporate = org.units.find((u) => u.unit_id === null);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
      <section
        aria-label="Divisions"
        data-testid="divisions-panel"
        style={{ flex: '3 1 560px', display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <Panel title="Structure">
          <div className="tst-row">
            <span>
              <strong>Corporate</strong> · led by you
            </span>
            <span className="tst-muted">
              {corporate?.members.length ?? 0} direct staff · {s.divisions.length} of{' '}
              {s.max_divisions} divisions
            </span>
          </div>
          {s.divisions.length === 0 && (
            <p className="tst-muted" style={{ fontSize: 13 }}>
              No divisions yet. A division has a president and its own P&amp;L.
            </p>
          )}
          {s.divisions.map((d) => (
            <DivisionCard
              key={d.unit_id}
              d={d}
              cost={costs.set_shared_services ?? 0}
              onServices={(services) =>
                act.mutate({ action: 'services', unit_id: d.unit_id, services })
              }
            />
          ))}
          {act.error && (
            <Alert color="warn" data-testid="scaleup-error">
              {act.error.message}
            </Alert>
          )}
        </Panel>
        <Panel title="Support coverage" testId="support-panel">
          <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
            {s.support_rule}.
          </p>
          {s.support.map((p) => (
            <div className="tst-row" key={p.key} data-testid="support-pool">
              <span>
                {p.label}: <span className="tst-num">{p.support_staff}</span> of{' '}
                <span className="tst-num">{p.needed}</span> needed for {p.headcount} staff
              </span>
              <span style={{ color: p.covered ? 'var(--tst-good)' : 'var(--tst-warn)' }}>
                {p.covered
                  ? 'Covered'
                  : `Output ${pct(p.output_effect_pct)} (est.), morale ${p.morale_effect.toFixed(1)}`}
              </span>
            </div>
          ))}
        </Panel>
        {s.cross_division.length > 0 && (
          <Panel title="Cross-division work" testId="cross-division">
            {s.cross_division.map((c) => (
              <div key={c.product_id} className="tst-row">
                <span>
                  {c.product_name} is built in {c.division_names.join(' and ')}: output{' '}
                  {pct(c.output_effect_pct)}
                </span>
                <span className="tst-muted">{c.fix}</span>
              </div>
            ))}
          </Panel>
        )}
      </section>
      <Panel title="Executive team" testId="exec-team" style={{ flex: '2 1 380px' }}>
        <div className="tst-row">
          <span style={{ width: 48, fontWeight: 600 }}>CEO</span>
          <span style={{ flex: 1 }}>You (until the IPO)</span>
        </div>
        {s.seats.map((x) => (
          <SeatRow
            key={x.seat}
            saveId={saveId}
            seat={x}
            removeCost={costs.remove_executive ?? 0}
            onAppoint={() => setSeat(x.seat)}
            onRemove={() => act.mutate({ action: 'remove', seat: x.seat })}
            onAuthority={() => setAuthority(x)}
          />
        ))}
        <p className="tst-muted" style={{ fontSize: 12 }}>
          {s.note}
        </p>
        {s.proposals.length > 0 && (
          <div data-testid="exec-proposals">
            <h4 style={{ margin: '12px 0 4px' }}>Proposals</h4>
            {s.proposals.map((p) => (
              <div className="tst-row" key={p.proposal_id} data-testid="exec-proposal">
                <span style={{ flex: 1 }}>
                  <strong>{p.name}</strong> ({p.seat.toUpperCase()}), {p.date_label}: {p.text}
                </span>
                {p.status === 'pending' ? (
                  <span style={{ display: 'flex', gap: 4 }}>
                    <Button
                      size="compact-xs"
                      data-testid="proposal-approve"
                      loading={act.isPending}
                      onClick={() =>
                        act.mutate({
                          action: 'proposal',
                          proposal_id: p.proposal_id,
                          approve: true,
                        })
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      size="compact-xs"
                      variant="default"
                      data-testid="proposal-decline"
                      loading={act.isPending}
                      onClick={() =>
                        act.mutate({
                          action: 'proposal',
                          proposal_id: p.proposal_id,
                          approve: false,
                        })
                      }
                    >
                      Decline
                    </Button>
                  </span>
                ) : (
                  <span className="tst-muted">{p.status}</span>
                )}
              </div>
            ))}
          </div>
        )}
        {s.decisions.length > 0 && (
          <div data-testid="exec-decisions">
            <h4 style={{ margin: '12px 0 4px' }}>Recent decisions</h4>
            {s.decisions.map((d, i) => (
              <div className="tst-row" key={i} data-testid="exec-decision" style={{ fontSize: 13 }}>
                <span style={{ flex: 1 }}>
                  {d.date_label} · {d.name} ({d.seat.toUpperCase()}): {d.text}
                </span>
                {d.mistake && <span style={{ color: 'var(--tst-warn)' }}>misstep</span>}
              </div>
            ))}
          </div>
        )}
      </Panel>
      {seat !== null && <AppointDialog saveId={saveId} seat={seat} onClose={() => setSeat(null)} />}
      {authority && (
        <AuthorityDialog
          saveId={saveId}
          seat={authority}
          energy={costs.set_authority ?? 0}
          onClose={() => setAuthorityKey(null)}
        />
      )}
    </div>
  );
}

function DivisionCard({
  d,
  cost,
  onServices,
}: {
  d: Division;
  cost: number;
  onServices: (services: 'central' | 'embedded') => void;
}) {
  const other = d.services === 'central' ? 'embedded' : 'central';
  return (
    <div
      data-testid="division-card"
      style={{
        border: '1px solid var(--tst-border)',
        borderRadius: 8,
        padding: '10px 14px',
        marginTop: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'baseline' }}>
        <strong>{d.name}</strong>
        <span className="tst-muted">{d.headcount} staff</span>
        <span
          data-testid="services-chip"
          style={{
            fontSize: 11,
            textTransform: 'uppercase',
            background: 'var(--tst-grey-bg)',
            borderRadius: 4,
            padding: '2px 7px',
          }}
        >
          {d.services}
        </span>
        <span style={{ marginLeft: 'auto' }} className="tst-num" data-testid="division-profit">
          {d.operating_profit_cents === null
            ? 'No month yet'
            : `Last month ${formatMoneyShort(d.operating_profit_cents)}`}
        </span>
      </div>
      <div className="tst-muted" style={{ fontSize: 13 }}>
        President: {d.president_name ?? 'none yet'} · Products:{' '}
        {d.product_names.length ? d.product_names.join(', ') : 'none'}
      </div>
      <div style={{ fontSize: 13 }}>{d.effect_note}</div>
      <div>
        <Button
          size="compact-sm"
          variant="default"
          data-testid="set-services"
          onClick={() => onServices(other)}
        >
          Make {other} · {cost}
        </Button>
      </div>
    </div>
  );
}

function SeatRow({
  saveId,
  seat,
  removeCost,
  onAppoint,
  onRemove,
  onAuthority,
}: {
  saveId: string;
  seat: Seat;
  removeCost: number;
  onAppoint: () => void;
  onRemove: () => void;
  onAuthority: () => void;
}) {
  return (
    <div className="tst-row" data-testid={`seat-${seat.seat}`} style={{ gap: 8 }}>
      <span style={{ width: 48, fontWeight: 600 }}>{seat.label}</span>
      <span style={{ flex: 1 }}>
        {seat.holder_id !== null ? (
          <>
            <Link to={`/game/${saveId}/people/${seat.holder_id}`}>{seat.holder_name}</Link>{' '}
            <span className="tst-muted">
              {seat.fit} for {seat.label}
              {seat.estimated_effect_pct !== null &&
                ` · ${seat.effect_label} ${pct(seat.estimated_effect_pct)} (est.)`}
            </span>
          </>
        ) : (
          <>
            vacant{' '}
            {seat.vacancy_penalty_pct !== null && (
              <span style={{ color: 'var(--tst-warn)' }} data-testid="vacancy-penalty">
                {seat.effect_label} {pct(seat.vacancy_penalty_pct)}
              </span>
            )}
          </>
        )}
      </span>
      {seat.holder_id === null ? (
        <Button size="compact-sm" variant="default" onClick={onAppoint} data-testid="appoint">
          Appoint…
        </Button>
      ) : (
        <>
          {seat.authority && (
            <Button
              size="compact-sm"
              variant={seat.authority.enabled ? 'filled' : 'default'}
              onClick={onAuthority}
              data-testid="authority"
              title={seat.authority.acts_on}
            >
              {seat.authority.enabled ? 'Authority on' : 'Give authority…'}
            </Button>
          )}
          <Button size="compact-sm" variant="default" onClick={onRemove} data-testid="remove-exec">
            Remove · {removeCost}
          </Button>
        </>
      )}
    </div>
  );
}

const GUARD_LABELS: Record<string, string> = {
  headcount_cap: 'Headcount cap',
  max_salary_ratio_bp: 'Max offer, % of the ask',
  price_band_pct: 'Price band, ± %',
  marketing_pct_of_revenue: 'Marketing, % of revenue',
  coverage_target: 'Support coverage target',
  lease_approval_rent_cents: 'Leases above this rent need your approval ($ a month)',
  runway_months: 'Propose funding below this runway (months)',
  repay_above_months: 'Repay debt with cash above (months of burn)',
};

/** A seat's authority and guardrails (24.1, M10c). Percent-of-ask is entered as a percent;
 * cents as dollars. */
export function AuthorityDialog({
  saveId,
  seat,
  energy,
  onClose,
}: {
  saveId: string;
  seat: Seat;
  energy: number;
  onClose: () => void;
}) {
  const act = useScaleupAction(saveId);
  const a = seat.authority;
  const shown = (key: string, v: number): number =>
    key === 'max_salary_ratio_bp' ? v / 100 : key === 'lease_approval_rent_cents' ? v / 100 : v;
  const stored = (key: string, v: number): number =>
    key === 'max_salary_ratio_bp' || key === 'lease_approval_rent_cents' ? Math.round(v * 100) : v;
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      Object.entries(a?.guardrails ?? {})
        .filter(([, v]) => typeof v === 'number')
        .map(([k, v]) => [k, shown(k, v as number)]),
    ),
  );
  if (!a) return null;
  const submit = (enabled: boolean) =>
    act.mutate(
      {
        action: 'authority',
        seat: seat.seat,
        enabled,
        guardrails: Object.fromEntries(Object.entries(values).map(([k, v]) => [k, stored(k, v)])),
      },
      { onSuccess: onClose },
    );
  return (
    <Modal opened onClose={onClose} title={`${seat.label} authority`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          {a.acts_on}. {seat.holder_name} acts each month with their own energy, through the same
          actions as you; how well depends on how good they are at the job.
        </p>
        {Object.keys(values).map((k) => (
          <NumberInput
            key={k}
            label={GUARD_LABELS[k] ?? k}
            min={0}
            value={values[k]}
            onChange={(v) => setValues({ ...values, [k]: Number(v) || 0 })}
            data-testid={`guard-${k}`}
          />
        ))}
        {act.error && <Alert color="warn">{act.error.message}</Alert>}
        <div style={{ display: 'flex', gap: 8 }}>
          <Button loading={act.isPending} onClick={() => submit(true)} data-testid="authority-on">
            {a.enabled ? 'Save guardrails' : 'Give authority'} · {energy}
          </Button>
          {a.enabled && (
            <Button
              variant="default"
              loading={act.isPending}
              onClick={() => submit(false)}
              data-testid="authority-off"
            >
              Withdraw · {energy}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

function AppointDialog({
  saveId,
  seat,
  onClose,
}: {
  saveId: string;
  seat: string;
  onClose: () => void;
}) {
  const candidates = useSeatCandidates(saveId, seat);
  const act = useScaleupAction(saveId);
  const data = candidates.data;
  // The salary to appoint at, in whole dollars, by person; unset: their default (M8r).
  const [salaries, setSalaries] = useState<Record<number, number>>({});
  return (
    <Modal
      opened
      onClose={onClose}
      title={data ? `Appoint a ${data.seat.label}` : 'Appoint'}
      size="lg"
      data-testid="appoint-dialog"
    >
      {data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <p className="tst-muted" style={{ fontSize: 13, margin: 0 }}>
            {data.note} Energy {data.energy_cost}.
          </p>
          <p style={{ fontSize: 13, margin: 0 }}>
            No one suitable?{' '}
            <Link to={`/game/${saveId}/recruitment`} onClick={onClose}>
              Open an exec-level search
            </Link>
            .
          </p>
          {data.candidates.map((c) => {
            const dollars = salaries[c.person_id] ?? Math.round(c.exec_salary_cents / 100);
            return (
              <div key={c.person_id} className="tst-row" data-testid="appoint-candidate">
                <span style={{ flex: 1 }}>
                  <strong>{c.name}</strong>{' '}
                  <span className="tst-muted">
                    {c.role} · {c.level} · {c.fit} · {data.seat.effect_label}{' '}
                    {pct(c.estimated_effect_pct)} (est.)
                  </span>
                  {c.problem && (
                    <div className="tst-muted" style={{ fontSize: 12 }}>
                      {c.problem}
                    </div>
                  )}
                </span>
                {c.problem === null && (
                  <NumberInput
                    aria-label={`Salary for ${c.name}`}
                    prefix="$"
                    thousandSeparator=","
                    allowDecimal={false}
                    allowNegative={false}
                    w={140}
                    size="xs"
                    value={dollars}
                    onChange={(v) =>
                      setSalaries((s) => ({ ...s, [c.person_id]: typeof v === 'number' ? v : 0 }))
                    }
                    description={`a year · now ${formatMoneyWhole(c.salary_cents)}`}
                    inputWrapperOrder={['input', 'description']}
                    classNames={{ input: 'tst-num' }}
                    data-testid="appoint-salary"
                  />
                )}
                <Button
                  size="compact-sm"
                  disabled={c.problem !== null || act.isPending}
                  data-testid="appoint-confirm"
                  onClick={() =>
                    act.mutate(
                      {
                        action: 'appoint',
                        seat,
                        person_id: c.person_id,
                        salary_cents: dollars * 100,
                      },
                      { onSuccess: onClose },
                    )
                  }
                >
                  Appoint
                </Button>
              </div>
            );
          })}
          {act.error && <Alert color="warn">{act.error.message}</Alert>}
        </div>
      )}
    </Modal>
  );
}
