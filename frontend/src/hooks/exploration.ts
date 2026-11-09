// TanStack Query hooks for exploration (M18, formulas.md 34): the Exploration screen and the
// founder's exploration actions. Kept beside hooks/api.ts so the lanes' hooks merge cleanly.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Exploration = Schemas['ExplorationOut'];
export type ExplorationProject = Schemas['ExplorationProjectOut'];
export type GeoBlock = Schemas['GeoBlockOut'];
export type GeoRegion = Schemas['GeoRegionOut'];
export type EstimateRange = Schemas['EstimateRangeOut'];
export type StageName = Schemas['StageIn']['stage'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const projectPath = (saveId: string, projectId: number) => ({
  params: { path: { save_id: saveId, project_id: projectId } },
});

export function useExploration(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'exploration'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/exploration', path(saveId))),
  });
}

export type ExplorationAction =
  | { kind: 'desk'; region: string; commodity: string }
  | { kind: 'licence'; region: string; block: number }
  | { kind: 'renew' | 'sell' | 'relinquish'; projectId: number }
  | { kind: 'stage'; projectId: number; stage: StageName; commodity?: string | null }
  | { kind: 'drill'; projectId: number; holes: number };

async function apply(saveId: string, a: ExplorationAction) {
  switch (a.kind) {
    case 'desk':
      return unwrap(
        await api.POST('/api/saves/{save_id}/exploration/desk-study', {
          ...path(saveId),
          body: { region: a.region, commodity: a.commodity },
        }),
      );
    case 'licence':
      return unwrap(
        await api.POST('/api/saves/{save_id}/exploration/licence', {
          ...path(saveId),
          body: { region: a.region, block: a.block },
        }),
      );
    case 'stage':
      return unwrap(
        await api.POST('/api/saves/{save_id}/exploration/projects/{project_id}/stage', {
          ...projectPath(saveId, a.projectId),
          body: { stage: a.stage, commodity: a.commodity ?? null },
        }),
      );
    case 'drill':
      return unwrap(
        await api.POST('/api/saves/{save_id}/exploration/projects/{project_id}/drill', {
          ...projectPath(saveId, a.projectId),
          body: { holes: a.holes },
        }),
      );
    case 'renew':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/exploration/projects/{project_id}/renew',
          projectPath(saveId, a.projectId),
        ),
      );
    case 'sell':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/exploration/projects/{project_id}/sell',
          projectPath(saveId, a.projectId),
        ),
      );
    case 'relinquish':
      return unwrap(
        await api.POST(
          '/api/saves/{save_id}/exploration/projects/{project_id}/relinquish',
          projectPath(saveId, a.projectId),
        ),
      );
  }
}

/** Any exploration action: cash, energy and the inbox move, so the whole save refetches. */
export function useExplorationAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: ExplorationAction) => apply(saveId, a),
    onSuccess: () => void invalidate(),
  });
}
