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
export type Org = Schemas['OrgOut'];
export type OrgUnit = Schemas['UnitOut'];
export type OrgManager = Schemas['ManagerOut'];
export type OrgMeta = Schemas['OrgMetaOut'];
export type ChangePreview = Schemas['ChangePreviewOut'];
export type PayPreview = Schemas['PayPreviewOut'];
export type HiringPlan = Schemas['HiringPlanOut'];
export type HiringPlanIn = Schemas['HiringPlanIn'];
export type HiringPlanPatch = Schemas['HiringPlanPatchIn'];
export type MoraleBreakdown = Schemas['MoraleBreakdownOut'];

/** One reorganization, as the Org screen builds it; maps to the preview body and the action. */
export type OrgChange =
  | { change: 'create_unit'; kind: 'team' | 'department'; name: string; parent_id?: number | null }
  | { change: 'dissolve_unit'; unit_id: number }
  | { change: 'rename_unit'; unit_id: number; name: string }
  | { change: 'move_unit'; unit_id: number; parent_id: number | null }
  | { change: 'set_leader'; unit_id: number; person_id: number | null }
  | { change: 'move_person'; person_id: number; unit_id: number | null }
  | { change: 'set_policy'; unit_id: number | null; policy: 'office' | 'remote' | null };

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
  inbox: (saveId: string, offset = 0) => ['saves', saveId, 'inbox', offset] as const,
  people: (saveId: string) => ['saves', saveId, 'people'] as const,
  person: (saveId: string, personId: number) => ['saves', saveId, 'person', personId] as const,
  searches: (saveId: string) => ['saves', saveId, 'searches'] as const,
  candidates: (saveId: string) => ['saves', saveId, 'candidates'] as const,
  offerPreview: (saveId: string, candidateId: number, salary: number, equity: number) =>
    ['saves', saveId, 'offer-preview', candidateId, salary, equity] as const,
  scenarios: ['meta', 'scenarios'] as const,
  newGame: ['meta', 'new-game'] as const,
  hiring: ['meta', 'hiring'] as const,
  orgMeta: ['meta', 'org'] as const,
  org: (saveId: string) => ['saves', saveId, 'org'] as const,
  orgPreview: (saveId: string, change: OrgChange | null) =>
    ['saves', saveId, 'org-preview', change] as const,
  payPreview: (saveId: string, personId: number, kind: string, salary: number) =>
    ['saves', saveId, 'pay-preview', personId, kind, salary] as const,
  morale: (saveId: string, personId: number) => ['saves', saveId, 'morale', personId] as const,
  plans: (saveId: string) => ['saves', saveId, 'plans'] as const,
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

export const INBOX_PAGE = 50; // messages per inbox page (M2b)

export function useInbox(saveId: string, offset = 0) {
  return useQuery({
    queryKey: keys.inbox(saveId, offset),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/inbox', {
          params: { path: { save_id: saveId }, query: { limit: INBOX_PAGE, offset } },
        }),
      ),
    placeholderData: keepPreviousData,
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
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (personId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/people/{person_id}/fire', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    // Refetch everything except the fired person's own profile and morale, which no longer
    // exist (refetching them would error the profile before it navigates away).
    onSuccess: (_out, personId) =>
      client.invalidateQueries({
        queryKey: keys.save(saveId),
        predicate: (q) =>
          !(['person', 'morale'].includes(String(q.queryKey[2])) && q.queryKey[3] === personId),
      }),
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

// --- Org (M2b) --------------------------------------------------------------------------------

export function useOrgMeta() {
  return useQuery({
    queryKey: keys.orgMeta,
    queryFn: async () => unwrap(await api.GET('/api/meta/org')),
    staleTime: Infinity,
  });
}

export function useOrg(saveId: string) {
  return useQuery({
    queryKey: keys.org(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/org', path(saveId))),
  });
}

/** One-off morale changes and energy for a reorganization; nothing is saved. */
export function useOrgPreview(saveId: string, change: OrgChange | null) {
  return useQuery({
    queryKey: keys.orgPreview(saveId, change),
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/org/preview', {
          ...path(saveId),
          body: change as Schemas['OrgChangeIn'],
        }),
      ),
    enabled: change !== null,
  });
}

