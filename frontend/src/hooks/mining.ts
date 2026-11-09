// TanStack Query hooks for mines (M19, formulas.md 35): the Mines screen and the founder's
// mining actions. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Mines = Schemas['MinesOut'];
export type Mine = Schemas['MineOut'];
export type MineQuote = Schemas['MineQuoteOut'];
export type MiningCompany = Schemas['MiningCompanyOut'];
export type RegionEvent = Schemas['RegionEventOut'];
export type RivalMiner = Schemas['RivalMinerOut'];
export type RivalBid = Schemas['RivalBidOut'];
export type MineMonth = Schemas['MineMonthOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const minePath = (saveId: string, mineId: number) => ({
  params: { path: { save_id: saveId, mine_id: mineId } },
});

export function useMines(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'mines'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/mines', path(saveId))),
  });
}

export type MiningAction =
  | { kind: 'found'; name: string; region: string; cents: number }
  | { kind: 'transfer'; to: number; projectId?: number; facilityId?: number }
  | { kind: 'build'; projectId: number; capacity?: number | null }
  | { kind: 'sales'; mineId: number; buyerId: number | null; priceKind: string; margin?: number }
  | { kind: 'staff'; mineId: number; unitId: number | null }
  | { kind: 'safety'; mineId: number; safety: string }
  | {
      kind: 'deal';
      mineId: number;
      dealKind: string;
      volume: number;
      months?: number;
      years?: number;
    }
  | { kind: 'care'; mineId: number; restart: boolean }
  | { kind: 'close'; mineId: number }
  | { kind: 'bid'; bidId: number; accept: boolean };

async function apply(saveId: string, a: MiningAction) {
  switch (a.kind) {
    case 'found':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/subsidiaries', {
          ...path(saveId),
          body: { name: a.name, region: a.region, cents: a.cents },
        }),
      );
    case 'transfer':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/transfer', {
          ...path(saveId),
          body: {
            to_company_id: a.to,
            project_id: a.projectId ?? null,
            facility_id: a.facilityId ?? null,
          },
        }),
      );
    case 'build':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/build', {
          ...path(saveId),
          body: { project_id: a.projectId, capacity_t: a.capacity ?? null },
        }),
      );
    case 'sales':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/sales', {
          ...minePath(saveId, a.mineId),
          body: { buyer_id: a.buyerId, price_kind: a.priceKind, margin: a.margin ?? null },
        }),
      );
    case 'staff':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/staff', {
          ...minePath(saveId, a.mineId),
          body: { unit_id: a.unitId },
        }),
      );
    case 'safety':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/safety', {
          ...minePath(saveId, a.mineId),
          body: { safety: a.safety },
        }),
      );
    case 'deal':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/deals', {
          ...minePath(saveId, a.mineId),
          body: {
            deal_kind: a.dealKind,
            volume_t_year: a.volume,
            months: a.months ?? null,
            years: a.years ?? null,
          },
        }),
      );
    case 'care':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/care', {
          ...minePath(saveId, a.mineId),
          body: { restart: a.restart },
        }),
      );
    case 'close':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/{mine_id}/close', minePath(saveId, a.mineId)),
      );
    case 'bid':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mines/bids/{bid_id}', {
          params: { path: { save_id: saveId, bid_id: a.bidId } },
          body: { accept: a.accept },
        }),
      );
  }
}

/** Any mining action: cash, energy and the inbox move, so the whole save refetches. */
export function useMiningAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: MiningAction) => apply(saveId, a),
    onSuccess: () => void invalidate(),
  });
}
