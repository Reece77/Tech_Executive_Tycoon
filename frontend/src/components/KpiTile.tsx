import { Paper, Text } from '@mantine/core';

interface Props {
  label: string;
  value: string;
  hint?: string;
  testId?: string;
}

export function KpiTile({ label, value, hint, testId }: Props) {
  return (
    <Paper withBorder p="sm" radius="sm" title={hint}>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text size="xl" fw={700} className="tst-num" data-testid={testId}>
        {value}
      </Text>
    </Paper>
  );
}
