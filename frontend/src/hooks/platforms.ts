// TanStack Query hooks for platforms (M31, formulas.md 44): the Platforms screen, the product
// screens' platform sections and the founder's platform actions. Kept beside hooks/api.ts so
// the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Platforms = Schemas['PlatformsOut'];
export type Platform = Schemas['PlatformOut'];
export type PlatformRegion = Schemas['PlatformRegionOut'];
export type DeviceLine = Schemas['DeviceLineOut'];
export type AppProduct = Schemas['AppProductOut'];
export type Standard = Schemas['StandardOut'];
export type PlatformRulesIn = Schemas['PlatformRulesIn'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function usePlatforms(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'platforms'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/platforms', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useSetDevicePlatform(saveId: string) {
  return useAct(saveId, async (body: Schemas['DevicePlatformIn']) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/platforms/device-platform', { ...path(saveId), body }),
    ),
  );
}

export function useSetPlatformRules(saveId: string) {
  return useAct(saveId, async (body: PlatformRulesIn) =>
    unwrap(await api.POST('/api/saves/{save_id}/platforms/rules', { ...path(saveId), body })),
  );
}

export function useCreateDeveloperPlatform(saveId: string) {
  return useAct(saveId, async (productId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/platforms/developer', {
        ...path(saveId),
        body: { product_id: productId },
      }),
    ),
  );
}

export function useOpenSource(saveId: string) {
  return useAct(saveId, async (body: Schemas['OpenSourceIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/platforms/open-source', { ...path(saveId), body })),
  );
}

export function useSetSteering(saveId: string) {
  return useAct(saveId, async (body: Schemas['SteeringIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/platforms/steering', { ...path(saveId), body })),
  );
}

export function useComplyListing(saveId: string) {
  return useAct(saveId, async (productId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/platforms/comply', {
        ...path(saveId),
        body: { product_id: productId },
      }),
    ),
  );
}

export function useAdoptStandard(saveId: string) {
  return useAct(saveId, async (body: Schemas['AdoptIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/platforms/adopt', { ...path(saveId), body })),
  );
}

/** A share from the API (0-1) as a percent: 0.4612 -> "46.1%". Formatting only. */
export function formatShare(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}
