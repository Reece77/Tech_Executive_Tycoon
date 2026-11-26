import { Alert, Button, Container, Group, Stack, Title } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { useNewGameMeta } from '../hooks/api';
import { useScenarios, type ScenarioCard } from '../hooks/scenarios';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { CustomScenarios } from './CustomScenarios';

// The Scenarios screen (M51, formulas.md 63.3): every scenario with its brief, its difficulty
// (from the sensible script's wins on seeds 1-10), and the best result and challenges across
// every save in this profile. Results live in an app-wide file, so deleting a save keeps them.

const helper = createColumnHelper<GameTableFeatures, ScenarioCard>();

export function ScenariosScreen() {
  const { data, error, isPending } = useScenarios();
  const labels = useNewGameMeta().data?.challenges;
  const challengeLabel = useMemo(
    () => new Map((labels ?? []).map((c) => [c.key, c.label])),
    [labels],
  );
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', {
          header: 'Scenario',
          meta: { term: 'scenarios.scenario' },
          cell: ({ row }) => (
            <Stack gap={2}>
              <span style={{ fontWeight: 600 }}>{row.original.label}</span>
              <span className="tst-muted" style={{ fontSize: 12, lineHeight: 1.4 }}>
                {row.original.description}
              </span>
            </Stack>
          ),
        }),
        helper.accessor('year', {
          header: 'Start',
          meta: { term: 'scenarios.start' },
        }),
        helper.accessor('goal', {
          header: 'Goal',
          meta: { term: 'scenarios.goal' },
          cell: ({ row }) => `${row.original.goal} by ${row.original.deadline_label}`,
        }),
        helper.accessor((s) => s.difficulty ?? '', {
          id: 'difficulty',
          header: 'Difficulty',
          meta: { term: 'scenarios.difficulty' },
          cell: ({ row }) =>
            row.original.difficulty
              ? `${row.original.difficulty} (${row.original.sensible_wins ?? 0}/10)`
              : '—',
        }),
        helper.accessor((s) => s.best?.adjusted ?? -1, {
          id: 'best',
          header: 'Best result',
          meta: { term: 'scenarios.best' },
          cell: ({ row }) => {
            const best = row.original.best;
            if (!best) return <span className="tst-muted">Not played</span>;
            return (
              <span data-testid={`scenario-best-${row.original.key}`}>
                {best.result === 'success' ? 'Won' : 'Lost'} · {best.adjusted}
              </span>
            );
          },
        }),
        helper.accessor((s) => s.best?.date_label ?? '', {
          id: 'best_date',
          header: 'When',
          meta: { term: 'scenarios.when' },
          cell: ({ row }) =>
            row.original.best
              ? `${row.original.best.company} · ${row.original.best.date_label}`
              : '—',
        }),
        helper.accessor((s) => (s.best?.challenges ?? []).join(', '), {
          id: 'challenges',
          header: 'Challenges',
          meta: { term: 'scenarios.challenges' },
          cell: ({ row }) => {
            const used = row.original.best?.challenges ?? [];
            return used.length ? used.map((c) => challengeLabel.get(c) ?? c).join(', ') : '—';
          },
        }),
        helper.display({
          id: 'play',
          header: '',
          meta: { term: 'scenarios.play' },
          cell: ({ row }) => (
            <Button
              component={Link}
              to={`/new?scenario=${row.original.key}`}
              size="xs"
              variant="default"
              data-testid={`scenario-play-${row.original.key}`}
            >
              Play
            </Button>
          ),
        }),
      ]),
    [challengeLabel],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: data?.scenarios ?? [],
    getRowId: (s) => s.key,
  });
  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={2}>Scenarios</Title>
          <Group>
            <Button component={Link} to="/editor" variant="default" data-testid="open-editor">
              Scenario editor
            </Button>
            <Button component={Link} to="/" variant="default">
              Main menu
            </Button>
          </Group>
        </Group>
        {isPending ? (
          <Loading />
        ) : error || !data ? (
          <LoadError title="Could not load scenarios" error={error} />
        ) : (
          <>
            <Alert color="blue" data-testid="scenarios-rules">
              Best results across every save in profile “{data.profile}”: a win beats a loss, then
              the higher score after challenge multipliers. Difficulty is how often a sensible
              scripted player won on ten seeds.
            </Alert>
            <Panel title="Every scenario" testId="scenarios">
              <DataTable table={table} label="Scenarios" rowTestId="scenario-row" />
            </Panel>
            <CustomScenarios />
          </>
        )}
      </Stack>
    </Container>
  );
}
