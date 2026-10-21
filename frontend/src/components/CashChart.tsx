import { Paper, Text } from '@mantine/core';
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
import { formatMoney, formatMoneyShort } from '../lib/format';

export function CashChart({ history }: { history: Overview['history'] }) {
  return (
    <Paper withBorder p="sm" radius="sm">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb="xs">
        Cash, last 12 months
      </Text>
      {history.length === 0 ? (
        <Text c="dimmed" size="sm" h={240}>
          No month has closed yet. Press Continue to play January 2010.
        </Text>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={history} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--tst-border)" strokeDasharray="3 3" />
            <XAxis dataKey="date_label" stroke="var(--tst-text-muted)" fontSize={12} />
            <YAxis
              stroke="var(--tst-text-muted)"
              fontSize={12}
              tickFormatter={(v: number) => formatMoneyShort(v)}
              width={64}
            />
            <Tooltip
              formatter={(v) => formatMoney(Number(v))}
              contentStyle={{
                background: 'var(--tst-surface-raised)',
                border: '1px solid var(--tst-border)',
              }}
            />
            <Line
              type="monotone"
              dataKey="cash_cents"
              name="Cash"
              stroke="var(--tst-accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Paper>
  );
}
