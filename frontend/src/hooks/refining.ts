// TanStack Query hooks for refining (M20, formulas.md 36): the Refineries screen and the
// founder's refinery actions. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Refineries = Schemas['RefineriesOut'];
export type Plant = Schemas['RefineryPlantOut'];
export type Recipe = Schemas['RecipeOut'];
export type RefineryQuote = Schemas['RefineryQuoteOut'];
export type ChainLink = Schemas['ChainLinkOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const plantPath = (saveId: string, facilityId: number) => ({
  params: { path: { save_id: saveId, facility_id: facilityId } },
});

export function useRefineries(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'refineries'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/refineries', path(saveId))),
  });
}

export function useRefineryQuote(
  saveId: string,
  recipe: string,
  region: string,
  capacity: number | null,
) {
  return useQuery({
    queryKey: ['saves', saveId, 'refineries', 'quote', recipe, region, capacity],
    enabled: Boolean(recipe && region && capacity),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/refineries/quote', {
          params: {
            path: { save_id: saveId },
            query: { recipe, region, size: capacity ?? 0 },
          },
        }),
      ),
  });
}

export type RefiningAction =
  | { kind: 'build'; recipe: string; region: string; capacity: number; hostId?: number | null }
  | { kind: 'deal'; side: 'buy' | 'sell'; good: string; months: number; volume: number }
  | { kind: 'staff'; facilityId: number; unitId: number | null }
  | { kind: 'sell'; facilityId: number };

async function apply(saveId: string, a: RefiningAction) {
  switch (a.kind) {
    case 'build':
      return unwrap(
        await api.POST('/api/saves/{save_id}/refineries/build', {
          ...path(saveId),
          body: {
            recipe: a.recipe,
            region: a.region,
            size: a.capacity,
            host_id: a.hostId ?? null,
          },
        }),
      );
    case 'deal':
      return unwrap(
        await api.POST('/api/saves/{save_id}/refineries/deal', {
          ...path(saveId),
          body: { side: a.side, good: a.good, months: a.months, volume: a.volume },
        }),
      );
    case 'staff':
      return unwrap(
        await api.POST('/api/saves/{save_id}/refineries/{facility_id}/staff', {
          ...plantPath(saveId, a.facilityId),
          body: { unit_id: a.unitId },
        }),
      );
    case 'sell':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/refineries/{facility_id}/sell',
          plantPath(saveId, a.facilityId),
        ),
      );
  }
}

/** Any refining action: cash, energy and the inbox move, so the whole save refetches. */
export function useRefiningAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: RefiningAction) => apply(saveId, a),
    onSuccess: () => void invalidate(),
  });
}
