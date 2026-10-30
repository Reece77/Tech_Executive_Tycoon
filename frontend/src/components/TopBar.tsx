import { Button, Loader } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { FinanceSummary, Overview } from '../hooks/api';
import { formatMoneyWhole, formatRunway } from '../lib/format';

interface Props {
  overview: Overview | undefined;
  summary?: FinanceSummary;
  advancing: boolean;
  blocked?: boolean; // an open critical event (M6)
  onContinue: () => void;
}

const BADGE = {
  fontSize: 12,
  fontWeight: 700,
  color: 'var(--tst-bg)',
  background: 'var(--tst-warn)',
  borderRadius: 4,
  padding: '4px 10px',
  textDecoration: 'none',
} as const;

/** Orange while cash is negative (M4b); links to the bridge offer when one is open. */
function InsolventBadge({ saveId, summary }: { saveId: string; summary?: FinanceSummary }) {
  const bridge = summary?.open_bridge_id != null;
  const months = summary?.insolvent_months ?? 0;
  const title = bridge
    ? 'Cash is below zero. Your investors offer a bridge: open it on Fundraising.'
    : `Cash is below zero${months ? ` at ${months} month end${months === 1 ? '' : 's'} in a row` : ''}. Three in a row is bankruptcy.`;
  return (
    <Link
      to={`/game/${saveId}/finance/fundraising`}
      style={BADGE}
      title={title}
      data-testid="insolvent-badge"
    >
      Insolvent{bridge ? ' · bridge offered' : ''}
    </Link>
  );
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span className="tst-ptitle" style={{ margin: 0, fontSize: 11, fontWeight: 400 }}>
        {label}
      </span>
      {children}
    </div>
  );
}

export function EnergyMeter({ energy, max }: { energy: number; max: number }) {
  const pct = max > 0 ? Math.round((energy / max) * 100) : 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140 }}>
      <span className="tst-ptitle" style={{ margin: 0, fontSize: 11, fontWeight: 400 }}>
        Founder energy{' '}
        <span className="tst-num" style={{ color: 'var(--tst-text)' }} data-testid="energy">
          {energy} / {max}
        </span>
      </span>
      <div
        role="meter"
        aria-label="Founder energy"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={energy}
        style={{ height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: 6,
            background: 'var(--tst-accent)',
            borderRadius: 3,
          }}
        />
      </div>
    </div>
  );
}

export function TopBar({ overview, summary, advancing, blocked = false, onContinue }: Props) {
  const ended = overview !== undefined && overview.game_state !== 'active';
  return (
    <header
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 24,
        padding: '12px 20px',
        background: 'var(--tst-panel)',
        borderBottom: '1px solid var(--tst-border)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <Link
          to="/"
          style={{
            color: 'var(--tst-text)',
            textDecoration: 'none',
            fontSize: 16,
            fontWeight: 700,
          }}
          data-testid="company-name"
          title="Back to saved games"
        >
          {overview?.company_name ?? '…'}
        </Link>
        <span className="tst-muted" style={{ fontSize: 12 }} data-testid="stage">
          {overview ? `Stage ${overview.stage} · ${overview.stage_label}` : ' '}
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 28,
          marginLeft: 'auto',
          alignItems: 'center',
        }}
      >
        <Stat label="Date">
          <span className="tst-num" style={{ fontSize: 15 }} data-testid="game-date">
            {overview?.date_label ?? '…'}
          </span>
        </Stat>
        <Stat label="Cash">
          <span
            className="tst-num"
            style={{
              fontSize: 15,
              color: overview && overview.cash_cents < 0 ? 'var(--tst-warn)' : undefined,
            }}
            data-testid="top-cash"
          >
            {overview ? formatMoneyWhole(overview.cash_cents) : '…'}
          </span>
        </Stat>
        {overview && !ended && overview.cash_cents < 0 && (
          <InsolventBadge saveId={overview.save_id} summary={summary} />
        )}
        <Stat label="Runway">
          <span
            className="tst-num"
            style={{
              fontSize: 15,
              color: overview?.runway_low ? 'var(--tst-warn)' : undefined,
            }}
            data-testid="top-runway"
          >
            {overview ? formatRunway(overview.runway_months) : '…'}
          </span>
        </Stat>
        {overview && !ended && (
          <EnergyMeter energy={overview.energy.energy} max={overview.energy.max} />
        )}
        {ended && overview && (
          <Link to={`/game/${overview.save_id}/over`} style={BADGE} data-testid="game-over-badge">
            Game over
          </Link>
        )}
        {overview && (
          <Button
            component={Link}
            to={`/game/${overview.save_id}/settings`}
            variant="default"
            h={44}
            data-testid="settings-button"
          >
            Settings
          </Button>
        )}
        <Button
          size="md"
          radius="md"
          h={44}
          px={28}
          onClick={onContinue}
          disabled={!overview || advancing || ended || blocked}
          title={blocked ? 'Answer the critical event first' : undefined}
          leftSection={advancing ? <Loader size="xs" color="dark" /> : undefined}
          data-testid="continue"
        >
          Continue <span style={{ fontWeight: 400, opacity: 0.75, marginLeft: 6 }}>· Space</span>
        </Button>
        {blocked && (
          <span style={{ fontSize: 12, color: 'var(--tst-warn)' }} data-testid="continue-blocked">
            Answer the critical event first
          </span>
        )}
      </div>
    </header>
  );
}
