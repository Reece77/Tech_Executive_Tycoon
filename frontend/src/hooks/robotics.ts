// TanStack Query hooks for robotics and robotaxis (M39, formulas.md 53): the Robotics and Mobility
// screens and the founder's robotics actions. Kept beside hooks/api.ts so lanes' hooks merge
// cleanly. No game values are computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Robotics = Schemas['RoboticsScreenOut'];
export type RobotRegion = Schemas['RobotRegionOut'];
export type RobotMaker = Schemas['RobotMakerOut'];
export type RobotLine = Schemas['RobotLineOut'];
export type PlantAutomation = Schemas['PlantAutomationOut'];
export type Mobility = Schemas['MobilityScreenOut'];
export type City = Schemas['RobotaxiCityOut'];
export type RivalService = Schemas['RivalServiceOut'];
export type Zone = Schemas['ZoneOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useRobotics(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'robotics'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/robotics', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useMobility(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'mobility'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/mobility', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useInstallRobots(saveId: string) {
  return useAct(saveId, async (args: { facilityId: number; body: Schemas['InstallRobotsIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/robotics/plants/{facility_id}/robots', {
        params: { path: { save_id: saveId, facility_id: args.facilityId } },
        body: args.body,
      }),
    ),
  );
}

export function useSetHumanoidSpec(saveId: string) {
  return useAct(saveId, async (args: { productId: number; body: Schemas['HumanoidSpecIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/robotics/humanoids/{product_id}/spec', {
        params: { path: { save_id: saveId, product_id: args.productId } },
        body: args.body,
      }),
    ),
  );
}

export function useOpenZone(saveId: string) {
  return useAct(saveId, async (body: Schemas['OpenZoneIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/mobility/zones', { ...path(saveId), body })),
  );
}

export function useAddRobotaxis(saveId: string) {
  return useAct(saveId, async (args: { zoneId: number; body: Schemas['AddCarsIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/mobility/zones/{zone_id}/cars', {
        params: { path: { save_id: saveId, zone_id: args.zoneId } },
        body: args.body,
      }),
    ),
  );
}

export function useSetRidePrice(saveId: string) {
  return useAct(saveId, async (args: { zoneId: number; priceCents: number }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/mobility/zones/{zone_id}/price', {
        params: { path: { save_id: saveId, zone_id: args.zoneId } },
        body: { price_cents: args.priceCents },
      }),
    ),
  );
}

export function useCloseZone(saveId: string) {
  return useAct(saveId, async (zoneId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/mobility/zones/{zone_id}/close', {
        params: { path: { save_id: saveId, zone_id: zoneId } },
      }),
    ),
  );
}

export function useBuildDepot(saveId: string) {
  return useAct(saveId, async (body: Schemas['BuildDepotIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/mobility/depots', { ...path(saveId), body })),
  );
}

/** A share as a percentage: formatting only. */
export function pct(share: number, digits = 1): string {
  return `${(share * 100).toFixed(digits)}%`;
}
