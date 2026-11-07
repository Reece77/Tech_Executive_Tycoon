// TanStack Query hooks for M15b (formulas.md 30): rankings, Continue until, and the choices
// after an exit (serial founder). Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { keys, unwrap, useInvalidateSave } from './api';

export type Rankings = Schemas['RankingsOut'];
export type RankingList = Schemas['RankingListOut'];
export type ContinueUntil = Schemas['ContinueUntilOut'];
export type Venture = Schemas['VentureOut'];
export type FoundAgainIn = Schemas['FoundAgainIn'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useRankings(saveId: string, year?: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'rankings', year ?? null],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/rankings', {
          params: { path: { save_id: saveId }, query: year === undefined ? {} : { year } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Play months until something needs the player, up to a year (30.5). */
export function useContinueUntil(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/continue-until', path(saveId))),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.saves, exact: true });
      void invalidate();
    },
  });
}

/** Every company the player has run, oldest first (M15b addendum 10). */
export function useHistoryCompanies(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'history', 'companies'],
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/history/companies', path(saveId))),
  });
}

function useExitChoice(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return () => {
    void client.invalidateQueries({ queryKey: keys.saves, exact: true });
    void invalidate();
  };
}

export function useFoundAgain(saveId: string) {
  const done = useExitChoice(saveId);
  return useMutation({
    mutationFn: async (body: FoundAgainIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/exit/found-again', { ...path(saveId), body })),
    onSuccess: done,
  });
}

export function useRetire(saveId: string) {
  const done = useExitChoice(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/exit/retire', path(saveId))),
    onSuccess: done,
  });
}
