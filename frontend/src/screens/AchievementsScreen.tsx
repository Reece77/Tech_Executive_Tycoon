import { Alert, Button, Container, Group, Stack, Title } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { useAchievements, type Achievement } from '../hooks/profile';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// Achievements (M25 section 2): earned, locked, and hidden ones as "???", across every game
// in this profile. Sandbox and modded games earn none.

const helper = createColumnHelper<GameTableFeatures, Achievement>();

export function AchievementsScreen() {
  const { data, error, isPending } = useAchievements();
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('earned', {
          header: 'Status',
          meta: { term: 'achievement.status' },
          cell: ({ row }) =>
            row.original.earned ? (
              <strong>Earned</strong>
            ) : (
              <span className="tst-muted">{row.original.hidden ? 'Hidden' : 'Locked'}</span>
            ),
        }),
        helper.accessor('title', {
          header: 'Achievement',
          meta: { term: 'achievement.title' },
          cell: ({ row }) => <span style={{ fontWeight: 600 }}>{row.original.title}</span>,
        }),
        helper.accessor('description', {
          header: 'How',
          meta: { term: 'achievement.description' },
        }),
        helper.accessor((a) => a.date_label ?? '', {
          id: 'earned_in',
          header: 'Earned in',
          meta: { term: 'achievement.earned_in' },
          cell: ({ row }) =>
            row.original.earned
              ? `${row.original.company ?? ''} · ${row.original.date_label ?? ''}`
              : '—',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: data?.achievements ?? [],
    getRowId: (a) => a.key,
  });
  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={2}>Achievements</Title>
          <Button component={Link} to="/" variant="default">
            Main menu
          </Button>
        </Group>
        {isPending ? (
          <Loading />
        ) : error || !data ? (
          <LoadError title="Could not load achievements" error={error} />
        ) : (
          <>
            <Alert color="blue" data-testid="achievements-rules">
              {data.earned} of {data.total} earned in profile “{data.profile}”. Achievements count
              across every game; Sandbox and modded games earn none, and scenario wins count only in
              scenario mode.
            </Alert>
            <Panel title="All achievements" testId="achievements">
              <DataTable table={table} label="Achievements" rowTestId="achievement-row" />
            </Panel>
          </>
        )}
      </Stack>
    </Container>
  );
}
