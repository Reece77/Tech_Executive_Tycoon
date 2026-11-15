// TanStack Query hooks for semiconductor equipment (M33, formulas.md 47): the Equipment screen
// and the founder's tool orders, prepayments and lithography programme. Kept beside hooks/api.ts
// so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Equipment = Schemas['EquipmentOut'];
export type ToolGeneration = Schemas['ToolGenerationOut'];
export type ToolOrder = Schemas['ToolOrderOut'];
export type LithoStage = Schemas['LithoStageOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useEquipment(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'equipment'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/equipment', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useOrderTools(saveId: string) {
  return useAct(saveId, async (body: Schemas['OrderToolsIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/equipment/orders', { ...path(saveId), body })),
  );
}

export function usePrepay(saveId: string) {
  return useAct(saveId, async (orderId: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/equipment/prepay', {
        ...path(saveId),
        body: { order_id: orderId },
      }),
    ),
  );
}

export function useStartLitho(saveId: string) {
  return useAct(saveId, async (body: Schemas['LithoStartIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/equipment/litho/start', { ...path(saveId), body })),
  );
}

export function useStopLitho(saveId: string) {
  return useAct(saveId, async (stage: string) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/equipment/litho/stop', {
        ...path(saveId),
        body: { stage },
      }),
    ),
  );
}
