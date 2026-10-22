import {
  Alert,
  Button,
  Center,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { SavesTable } from '../components/SavesTable';
import { useCreateSave, useSaves, useScenarios } from '../hooks/api';
import { formatMoney } from '../lib/format';
import { toSaveSlug } from '../lib/slug';

const SEED_RE = /^\d*$/;

export function MainMenu() {
  return (
    <Container size="md" py="xl">
      <Stack gap="xl">
        <Title order={2}>Tech Startup Tycoon</Title>
        <SavesSection />
        <NewGameForm />
      </Stack>
    </Container>
  );
}

function SavesSection() {
  const saves = useSaves();
  return (
    <Paper withBorder p="md" radius="sm">
      <Title order={4} mb="sm">
        Saved games
      </Title>
      {saves.isPending ? (
        <Center h={60}>
          <Loader size="sm" />
        </Center>
      ) : saves.error ? (
        <Alert color="red" title="Could not load saves">
          {saves.error.message}
        </Alert>
      ) : (
        <SavesTable saves={saves.data} />
      )}
    </Paper>
  );
}

function NewGameForm() {
  const navigate = useNavigate();
  const scenarios = useScenarios();
  const create = useCreateSave();
  const [companyName, setCompanyName] = useState('');
  const [scenario, setScenario] = useState<string | null>('garage_bootstrap');
  const [seed, setSeed] = useState('');

  const slug = toSaveSlug(companyName);
  const seedValid = SEED_RE.test(seed) && (seed === '' || Number.isSafeInteger(Number(seed)));
  const canSubmit = slug !== '' && scenario !== null && seedValid && !create.isPending;
  const selected = scenarios.data?.find((s) => s.id === scenario);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    create.mutate(
      {
        name: slug,
        company_name: companyName.trim(),
        scenario,
        seed: seed === '' ? null : Number(seed),
      },
      { onSuccess: (save) => void navigate(`/game/${save.save_id}/overview`) },
    );
  };

  return (
    <Paper withBorder p="md" radius="sm" component="form" onSubmit={onSubmit}>
      <Title order={4} mb="sm">
        New game
      </Title>
      <Stack gap="sm">
        <TextInput
          label="Company name"
          value={companyName}
          onChange={(e) => setCompanyName(e.currentTarget.value)}
          description={slug ? `Save file: ${slug}` : undefined}
          maxLength={80}
          required
          data-testid="company-name-input"
        />
        <Select
          label="Scenario"
          value={scenario}
          onChange={setScenario}
          data={(scenarios.data ?? []).map((s) => ({
            value: s.id,
            label: s.selectable ? s.name : `${s.name} (unlocks in ${s.available_in})`,
            disabled: !s.selectable,
          }))}
          allowDeselect={false}
          disabled={scenarios.isPending}
          data-testid="scenario-select"
        />
        {selected && (
          <Text size="sm" c="dimmed">
            {selected.description} Starting cash: {formatMoney(selected.starting_cash_cents)}.
          </Text>
        )}
        <TextInput
          label="Seed (optional)"
          value={seed}
          onChange={(e) => setSeed(e.currentTarget.value.trim())}
          error={seedValid ? undefined : 'Whole number up to 9007199254740991'}
          description="Leave blank for a random game; reuse a seed to replay the same world."
          data-testid="seed-input"
        />
        {create.error && (
          <Alert color="red" title="Could not create the game">
            {create.error.message}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button type="submit" disabled={!canSubmit} loading={create.isPending}>
            Start game
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}
