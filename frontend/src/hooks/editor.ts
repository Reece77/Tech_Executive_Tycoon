// TanStack Query hooks for the scenario editor and custom scenarios (M52, formulas.md 66.1-66.2).
// The files live in saves/scenarios; the editor never reads or writes a save, except to start
// one from a custom scenario. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { keys, unwrap, useInvalidateSave } from './api';

export type CustomSpec = Schemas['CustomScenario'];
export type EditorOptions = Schemas['EditorOut'];
export type CustomCard = Schemas['CustomCardOut'];
export type CheckResult = Schemas['CustomCheckOut'];
export type PreviewSummary = Schemas['PreviewOut'];
export type Difficulty = Schemas['DifficultyOut'];

const custom = ['custom-scenarios'] as const;

export function useEditorOptions() {
  return useQuery({
    queryKey: ['editor', 'options'],
    queryFn: async () => unwrap(await api.GET('/api/editor')),
    staleTime: Infinity,
  });
}

export function useCustomScenarios() {
  return useQuery({
    queryKey: custom,
    queryFn: async () => unwrap(await api.GET('/api/scenarios/custom')),
  });
}

/** A start to edit: blank_<year>, a scenarios.yaml key, or (custom) a saved custom scenario. */
export async function openStart(start: string, saved: boolean): Promise<CustomSpec> {
  if (saved) {
    return unwrap(
      await api.GET('/api/scenarios/custom/{slug}', { params: { path: { slug: start } } }),
    ) as CustomSpec;
  }
  return unwrap(
    await api.GET('/api/editor/open/{start}', { params: { path: { start } } }),
  ) as CustomSpec;
}

export function useCheck(spec: CustomSpec | null) {
  return useQuery({
    queryKey: ['editor', 'check', JSON.stringify(spec)],
    queryFn: async () => {
      if (spec === null) throw new Error('nothing to check');
      return unwrap(await api.POST('/api/editor/check', { body: spec }));
    },
    enabled: spec !== null,
    placeholderData: (previous) => previous,
  });
}

export function useSaveCustom() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (m: { spec: CustomSpec; existing: boolean }) =>
      unwrap(
        m.existing
          ? await api.PUT('/api/scenarios/custom/{slug}', {
              params: { path: { slug: m.spec.key } },
              body: m.spec,
            })
          : await api.POST('/api/scenarios/custom', { body: m.spec }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: custom }),
  });
}

export function useDeleteCustom() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (slug: string) =>
      unwrap(await api.DELETE('/api/scenarios/custom/{slug}', { params: { path: { slug } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: custom }),
  });
}

export function useImportCustom() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas['CustomImportIn']) =>
      unwrap(await api.POST('/api/scenarios/custom-import', { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: custom }),
  });
}

export async function exportCustom(slug: string): Promise<Schemas['ExportOut']> {
  return unwrap(
    await api.GET('/api/scenarios/custom/{slug}/export', { params: { path: { slug } } }),
  );
}

export function usePreview() {
  return useMutation({
    mutationFn: async (spec: CustomSpec) =>
      unwrap(await api.POST('/api/editor/preview', { body: spec })),
  });
}

export function useStartDifficulty() {
  return useMutation({
    mutationFn: async (spec: CustomSpec) =>
      unwrap(await api.POST('/api/editor/difficulty', { body: spec })),
  });
}

/** Polls a running estimate every few seconds until it is done or failed. */
export function useDifficulty(jobId: string | null) {
  return useQuery({
    queryKey: ['editor', 'difficulty', jobId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/editor/difficulty/{job_id}', {
          params: { path: { job_id: jobId ?? '' } },
        }),
      ),
    enabled: jobId !== null,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 3000 : false),
  });
}

/** Start a game from a saved custom scenario (66.2). */
export function useStartCustomGame() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (m: { slug: string; name: string; company: string; seed: number | null }) =>
      unwrap(
        await api.POST('/api/saves', {
          body: {
            name: m.name,
            company_name: m.company,
            scenario: 'garage_bootstrap',
            seed: m.seed,
            custom: m.slug,
          },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.saves }),
  });
}

/** M52 (66.3): after December 2069, continue in sandbox with no end. */
export function useContinueSandbox(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/campaign/sandbox', {
          params: { path: { save_id: saveId } },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.saves, exact: true });
      void invalidate();
    },
  });
}
