// TanStack Query hooks for negotiations by conversation (M47, formulas.md 58). The engine decides
// every outcome; these only send the player's offer, message or picked moves. No game values are
// computed here.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Negotiation = Schemas['NegotiationOut'];
export type NegotiationRound = Schemas['NegotiationRoundOut'];
export type NegotiationList = Schemas['NegotiationListOut'];
export type MoveIn = Schemas['NegotiationMoveIn'];
export type DealParams = Record<string, string | number | boolean>;

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const key = (saveId: string, id?: number) =>
  id === undefined ? ['saves', saveId, 'negotiations'] : ['saves', saveId, 'negotiations', id];

export function useNegotiations(saveId: string) {
  return useQuery({
    queryKey: key(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/negotiations', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useNegotiation(saveId: string, id: number | null) {
  return useQuery({
    queryKey: key(saveId, id ?? -1),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/negotiations/{negotiation_id}', {
          params: { path: { save_id: saveId, negotiation_id: id ?? 0 } },
        }),
      ),
    enabled: saveId !== '' && id !== null,
  });
}

function useSet(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return (n: Negotiation) => {
    client.setQueryData(key(saveId, n.negotiation_id), n);
    void client.invalidateQueries({ queryKey: key(saveId) });
    void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    // An agreement or a walk-away changes the game: the deal's own screens re-read it.
    if (n.status !== 'open') void invalidate();
  };
}

export function useOpenNegotiation(saveId: string) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: { kind: string; params: DealParams }) =>
      unwrap(await api.POST('/api/saves/{save_id}/negotiations', { ...path(saveId), body })),
    onSuccess: set,
  });
}

export function usePlayRound(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['NegotiationRoundIn']) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/negotiations/{negotiation_id}/rounds', {
          params: { path: { save_id: saveId, negotiation_id: id } },
          body,
        }),
      ),
    onSuccess: set,
  });
}

export function useFinishNegotiation(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (how: 'accept' | 'skip') =>
      unwrap(
        how === 'accept'
          ? await api.POST('/api/saves/{save_id}/negotiations/{negotiation_id}/accept', {
              params: { path: { save_id: saveId, negotiation_id: id } },
            })
          : await api.POST('/api/saves/{save_id}/negotiations/{negotiation_id}/skip', {
              params: { path: { save_id: saveId, negotiation_id: id } },
            }),
      ),
    onSuccess: set,
  });
}
