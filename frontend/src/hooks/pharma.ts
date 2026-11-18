// TanStack Query hooks for pharmaceuticals (M42, formulas.md 55): the Pharma screen and the
// founder's actions on it. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Pharma = Schemas['PharmaOut'];
export type RxProgramme = Schemas['RxProgrammeOut'];
export type RxDrug = Schemas['RxDrugOut'];
export type RxAsset = Schemas['RxAssetOut'];
export type RxRival = Schemas['RxRivalOut'];
export type RxRange = Schemas['RxRangeOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function usePharma(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'pharma'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/pharma', path(saveId))),
    enabled: saveId !== '',
  });
}

function usePharmaAction<B>(saveId: string, post: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: post, onSuccess: () => void invalidate() });
}

export function useStartProgramme(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxStartIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/start', { ...path(saveId), body })),
  );
}

export function useStartTrial(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxTrialIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/trial', { ...path(saveId), body })),
  );
}

export function useStopProgramme(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxProgrammeIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/stop', { ...path(saveId), body })),
  );
}

export function useFileDrug(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxFileIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/file', { ...path(saveId), body })),
  );
}

export function useSetDrugPrice(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxPriceIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/price', { ...path(saveId), body })),
  );
}

export function useBuildPharmaPlant(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxPlantIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/plant', { ...path(saveId), body })),
  );
}

export function usePharmaPlantQuality(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxPlantQualityIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/plant-quality', { ...path(saveId), body })),
  );
}

export function useChooseCmo(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxCmoIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/cmo', { ...path(saveId), body })),
  );
}

export function useLicenseAsset(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxLicenseInIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/license-in', { ...path(saveId), body })),
  );
}

export function useOutLicense(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxLicenseOutIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/license-out', { ...path(saveId), body })),
  );
}

export function useLicensePlatform(saveId: string) {
  return usePharmaAction(saveId, async (body: Schemas['RxPlatformIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/pharma/platform', { ...path(saveId), body })),
  );
}

/** A range from the API as a percentage band (formatting only). */
export function formatBand(r: RxRange | null | undefined): string {
  if (!r) return '—';
  return `${Math.round(r.lo * 100)}-${Math.round(r.hi * 100)}%`;
}

/** An efficacy estimate's range, on the molecules' 0-1 score (formatting only). */
export function formatScore(r: RxRange): string {
  return `${r.lo.toFixed(2)}-${r.hi.toFixed(2)}`;
}