async function applyOrgChange(saveId: string, change: OrgChange) {
  const unit = (unitId: number) => ({ params: { path: { save_id: saveId, unit_id: unitId } } });
  switch (change.change) {
    case 'create_unit':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/units', {
          ...path(saveId),
          body: { kind: change.kind, name: change.name, parent_id: change.parent_id ?? null },
        }),
      );
    case 'dissolve_unit':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/units/{unit_id}/dissolve', unit(change.unit_id)),
      );
    case 'rename_unit':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/units/{unit_id}/rename', {
          ...unit(change.unit_id),
          body: { name: change.name },
        }),
      );
    case 'move_unit':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/units/{unit_id}/move', {
          ...unit(change.unit_id),
          body: { parent_id: change.parent_id },
        }),
      );
    case 'set_leader':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/units/{unit_id}/leader', {
          ...unit(change.unit_id),
          body: { person_id: change.person_id },
        }),
      );
    case 'move_person':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/people/{person_id}/move', {
          params: { path: { save_id: saveId, person_id: change.person_id } },
          body: { unit_id: change.unit_id },
        }),
      );
    case 'set_policy':
      return unwrap(
        await api.POST('/api/saves/{save_id}/org/policy', {
          ...path(saveId),
          body: { unit_id: change.unit_id, policy: change.policy },
        }),
      );
  }
}

export function useOrgChange(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (change: OrgChange) => applyOrgChange(saveId, change),
    onSuccess: invalidate,
  });
}

// --- Raises, promotions, morale breakdown ------------------------------------------------------

export function usePayPreview(
  saveId: string,
  personId: number,
  kind: 'raise' | 'promote',
  salaryCents: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: keys.payPreview(saveId, personId, kind, salaryCents),
    queryFn: async () => {
      const params = { params: { path: { save_id: saveId, person_id: personId } } };
      return unwrap(
        kind === 'raise'
          ? await api.POST('/api/saves/{save_id}/people/{person_id}/raise-preview', {
              ...params,
              body: { salary_cents: salaryCents },
            })
          : await api.POST('/api/saves/{save_id}/people/{person_id}/promote-preview', params),
      );
    },
    enabled: enabled && (kind === 'promote' || salaryCents > 0),
    placeholderData: keepPreviousData,
  });
}

export function useGiveRaise(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ personId, salaryCents }: { personId: number; salaryCents: number }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/people/{person_id}/raise', {
          params: { path: { save_id: saveId, person_id: personId } },
          body: { salary_cents: salaryCents },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function usePromote(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (personId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/people/{person_id}/promote', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useMoraleBreakdown(saveId: string, personId: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.morale(saveId, personId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/people/{person_id}/morale', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    enabled,
  });
}

// --- Hiring plans -----------------------------------------------------------------------------

export function usePlans(saveId: string) {
  return useQuery({
    queryKey: keys.plans(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/hiring-plans', path(saveId))),
  });
}

export function useCreatePlan(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: HiringPlanIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/hiring-plans', { ...path(saveId), body })),
    onSuccess: invalidate,
  });
}

export function useUpdatePlan(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ planId, body }: { planId: number; body: HiringPlanPatch }) =>
      unwrap(
        await api.PATCH('/api/saves/{save_id}/hiring-plans/{plan_id}', {
          params: { path: { save_id: saveId, plan_id: planId } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useClosePlan(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (planId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/hiring-plans/{plan_id}/close', {
          params: { path: { save_id: saveId, plan_id: planId } },
        }),
      ),
    onSuccess: invalidate,
  });
}
