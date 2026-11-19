// TanStack Query hooks for defence and government contracts (M44, formulas.md 57): the Government
// screen and the founder's government actions. Kept beside hooks/api.ts so lanes' hooks merge
// cleanly. No game values are computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Government = Schemas['GovernmentScreenOut'];
export type Tender = Schemas['TenderOut'];
export type GovContract = Schemas['GovContractOut'];
export type GovClearance = Schemas['ClearanceOut'];
export type RivalAward = Schemas['RivalAwardOut'];
export type Buyer = Schemas['GovBuyerOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useGovernment(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'government'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/government', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function usePlaceBid(saveId: string) {
  return useAct(saveId, async (args: { tenderId: number; body: Schemas['TenderBidIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/government/tenders/{tender_id}/bid', {
        params: { path: { save_id: saveId, tender_id: args.tenderId } },
        body: args.body,
      }),
    ),
  );
}

export function useWithdrawBid(saveId: string) {
  return useAct(saveId, async (tenderId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/government/tenders/{tender_id}/withdraw', {
        params: { path: { save_id: saveId, tender_id: tenderId } },
      }),
    ),
  );
}

export function useProtestAward(saveId: string) {
  return useAct(saveId, async (tenderId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/government/tenders/{tender_id}/protest', {
        params: { path: { save_id: saveId, tender_id: tenderId } },
      }),
    ),
  );
}

export function useRequestClearances(saveId: string) {
  return useAct(saveId, async (body: Schemas['ClearanceIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/government/clearances', { ...path(saveId), body })),
  );
}

export function useSponsorFacility(saveId: string) {
  return useAct(saveId, async (facilityId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/government/facilities/{facility_id}/clearance', {
        params: { path: { save_id: saveId, facility_id: facilityId } },
      }),
    ),
  );
}
