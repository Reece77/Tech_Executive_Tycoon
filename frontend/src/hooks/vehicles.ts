// TanStack Query hooks for electric vehicles (M38, formulas.md 49): the Vehicles screen, a car
// line's page and the founder's vehicle actions. Kept beside hooks/api.ts so lanes' hooks merge
// cleanly. No game values are computed here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Vehicles = Schemas['VehiclesScreenOut'];
export type VehicleRegion = Schemas['VehicleRegionOut'];
export type RivalCar = Schemas['RivalCarOut'];
export type MyCar = Schemas['MyCarOut'];
export type CellPlant = Schemas['CellPlantOut'];
export type Charging = Schemas['ChargingOut'];
export type VehiclePlant = Schemas['VehiclePlantOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useVehicles(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'vehicles'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/vehicles', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useVehicleCar(saveId: string, productId: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'vehicles', 'car', productId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/vehicles/cars/{product_id}', {
          params: { path: { save_id: saveId, product_id: productId } },
        }),
      ),
    enabled: saveId !== '' && productId > 0,
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useSetVehicleSpec(saveId: string, productId: number) {
  return useAct(saveId, async (body: Schemas['SetVehicleSpecIn']) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/vehicles/cars/{product_id}/spec', {
        params: { path: { save_id: saveId, product_id: productId } },
        body,
      }),
    ),
  );
}

export function useBuildCellPlant(saveId: string) {
  return useAct(saveId, async (body: Schemas['BuildCellPlantIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/vehicles/cell-plants', { ...path(saveId), body })),
  );
}

export function useBuildCharging(saveId: string) {
  return useAct(saveId, async (body: Schemas['BuildChargingIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/vehicles/charging', { ...path(saveId), body })),
  );
}

export function useSetChargingAccess(saveId: string) {
  return useAct(saveId, async (args: { facilityId: number; exclusive: boolean }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/vehicles/charging/{facility_id}/access', {
        params: { path: { save_id: saveId, facility_id: args.facilityId } },
        body: { exclusive: args.exclusive },
      }),
    ),
  );
}

/** A share as a percentage: formatting only. */
export function pct(share: number, digits = 1): string {
  return `${(share * 100).toFixed(digits)}%`;
}
