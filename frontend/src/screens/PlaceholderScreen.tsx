import { Paper, Stack, Text, Title } from '@mantine/core';
import { useParams } from 'react-router';
import { NAV_ITEMS } from '../lib/nav';

export function PlaceholderScreen() {
  const { section } = useParams();
  const item = NAV_ITEMS.find((i) => i.path === section);
  return (
    <Stack gap="md">
      <Title order={3}>{item?.label ?? 'Not found'}</Title>
      <Paper withBorder p="lg" radius="sm">
        <Text c="dimmed">
          {item?.arrivesIn ? `Arrives in ${item.arrivesIn}.` : 'This screen does not exist.'}
        </Text>
      </Paper>
    </Stack>
  );
}
