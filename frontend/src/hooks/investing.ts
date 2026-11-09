// TanStack Query hooks for the founder's own investments (M26, formulas.md 37): the profile's
// Investments tab, joining rounds, backing a network founder, trading listed shares and the
// family office. Kept beside hooks/founder.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Investments = Schemas['InvestmentsOut'];
export type AngelStake = Schemas['AngelStakeOut'];
export type OpenRound = Schemas['OpenRoundOut'];
export type Holding = Schemas['HoldingOut'];
export type Listed = Schemas['ListedOut'];
export type Trade = Schemas['TradeOut'];

export const investingKeys = {
  investments: (saveId: string) => ['saves', saveId, 'investments'] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useInvestments(saveId: string, enabled = true) {
  return useQuery({
    queryKey: investingKeys.investments(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/founder/investments', path(saveId))),
    enabled,
  });
}

function useInvestingAction<T>(
  saveId: string,
  post: (body: T) => Promise<Schemas['InvestmentsActionOut']>,
) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: post,
    onSuccess: (out) => {
      client.setQueryData(investingKeys.investments(saveId), out.investments);
      void invalidate();
    },
  });
}

export function useJoinRound(saveId: string) {
  return useInvestingAction(saveId, async (body: Schemas['JoinRoundIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/angel', { ...path(saveId), body })),
  );
}

export function useBackStartup(saveId: string) {
  return useInvestingAction(saveId, async (body: Schemas['BackStartupIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/back-startup', { ...path(saveId), body })),
  );
}

export function useTradeShares(saveId: string) {
  return useInvestingAction(saveId, async (body: Schemas['TradeIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/shares', { ...path(saveId), body })),
  );
}

export function useFormFamilyOffice(saveId: string) {
  return useInvestingAction(saveId, async (body: Schemas['OfficeMandateIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/founder/family-office', { ...path(saveId), body })),
  );
}

export function useMoveFamilyOffice(saveId: string) {
  return useInvestingAction(saveId, async (cents: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/founder/family-office/move', {
        ...path(saveId),
        body: { cents },
      }),
    ),
  );
}

export function useSetOfficeMandate(saveId: string) {
  return useInvestingAction(saveId, async (body: Schemas['OfficeMandateIn']) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/founder/family-office/mandate', {
        ...path(saveId),
        body,
      }),
    ),
  );
}
