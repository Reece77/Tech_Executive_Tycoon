// TanStack Query hooks for power (M32, formulas.md 46): the Power screen, plant pages, the
// siting panel on build screens, quotes, and the founder's power actions. Kept beside
// hooks/api.ts so the lanes' hooks merge cleanly. No game values are computed here.
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Power = Schemas['PowerScreenOut'];
export type PowerRegion = Schemas['PowerRegionOut'];
export type PowerPlant = Schemas['PowerPlantOut'];
export type Ppa = Schemas['PpaOut'];
export type PlantType = Schemas['PlantTypeOut'];
export type Siting = Schemas['SitingOut'];
export type PlantQuote = Schemas['PlantQuoteOut'];
export type PpaQuote = Schemas['PpaQuoteOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const FIRST_YEAR = 2010;

/** A turn as its month (turn 0 = January 2010): formatting only. */
export function turnLabel(turn: number): string {
  return `${MONTHS[turn % 12]} ${FIRST_YEAR + Math.floor(turn / 12)}`;
}

export function formatMwh(mwh: number): string {
  if (mwh >= 1e6) return `${(mwh / 1e6).toFixed(2)} TWh`;
  if (mwh >= 1e3) return `${(mwh / 1e3).toFixed(1)} GWh`;
  return `${mwh.toFixed(0)} MWh`;
}

export function usePower(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'power'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/power', path(saveId))),
    enabled: saveId !== '',
  });
}

export function usePowerPlant(saveId: string, facilityId: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'power', 'plant', facilityId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/power/plants/{facility_id}', {
          params: { path: { save_id: saveId, facility_id: facilityId } },
        }),
      ),
    enabled: saveId !== '' && facilityId > 0,
  });
}

export function useSiting(saveId: string, kind: string, size: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'power', 'siting', kind, size],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/power/siting', {
          params: { path: { save_id: saveId }, query: { kind, capacity: size } },
        }),
      ),
    enabled: saveId !== '' && kind !== '' && size > 0,
    placeholderData: keepPreviousData,
  });
}

export function usePlantQuote(
  saveId: string,
  plantType: string,
  mw: number,
  region: string,
  siteId: number | null,
) {
  return useQuery({
    queryKey: ['saves', saveId, 'power', 'quote', plantType, mw, region, siteId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/power/quote/plant', {
          params: {
            path: { save_id: saveId },
            query: { plant_type: plantType, mw, region, site_id: siteId ?? undefined },
          },
        }),
      ),
    enabled: saveId !== '' && plantType !== '' && mw > 0 && region !== '',
    placeholderData: keepPreviousData,
  });
}

export function usePpaQuote(
  saveId: string,
  region: string,
  producer: string,
  mwhMonth: number,
  years: number,
) {
  return useQuery({
    queryKey: ['saves', saveId, 'power', 'ppa-quote', region, producer, mwhMonth, years],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/power/quote/ppa', {
          params: {
            path: { save_id: saveId },
            query: { region, producer, mwh_month: mwhMonth, years },
          },
        }),
      ),
    enabled: saveId !== '' && region !== '' && producer !== '' && mwhMonth > 0,
    placeholderData: keepPreviousData,
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useBuildPowerPlant(saveId: string) {
  return useAct(saveId, async (body: Schemas['BuildPlantIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/power/plants', { ...path(saveId), body })),
  );
}

export function useSignPpa(saveId: string) {
  return useAct(saveId, async (body: Schemas['SignPpaIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/power/ppas', { ...path(saveId), body })),
  );
}

export function useTerminatePpa(saveId: string) {
  return useAct(saveId, async (ppaId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/contracts/terminate', {
        ...path(saveId),
        body: { contract: 'ppa', contract_id: ppaId },
      }),
    ),
  );
}
