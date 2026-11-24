// TanStack Query hooks for press interviews, crisis press conferences and one-to-ones (M49,
// formulas.md 61). The engine decides every effect; these only send the player's answer or
// picked moves. No game values are computed here.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Talk = Schemas['TalkOut'];
export type TalkList = Schemas['TalkListOut'];
export type TalkAvailable = Schemas['TalkAvailableOut'];
export type TalkPerson = Schemas['TalkPersonOut'];
export type TalkPromise = Schemas['TalkPromiseOut'];
export type TalkParams = Record<string, string | number | boolean>;

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
export const talkKeys = {
  all: (saveId: string) => ['saves', saveId, 'talks'] as const,
  list: (saveId: string, personId?: number) =>
    personId === undefined
      ? (['saves', saveId, 'talks', 'list'] as const)
      : (['saves', saveId, 'talks', 'list', personId] as const),
  one: (saveId: string, id: number) => ['saves', saveId, 'talks', 'one', id] as const,
};

/** This month's interviews and conferences, past talks, people and promised promotions; with
 * `personId`, one person's. */
export function useTalks(saveId: string, personId?: number) {
  return useQuery({
    queryKey: talkKeys.list(saveId, personId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/talks', {
          params: {
            path: { save_id: saveId },
            query: personId === undefined ? {} : { person_id: personId },
          },
        }),
      ),
    enabled: saveId !== '',
  });
}

export function useTalk(saveId: string, id: number | null) {
  return useQuery({
    queryKey: talkKeys.one(saveId, id ?? -1),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/talks/{talk_id}', {
          params: { path: { save_id: saveId, talk_id: id ?? 0 } },
        }),
      ),
    enabled: saveId !== '' && id !== null,
  });
}

function useSet(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return (t: Talk) => {
    client.setQueryData(talkKeys.one(saveId, t.talk_id), t);
    void client.invalidateQueries({ queryKey: talkKeys.all(saveId) });
    void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    // A finished talk changes the game (brand, credibility, morale, a press event answered,
    // a promise made): the person, people, inbox and overview re-read.
    if (t.status !== 'open') void invalidate();
  };
}

export function useOpenTalk(saveId: string) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: { kind: string; params?: TalkParams }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/talks', {
          ...path(saveId),
          body: { kind: body.kind, params: body.params ?? {} },
        }),
      ),
    onSuccess: set,
  });
}

export function useAnswerTalk(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['TalkAnswerIn']) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/talks/{talk_id}/answers', {
          params: { path: { save_id: saveId, talk_id: id } },
          body,
        }),
      ),
    onSuccess: set,
  });
}

export function useSkipTalk(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/talks/{talk_id}/skip', {
          params: { path: { save_id: saveId, talk_id: id } },
        }),
      ),
    onSuccess: set,
  });
}
