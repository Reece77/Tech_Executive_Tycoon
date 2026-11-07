// After an exit (M15b addendum 10): found a new company in the same world and month, putting
// the proceeds in less what you keep, or retire, which ends the game.
import { Button, NumberInput, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { GameOver } from '../hooks/api';
import { useFoundAgain, useRetire } from '../hooks/modes';
import { formatMoneyWhole } from '../lib/format';
import { Term } from './Term';

const CENTS = 100;

export function ExitChoicePanel({ saveId, over }: { saveId: string; over: GameOver }) {
  const navigate = useNavigate();
  const found = useFoundAgain(saveId);
  const retire = useRetire(saveId);
  const proceeds = over.exit_proceeds_cents ?? 0;
  const [name, setName] = useState('');
  const [keepDollars, setKeepDollars] = useState(0);
  const keep = Math.max(0, Math.round(keepDollars * CENTS));
  const invest = proceeds - keep;
  const minimum = over.min_new_cash_cents ?? 0;
  const tooLittle = invest < minimum;
  const error = found.error ?? retire.error;
  return (
    <section className="tst-panel" aria-label="What next" data-testid="exit-choice">
      <h2 className="tst-ptitle">
        <Term term="serial_founder">What next</Term>
      </h2>
      <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--tst-text-2)' }}>
        Found a new company in the same world and month: you keep your skills, reputation and
        network, and your proceeds become its starting cash, less what you keep. Or retire.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
        <TextInput
          label="New company name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          maxLength={60}
          data-testid="found-again-name"
          style={{ minWidth: 220 }}
        />
        <NumberInput
          label="Keep for yourself ($)"
          min={0}
          value={keepDollars}
          onChange={(v) => setKeepDollars(typeof v === 'number' ? v : Number(v) || 0)}
          thousandSeparator=","
          data-testid="found-again-keep"
          style={{ width: 180 }}
        />
        <span className="tst-num" style={{ fontSize: 13 }} data-testid="found-again-invest">
          Starting cash {formatMoneyWhole(Math.max(invest, 0))}
        </span>
        <Button
          disabled={!name.trim() || tooLittle || found.isPending}
          onClick={() =>
            found.mutate(
              { company_name: name.trim(), keep_cents: keep },
              { onSuccess: () => void navigate(`/game/${saveId}/overview`) },
            )
          }
          data-testid="found-again"
        >
          Found a new company
        </Button>
        <Button
          variant="light"
          color="gray"
          disabled={retire.isPending}
          onClick={() => retire.mutate()}
          data-testid="retire"
        >
          Retire
        </Button>
      </div>
      {tooLittle && (
        <p className="tst-muted" style={{ margin: '8px 0 0', fontSize: 12 }}>
          Put at least {formatMoneyWhole(minimum)} into the new company.
        </p>
      )}
      {error && (
        <p role="alert" style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--tst-warn)' }}>
          {error.message}
        </p>
      )}
    </section>
  );
}
