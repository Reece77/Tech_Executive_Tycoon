// TanStack Query hooks for the installed game (M58): its version, the update offered with
// its notes, the first-run import of the repository's saves, and the API key. Outside the
// installed game `/api/desktop` says `desktop: false` and nothing here shows.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { keys, unwrap } from './api';

export type Desktop = Schemas['DesktopOut'];
export type ImportOffer = Schemas['ImportOfferOut'];

const DESKTOP_KEY = ['desktop'] as const;
const BUSY_POLL_MS = 1000; // while an update check or install is under way
const BUSY = new Set(['checking', 'downloading', 'backing_up', 'installing']);
const TOKEN_HEADER = 'X-TST-Instance';

// M57r-B: the installed game's desktop writes carry the instance token that only its own
// page can read from GET /api/desktop.
function tokenHeaders(client: ReturnType<typeof useQueryClient>): Record<string, string> {
  const token = client.getQueryData<Desktop>(DESKTOP_KEY)?.write_token;
  return token ? { [TOKEN_HEADER]: token } : {};
}

export function useDesktop() {
  return useQuery({
    queryKey: DESKTOP_KEY,
    queryFn: async () => unwrap(await api.GET('/api/desktop')),
    refetchInterval: (q) =>
      q.state.data && q.state.data.desktop && BUSY.has(q.state.data.update_state ?? 'none')
        ? BUSY_POLL_MS
        : false,
  });
}

export function useStartUpdate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/desktop/update', { headers: tokenHeaders(client) })),
    onSuccess: (data) => client.setQueryData(DESKTOP_KEY, data),
  });
}

export function useUpdateLater() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/desktop/update/later', { headers: tokenHeaders(client) })),
    onSuccess: (data) => client.setQueryData(DESKTOP_KEY, data),
  });
}

export function useAnswerImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (accept: boolean) =>
      unwrap(
        await api.POST('/api/desktop/import', { body: { accept }, headers: tokenHeaders(client) }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: DESKTOP_KEY });
      void client.invalidateQueries({ queryKey: keys.saves });
    },
  });
}

export function useSetApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) =>
      unwrap(
        await api.PUT('/api/desktop/api-key', { body: { key }, headers: tokenHeaders(client) }),
      ),
    onSuccess: (data) => {
      client.setQueryData(DESKTOP_KEY, data);
      void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    },
  });
}
