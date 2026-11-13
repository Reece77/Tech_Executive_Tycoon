import { Button, Container, Group, Stack, Title } from '@mantine/core';
import { Link } from 'react-router';
import { Panel } from '../components/ScreenState';
import { useSaves } from '../hooks/api';
import { useAchievements } from '../hooks/profile';
import { formatWhen } from '../lib/format';
import { SavesManager } from './SavesScreen';

export function MainMenu() {
  const achievements = useAchievements().data;
  // M29 (42.5): Continue opens the save played last (the API lists them newest first).
  const last = useSaves().data?.find((s) => s.game_state === 'active' && !s.busy);
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
            <Button
              component={Link}
              to="/new"
              size="md"
              h={44}
              variant={last ? 'default' : 'filled'}
              data-testid="new-game"
            >
              New game
            </Button>
            {last && (
              <Button
                component={Link}
                to={`/game/${last.save_id}`}
                size="md"
                h={44}
                data-testid="continue-last"
                title={`Last played ${formatWhen(last.last_played)}`}
              >
                Continue {last.display_name}
              </Button>
            )}
          </Group>
        </Group>
        <Panel title="Saves">
          <SavesManager />
        </Panel>
      </Stack>
    </Container>
  );
}
