import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Overview } from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../lib/format';

export function CashChart({ history }: { history: Overview['history'] }) {
  if (history.length === 0) {
    return (
      <p className="tst-muted" style={{ margin: 0, fontSize: 14, minHeight: 120 }}>
        No month has closed yet. Press Continue to play January 2010.
      </p>
    );
  }
  const last = history[history.length - 1];
  return (
    <div
      role="img"
      aria-label={`Cash at month end, ${history[0].date_label} to ${last.date_label}; now ${formatMoneyWhole(last.cash_cents)}`}
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={history} margin={{ top: 16, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
          <XAxis
            dataKey="date_label"
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(label: string) => label.split(' ')[0]}
          />
          <YAxis
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(v: number) => formatMoneyShort(v)}
            width={64}
          />
          <Tooltip
            formatter={(v) => formatMoneyWhole(Number(v))}
            contentStyle={{
              background: 'var(--tst-panel)',
              border: '1px solid var(--tst-border)',
              fontFamily: 'var(--tst-font-mono)',
            }}
          />
          <Line
            type="linear"
            dataKey="cash_cents"
            name="Cash"
            stroke="var(--tst-accent)"
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: 'var(--tst-accent)' }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
