// TanStack Query hooks for the founder's family (M36, formulas.md 45): the Family screen and
// the founder profile's Family tab. Kept beside hooks/founder.ts so the lanes' hooks merge
// cleanly. Every action answers with the family, the energy budget and the unread count.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Family = Schemas['FamilyOut'];
export type FamilyMember = Schemas['FamilyMemberOut'];
export type Estate = Schemas['EstateOut'];
export type Adviser = Schemas['AdviserOut'];
export type Dynasty = Schemas['DynastyOut'];
export type EducateIn = Schemas['EducateIn'];
export type FamilyJobIn = Schemas['FamilyJobIn'];
export type SuccessionIn = Schemas['SuccessionIn'];
export type FamilyGiftIn = Schemas['tst__api__schemas__family__GiftIn'];

export const familyKeys = {
  family: (saveId: string) => ['saves', saveId, 'family'] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useFamily(saveId: string, enabled = true) {
  return useQuery({
    queryKey: familyKeys.family(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/family', path(saveId))),
    enabled,
  });
}

/** One family action: the answer replaces the family at once, and the whole save refetches
 * (energy on the top bar, the inbox count, and after a succession, the founder). */
function useFamilyAction<T>(
  saveId: string,
  post: (body: T) => Promise<Schemas['FamilyActionOut']>,
) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: post,
    onSuccess: (out) => {
      client.setQueryData(familyKeys.family(saveId), out.family);
      void invalidate();
    },
  });
}

export function useSetFamilyTime(saveId: string) {
  return useFamilyAction(saveId, async (energy: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/family/time', { ...path(saveId), body: { energy } }),
    ),
  );
}

export function useEducate(saveId: string) {
  return useFamilyAction(saveId, async (body: EducateIn) =>
    unwrap(await api.POST('/api/saves/{save_id}/family/educate', { ...path(saveId), body })),
  );
}

export function useSetMentoring(saveId: string) {
  return useFamilyAction(saveId, async (body: Schemas['MentorIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/family/mentor', { ...path(saveId), body })),
  );
}

export function useOfferFamilyJob(saveId: string) {
  return useFamilyAction(saveId, async (body: FamilyJobIn) =>
    unwrap(await api.POST('/api/saves/{save_id}/family/job', { ...path(saveId), body })),
  );
}

export function useNameSuccessor(saveId: string) {
  return useFamilyAction(saveId, async (body: SuccessionIn) =>
    unwrap(await api.POST('/api/saves/{save_id}/family/succession', { ...path(saveId), body })),
  );
}

export function useGiftShares(saveId: string) {
  return useFamilyAction(saveId, async (body: FamilyGiftIn) =>
    unwrap(await api.POST('/api/saves/{save_id}/family/gift', { ...path(saveId), body })),
  );
}

export function useFundTrust(saveId: string) {
  return useFamilyAction(saveId, async (shares: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/family/trust', { ...path(saveId), body: { shares } }),
    ),
  );
}

export function useFoundationShares(saveId: string) {
  return useFamilyAction(saveId, async (shares: number) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/family/foundation-shares', {
        ...path(saveId),
        body: { shares },
      }),
    ),
  );
}

export function useRetireAdviser(saveId: string) {
  return useFamilyAction(saveId, async () =>
    unwrap(await api.POST('/api/saves/{save_id}/family/adviser/retire', path(saveId))),
  );
}
