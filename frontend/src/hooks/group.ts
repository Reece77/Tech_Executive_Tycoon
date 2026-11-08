// TanStack Query hooks for the group (M16, formulas.md 31): the Group screen and the
// founder's actions as Chair. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Group = Schemas['GroupOut'];
export type GroupEntity = Schemas['GroupEntityOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useGroup(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'group'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/group', path(saveId))),
  });
}

/** Form the holding company (31.2): every screen's numbers move, so the whole save refetches. */
export function useFormHolding(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/saves/{save_id}/group/form', path(saveId))),
    onSuccess: () => void invalidate(),
  });
}
