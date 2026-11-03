import { Alert, Button, Chip } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import { usePublic, usePublicAction, type Ceo } from '../hooks/api';
import { scopeLabel } from '../lib/public';
import { Term } from './Term';

/**
 * The CEO seat on the Executive team panel (M13, formulas.md 25.6): you, until the company is
 * public; then an Appoint CEO control; with a CEO, you are Chair, the CEO's authority as
 * toggles, their recent decisions with Override, and Dismiss.
 */
export function CeoSeat({ saveId, authorityEnergy }: { saveId: string; authorityEnergy: number }) {
  const data = usePublic(saveId);
  const ceo = data.data?.ceo;
  return (
    <div data-testid="ceo-seat" style={{ display: 'flex', flexDirection: 'column' }}>
      {!ceo || ceo.person_id === null ? (
        <NoCeo saveId={saveId} ceo={ceo} />
      ) : (
        <WithCeo saveId={saveId} ceo={ceo} authorityEnergy={authorityEnergy} />
      )}
    </div>
  );
}

function NoCeo({ saveId, ceo }: { saveId: string; ceo: Ceo | undefined }) {
  const [picked, setPicked] = useState<number | null>(null);
  const act = usePublicAction(saveId);
  const candidates = ceo?.candidates ?? [];
  const chosen = picked ?? candidates[0]?.person_id ?? null;
  return (
    <>
      <div className="tst-row">
        <span style={{ width: 48, fontWeight: 600 }}>
          <Term term="ceo.ceo">CEO</Term>
        </span>
        <span style={{ flex: 1 }}>
          You
          {ceo && !ceo.seat_open && <span className="tst-muted"> (until the IPO)</span>}
        </span>
      </div>
      {ceo?.seat_open && (
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '6px 0 10px' }}
          data-testid="ceo-appoint-panel"
        >
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Appoint a CEO to run the company day to day; you step up to{' '}
            <Term term="ceo.chair">Chair</Term> and keep capital, strategy and guidance.
          </span>
          {ceo.problem && (
            <span className="tst-muted" style={{ fontSize: 13 }}>
              {ceo.problem}
            </span>
          )}
          {candidates.length === 0 ? (
            <span className="tst-muted" style={{ fontSize: 13 }}>
              No one on the staff can take the seat yet.{' '}
              <Link to={`/game/${saveId}/recruitment`}>Open an exec-level search</Link>.
            </span>
          ) : (
            <div role="radiogroup" aria-label="CEO candidates">
              {candidates.map((c) => (
                <label
                  key={c.person_id}
                  className="tst-row"
                  style={{ cursor: 'pointer', gap: 8, justifyContent: 'flex-start' }}
                  data-testid={`ceo-candidate-${c.person_id}`}
                >
                  <input
                    type="radio"
                    name="ceo-candidate"
                    checked={chosen === c.person_id}
                    onChange={() => setPicked(c.person_id)}
                  />
                  <Link to={`/game/${saveId}/people/${c.person_id}`}>{c.name}</Link>
                  <span className="tst-muted">
                    {c.role} · {c.level}
                  </span>
                </label>
              ))}
            </div>
          )}
          {act.error && (
            <Alert color="warn" data-testid="ceo-error">
              {act.error.message}
            </Alert>
          )}
          {candidates.length > 0 && (
            <Button
              h={44}
              style={{ alignSelf: 'flex-start' }}
              disabled={chosen === null}
              loading={act.isPending}
              onClick={() =>
                chosen !== null && act.mutate({ kind: 'appointCeo', personId: chosen })
              }
              data-testid="ceo-appoint"
            >
              Appoint CEO · {ceo.appoint_energy} energy
            </Button>
          )}
        </div>
      )}
    </>
  );
}

function WithCeo({
  saveId,
  ceo,
  authorityEnergy,
}: {
  saveId: string;
  ceo: Ceo;
  authorityEnergy: number;
}) {
  const act = usePublicAction(saveId);
  const toggle = (scope: string) => {
    const scopes = ceo.scopes.includes(scope)
      ? ceo.scopes.filter((s) => s !== scope)
      : [...ceo.scopes, scope];
    act.mutate({ kind: 'authority', scopes });
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 10 }}>
      <div className="tst-row" style={{ gap: 8 }}>
        <span style={{ width: 48, fontWeight: 600 }}>
          <Term term="ceo.ceo">CEO</Term>
        </span>
        <span style={{ flex: 1 }}>
          <Link to={`/game/${saveId}/people/${ceo.person_id}`} data-testid="ceo-name">
            {ceo.name}
          </Link>{' '}
          <span className="tst-muted">since {ceo.since}</span>
        </span>
        <Button
          size="compact-sm"
          variant="default"
          loading={act.isPending && act.variables?.kind === 'dismissCeo'}
          onClick={() => act.mutate({ kind: 'dismissCeo' })}
          data-testid="ceo-dismiss"
        >
          Dismiss · {ceo.appoint_energy}
        </Button>
      </div>
      <span style={{ fontSize: 13 }} data-testid="ceo-chair">
        You are <Term term="ceo.chair">Chair</Term> (energy {ceo.chair_energy} a month).
      </span>
      <div>
        <div className="tst-muted" style={{ fontSize: 12, marginBottom: 4 }}>
          <Term term="ceo.authority">The CEO runs</Term> (each change {authorityEnergy} energy)
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }} data-testid="ceo-scopes">
          {ceo.all_scopes.map((s) => (
            <Chip
              key={s}
              size="xs"
              checked={ceo.scopes.includes(s)}
              onChange={() => toggle(s)}
              disabled={act.isPending}
              data-testid={`ceo-scope-${s}`}
            >
              {scopeLabel(s)}
            </Chip>
          ))}
        </div>
      </div>
      <div data-testid="ceo-decisions">
        <h4 style={{ margin: '8px 0 4px' }}>
          <Term term="ceo.override">The CEO&apos;s decisions</Term>
        </h4>
        {ceo.decisions.length === 0 && (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            None yet: the CEO acts at Continue.
          </span>
        )}
        {ceo.decisions.map((d) => (
          <div
            className="tst-row"
            key={d.id}
            data-testid="ceo-decision"
            data-overridden={d.overridden}
            style={{ fontSize: 13, gap: 8 }}
          >
            <span style={{ flex: 1, textDecoration: d.overridden ? 'line-through' : undefined }}>
              {d.label} · {scopeLabel(d.scope)}: {d.text}
            </span>
            {d.mistake && <span style={{ color: 'var(--tst-warn)' }}>misstep</span>}
            {d.overridden ? (
              <span className="tst-muted" data-testid="ceo-overridden">
                overridden
              </span>
            ) : (
              d.can_override && (
                <Button
                  size="compact-xs"
                  variant="default"
                  loading={
                    act.isPending &&
                    act.variables?.kind === 'override' &&
                    act.variables.decisionId === d.id
                  }
                  disabled={act.isPending}
                  onClick={() => act.mutate({ kind: 'override', decisionId: d.id })}
                  data-testid="ceo-override"
                >
                  Override · {ceo.override_energy}
                </Button>
              )
            )}
          </div>
        ))}
      </div>
      {act.error && (
        <Alert color="warn" data-testid="ceo-error">
          {act.error.message}
        </Alert>
      )}
    </div>
  );
}
