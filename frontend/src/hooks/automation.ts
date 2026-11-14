// TanStack Query hooks for automation everywhere (M27a, formulas.md 40): the Automation screen,
// giving and taking back areas, their settings, Automate everything, the digest and records.
// Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Automation = Schemas['AutomationOut'];
export type Area = Schemas['AreaOut'];
export type AreaCandidate = Schemas['CandidateOut'];
export type AutomatePlan = Schemas['AutomatePlanOut'];
export type Digest = Schemas['DigestOut'];
export type OwnerRecord = Schemas['RecordOut'];
export type AreaOwnerIn = Schemas['AreaOwnerIn'];
export type AreaSettingsIn = Schemas['AreaSettingsIn'];

export const automationKeys = {
  automation: (saveId: string) => ['saves', saveId, 'automation'] as const,
  plan: (saveId: string) => ['saves', saveId, 'automation', 'plan'] as const,
  digest: (saveId: string, turn: number | null) =>
    ['saves', saveId, 'automation', 'digest', turn] as const,
  record: (saveId: string, personId: number) =>
    ['saves', saveId, 'automation', 'record', personId] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useAutomation(saveId: string) {
  return useQuery({
    queryKey: automationKeys.automation(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/automation', path(saveId))),
    enabled: saveId !== '',
  });
}

/** Automate everything's plan, fetched only when the player opens the confirmation. */
export function useAutomatePlan(saveId: string, enabled: boolean) {
  return useQuery({
    queryKey: automationKeys.plan(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/automation/plan', path(saveId))),
    enabled,
  });
}

export function useDigest(saveId: string, turn: number | null = null) {
  return useQuery({
    queryKey: automationKeys.digest(saveId, turn),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/automation/digest', {
          params: { path: { save_id: saveId }, query: turn === null ? {} : { turn } },
        }),
      ),
    enabled: saveId !== '',
  });
}

export function useOwnerRecord(saveId: string, personId: number | null) {
  return useQuery({
    queryKey: automationKeys.record(saveId, personId ?? 0),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/automation/record/{person_id}', {
          params: { path: { save_id: saveId, person_id: personId ?? 0 } },
        }),
      ),
    enabled: personId !== null,
  });
}

export function useSetAreaOwner(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: AreaOwnerIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/automation/owner', { ...path(saveId), body })),
    onSuccess: () => void invalidate(),
  });
}

export function useTakeBackArea(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (area: string) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/automation/take-back', {
          ...path(saveId),
          body: { area },
        }),
      ),
    onSuccess: () => void invalidate(),
  });
}

export function useAreaSettings(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: AreaSettingsIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/automation/settings', { ...path(saveId), body })),
    onSuccess: () => void invalidate(),
  });
}

export function useAutomateEverything(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (assignments: AreaOwnerIn[]) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/automation/all', {
          ...path(saveId),
          body: { assignments },
        }),
      ),
    onSuccess: () => void invalidate(),
  });
}
