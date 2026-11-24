// TanStack Query hooks for board meetings, earnings calls and investor days (M48, formulas.md
// 59). The engine decides every effect; these only send the player's answer or picked moves.
// No game values are computed here.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Meeting = Schemas['MeetingOut'];
export type MeetingList = Schemas['MeetingListOut'];
export type MeetingAnswer = Schemas['MeetingAnswerOut'];
export type MeetingMoveIn = Schemas['MeetingMoveIn'];
export type MeetingParams = Record<string, string | number | boolean>;

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });
const key = (saveId: string, id?: number) =>
  id === undefined ? ['saves', saveId, 'meetings'] : ['saves', saveId, 'meetings', id];

export function useMeetings(saveId: string) {
  return useQuery({
    queryKey: key(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/meetings', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useMeeting(saveId: string, id: number | null) {
  return useQuery({
    queryKey: key(saveId, id ?? -1),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/meetings/{meeting_id}', {
          params: { path: { save_id: saveId, meeting_id: id ?? 0 } },
        }),
      ),
    enabled: saveId !== '' && id !== null,
  });
}

function useSet(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return (m: Meeting) => {
    client.setQueryData(key(saveId, m.meeting_id), m);
    void client.invalidateQueries({ queryKey: key(saveId) });
    void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    // A finished meeting changes the game (confidence, sentiment, promises): screens re-read.
    if (m.status !== 'open') void invalidate();
  };
}

export function useOpenMeeting(saveId: string) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: { kind: string; params?: MeetingParams }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/meetings', {
          ...path(saveId),
          body: { kind: body.kind, params: body.params ?? {} },
        }),
      ),
    onSuccess: set,
  });
}

export function useAnswerMeeting(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['MeetingAnswerIn']) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/meetings/{meeting_id}/answers', {
          params: { path: { save_id: saveId, meeting_id: id } },
          body,
        }),
      ),
    onSuccess: set,
  });
}

export function useSkipMeeting(saveId: string, id: number) {
  const set = useSet(saveId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/meetings/{meeting_id}/skip', {
          params: { path: { save_id: saveId, meeting_id: id } },
        }),
      ),
    onSuccess: set,
  });
}
