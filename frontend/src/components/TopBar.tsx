import { Button, Group, Kbd, Loader, Text } from '@mantine/core';
import { Link } from 'react-router';
import type { Overview } from '../hooks/api';
import { formatMoney } from '../lib/format';

interface Props {
  overview: Overview | undefined;
  advancing: boolean;
  onContinue: () => void;
}

export function TopBar({ overview, advancing, onContinue }: Props) {
  return (
    <Group h="100%" px="md" justify="space-between" wrap="nowrap">
      <Group gap="lg" wrap="nowrap">
        <Text component={Link} to="/" fw={700} c="dimmed" size="sm">
          TST
        </Text>
        <Text fw={600} data-testid="company-name">
          {overview?.company_name ?? '…'}
        </Text>
      </Group>
      <Group gap="xl" wrap="nowrap">
        <div>
          <Text size="xs" c="dimmed">
            Date
          </Text>
          <Text fw={600} className="tst-num" data-testid="game-date">
            {overview?.date_label ?? '…'}
          </Text>
        </div>
        <div>
          <Text size="xs" c="dimmed">
            Cash
          </Text>
          <Text fw={600} className="tst-num" data-testid="top-cash">
            {overview ? formatMoney(overview.cash_cents) : '…'}
          </Text>
        </div>
        <Button
          size="md"
          onClick={onContinue}
          disabled={!overview || advancing}
          leftSection={advancing ? <Loader size="xs" color="white" /> : undefined}
          rightSection={
            <Kbd size="xs" visibleFrom="sm">
              Space
            </Kbd>
          }
          data-testid="continue"
        >
          Continue
        </Button>
      </Group>
    </Group>
  );
}
