// TanStack Query hooks for telecom (M53, formulas.md 62): the Telecom screen and the founder's
// telecom actions. Kept beside hooks/api.ts so lanes' hooks merge cleanly. No game values are
// computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Telecom = Schemas['TelecomScreenOut'];
export type RegionNetwork = Schemas['RegionNetworkOut'];
export type Radio = Schemas['RadioOut'];
export type Licence = Schemas['SpectrumLicenceOut'];
export type Auction = Schemas['AuctionOut'];
export type Vendor = Schemas['VendorOut'];
export type Ban = Schemas['BanOut'];
export type Payback = Schemas['NetworkPaybackOut'];
export type Operator = Schemas['OperatorOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useTelecom(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'telecom'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/telecom', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useBuildTowers(saveId: string) {
  return useAct(saveId, async (body: Schemas['TowersIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/telecom/towers', { ...path(saveId), body })),
  );
}

export function useAddRadios(saveId: string) {
  return useAct(saveId, async (body: Schemas['RadiosIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/telecom/radios', { ...path(saveId), body })),
  );
}

export function useBuildFibre(saveId: string) {
  return useAct(saveId, async (body: Schemas['FibreIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/telecom/fibre', { ...path(saveId), body })),
  );
}

export function useBuildCable(saveId: string) {
  return useAct(saveId, async (body: Schemas['CableIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/telecom/cables', { ...path(saveId), body })),
  );
}

export function useBidSpectrum(saveId: string) {
  return useAct(saveId, async (args: { auctionId: number; body: Schemas['SpectrumBidIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/telecom/auctions/{auction_id}/bid', {
        params: { path: { save_id: saveId, auction_id: args.auctionId } },
        body: args.body,
      }),
    ),
  );
}

export function useReplaceRadios(saveId: string) {
  return useAct(saveId, async (args: { facilityId: number; body: Schemas['ReplaceRadiosIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/telecom/radios/{facility_id}/replace', {
        params: { path: { save_id: saveId, facility_id: args.facilityId } },
        body: args.body,
      }),
    ),
  );
}

export function useSetTelecomLine(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['LineSettingIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/telecom/lines/{product_id}', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}
