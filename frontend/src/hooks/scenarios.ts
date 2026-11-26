// TanStack Query hook for the Scenarios screen (M51, formulas.md 63.3): read from the app-wide
// results file through the API, never from a save.
import { useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap } from './api';

export type Scenarios = Schemas['ScenariosOut'];
export type ScenarioCard = Schemas['ScenarioCardOut'];
export type ScenarioResult = Schemas['ScenarioResultOut'];

export function useScenarios() {
  return useQuery({
    queryKey: ['scenarios'],
    queryFn: async () => unwrap(await api.GET('/api/scenarios')),
  });
}
