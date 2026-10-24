// TanStack Query hooks over the generated client. All server state goes through here.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';

export type Overview = Schemas['OverviewOut'];
export type Save = Schemas['SaveOut'];
export type Scenario = Schemas['ScenarioOut'];
export type CreateSave = Schemas['CreateSaveIn'];
export type FounderIn = Schemas['FounderIn'];
export type FounderPreview = Schemas['FounderPreviewOut'];
export type NewGameMeta = Schemas['NewGameMetaOut'];
export type HiringMeta = Schemas['HiringMetaOut'];
export type Person = Schemas['PersonSummaryOut'];
export type Profile = Schemas['PersonProfileOut'];
export type Attribute = Schemas['AttributeOut'];
export type InboxItem = Schemas['InboxItemOut'];
export type Search = Schemas['SearchOut'];
export type OfferPreview = Schemas['OfferPreviewOut'];

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
  inbox: (saveId: string) => ['saves', saveId, 'inbox'] as const,
  people: (saveId: string) => ['saves', saveId, 'people'] as const,
  person: (saveId: string, personId: number) => ['saves', saveId, 'person', personId] as const,
  searches: (saveId: string) => ['saves', saveId, 'searches'] as const,
  candidates: (saveId: string) => ['saves', saveId, 'candidates'] as const,
  offerPreview: (saveId: string, candidateId: number, salary: number, equity: number) =>
    ['saves', saveId, 'offer-preview', candidateId, salary, equity] as const,
  scenarios: ['meta', 'scenarios'] as const,
  newGame: ['meta', 'new-game'] as const,
  hiring: ['meta', 'hiring'] as const,
  founderPreview: (body: FounderIn) => ['meta', 'founder-preview', body] as const,
};

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

// --- Meta -------------------------------------------------------------------------------------

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

export function useNewGameMeta() {
  return useQuery({
    queryKey: keys.newGame,
    queryFn: async () => unwrap(await api.GET('/api/meta/new-game')),
    staleTime: Infinity,
  });
}

export function useHiringMeta() {
  return useQuery({
    queryKey: keys.hiring,
    queryFn: async () => unwrap(await api.GET('/api/meta/hiring')),
    staleTime: Infinity,
  });
}

/** Founder build preview; pass an already-debounced body (null while the meta loads). */
export function useFounderPreview(body: FounderIn | null) {
  return useQuery({
    queryKey: keys.founderPreview(body ?? {}),
    queryFn: async () => unwrap(await api.POST('/api/meta/founder-preview', { body: body ?? {} })),
    enabled: body !== null,
    placeholderData: keepPreviousData,
  });
}

export function useCreateSave() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateSave) => unwrap(await api.POST('/api/saves', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.saves }),
  });
}

// --- Turn and overview ------------------------------------------------------------------------

export function useOverview(saveId: string) {
  return useQuery({
    queryKey: keys.overview(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/overview', path(saveId))),
  });
}

/** Every action changes energy, the inbox, or the team: refetch everything for this save. */
function useInvalidateSave(saveId: string) {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: keys.save(saveId) });
}

export function useAdvance(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/saves/{save_id}/advance', path(saveId))),
    // Not awaited: the new month shows at once and Continue is ready again while the
    // other screens refetch in the background.
    onSuccess: (overview) => {
      client.setQueryData(keys.overview(saveId), overview);
      void client.invalidateQueries({ queryKey: keys.saves, exact: true });
      void invalidate();
    },
  });
}

// --- Inbox ------------------------------------------------------------------------------------

export function useInbox(saveId: string) {
  return useQuery({
    queryKey: keys.inbox(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/inbox', path(saveId))),
  });
}

export function useSetRead(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ itemId, read }: { itemId: number; read: boolean }) => {
      const params = { params: { path: { save_id: saveId, item_id: itemId } } };
      return unwrap(
        read
          ? await api.POST('/api/saves/{save_id}/inbox/{item_id}/read', params)
          : await api.POST('/api/saves/{save_id}/inbox/{item_id}/unread', params),
      );
    },
    onSuccess: invalidate,
  });
}

// --- People -----------------------------------------------------------------------------------

export function usePeople(saveId: string) {
  return useQuery({
    queryKey: keys.people(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/people', path(saveId))),
  });
}

export function usePerson(saveId: string, personId: number) {
  return useQuery({
    queryKey: keys.person(saveId, personId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/people/{person_id}', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    enabled: Number.isSafeInteger(personId) && personId > 0,
  });
}

export function useFire(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (personId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/people/{person_id}/fire', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

// --- Recruitment ------------------------------------------------------------------------------

export function useSearches(saveId: string) {
  return useQuery({
    queryKey: keys.searches(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/recruitment/searches', path(saveId))),
  });
}

export function useCandidates(saveId: string) {
  return useQuery({
    queryKey: keys.candidates(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/recruitment/candidates', path(saveId))),
  });
}

export function useOpenSearch(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['SearchIn']) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/searches', { ...path(saveId), body }),
      ),
    onSuccess: invalidate,
  });
}

export function useCloseSearch(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (searchId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/searches/{search_id}/close', {
          params: { path: { save_id: saveId, search_id: searchId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useCheckCandidate(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({
      candidateId,
      kind,
    }: {
      candidateId: number;
      kind: 'interview' | 'refs';
    }) => {
      const params = { params: { path: { save_id: saveId, candidate_id: candidateId } } };
      return unwrap(
        kind === 'interview'
          ? await api.POST(
              '/api/saves/{save_id}/recruitment/candidates/{candidate_id}/interview',
              params,
            )
          : await api.POST(
              '/api/saves/{save_id}/recruitment/candidates/{candidate_id}/reference-check',
              params,
            ),
      );
    },
    onSuccess: invalidate,
  });
}

/** Hint, floor and rule checks for an offer; pass debounced values. */
export function useOfferPreview(
  saveId: string,
  candidateId: number,
  salaryCents: number,
  equityBp: number,
) {
  return useQuery({
    queryKey: keys.offerPreview(saveId, candidateId, salaryCents, equityBp),
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/candidates/{candidate_id}/offer-preview', {
          params: { path: { save_id: saveId, candidate_id: candidateId } },
          body: { salary_cents: salaryCents, equity_bp: equityBp },
        }),
      ),
    enabled: salaryCents > 0 && equityBp >= 0,
    placeholderData: keepPreviousData,
  });
}

export function useMakeOffer(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (offer: { candidateId: number; salaryCents: number; equityBp: number }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/candidates/{candidate_id}/offer', {
          params: { path: { save_id: saveId, candidate_id: offer.candidateId } },
          body: { salary_cents: offer.salaryCents, equity_bp: offer.equityBp },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useWithdrawOffer(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (offerId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/offers/{offer_id}/withdraw', {
          params: { path: { save_id: saveId, offer_id: offerId } },
        }),
      ),
    onSuccess: invalidate,
  });
}
