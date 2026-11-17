// TanStack Query hooks for M37 (formulas.md 52): the campaign's length, the choice at December
// 2039 and dynasty years' eras, successions and deaths. Beside hooks/api.ts so lanes merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { keys, unwrap, useInvalidateSave } from './api';

export type Campaign = Schemas['CampaignOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useCampaign(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'campaign'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/campaign', path(saveId))),
  });
}

function useAfter(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return () => {
    void client.invalidateQueries({ queryKey: keys.saves, exact: true });
    void invalidate();
  };
}

/** Continue in dynasty mode, to December 2069 (52.1). */
export function useContinueDynasty(saveId: string) {
  const after = useAfter(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/campaign/continue', path(saveId))),
    onSuccess: after,
  });
}

/** End a standard campaign at December 2039 (52.1). */
export function useEndCampaign(saveId: string) {
  const after = useAfter(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/campaign/end', path(saveId))),
    onSuccess: after,
  });
}
