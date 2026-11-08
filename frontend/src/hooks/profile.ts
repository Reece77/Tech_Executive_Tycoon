// TanStack Query hooks for achievements (M25 section 2). Kept beside hooks/api.ts so the
// lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap } from './api';

export type Achievements = Schemas['AchievementsOut'];
export type Achievement = Schemas['AchievementOut'];

export function useAchievements() {
  return useQuery({
    queryKey: ['profile', 'achievements'],
    queryFn: async () => unwrap(await api.GET('/api/profile/achievements')),
  });
}

/** The profile as one save sees it: under the save's key, so every action and Continue
 * (which invalidate the save) fetch it again and a new achievement's toast shows. */
export function useSaveAchievements(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'achievements'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/achievements', {
          params: { path: { save_id: saveId } },
        }),
      ),
    enabled: saveId !== '',
  });
}

export function useMarkSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (keys: string[]) =>
      unwrap(await api.POST('/api/profile/achievements/seen', { body: { keys } })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['profile', 'achievements'] });
    },
  });
}
