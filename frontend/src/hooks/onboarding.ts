// TanStack Query hooks for onboarding and navigation (M29, formulas.md 42): unlocks, Getting
// started, What next, the palette's index, their settings and Back up. Kept beside
// hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { keys, unwrap } from './api';

export type Unlocks = Schemas['UnlocksOut'];
export type System = Schemas['SystemOut'];
export type GettingStarted = Schemas['GettingStartedOut'];
export type WhatNextItem = Schemas['WhatNextItemOut'];
export type PaletteEntry = Schemas['PaletteEntryOut'];
export type OnboardingSettings = Schemas['OnboardingSettings'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const SETTINGS_KEY = ['settings', 'onboarding'] as const;

export function useUnlocks(saveId: string) {
  return useQuery({
    queryKey: [...keys.save(saveId), 'unlocks'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/unlocks', path(saveId))),
    enabled: saveId !== '',
  });
}

/** The keys of the systems the side bar shows, or null while loading (show everything). */
export function useUnlockedKeys(saveId: string): ReadonlySet<string> | null {
  const data = useUnlocks(saveId).data;
  if (!data) return null;
  return new Set(data.systems.filter((s) => s.unlocked).map((s) => s.key));
}

export function useOpenSystem(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/unlocks/{key}/open', {
          params: { path: { save_id: saveId, key } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.save(saveId) }),
  });
}

export function useGettingStarted(saveId: string) {
  return useQuery({
    queryKey: [...keys.save(saveId), 'getting-started'],
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/getting-started', path(saveId))),
  });
}

export function useDismissGettingStarted(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/getting-started/dismiss', path(saveId))),
    onSuccess: (out) => client.setQueryData([...keys.save(saveId), 'getting-started'], out),
  });
}

export function useWhatNext(saveId: string) {
  return useQuery({
    queryKey: [...keys.save(saveId), 'what-next'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/what-next', path(saveId))),
  });
}

export function usePalette(saveId: string, enabled = true) {
  return useQuery({
    queryKey: [...keys.save(saveId), 'palette'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/palette', path(saveId))),
    enabled: enabled && saveId !== '',
    staleTime: 30_000,
  });
}

export function useOnboardingSettings() {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: async () => unwrap(await api.GET('/api/settings/ui/onboarding')),
  });
}

export function useUpdateOnboardingSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: OnboardingSettings) =>
      unwrap(await api.PUT('/api/settings/ui/onboarding', { body })),
    onSuccess: (out) => {
      client.setQueryData(SETTINGS_KEY, out);
      // what is shown, what blocks Continue and a holiday's default stop all follow it
      void client.invalidateQueries({ queryKey: keys.saves });
    },
  });
}

export function useBackUp() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (saveId: string) =>
      unwrap(await api.POST('/api/saves/{save_id}/backups', path(saveId))),
    onSuccess: (_out, saveId) => {
      void client.invalidateQueries({ queryKey: ['backups', saveId] });
      void client.invalidateQueries({ queryKey: keys.saves, exact: true });
    },
  });
}
