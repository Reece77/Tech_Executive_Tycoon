// TanStack Query hooks for medical devices (M41, formulas.md 50): the Medical screen and the
// founder's actions on it. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Medical = Schemas['MedicalOut'];
export type MedicalDevice = Schemas['DeviceOut'];
export type MedicalRoute = Schemas['RouteOut'];
export type MedicalStudy = Schemas['StudyOut'];
export type MedicalRegion = Schemas['RegionOut'];
export type MedicalRival = Schemas['RivalProductOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useMedical(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'medical'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/medical', path(saveId))),
    enabled: saveId !== '',
  });
}

function useMedicalAction<B>(saveId: string, post: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: post, onSuccess: () => void invalidate() });
}

export function useDesignDevice(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['DesignIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/design', { ...path(saveId), body })),
  );
}

export function useSubmitDevice(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['SubmitIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/submit', { ...path(saveId), body })),
  );
}

export function useStartStudy(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['StudyIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/study', { ...path(saveId), body })),
  );
}

export function useRequestCoverage(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['CoverageIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/coverage', { ...path(saveId), body })),
  );
}

export function useMedicalSupport(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['SupportIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/support', { ...path(saveId), body })),
  );
}

export function usePlantQuality(saveId: string) {
  return useMedicalAction(saveId, async (body: Schemas['PlantQualityIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/medical/plant-quality', { ...path(saveId), body })),
  );
}
