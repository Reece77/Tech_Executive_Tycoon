// TanStack Query hooks for media (M55, formulas.md 65): one view for the Studio, Streaming, Games
// and Social screens, and the founder's media actions. Kept beside hooks/api.ts so lanes' hooks
// merge cleanly. No game values are computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Media = Schemas['MediaScreenOut'];
export type Title = Schemas['TitleOut'];
export type Lead = Schemas['LeadOut'];
export type LeadOffer = Schemas['LeadOfferOut'];
export type Service = Schemas['MediaServiceOut'];
export type ServiceMonth = Schemas['ServiceMonthOut'];
export type GameTitle = Schemas['GameTitleOut'];
export type Network = Schemas['SocialNetworkOut'];
export type AdMarket = Schemas['AdMarketOut'];
export type RegionCustomers = Schemas['RegionCustomersOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const titlePath = (saveId: string, titleId: number) => ({
  params: { path: { save_id: saveId, title_id: titleId } },
});

export function useMedia(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'media'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/media', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useGreenlight(saveId: string) {
  return useAct(saveId, async (body: Schemas['GreenlightIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/media/titles', { ...path(saveId), body })),
  );
}

export function useCancelTitle(saveId: string) {
  return useAct(saveId, async (titleId: number) =>
    unwrap(
      await api.POST(
        '/api/saves/{save_id}/media/titles/{title_id}/cancel',
        titlePath(saveId, titleId),
      ),
    ),
  );
}

export function useOverrule(saveId: string) {
  return useAct(saveId, async (titleId: number) =>
    unwrap(
      await api.POST(
        '/api/saves/{save_id}/media/titles/{title_id}/overrule',
        titlePath(saveId, titleId),
      ),
    ),
  );
}

export function useCutBudget(saveId: string) {
  return useAct(saveId, async (args: { titleId: number; budget_cents: number }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/media/titles/{title_id}/budget', {
        ...titlePath(saveId, args.titleId),
        body: { budget_cents: args.budget_cents },
      }),
    ),
  );
}

export function useMoveRelease(saveId: string) {
  return useAct(saveId, async (args: { titleId: number; months: number }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/media/titles/{title_id}/move', {
        ...titlePath(saveId, args.titleId),
        body: { months: args.months },
      }),
    ),
  );
}

export function useLiveService(saveId: string) {
  return useAct(saveId, async (args: { titleId: number; on: boolean }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/media/titles/{title_id}/live-service', {
        ...titlePath(saveId, args.titleId),
        body: { on: args.on },
      }),
    ),
  );
}

export function useSignLead(saveId: string) {
  return useAct(saveId, async (body: Schemas['SignIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/media/leads', { ...path(saveId), body })),
  );
}

export function useLicense(saveId: string) {
  return useAct(saveId, async (body: Schemas['MediaLicenceIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/media/licences', { ...path(saveId), body })),
  );
}

export function useSetMediaLine(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['MediaLineIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/media/lines/{product_id}', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}

export function useDivest(saveId: string) {
  return useAct(saveId, async (lawId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/media/laws/{law_id}/divest', {
        params: { path: { save_id: saveId, law_id: lawId } },
      }),
    ),
  );
}
