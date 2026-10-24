import { Button, Loader } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { Overview } from '../hooks/api';
import { formatMoneyWhole, formatRunway } from '../lib/format';

interface Props {
  overview: Overview | undefined;
  advancing: boolean;
  onContinue: () => void;
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

export function TopBar({ overview, advancing, onContinue }: Props) {
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
          <span className="tst-num" style={{ fontSize: 15 }} data-testid="top-cash">
            {overview ? formatMoneyWhole(overview.cash_cents) : '…'}
          </span>
        </Stat>
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
        {overview && <EnergyMeter energy={overview.energy.energy} max={overview.energy.max} />}
        <Button
          size="md"
          radius="md"
          h={44}
          px={28}
          onClick={onContinue}
          disabled={!overview || advancing}
          leftSection={advancing ? <Loader size="xs" color="dark" /> : undefined}
          data-testid="continue"
        >
          Continue <span style={{ fontWeight: 400, opacity: 0.75, marginLeft: 6 }}>· Space</span>
        </Button>
      </div>
    </header>
  );
}
