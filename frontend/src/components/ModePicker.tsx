// How the new game plays (M15b, formulas.md 30.2-30.3): the campaign, a Sandbox start in any
// year with its own cash, rivals and eras, or one of the historical scenarios.
import { NumberInput, SegmentedControl, Select } from '@mantine/core';
import type { NewGameMeta } from '../hooks/api';
import type { Schemas } from '../api/client';
import { Term } from './Term';

export type SandboxIn = Schemas['SandboxIn'];
export type ModeChoice =
  | { kind: 'campaign' }
  | { kind: 'sandbox'; sandbox: SandboxIn }
  | { kind: 'historical'; key: string };

const RIVALS = [
  { value: 'all', label: 'All rivals' },
  { value: 'half', label: 'Half the rivals' },
  { value: 'none', label: 'No rivals' },
];
const ERAS = [
  { value: 'historical', label: 'Eras as history had them' },
  { value: 'seeded', label: 'Later eras seeded around their dates' },
];

function defaultSandbox(meta: NewGameMeta): SandboxIn {
  return { start_year: meta.sandbox?.year_min ?? 2010, rivals: 'all', eras: 'historical' };
}

export function ModePicker({
  meta,
  value,
  onChange,
}: {
  meta: NewGameMeta;
  value: ModeChoice;
  onChange: (v: ModeChoice) => void;
}) {
  const sb = meta.sandbox;
  const historical = meta.historical ?? [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="mode-picker">
      <span style={{ fontSize: 14, fontWeight: 500 }}>
        <Term term="game_mode">Mode</Term>
      </span>
      <SegmentedControl
        value={value.kind}
        onChange={(k) =>
          onChange(
            k === 'sandbox'
              ? { kind: 'sandbox', sandbox: defaultSandbox(meta) }
              : k === 'historical'
                ? { kind: 'historical', key: historical[0]?.key ?? '' }
                : { kind: 'campaign' },
          )
        }
        data={[
          { value: 'campaign', label: 'Campaign' },
          { value: 'sandbox', label: 'Sandbox' },
          { value: 'historical', label: 'Historical scenario' },
        ]}
        data-testid="mode-kind"
      />
      {value.kind === 'sandbox' && sb && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <NumberInput
            label="Start year"
            min={sb.year_min}
            max={sb.year_max}
            value={value.sandbox.start_year}
            onChange={(v) =>
              onChange({
                ...value,
                sandbox: { ...value.sandbox, start_year: Number(v) || sb.year_min },
              })
            }
            data-testid="sandbox-year"
            style={{ width: 140 }}
          />
          <NumberInput
            label="Starting cash ($)"
            description="Empty: the background's"
            min={sb.cash_min_dollars}
            max={sb.cash_max_dollars}
            thousandSeparator=","
            value={value.sandbox.cash_dollars ?? ''}
            onChange={(v) =>
              onChange({
                ...value,
                sandbox: { ...value.sandbox, cash_dollars: v === '' ? null : Number(v) },
              })
            }
            data-testid="sandbox-cash"
            style={{ width: 200 }}
          />
          <Select
            label="Rivals"
            data={RIVALS}
            value={value.sandbox.rivals ?? 'all'}
            allowDeselect={false}
            onChange={(v) =>
              onChange({
                ...value,
                sandbox: { ...value.sandbox, rivals: (v ?? 'all') as SandboxIn['rivals'] },
              })
            }
            data-testid="sandbox-rivals"
            style={{ width: 180 }}
          />
          <Select
            label="Eras"
            data={ERAS}
            value={value.sandbox.eras ?? 'historical'}
            allowDeselect={false}
            onChange={(v) =>
              onChange({
                ...value,
                sandbox: { ...value.sandbox, eras: (v ?? 'historical') as SandboxIn['eras'] },
              })
            }
            data-testid="sandbox-eras"
            style={{ width: 280 }}
          />
          <span className="tst-muted" style={{ fontSize: 12, flexBasis: '100%' }}>
            In a Sandbox game the board cannot remove you, and its score is kept out of the Hall of
            Fame.
          </span>
        </div>
      )}
      {value.kind === 'historical' && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: 10,
          }}
        >
          {historical.map((h) => (
            <button
              key={h.key}
              type="button"
              className="tst-card"
              aria-pressed={value.key === h.key}
              onClick={() => onChange({ kind: 'historical', key: h.key })}
              data-testid={`historical-${h.key}`}
            >
              <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontWeight: 600 }}>{h.label}</span>
                <span className="tst-num tst-muted" style={{ fontSize: 13 }}>
                  {h.year}
                </span>
              </span>
              <span className="tst-muted" style={{ fontSize: 13, lineHeight: 1.45 }}>
                {h.description}
              </span>
              <span style={{ fontSize: 13 }}>
                Goal: {h.goal} by {h.deadline_label}.
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
