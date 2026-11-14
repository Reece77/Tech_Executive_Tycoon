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
export type HeadcountTargetIn = Schemas['HeadcountTargetIn'];

export const automationKeys = {
  automation: (saveId: string, companyId: number | null = null) =>
    ['saves', saveId, 'automation', companyId] as const,
  plan: (saveId: string, companyId: number | null = null) =>
    ['saves', saveId, 'automation', 'plan', companyId] as const,
  digest: (saveId: string, turn: number | null) =>
    ['saves', saveId, 'automation', 'digest', turn] as const,
  record: (saveId: string, personId: number) =>
    ['saves', saveId, 'automation', 'record', personId] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

/** The Automation screen for the player's company, or (M27b) one of its subsidiaries. */
export function useAutomation(saveId: string, companyId: number | null = null) {
  return useQuery({
    queryKey: automationKeys.automation(saveId, companyId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/automation', {
          params: {
            path: { save_id: saveId },
            query: companyId === null ? {} : { company_id: companyId },
          },
        }),
      ),
    enabled: saveId !== '',
  });
}

/** Automate everything's plan, fetched only when the player opens the confirmation. */
export function useAutomatePlan(saveId: string, enabled: boolean, companyId: number | null = null) {
  return useQuery({
    queryKey: automationKeys.plan(saveId, companyId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/automation/plan', {
          params: {
            path: { save_id: saveId },
            query: companyId === null ? {} : { company_id: companyId },
          },
        }),
      ),
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

export function useTakeBackArea(saveId: string, companyId: number | null = null) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (area: string) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/automation/take-back', {
          ...path(saveId),
          body: { area, company_id: companyId },
        }),
      ),
    onSuccess: () => void invalidate(),
  });
}

/** M27b: a unit's headcount target in a role, which Hiring fills (0 removes it). */
export function useHeadcountTarget(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: HeadcountTargetIn) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/automation/headcount', { ...path(saveId), body }),
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
