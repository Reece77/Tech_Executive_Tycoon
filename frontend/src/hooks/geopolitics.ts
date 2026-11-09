// TanStack Query hooks for geopolitics (M22, formulas.md 39): the World screen and the
// founder's export-control actions. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type World = Schemas['WorldOut'];
export type Rule = Schemas['RuleOut'];
export type Licence = Schemas['LicenceOut'];
export type ProductExposure = Schemas['ProductExposureOut'];
export type SupplyExposure = Schemas['SupplyExposureOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useWorld(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'world'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/world', path(saveId))),
  });
}

export type WorldAction =
  | { kind: 'licence'; productId: number; country: string }
  | { kind: 'grey'; productId: number; country: string; on: boolean }
  | { kind: 'variant'; productId: number }
  | { kind: 'partner'; companyId: number | null }
  | { kind: 'tools'; country: string };

async function apply(saveId: string, a: WorldAction) {
  switch (a.kind) {
    case 'licence':
      return unwrap(
        await api.POST('/api/saves/{save_id}/world/licence', {
          ...path(saveId),
          body: { product_id: a.productId, country: a.country },
        }),
      );
    case 'grey':
      return unwrap(
        await api.POST('/api/saves/{save_id}/world/grey', {
          ...path(saveId),
          body: { product_id: a.productId, country: a.country, on: a.on },
        }),
      );
    case 'variant':
      return unwrap(
        await api.POST('/api/saves/{save_id}/world/variant', {
          ...path(saveId),
          body: { product_id: a.productId },
        }),
      );
    case 'tools':
      return unwrap(
        await api.POST('/api/saves/{save_id}/world/tool-licence', {
          ...path(saveId),
          body: { country: a.country },
        }),
      );
    case 'partner':
      return unwrap(
        await api.POST('/api/saves/{save_id}/world/partner', {
          ...path(saveId),
          body: { company_id: a.companyId },
        }),
      );
  }
}

/** Any export-control action: energy and the inbox move, so the whole save refetches. */
export function useWorldAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: WorldAction) => apply(saveId, a),
    onSuccess: () => void invalidate(),
  });
}
