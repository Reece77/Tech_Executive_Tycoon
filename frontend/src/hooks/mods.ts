// TanStack Query hooks for the data editor and mods (M25 section 3). Kept beside hooks/api.ts
// so the lanes' hooks merge cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap } from './api';

export type Mod = Schemas['ModOut'];
export type ModChange = Schemas['ModChangeIn'];
export type EditorFile = Schemas['EditorFileOut'];

/** `spoilers`: "Show spoiler fields" is on (PM ruling 2026-11-08): changes to fields the
 * game keeps hidden are listed too. The editor reads data files only, never a save. */
export function useMods(spoilers = false) {
  return useQuery({
    queryKey: ['mods', 'list', spoilers],
    queryFn: async () => unwrap(await api.GET('/api/mods', { params: { query: { spoilers } } })),
  });
}

export function useDataFiles() {
  return useQuery({
    queryKey: ['mods', 'files'],
    queryFn: async () => unwrap(await api.GET('/api/mods/files')),
    staleTime: Infinity,
  });
}

export function useDataFile(file: string | null, mod: string | null, spoilers = false) {
  return useQuery({
    queryKey: ['mods', 'file', file, mod ?? '', spoilers],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/mods/files/{file}', {
          params: { path: { file: file ?? '' }, query: mod ? { mod, spoilers } : { spoilers } },
        }),
      ),
    enabled: file !== null,
  });
}

export function useSaveMod() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (m: {
      name: string;
      description: string;
      changes: ModChange[];
      spoilers: boolean;
    }) =>
      unwrap(
        await api.PUT('/api/mods/{name}', {
          params: { path: { name: m.name } },
          body: { description: m.description, changes: m.changes, spoilers: m.spoilers },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['mods'] }),
  });
}

export function useDeleteMod() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const res = await api.DELETE('/api/mods/{name}', { params: { path: { name } } });
      if (!res.response.ok) unwrap(res);
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ['mods'] }),
  });
}
