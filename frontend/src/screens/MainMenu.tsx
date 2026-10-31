import { Button, Container, Group, Stack, Title } from '@mantine/core';
import { Link } from 'react-router';
import { Panel } from '../components/ScreenState';
import { SavesManager } from './SavesScreen';

export function MainMenu() {
  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between">
          <Title order={2}>Tech Startup Tycoon</Title>
          <Button component={Link} to="/new" size="md" h={44} data-testid="new-game">
            New game
          </Button>
        </Group>
        <Panel title="Saves">
          <SavesManager />
        </Panel>
      </Stack>
    </Container>
  );
}
