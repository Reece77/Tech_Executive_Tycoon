// TanStack Query hooks for space and satellites (M40, formulas.md 56): the Space screen and the
// founder's space actions. Kept beside hooks/api.ts so lanes' hooks merge cleanly. No game values
// are computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Space = Schemas['SpaceScreenOut'];
export type Vehicle = Schemas['VehicleOut'];
export type LaunchRow = Schemas['LaunchOut'];
export type CostPerKg = Schemas['CostPerKgOut'];
export type ConstellationRow = Schemas['ConstellationOut'];
export type BroadbandLine = Schemas['BroadbandLineOut'];
export type RegionService = Schemas['RegionServiceOut'];
export type RivalConstellation = Schemas['RivalConstellationOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useSpace(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'space'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/space', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useSetLaunchSpec(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['LaunchSpecIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/space/vehicles/{product_id}/spec', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}

export function usePlanConstellation(saveId: string) {
  return useAct(saveId, async (body: Schemas['ConstellationIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/space/constellations', { ...path(saveId), body })),
  );
}

export function useSetConstellationPlan(saveId: string) {
  return useAct(saveId, async (args: { id: number; body: Schemas['ConstellationPlanIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/space/constellations/{constellation_id}/plan', {
        params: { path: { save_id: saveId, constellation_id: args.id } },
        body: args.body,
      }),
    ),
  );
}

export function useApplyLicence(saveId: string) {
  return useAct(saveId, async (body: Schemas['SpaceLicenceIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/space/licences', { ...path(saveId), body })),
  );
}

export function useSetTerminalPrice(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['TerminalPriceIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/space/broadband/{product_id}/terminal', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}

export function useSetD2dPartner(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['D2dPartnerIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/space/broadband/{product_id}/d2d', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}
