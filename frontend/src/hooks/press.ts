// TanStack Query hooks for press, promises, credibility, rival CEOs and Replace (M14b,
// formulas.md 29). Kept beside hooks/api.ts so the M14 lane's hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Press = Schemas['PressOut'];
export type PressPromise = Schemas['PromiseOut'];
export type PromiseForm = Schemas['PromiseFormOut'];
export type PromiseIn = Schemas['PromiseIn'];
export type Feud = Schemas['FeudOut'];
export type RivalLeader = Schemas['RivalLeaderOut'];
export type Replaceable = Schemas['ReplaceableOut'];

export const pressKeys = {
  press: (saveId: string) => ['saves', saveId, 'press'] as const,
  feuds: (saveId: string) => ['saves', saveId, 'feuds'] as const,
  leader: (saveId: string, rivalId: number) => ['saves', saveId, 'rival-leader', rivalId] as const,
  replaceable: (saveId: string) => ['saves', saveId, 'replaceable'] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function usePress(saveId: string) {
  return useQuery({
    queryKey: pressKeys.press(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/press', path(saveId))),
  });
}

/** A public promise in this month's answered press moment (29.2); spends energy. */
export function useMakePromise(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: PromiseIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/press/promises', { ...path(saveId), body })),
    onSuccess: (out) => {
      client.setQueryData(pressKeys.press(saveId), out.press);
      void invalidate();
    },
  });
}

export function useFeuds(saveId: string) {
  return useQuery({
    queryKey: pressKeys.feuds(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/feuds', path(saveId))),
  });
}

export function useRivalLeader(saveId: string, rivalId: number) {
  return useQuery({
    queryKey: pressKeys.leader(saveId, rivalId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/rivals/{rival_id}/leader', {
          params: { path: { save_id: saveId, rival_id: rivalId } },
        }),
      ),
    enabled: rivalId > 0,
  });
}

/** Resignations and poaches Replace can fill (29.5). */
export function useReplaceable(saveId: string) {
  return useQuery({
    queryKey: pressKeys.replaceable(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/recruitment/replaceable', path(saveId))),
  });
}

/** Replace with a recruiter: a hiring plan for the role and level, found faster (29.5). */
export function useReplace(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (personId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/replace', {
          ...path(saveId),
          body: { person_id: personId },
        }),
      ),
    onSuccess: invalidate,
  });
}
