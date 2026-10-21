// TanStack Query hooks over the generated client. All server state goes through here.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';

export type Overview = Schemas['OverviewOut'];
export type Save = Schemas['SaveOut'];
export type Scenario = Schemas['ScenarioOut'];
export type CreateSave = Schemas['CreateSaveIn'];

export class ApiError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const body = result.error as Partial<Schemas['ErrorOut']> | undefined;
  throw new ApiError(
    body?.code ?? `http_${result.response.status}`,
    body?.message ?? result.response.statusText,
  );
}

export const keys = {
  saves: ['saves'] as const,
  save: (saveId: string) => ['saves', saveId] as const,
  overview: (saveId: string) => ['saves', saveId, 'overview'] as const,
  scenarios: ['meta', 'scenarios'] as const,
};

export function useSaves() {
  return useQuery({
    queryKey: keys.saves,
    queryFn: async () => unwrap(await api.GET('/api/saves')),
  });
}

export function useScenarios() {
  return useQuery({
    queryKey: keys.scenarios,
    queryFn: async () => unwrap(await api.GET('/api/meta/scenarios')),
    staleTime: Infinity,
  });
}

export function useOverview(saveId: string) {
  return useQuery({
    queryKey: keys.overview(saveId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/overview', { params: { path: { save_id: saveId } } }),
      ),
  });
}

export function useCreateSave() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateSave) => unwrap(await api.POST('/api/saves', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.saves }),
  });
}

export function useAdvance(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/advance', { params: { path: { save_id: saveId } } }),
      ),
    onSuccess: async (overview) => {
      client.setQueryData(keys.overview(saveId), overview);
      await client.invalidateQueries({ queryKey: keys.saves });
      await client.invalidateQueries({ queryKey: keys.save(saveId) });
    },
  });
}
