// TanStack Query hooks for regulation (M34, formulas.md 48): the Regulation screen and the
// founder's actions on it. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Regulation = Schemas['RegulationOut'];
export type RegulationCase = Schemas['CaseOut'];
export type RegulationDuty = Schemas['DutyOut'];
export type RegulationDesignation = Schemas['DesignationOut'];
export type RegulationTest = Schemas['TestOut'];
export type RegulationOrder = Schemas['OrderOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useRegulation(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'regulation'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/regulation', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useComplyDuties(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/regulation/comply', path(saveId))),
    onSuccess: () => void invalidate(),
  });
}

export function useAnswerOrder(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['AnswerOrderIn']) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/regulation/orders/answer', { ...path(saveId), body }),
      ),
    onSuccess: () => void invalidate(),
  });
}
