// TanStack Query hooks for fabs and process nodes (M21, formulas.md 38): the Fabs screen, the
// node timeline and the founder's fab actions. Kept beside hooks/api.ts so the lanes' hooks merge
// cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Fabs = Schemas['FabsOut'];
export type Fab = Schemas['FabOut'];
export type Nodes = Schemas['NodesOut'];
export type NodeRow = Schemas['NodeOut'];
export type FabQuote = Schemas['FabQuoteOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const fabPath = (saveId: string, facilityId: number) => ({
  params: { path: { save_id: saveId, facility_id: facilityId } },
});

export function useFabs(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'fabs'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/fabs', path(saveId))),
  });
}

export function useNodes(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'nodes'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/nodes', path(saveId))),
  });
}

export function useFabQuote(
  saveId: string,
  node: string,
  region: string,
  size: number | null,
  duv: boolean,
) {
  return useQuery({
    queryKey: ['saves', saveId, 'fabs', 'quote', node, region, size, duv],
    enabled: Boolean(node && region && size),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/fabs/quote', {
          params: { path: { save_id: saveId }, query: { node, region, size: size ?? 0, duv } },
        }),
      ),
  });
}

export type FabAction =
  | { kind: 'build'; node: string; region: string; size: number; duv: boolean }
  | { kind: 'upgrade'; facilityId: number }
  | { kind: 'staff'; facilityId: number; unitId: number | null }
  | { kind: 'sell'; facilityId: number };

async function apply(saveId: string, a: FabAction) {
  switch (a.kind) {
    case 'build':
      return unwrap(
        await api.POST('/api/saves/{save_id}/fabs/build', {
          ...path(saveId),
          body: { node: a.node, region: a.region, size: a.size, duv: a.duv },
        }),
      );
    case 'upgrade':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/fabs/{facility_id}/upgrade',
          fabPath(saveId, a.facilityId),
        ),
      );
    case 'staff':
      return unwrap(
        await api.POST('/api/saves/{save_id}/fabs/{facility_id}/staff', {
          ...fabPath(saveId, a.facilityId),
          body: { unit_id: a.unitId },
        }),
      );
    case 'sell':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/fabs/{facility_id}/sell',
          fabPath(saveId, a.facilityId),
        ),
      );
  }
}

/** Any fab action: cash, energy and the inbox move, so the whole save refetches. */
export function useFabAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: FabAction) => apply(saveId, a),
    onSuccess: () => void invalidate(),
  });
}
