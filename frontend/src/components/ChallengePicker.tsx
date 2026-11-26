// Challenge rules for a new game (M51, formulas.md 63.2): any campaign, Sandbox or scenario.
// Each rule is enforced by the engine (its actions are refused) and multiplies the score the
// result screen shows; the numbers come from the API.
import { Checkbox, Stack, Text } from '@mantine/core';
import type { NewGameMeta } from '../hooks/api';
import { Term } from './Term';

export function ChallengePicker({
  meta,
  value,
  onChange,
}: {
  meta: NewGameMeta;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const rules = meta.challenges ?? [];
  if (rules.length === 0) return null;
  return (
    <Stack gap={6} data-testid="challenge-picker">
      <span style={{ fontSize: 14, fontWeight: 500 }}>
        <Term term="challenges">Challenges</Term>
      </span>
      <Text size="xs" c="dimmed">
        Optional rules the game enforces. Each multiplies your company score on the result screen.
      </Text>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 8,
        }}
      >
        {rules.map((c) => (
          <Checkbox
            key={c.key}
            checked={value.includes(c.key)}
            onChange={(e) =>
              onChange(
                e.currentTarget.checked ? [...value, c.key] : value.filter((k) => k !== c.key),
              )
            }
            label={`${c.label} (score ×${c.score_mult.toFixed(2)})`}
            description={c.description}
            data-testid={`challenge-${c.key}`}
          />
        ))}
      </div>
    </Stack>
  );
}
