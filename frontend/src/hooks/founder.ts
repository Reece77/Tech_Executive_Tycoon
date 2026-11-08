// TanStack Query hooks for the founder's life (M24, formulas.md 32): the profile's Personal,
// Foundation and Persona tabs, Government affairs, and the founder's own actions. Kept beside
// hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Founder = Schemas['FounderOut'];
export type Stress = Schemas['StressOut'];
export type Legacy = Schemas['LegacyOut'];
export type InfluenceRow = Schemas['InfluenceOut'];

export const founderKeys = {
  founder: (saveId: string) => ['saves', saveId, 'founder'] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useFounder(saveId: string, enabled = true) {
  return useQuery({
    queryKey: founderKeys.founder(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/founder', path(saveId))),
    enabled,
  });
}

function useFounderAction<T>(
  saveId: string,
  post: (body: T) => Promise<Schemas['FounderActionOut']>,
) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: post,
    onSuccess: (out) => {
      client.setQueryData(founderKeys.founder(saveId), out.founder);
      void invalidate();
    },
  });
}

export function useSellShares(saveId: string) {
  return useFounderAction(saveId, async (shares: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/founder/sell-shares', {
        ...path(saveId),
        body: { shares },
      }),
    ),
  );
}

export function useCreateFoundation(saveId: string) {
  return useFounderAction(saveId, async (body: Schemas['FoundationIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/foundation', { ...path(saveId), body })),
  );
}

export function useGive(saveId: string) {
  return useFounderAction(saveId, async (amountCents: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/founder/gifts', {
        ...path(saveId),
        body: { amount_cents: amountCents },
      }),
    ),
  );
}

export function useSetLobbying(saveId: string) {
  return useFounderAction(saveId, async (body: Schemas['LobbyingIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/lobbying', { ...path(saveId), body })),
  );
}
