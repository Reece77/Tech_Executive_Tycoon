import { Button, Container, Group, Stack, Title } from '@mantine/core';
import { Link } from 'react-router';
import { Panel } from '../components/ScreenState';
import { useAchievements } from '../hooks/profile';
import { SavesManager } from './SavesScreen';

export function MainMenu() {
  const achievements = useAchievements().data;
  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between">
          <Title order={2}>Tech Startup Tycoon</Title>
          <Group gap="sm">
            <Button
              component={Link}
              to="/achievements"
              variant="default"
              size="md"
              h={44}
              data-testid="achievements-link"
            >
              Achievements{achievements ? ` ${achievements.earned}/${achievements.total}` : ''}
            </Button>
            <Button
              component={Link}
              to="/mods"
              variant="default"
              size="md"
              h={44}
              data-testid="data-editor-link"
            >
              Data editor
            </Button>
            <Button component={Link} to="/new" size="md" h={44} data-testid="new-game">
              New game
            </Button>
          </Group>
        </Group>
        <Panel title="Saves">
          <SavesManager />
        </Panel>
      </Stack>
    </Container>
  );
}
