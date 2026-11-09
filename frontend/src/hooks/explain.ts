// TanStack Query hooks for Explain and Ask why (M25). Kept beside hooks/api.ts so the lanes'
// hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap } from './api';

export type Explain = Schemas['ExplainOut'];
export type ExplainAnswer = Schemas['ExplainAnswerOut'];

export function useExplain(
  saveId: string,
  metric: string,
  entity: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['saves', saveId, 'explain', metric, entity ?? ''],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/explain/{metric}', {
          params: {
            path: { save_id: saveId, metric },
            query: entity === null ? {} : { entity },
          },
        }),
      ),
    enabled: enabled && saveId !== '',
  });
}

export function useAskExplain(saveId: string, metric: string, entity: string | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (question: string) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/explain/{metric}/ask', {
          params: { path: { save_id: saveId, metric } },
          body: { question, entity },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    },
  });
}
