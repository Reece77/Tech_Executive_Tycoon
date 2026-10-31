import { Alert, Button, Modal } from '@mantine/core';
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
import { formatMoneyShort } from '../lib/format';
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
                  : `Output ${pct(p.output_effect_pct)}, morale ${p.morale_effect.toFixed(1)}`}
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
          />
        ))}
        <p className="tst-muted" style={{ fontSize: 12 }}>
          {s.note}
        </p>
      </Panel>
      {seat !== null && <AppointDialog saveId={saveId} seat={seat} onClose={() => setSeat(null)} />}
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
}: {
  saveId: string;
  seat: Seat;
  removeCost: number;
  onAppoint: () => void;
  onRemove: () => void;
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
        <Button size="compact-sm" variant="default" onClick={onRemove} data-testid="remove-exec">
          Remove · {removeCost}
        </Button>
      )}
    </div>
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
          {data.candidates.map((c) => (
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
              <Button
                size="compact-sm"
                disabled={c.problem !== null || act.isPending}
                data-testid="appoint-confirm"
                onClick={() =>
                  act.mutate(
                    { action: 'appoint', seat, person_id: c.person_id },
                    { onSuccess: onClose },
                  )
                }
              >
                Appoint
              </Button>
            </div>
          ))}
          {act.error && <Alert color="warn">{act.error.message}</Alert>}
        </div>
      )}
    </Modal>
  );
}
