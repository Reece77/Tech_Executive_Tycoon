import { Button, Container, Group, Stack, Title } from '@mantine/core';
import { Link } from 'react-router';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { SavesTable } from '../components/SavesTable';
import { useSaves } from '../hooks/api';

export function MainMenu() {
  const saves = useSaves();
  return (
    <Container size="md" py="xl">
      <Stack gap="xl">
        <Group justify="space-between">
          <Title order={2}>Tech Startup Tycoon</Title>
          <Button component={Link} to="/new" size="md" h={44} data-testid="new-game">
            New game
          </Button>
        </Group>
        <Panel title="Saved games">
          {saves.isPending ? (
            <Loading />
          ) : saves.error ? (
            <LoadError title="Could not load saves" error={saves.error} />
          ) : (
            <SavesTable saves={saves.data} />
          )}
        </Panel>
      </Stack>
    </Container>
  );
}
