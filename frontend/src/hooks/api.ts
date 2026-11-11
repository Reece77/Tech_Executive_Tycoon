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
export type Learned = Schemas['LearnedOut'];
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
export type Product = Schemas['ProductOut'];
export type ProductSegment = Schemas['ProductSegmentOut'];
export type Category = Schemas['CategoryOut'];
export type Market = Schemas['MarketOut'];
export type MarketSegment = Schemas['MarketSegmentOut'];
export type MarketProduct = Schemas['MarketProductOut'];
export type Portfolio = Schemas['PortfolioOut'];
export type PricePreview = Schemas['PricePreviewOut'];
export type ProductsMeta = Schemas['ProductsMetaOut'];
export type Statements = Schemas['StatementsOut'];
export type StatementPeriod = Schemas['StatementPeriodOut'];
export type CapTable = Schemas['CapTableOut'];
export type Holder = Schemas['HolderOut'];
export type Grant = Schemas['GrantOut'];
export type OwnershipEvent = Schemas['OwnershipEventOut'];
export type Rounds = Schemas['RoundsOut'];
export type Round = Schemas['RoundOut'];
export type TermSheet = Schemas['TermSheetOut'];
export type Safes = Schemas['SafesOut'];
export type Safe = Schemas['SafeOut'];
export type SafeHint = Schemas['SafeHintOut'];
export type RoundPreview = Schemas['RoundPreviewOut'];
export type DilutionLine = Schemas['DilutionLineOut'];
export type Board = Schemas['BoardOut'];
export type Director = Schemas['DirectorOut'];
export type FinanceSummary = Schemas['FinanceSummaryOut'];
export type Macro = Schemas['MacroOut']; // M10
export type Loans = Schemas['LoansOut'];
export type Loan = Schemas['LoanOut'];
export type LoanTerms = Schemas['LoanTermsOut'];
export type Payment = Schemas['PaymentOut'];
export type GameOver = Schemas['GameOverOut'];
export type Holiday = Schemas['HolidayOut'];
export type Backup = Schemas['BackupOut'];
export type HistoryRow = Schemas['HistoryRowOut'];
export type Breakdown = Schemas['BreakdownOut'];
export type TableViews = Schemas['TableViews'];
export type Coo = Schemas['CooOut'];
export type CooAnswer = Schemas['CooAnswerOut'];
export type TableView = Schemas['TableView'];
export type UiSettings = Schemas['UISettings'];
export type OverviewBreakdowns = Schemas['OverviewBreakdownsOut'];
export type Timeline = Schemas['TimelineOut'];
export type HistoryCharts = Schemas['ChartsOut'];
export type KpiPoint = Schemas['KpiPointOut'];
export type HallOfFame = Schemas['HallOfFameOut'];
export type StorylineHistory = Schemas['StorylineHistoryOut'];
export type HolidayIn = Schemas['HolidayIn'];
export type StatementPeriodKind = 'month' | 'quarter' | 'year';
export type Scaleup = Schemas['ScaleupOut'];
export type Division = Schemas['DivisionOut'];
export type Seat = Schemas['SeatOut'];
export type SupportPool = Schemas['SupportPoolOut'];
export type SeatCandidates = Schemas['SeatCandidatesOut'];
export type DivisionStatements = Schemas['DivisionStatementsOut'];
export type DivisionColumn = Schemas['DivisionColumnOut'];
export type Geo = Schemas['GeoOut'];
export type Research = Schemas['ResearchOut'];
export type ResearchProject = Schemas['ProjectOut'];
export type Era = Schemas['EraOut'];
export type RivalLead = Schemas['RivalLeadOut'];
export type ResearchDomain = Schemas['DomainOut'];
export type ResearchLicense = Schemas['LicenseOut'];
export type Office = Schemas['OfficeOut'];
export type City = Schemas['CityOut'];
export type LeasePreview = Schemas['LeasePreviewOut'];
export type ProductRegions = Schemas['ProductRegionsOut'];
export type ProductRegion = Schemas['ProductRegionOut'];
export type Infrastructure = Schemas['InfrastructureOut']; // M12a
export type Facility = Schemas['FacilityOut'];
export type Hardware = Schemas['HardwareOut']; // M12b
export type Commodities = Schemas['CommoditiesOut']; // M17
export type CommodityCostLine = Schemas['CommodityCostLineOut'];
export type Manufacturing = Schemas['ManufacturingOut'];
export type Plant = Schemas['PlantOut'];
export type HardwareChip = Schemas['ChipOut'];
export type ProductionContract = Schemas['ProductionContractOut'];
export type BuildPreview = Schemas['BuildPreviewOut'];
export type SupplyContract = Schemas['ContractOut'];
export type PublicCompany = Schemas['PublicOut']; // M13
export type Ipo = Schemas['IpoOut'];
export type PriceOption = Schemas['PriceOptionOut'];
export type Stock = Schemas['StockOut'];
export type GuidanceRow = Schemas['GuidanceRowOut'];
export type Ceo = Schemas['CeoOut'];
export type CeoDecision = Schemas['CeoDecisionOut'];

/** One scale-up action (M8): shared services, a product's division, a seat. */
export type ScaleupAction =
  | { action: 'services'; unit_id: number; services: 'central' | 'embedded' }
  | { action: 'product_division'; product_id: number; division_id: number | null }
  | { action: 'appoint'; seat: string; person_id: number; salary_cents?: number }
  | { action: 'remove'; seat: string }
  | { action: 'proposal'; proposal_id: number; approve: boolean } // M10c (24.1)
  | { action: 'pitch'; pitch_id: number; answer: 'approve' | 'decline' | 'modified' } // M13b
  | { action: 'pitch_policy'; auto_approve_cents: number | null; stop_for_big: boolean }
  | {
      action: 'authority';
      seat: string;
      enabled: boolean;
      guardrails?: Record<string, number | number[] | string[]>;
    }; // M10c (24.1)

/** One product action, as the product screens build it; maps to its route. */
export type ProductAction =
  | { action: 'price'; segment: string; price_cents: number }
  | { action: 'segment'; segment: string }
  | { action: 'assign'; unit_id: number | null }
  | { action: 'unassign'; unit_id: number | null }
  | { action: 'marketing'; budget_cents: number }
  | { action: 'launch' }
  | { action: 'sunset' }
  | { action: 'cancel' };

/** One reorganization, as the Org screen builds it; maps to the preview body and the action. */
export type OrgChange =
  | {
      change: 'create_unit';
      kind: 'team' | 'department' | 'division';
      name: string;
      parent_id?: number | null;
    }
  | { change: 'dissolve_unit'; unit_id: number }
  | { change: 'rename_unit'; unit_id: number; name: string }
  | { change: 'move_unit'; unit_id: number; parent_id: number | null }
  | { change: 'set_leader'; unit_id: number; person_id: number | null }
  | { change: 'move_person'; person_id: number; unit_id: number | null }
  | { change: 'set_policy'; unit_id: number | null; policy: 'office' | 'remote' | null };

export class ApiError extends Error {
  readonly code: string;
  /** The API's word that nothing was written, so the same request may be sent again (M8r). */
  readonly retryable: boolean;
  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

/** Mutations retry a refused write while another write to the same save finishes. Only an
 * answer the API marks `retryable` (refused before anything committed) is sent again, so a
 * Continue never plays a second month (M8r, Codex review 1 finding 2). M8: state loads grew
 * with the new rivals, and an inbox mark-read could still hold the save when an event choice
 * arrived. */
export function retryBusy(failures: number, error: unknown): boolean {
  return error instanceof ApiError && error.code === 'save_busy' && error.retryable && failures < 5;
}
export const BUSY_RETRY_MS = 250;

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const body = result.error as Partial<Schemas['ErrorOut']> | undefined;
  throw new ApiError(
    body?.code ?? `http_${result.response.status}`,
    body?.message ?? result.response.statusText,
    body?.retryable === true,
  );
}

export const keys = {
  saves: ['saves'] as const,
  save: (saveId: string) => ['saves', saveId] as const,
  overview: (saveId: string) => ['saves', saveId, 'overview'] as const,
  inbox: (saveId: string, offset = 0, kinds: readonly string[] | null = null) =>
    ['saves', saveId, 'inbox', offset, kinds] as const,
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
  productsMeta: ['meta', 'products'] as const,
  categories: (saveId: string) => ['saves', saveId, 'categories'] as const,
  market: (saveId: string, category: string, region: string | null = null) =>
    ['saves', saveId, 'market', category, region] as const,
  geo: (saveId: string) => ['saves', saveId, 'geo'] as const,
  infrastructure: (saveId: string) => ['saves', saveId, 'infrastructure'] as const,
  hardware: (saveId: string) => ['saves', saveId, 'hardware'] as const,
  commodities: (saveId: string) => ['saves', saveId, 'commodities'] as const, // M17
  manufacturing: (saveId: string, productId: number) =>
    ['saves', saveId, 'manufacturing', productId] as const,
  public: (saveId: string) => ['saves', saveId, 'public'] as const, // M13
  buildPreview: (
    saveId: string,
    kind: string,
    region: string,
    units: number,
    contract: number | null,
  ) => ['saves', saveId, 'build-preview', kind, region, units, contract] as const,
  research: (saveId: string) => ['saves', saveId, 'research'] as const, // M11
  mna: (saveId: string) => ['saves', saveId, 'mna'] as const, // M14
  eras: (saveId: string) => ['saves', saveId, 'eras'] as const,
  leasePreview: (saveId: string, city: string, seats: number) =>
    ['saves', saveId, 'lease-preview', city, seats] as const,
  productRegions: (saveId: string, productId: number) =>
    ['saves', saveId, 'product-regions', productId] as const,
  products: (saveId: string) => ['saves', saveId, 'products'] as const,
  product: (saveId: string, productId: number) => ['saves', saveId, 'product', productId] as const,
  portfolio: (saveId: string) => ['saves', saveId, 'portfolio'] as const,
  pricePreview: (saveId: string, productId: number, segment: string, price: number) =>
    ['saves', saveId, 'price-preview', productId, segment, price] as const,
  statements: (saveId: string, period: StatementPeriodKind, companyId?: number) =>
    ['saves', saveId, 'statements', period, companyId ?? null] as const,
  financeSummary: (saveId: string) => ['saves', saveId, 'finance-summary'] as const,
  capTable: (saveId: string, companyId?: number) =>
    ['saves', saveId, 'captable', companyId ?? null] as const,
  board: (saveId: string, companyId?: number) =>
    ['saves', saveId, 'board', companyId ?? null] as const,
  safes: (saveId: string) => ['saves', saveId, 'safes'] as const,
  safeHint: (saveId: string, amount: number, cap: number) =>
    ['saves', saveId, 'safe-hint', amount, cap] as const,
  rounds: (saveId: string) => ['saves', saveId, 'rounds'] as const,
  loans: (saveId: string) => ['saves', saveId, 'loans'] as const, // M10
  loanPreview: (saveId: string, instrument: string, amount: number) =>
    ['saves', saveId, 'loan-preview', instrument, amount] as const,
  macro: (saveId: string) => ['saves', saveId, 'macro'] as const,
  sheetPreview: (saveId: string, sheetId: number) =>
    ['saves', saveId, 'sheet-preview', sheetId] as const,
  gameOver: (saveId: string) => ['saves', saveId, 'game-over'] as const,
  scaleup: (saveId: string) => ['saves', saveId, 'scaleup'] as const,
  seatCandidates: (saveId: string, seat: string) =>
    ['saves', saveId, 'seat-candidates', seat] as const,
  divisionStatements: (saveId: string, period: StatementPeriodKind) =>
    ['saves', saveId, 'division-statements', period] as const,
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

// --- Saves manager (M7b) -------------------------------------------------------------------

export function useRenameSave() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ saveId, name }: { saveId: string; name: string }) =>
      unwrap(await api.POST('/api/saves/{save_id}/rename', { ...path(saveId), body: { name } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.saves }),
  });
}

export function useDuplicateSave() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ saveId, name }: { saveId: string; name: string }) =>
      unwrap(await api.POST('/api/saves/{save_id}/duplicate', { ...path(saveId), body: { name } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.saves, exact: true }),
  });
}

export function useDeleteSave() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (saveId: string) => {
      const res = await api.DELETE('/api/saves/{save_id}', path(saveId));
      if (!res.response.ok) unwrap(res);
    },
    onSuccess: (_data, saveId) => {
      client.removeQueries({ queryKey: keys.save(saveId) });
      void client.invalidateQueries({ queryKey: keys.saves, exact: true });
    },
  });
}

export function useBackups(saveId: string | null) {
  return useQuery({
    queryKey: ['backups', saveId],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/backups', path(saveId ?? ''))),
    enabled: saveId !== null,
  });
}

export function useRestoreBackup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ saveId, backupId }: { saveId: string; backupId: string }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/backups/{backup_id}/restore', {
          params: { path: { save_id: saveId, backup_id: backupId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.saves, exact: true }),
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
export function useInvalidateSave(saveId: string) {
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

/** One inbox page; `kinds` keeps only those message kinds across every page (M3b). */
export function useInbox(
  saveId: string,
  offset = 0,
  kinds: readonly string[] | null = null,
  unreadOnly = false,
  archived = false,
) {
  return useQuery({
    queryKey: [...keys.inbox(saveId, offset, kinds), unreadOnly, archived],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/inbox', {
          params: {
            path: { save_id: saveId },
            query: {
              limit: INBOX_PAGE,
              offset,
              unread_only: unreadOnly,
              archived,
              ...(kinds ? { kind: [...kinds] } : {}),
            },
          },
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

/** Archive or bring back one message (M4c). UI state only: no energy, no game effect. */
export function useArchive(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ itemId, archived }: { itemId: number; archived: boolean }) => {
      const params = { params: { path: { save_id: saveId, item_id: itemId } } };
      return unwrap(
        archived
          ? await api.POST('/api/saves/{save_id}/inbox/{item_id}/archive', params)
          : await api.POST('/api/saves/{save_id}/inbox/{item_id}/unarchive', params),
      );
    },
    onSuccess: invalidate,
  });
}

/** Star a message so it is never auto-archived, or unstar it (23.1, M10b). UI state only. */
export function useBookmark(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ itemId, bookmarked }: { itemId: number; bookmarked: boolean }) => {
      const params = { params: { path: { save_id: saveId, item_id: itemId } } };
      return unwrap(
        bookmarked
          ? await api.POST('/api/saves/{save_id}/inbox/{item_id}/bookmark', params)
          : await api.POST('/api/saves/{save_id}/inbox/{item_id}/unbookmark', params),
      );
    },
    onSuccess: invalidate,
  });
}

/** Mark every message read, or archive every read message (M4c). */
export function useInboxBulk(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (op: 'read-all' | 'archive-read') => {
      const params = { params: { path: { save_id: saveId } } };
      return unwrap(
        op === 'read-all'
          ? await api.POST('/api/saves/{save_id}/inbox/read-all', params)
          : await api.POST('/api/saves/{save_id}/inbox/archive-read', params),
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

/** Someone who has left (M7c), as the player knew them; `enabled` once the staff route 404s. */
export function useFormerPerson(saveId: string, personId: number, enabled: boolean) {
  return useQuery({
    queryKey: [...keys.person(saveId, personId), 'former'] as const,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/people/{person_id}/former', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    enabled: enabled && Number.isSafeInteger(personId) && personId > 0,
    retry: false,
  });
}
export type FormerProfile = Schemas['FormerProfileOut'];

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

/** The founder scouts every open candidate of a search (20 energy, M3). */
export function useScoutSearch(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (searchId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/recruitment/searches/{search_id}/scout', {
          params: { path: { save_id: saveId, search_id: searchId } },
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

/** The structure guide: what units, managers, divisions, support and seats do, with live
 * numbers (23.4, M10b). */
export function useOrgGuide(saveId: string) {
  return useQuery({
    queryKey: [...keys.org(saveId), 'guide'] as const,
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/org/guide', path(saveId))),
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

// --- Products and markets (M3b) ---------------------------------------------------------------

export function useProductsMeta() {
  return useQuery({
    queryKey: keys.productsMeta,
    queryFn: async () => unwrap(await api.GET('/api/meta/products')),
    staleTime: Infinity,
  });
}

export function useCategories(saveId: string) {
  return useQuery({
    queryKey: keys.categories(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/categories', path(saveId))),
  });
}

export function useMarket(saveId: string, category: string, region: string | null = null) {
  return useQuery({
    queryKey: keys.market(saveId, category, region),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/markets/{category}', {
          params: { path: { save_id: saveId, category }, query: region ? { region } : {} },
        }),
      ),
    enabled: category !== '',
    placeholderData: keepPreviousData,
  });
}

export function useProducts(saveId: string) {
  return useQuery({
    queryKey: keys.products(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/products', path(saveId))),
  });
}

export function useProduct(saveId: string, productId: number) {
  return useQuery({
    queryKey: keys.product(saveId, productId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/products/{product_id}', {
          params: { path: { save_id: saveId, product_id: productId } },
        }),
      ),
    enabled: Number.isSafeInteger(productId) && productId > 0,
  });
}

export function usePortfolio(saveId: string) {
  return useQuery({
    queryKey: keys.portfolio(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/portfolio', path(saveId))),
  });
}

/** Price score, appeal and share* before and after; pass a debounced price. */
export function usePricePreview(
  saveId: string,
  productId: number,
  segment: string,
  priceCents: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: keys.pricePreview(saveId, productId, segment, priceCents),
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/price-preview', {
          params: { path: { save_id: saveId, product_id: productId } },
          body: { segment, price_cents: priceCents },
        }),
      ),
    enabled: enabled && priceCents > 0,
    placeholderData: keepPreviousData,
  });
}

export function useCreateProduct(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['CreateProductIn']) =>
      unwrap(await api.POST('/api/saves/{save_id}/products', { ...path(saveId), body })),
    onSuccess: invalidate,
  });
}

async function applyProductAction(saveId: string, productId: number, a: ProductAction) {
  const p = { params: { path: { save_id: saveId, product_id: productId } } };
  switch (a.action) {
    case 'price':
      return unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/price', {
          ...p,
          body: { segment: a.segment, price_cents: a.price_cents },
        }),
      );
    case 'segment':
      return unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/segments', {
          ...p,
          body: { segment: a.segment },
        }),
      );
    case 'assign':
      return unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/assign', {
          ...p,
          body: { unit_id: a.unit_id },
        }),
      );
    case 'unassign':
      return unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/unassign', {
          ...p,
          body: { unit_id: a.unit_id },
        }),
      );
    case 'marketing':
      return unwrap(
        await api.POST('/api/saves/{save_id}/products/{product_id}/marketing', {
          ...p,
          body: { budget_cents: a.budget_cents },
        }),
      );
    case 'launch':
      return unwrap(await api.POST('/api/saves/{save_id}/products/{product_id}/launch', p));
    case 'sunset':
      return unwrap(await api.POST('/api/saves/{save_id}/products/{product_id}/sunset', p));
    case 'cancel':
      return unwrap(await api.POST('/api/saves/{save_id}/products/{product_id}/cancel', p));
  }
}

export function useProductAction(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, action }: { productId: number; action: ProductAction }) =>
      applyProductAction(saveId, productId, action),
    // A cancelled product no longer exists: do not refetch its own page.
    onSuccess: (_out, { productId, action }) =>
      client.invalidateQueries({
        queryKey: keys.save(saveId),
        predicate: (q) =>
          !(
            action.action === 'cancel' &&
            q.queryKey[2] === 'product' &&
            q.queryKey[3] === productId
          ),
      }),
  });
}

// --- Finance (M4b) ----------------------------------------------------------------------------

/** `companyId` (M16 company switcher): one company of the group; default the listed one. */
export function useStatements(saveId: string, period: StatementPeriodKind, companyId?: number) {
  return useQuery({
    queryKey: keys.statements(saveId, period, companyId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/finance/statements', {
          params: {
            path: { save_id: saveId },
            query: companyId === undefined ? { period } : { period, company_id: companyId },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useFinanceSummary(saveId: string) {
  return useQuery({
    queryKey: keys.financeSummary(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/finance/summary', path(saveId))),
  });
}

const scoped = (saveId: string, companyId?: number) => ({
  params: {
    path: { save_id: saveId },
    query: companyId === undefined ? {} : { company_id: companyId },
  },
});

export function useCapTable(saveId: string, companyId?: number) {
  return useQuery({
    queryKey: keys.capTable(saveId, companyId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/finance/captable', scoped(saveId, companyId))),
  });
}

export function useBoard(saveId: string, companyId?: number) {
  return useQuery({
    queryKey: keys.board(saveId, companyId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/finance/board', scoped(saveId, companyId))),
  });
}

export function useSafes(saveId: string) {
  return useQuery({
    queryKey: keys.safes(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/finance/safes', path(saveId))),
  });
}

/** The SAFE dialog's hint band and rule checks; pass debounced values. */
export function useSafeHint(saveId: string, amountCents: number, capCents: number) {
  return useQuery({
    queryKey: keys.safeHint(saveId, amountCents, capCents),
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/safes/hint', {
          ...path(saveId),
          body: { amount_cents: amountCents, cap_cents: capCents },
        }),
      ),
    enabled: amountCents > 0 && capCents > 0,
    placeholderData: keepPreviousData,
  });
}

export function useRaiseSafe(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['SafeIn']) =>
      unwrap(await api.POST('/api/saves/{save_id}/finance/safes', { ...path(saveId), body })),
    onSuccess: invalidate,
  });
}

export function useAcceptBridge(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (safeId: number) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/bridges/{safe_id}/accept', {
          params: { path: { save_id: saveId, safe_id: safeId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useNameNominee(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ seatId, personId }: { seatId: number; personId: number }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/board/seats/{seat_id}/nominee', {
          params: { path: { save_id: saveId, seat_id: seatId } },
          body: { person_id: personId },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useRounds(saveId: string) {
  return useQuery({
    queryKey: keys.rounds(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/finance/rounds', path(saveId))),
  });
}

export function useStartRound(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['RoundIn']) =>
      unwrap(await api.POST('/api/saves/{save_id}/finance/rounds', { ...path(saveId), body })),
    onSuccess: invalidate,
  });
}

/** Every holder before and after accepting a term sheet; nothing is saved. */
export function useTermSheetPreview(saveId: string, sheetId: number | null) {
  return useQuery({
    queryKey: keys.sheetPreview(saveId, sheetId ?? 0),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/finance/term-sheets/{sheet_id}/preview', {
          params: { path: { save_id: saveId, sheet_id: sheetId ?? 0 } },
        }),
      ),
    enabled: sheetId !== null,
  });
}

export function useAcceptTermSheet(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ sheetId, nomineeId }: { sheetId: number; nomineeId: number | null }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/term-sheets/{sheet_id}/accept', {
          params: { path: { save_id: saveId, sheet_id: sheetId } },
          body: { nominee_id: nomineeId },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useGameOver(saveId: string, enabled = true) {
  return useQuery({
    queryKey: keys.gameOver(saveId),
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/finance/game-over', path(saveId))),
    enabled,
  });
}

// --- Rivals (M5) ----------------------------------------------------------------------------------

export type Rivals = Schemas['RivalsOut'];
export type RivalRow = Schemas['RivalRowOut'];
export type RivalProfile = Schemas['RivalProfileOut'];
export type RivalMove = Schemas['RivalMoveOut'];
export type News = Schemas['NewsOut'];
export type Approach = Schemas['ApproachOut'];
export type RivalView = 'all' | 'markets' | 'startups';

export function useRivals(saveId: string, view: RivalView) {
  return useQuery({
    queryKey: ['saves', saveId, 'rivals', view],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/rivals', {
          params: { path: { save_id: saveId }, query: { view } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useRival(saveId: string, companyId: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'rival', companyId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/rivals/{company_id}', {
          params: { path: { save_id: saveId, company_id: companyId } },
        }),
      ),
    enabled: companyId > 0,
  });
}

export function useNews(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'news'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/news', path(saveId))),
  });
}

export function useApproaches(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'approaches'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/approaches', path(saveId))),
  });
}

/** The approach band now and after a raise to `salaryCents` (nothing is saved). */
export function useCounterPreview(saveId: string, approachId: number | null, salaryCents: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'counter', approachId, salaryCents],
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/approaches/{approach_id}/counter-preview', {
          params: { path: { save_id: saveId, approach_id: approachId ?? 0 } },
          body: { salary_cents: salaryCents },
        }),
      ),
    enabled: approachId !== null && salaryCents > 0,
    placeholderData: keepPreviousData,
  });
}

// --- Events, storylines, relationships and AI writing (M6) -----------------------------------

export type GameEventOut = Schemas['EventOut'];
export type Events = Schemas['EventsOut'];
export type Storyline = Schemas['StorylineOut'];
export type Relationship = Schemas['RelationshipOut'];
export type TeamMood = Schemas['TeamMoodOut'];
export type LlmSettings = Schemas['LLMSettingsOut'];
export type LlmSettingsIn = Schemas['LLMSettingsIn'];

/** This month's events to answer, recent answers, and the month's AI spend. */
export function useEvents(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'events'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/events', path(saveId))),
    enabled: saveId !== '',
  });
}

export function useEvent(saveId: string, eventId: number | null) {
  return useQuery({
    queryKey: ['saves', saveId, 'event', eventId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/events/{event_id}', {
          params: { path: { save_id: saveId, event_id: eventId ?? 0 } },
        }),
      ),
    enabled: eventId !== null && eventId > 0,
  });
}

/** Answer an event: its effects apply at once (energy 0). */
export function useChooseEvent(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ eventId, choice }: { eventId: number; choice: string }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/events/{event_id}/choose', {
          params: { path: { save_id: saveId, event_id: eventId } },
          body: { choice },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useStorylines(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'storylines'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/storylines', path(saveId))),
  });
}

export function useRelationships(saveId: string, personId: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'relationships', personId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/people/{person_id}/relationships', {
          params: { path: { save_id: saveId, person_id: personId } },
        }),
      ),
    enabled: personId > 0,
  });
}

export function useTeamMood(saveId: string, unitId: number | null) {
  return useQuery({
    queryKey: ['saves', saveId, 'team-mood', unitId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/org/team-mood', {
          params: { path: { save_id: saveId }, query: unitId === null ? {} : { unit_id: unitId } },
        }),
      ),
  });
}

export function useLlmSettings() {
  return useQuery({
    queryKey: ['settings', 'llm'],
    queryFn: async () => unwrap(await api.GET('/api/settings/llm')),
  });
}

export function useUpdateLlmSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: LlmSettingsIn) => unwrap(await api.PUT('/api/settings/llm', { body })),
    onSuccess: (data) => client.setQueryData(['settings', 'llm'], data),
  });
}

// --- Holiday (M7b, formulas.md 17.1) ------------------------------------------------------

const HOLIDAY_POLL_MS = 400; // how often a running holiday is checked

/** The save's holiday job; polled while it runs. When it ends, every screen refetches. */
export function useHoliday(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useQuery({
    queryKey: ['holiday', saveId],
    queryFn: async () => {
      const before = client.getQueryData<Holiday>(['holiday', saveId]);
      const next = unwrap(await api.GET('/api/saves/{save_id}/holiday', path(saveId)));
      if (before?.status === 'running' && next.status !== 'running') {
        void client.invalidateQueries({ queryKey: keys.saves, exact: true });
        void invalidate();
      } else if (next.status === 'running' && before?.months_done !== next.months_done) {
        void invalidate(); // each finished month shows in the top bar
      }
      return next;
    },
    enabled: saveId !== '',
    refetchInterval: (query) => (query.state.data?.status === 'running' ? HOLIDAY_POLL_MS : false),
  });
}

export function useStartHoliday(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: HolidayIn) =>
      unwrap(await api.POST('/api/saves/{save_id}/holiday', { ...path(saveId), body })),
    onSuccess: (data) => client.setQueryData(['holiday', saveId], data),
  });
}

export function useStopHoliday(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/saves/{save_id}/holiday/stop', path(saveId))),
    onSuccess: (data) => client.setQueryData(['holiday', saveId], data),
  });
}

// --- History (M7b, formulas.md 17.2) --------------------------------------------------------

export interface TimelineQuery {
  search?: string;
  year?: number;
  category?: 'people' | 'products' | 'finance' | 'rivals' | 'events';
  source?: 'player' | 'delegate' | 'default';
  person_id?: number;
  product_id?: number;
  offset?: number;
  limit?: number;
  company_id?: number; // M15b addendum 10: a company the player sold
}

export function useTimeline(saveId: string, query: TimelineQuery) {
  return useQuery({
    queryKey: ['saves', saveId, 'history', 'timeline', query],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/history/timeline', {
          params: { path: { save_id: saveId }, query },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** A company the player ran (M15b addendum 10); undefined: the current one. */
const companyQuery = (saveId: string, companyId?: number) => ({
  params: {
    path: { save_id: saveId },
    query: companyId === undefined ? {} : { company_id: companyId },
  },
});

export function useHistoryCharts(saveId: string, companyId?: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'history', 'charts', companyId ?? null],
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/history/charts', companyQuery(saveId, companyId))),
  });
}

export function useHistoryStorylines(saveId: string, companyId?: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'history', 'storylines', companyId ?? null],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/history/storylines', companyQuery(saveId, companyId)),
      ),
  });
}

export function useHallOfFame(saveId: string, companyId?: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'history', 'hall-of-fame', companyId ?? null],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/history/hall-of-fame', companyQuery(saveId, companyId)),
      ),
  });
}

// --- Tooltips (M7b) -----------------------------------------------------------------------

/** Definitions of every KPI and column header; loaded once. */
export function useGlossary() {
  return useQuery({
    queryKey: ['meta', 'glossary'],
    queryFn: async () => unwrap(await api.GET('/api/meta/glossary')).terms,
    staleTime: Infinity,
  });
}

/** The top bar's and Overview's driver breakdowns; fetched when a tooltip first opens. */
export function useOverviewBreakdowns(saveId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['saves', saveId, 'overview-breakdowns'],
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/overview/breakdowns', path(saveId))),
    enabled: enabled && saveId !== '',
  });
}

// --- Saved column views (M7b) -------------------------------------------------------------

export function useUiSettings() {
  return useQuery({
    queryKey: ['settings', 'ui'],
    queryFn: async () => unwrap(await api.GET('/api/settings/ui')),
    staleTime: Infinity,
  });
}

export function useSaveTableViews() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ tableId, views }: { tableId: string; views: TableViews }) =>
      unwrap(
        await api.PUT('/api/settings/ui/tables/{table_id}', {
          params: { path: { table_id: tableId } },
          body: views,
        }),
      ),
    // Shown at once; the server's copy replaces it when it answers.
    onMutate: ({ tableId, views }) => {
      const before = client.getQueryData<UiSettings>(['settings', 'ui']);
      client.setQueryData<UiSettings>(['settings', 'ui'], {
        tables: { ...(before?.tables ?? {}), [tableId]: views },
      });
    },
    onSuccess: (data) => client.setQueryData(['settings', 'ui'], data),
  });
}

// --- Ask my COO (M7b, formulas.md 17.3) ---------------------------------------------------

export function useCoo(saveId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['saves', saveId, 'coo'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/coo', path(saveId))),
    enabled: enabled && saveId !== '',
  });
}

export function useAskCoo(saveId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (question: string) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/coo/ask', { ...path(saveId), body: { question } }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['saves', saveId, 'coo'] });
      void client.invalidateQueries({ queryKey: ['settings', 'llm'] });
    },
  });
}

// --- Divisions and executives (M8) ------------------------------------------------------------

export function useScaleup(saveId: string) {
  return useQuery({
    queryKey: keys.scaleup(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/scaleup', path(saveId))),
  });
}

export function useSeatCandidates(saveId: string, seat: string | null) {
  return useQuery({
    queryKey: keys.seatCandidates(saveId, seat ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/scaleup/seats/{seat}/candidates', {
          params: { path: { save_id: saveId, seat: seat ?? '' } },
        }),
      ),
    enabled: seat !== null,
  });
}

async function applyScaleup(saveId: string, a: ScaleupAction) {
  switch (a.action) {
    case 'services':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/divisions/{unit_id}/services', {
          params: { path: { save_id: saveId, unit_id: a.unit_id } },
          body: { services: a.services },
        }),
      );
    case 'product_division':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/products/{product_id}/division', {
          params: { path: { save_id: saveId, product_id: a.product_id } },
          body: { division_id: a.division_id },
        }),
      );
    case 'appoint':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/seats/{seat}/appoint', {
          params: { path: { save_id: saveId, seat: a.seat } },
          body: { person_id: a.person_id, salary_cents: a.salary_cents ?? null },
        }),
      );
    case 'remove':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/seats/{seat}/remove', {
          params: { path: { save_id: saveId, seat: a.seat } },
        }),
      );
    case 'proposal':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/proposals/{proposal_id}/{answer}', {
          params: {
            path: {
              save_id: saveId,
              proposal_id: a.proposal_id,
              answer: a.approve ? 'approve' : 'decline',
            },
          },
        }),
      );
    case 'authority':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/seats/{seat}/authority', {
          params: { path: { save_id: saveId, seat: a.seat } },
          body: { enabled: a.enabled, guardrails: a.guardrails ?? {} },
        }),
      );
    case 'pitch': // M13b (27.1)
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/pitches/{pitch_id}/{answer}', {
          params: { path: { save_id: saveId, pitch_id: a.pitch_id, answer: a.answer } },
        }),
      );
    case 'pitch_policy':
      return unwrap(
        await api.POST('/api/saves/{save_id}/scaleup/pitch-policy', {
          params: { path: { save_id: saveId } },
          body: { auto_approve_cents: a.auto_approve_cents, stop_for_big: a.stop_for_big },
        }),
      );
  }
}

export function useScaleupAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: ScaleupAction) => applyScaleup(saveId, a),
    onSuccess: invalidate,
  });
}

export function useDivisionStatements(saveId: string, period: StatementPeriodKind) {
  return useQuery({
    queryKey: keys.divisionStatements(saveId, period),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/finance/divisions', {
          params: { path: { save_id: saveId }, query: { period } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

// --- Deep links (M7c) ---------------------------------------------------------------------------

/** One inbox message by id, wherever it falls in the pages (M7c). */
export function useInboxItem(saveId: string, itemId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['saves', saveId, 'inbox-item', itemId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/inbox/{item_id}', {
          params: { path: { save_id: saveId, item_id: itemId } },
        }),
      ),
    enabled: enabled && Number.isSafeInteger(itemId) && itemId > 0,
  });
}

/** The inbox message that carries an event's card (M7c). */
export function useEventItem(saveId: string, eventId: number) {
  return useQuery({
    queryKey: ['saves', saveId, 'event-item', eventId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/events/{event_id}/item', {
          params: { path: { save_id: saveId, event_id: eventId } },
        }),
      ),
    enabled: Number.isSafeInteger(eventId) && eventId > 0,
  });
}

// --- Debt and macro (M10, formulas.md 20) ---------------------------------------------------

export function useMacro(saveId: string) {
  return useQuery({
    queryKey: keys.macro(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/finance/macro', path(saveId))),
  });
}

export function useLoans(saveId: string) {
  return useQuery({
    queryKey: keys.loans(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/finance/loans', path(saveId))),
  });
}

/** The first month's payment and warrants for an amount; pass debounced values. */
export function useLoanPreview(saveId: string, instrument: string, amountCents: number) {
  return useQuery({
    queryKey: keys.loanPreview(saveId, instrument, amountCents),
    queryFn: async () =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/loans/preview', {
          ...path(saveId),
          body: { instrument, amount_cents: amountCents },
        }),
      ),
    enabled: amountCents > 0,
    placeholderData: keepPreviousData,
  });
}

export function useTakeLoan(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (body: Schemas['LoanIn']) =>
      unwrap(await api.POST('/api/saves/{save_id}/finance/loans', { ...path(saveId), body })),
    onSuccess: invalidate,
  });
}

export function useRepayLoan(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async ({ loanId, amountCents }: { loanId: number; amountCents: number | null }) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/finance/loans/{loan_id}/repay', {
          params: { path: { save_id: saveId, loan_id: loanId } },
          body: { amount_cents: amountCents },
        }),
      ),
    onSuccess: invalidate,
  });
}

// --- Cities, offices and regions (M9) -------------------------------------------------------

export function useGeo(saveId: string) {
  return useQuery({
    queryKey: keys.geo(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/geo', path(saveId))),
  });
}

export function useLeasePreview(saveId: string, city: string, seats: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.leasePreview(saveId, city, seats),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/geo/lease-preview', {
          params: { path: { save_id: saveId }, query: { city, seats } },
        }),
      ),
    enabled: enabled && city !== '',
  });
}

export type GeoAction =
  | { kind: 'lease'; city: string; seats: number }
  | { kind: 'close'; officeId: number }
  | { kind: 'unitOffice'; unitId: number; officeId: number | null };

async function applyGeo(saveId: string, a: GeoAction) {
  switch (a.kind) {
    case 'lease':
      return unwrap(
        await api.POST('/api/saves/{save_id}/geo/offices', {
          ...path(saveId),
          body: { city: a.city, seats: a.seats },
        }),
      );
    case 'close':
      return unwrap(
        await api.POST('/api/saves/{save_id}/geo/offices/{office_id}/close', {
          params: { path: { save_id: saveId, office_id: a.officeId } },
        }),
      );
    case 'unitOffice':
      return unwrap(
        await api.POST('/api/saves/{save_id}/geo/units/{unit_id}/office', {
          params: { path: { save_id: saveId, unit_id: a.unitId } },
          body: { office_id: a.officeId },
        }),
      );
  }
}

export function useGeoAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: GeoAction) => applyGeo(saveId, a),
    onSuccess: invalidate,
  });
}

export function useProductRegions(saveId: string, productId: number) {
  return useQuery({
    queryKey: keys.productRegions(saveId, productId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/products/{product_id}/regions', {
          params: { path: { save_id: saveId, product_id: productId } },
        }),
      ),
  });
}

export type RegionAction =
  | { kind: 'launch'; region: string }
  | { kind: 'price'; region: string; segment: string; priceCents: number }
  | { kind: 'marketing'; shares: Record<string, number> }; // bp; {} = by revenue (23.5)

async function applyRegion(saveId: string, productId: number, a: RegionAction) {
  if (a.kind === 'marketing') {
    return unwrap(
      await api.POST('/api/saves/{save_id}/products/{product_id}/regions/marketing', {
        params: { path: { save_id: saveId, product_id: productId } },
        body: { shares: a.shares },
      }),
    );
  }
  if (a.kind === 'launch') {
    return unwrap(
      await api.POST('/api/saves/{save_id}/products/{product_id}/regions', {
        params: { path: { save_id: saveId, product_id: productId } },
        body: { region: a.region },
      }),
    );
  }
  return unwrap(
    await api.POST('/api/saves/{save_id}/products/{product_id}/regions/{region}/price', {
      params: { path: { save_id: saveId, product_id: productId, region: a.region } },
      body: { segment: a.segment, price_cents: a.priceCents },
    }),
  );
}

export function useRegionAction(saveId: string, productId: number) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: RegionAction) => applyRegion(saveId, productId, a),
    onSuccess: invalidate,
  });
}

// --- Research (M11, formulas.md 21) --------------------------------------------------------

export function useResearch(saveId: string) {
  return useQuery({
    queryKey: keys.research(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/research', path(saveId))),
  });
}

export function useEras(saveId: string) {
  return useQuery({
    queryKey: keys.eras(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/eras', path(saveId))),
  });
}

export type ResearchAction =
  | { kind: 'start'; unitId: number; domain: string; budgetCents: number | null }
  | { kind: 'stop'; projectId: number }
  | { kind: 'budget'; projectId: number; budgetCents: number | null }
  | { kind: 'licenseIn' | 'licenseOut'; companyId: number; domain: string; points: number };

async function applyResearch(saveId: string, a: ResearchAction) {
  switch (a.kind) {
    case 'start':
      return unwrap(
        await api.POST('/api/saves/{save_id}/research/projects', {
          ...path(saveId),
          body: { unit_id: a.unitId, domain: a.domain, budget_cents: a.budgetCents },
        }),
      );
    case 'stop':
      return unwrap(
        await api.POST('/api/saves/{save_id}/research/projects/{project_id}/stop', {
          params: { path: { save_id: saveId, project_id: a.projectId } },
        }),
      );
    case 'budget':
      return unwrap(
        await api.POST('/api/saves/{save_id}/research/projects/{project_id}/budget', {
          params: { path: { save_id: saveId, project_id: a.projectId } },
          body: { budget_cents: a.budgetCents },
        }),
      );
    case 'licenseIn':
    case 'licenseOut':
      return unwrap(
        await api.POST(
          a.kind === 'licenseIn'
            ? '/api/saves/{save_id}/research/licenses/in'
            : '/api/saves/{save_id}/research/licenses/out',
          {
            ...path(saveId),
            body: { company_id: a.companyId, domain: a.domain, points: a.points },
          },
        ),
      );
  }
}

export function useResearchAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: ResearchAction) => applyResearch(saveId, a),
    onSuccess: invalidate,
  });
}

// --- Mergers and acquisitions (M14, formulas.md 28) -----------------------------------------

export type Mna = Schemas['MnaOut'];
export type MnaTarget = Schemas['TargetOut'];
export type MnaDeal = Schemas['DealOut'];
export type MnaActionResult = Schemas['MnaActionOut'];

export function useMna(saveId: string) {
  return useQuery({
    queryKey: keys.mna(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/mna', path(saveId))),
  });
}

export type MnaAction =
  | { kind: 'diligence'; companyId: number }
  | {
      kind: 'bid';
      companyId: number;
      priceCents: number;
      cashShare: number;
      hostile: boolean;
      mode: 'brand' | 'integrate';
    }
  | { kind: 'mode'; dealId: number; mode: 'brand' | 'integrate' }
  | { kind: 'abandon' | 'remedy'; dealId: number; own?: boolean }
  | { kind: 'directive'; companyId: number; directive: 'grow' | 'harvest' | 'defend' };

async function applyMna(saveId: string, a: MnaAction): Promise<MnaActionResult> {
  switch (a.kind) {
    case 'diligence':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/diligence', {
          ...path(saveId),
          body: { company_id: a.companyId },
        }),
      );
    case 'bid':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/offers', {
          ...path(saveId),
          body: {
            company_id: a.companyId,
            price_cents: a.priceCents,
            cash_share: a.cashShare,
            hostile: a.hostile,
            mode: a.mode,
          },
        }),
      );
    case 'mode':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/deals/{deal_id}/mode', {
          params: { path: { save_id: saveId, deal_id: a.dealId } },
          body: { mode: a.mode },
        }),
      );
    case 'abandon':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/deals/{deal_id}/abandon', {
          params: { path: { save_id: saveId, deal_id: a.dealId } },
        }),
      );
    case 'remedy':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/deals/{deal_id}/remedy', {
          params: { path: { save_id: saveId, deal_id: a.dealId }, query: { own: a.own ?? false } },
        }),
      );
    case 'directive':
      return unwrap(
        await api.POST('/api/saves/{save_id}/mna/subsidiaries/{company_id}/directive', {
          params: { path: { save_id: saveId, company_id: a.companyId } },
          body: { directive: a.directive },
        }),
      );
  }
}

export function useMnaAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: MnaAction) => applyMna(saveId, a),
    onSuccess: invalidate,
  });
}

// --- Infrastructure (M12a) --------------------------------------------------------------------

export function useInfrastructure(saveId: string) {
  return useQuery({
    queryKey: keys.infrastructure(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/infrastructure', path(saveId))),
  });
}

export function useBuildPreview(
  saveId: string,
  kind: string,
  region: string,
  units: number,
  contractId: number | null,
) {
  return useQuery({
    queryKey: keys.buildPreview(saveId, kind, region, units, contractId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/infrastructure/build-preview', {
          params: {
            path: { save_id: saveId },
            query: { kind, region, units, contract_id: contractId },
          },
        }),
      ),
    enabled: kind !== '' && region !== '',
  });
}

export type InfraAction =
  | {
      kind: 'build';
      facilityKind: string;
      region: string;
      units: number;
      contractId: number | null;
    }
  | { kind: 'sell'; facilityId: number }
  | { kind: 'staff'; facilityId: number; unitId: number | null }
  | { kind: 'contract'; good: string; months: number; volume: number }
  | { kind: 'cloud' };

async function applyInfra(saveId: string, a: InfraAction) {
  switch (a.kind) {
    case 'build':
      return unwrap(
        await api.POST('/api/saves/{save_id}/infrastructure/facilities', {
          ...path(saveId),
          body: {
            kind: a.facilityKind,
            region: a.region,
            units: a.units,
            contract_id: a.contractId,
          },
        }),
      );
    case 'sell':
      return unwrap(
        await api.POST('/api/saves/{save_id}/infrastructure/facilities/{facility_id}/sell', {
          params: { path: { save_id: saveId, facility_id: a.facilityId } },
        }),
      );
    case 'staff':
      return unwrap(
        await api.POST('/api/saves/{save_id}/infrastructure/facilities/{facility_id}/staff', {
          params: { path: { save_id: saveId, facility_id: a.facilityId } },
          body: { unit_id: a.unitId },
        }),
      );
    case 'contract':
      return unwrap(
        await api.POST('/api/saves/{save_id}/infrastructure/contracts', {
          ...path(saveId),
          body: { good: a.good, months: a.months, volume: a.volume },
        }),
      );
    case 'cloud':
      return unwrap(await api.POST('/api/saves/{save_id}/infrastructure/cloud', path(saveId)));
  }
}

export function useInfraAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: InfraAction) => applyInfra(saveId, a),
    onSuccess: invalidate,
  });
}

// --- IPO, the public company and the CEO seat (M13, formulas.md 25) -------------------------

export function usePublic(saveId: string) {
  return useQuery({
    queryKey: keys.public(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/public', path(saveId))),
    enabled: saveId !== '',
  });
}

export type PublicAction =
  | { kind: 'banks'; bank: string }
  | { kind: 'guidance'; revenueCents: number; marginBp: number }
  | { kind: 'buyback'; amountCents: number }
  | { kind: 'dividend'; perShareCents: number }
  | { kind: 'secondary'; shares: number }
  | { kind: 'appointCeo'; personId: number }
  | { kind: 'dismissCeo' }
  | { kind: 'authority'; scopes: string[] }
  | { kind: 'override'; decisionId: number };

async function applyPublic(saveId: string, a: PublicAction) {
  switch (a.kind) {
    case 'banks':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/banks', {
          ...path(saveId),
          body: { bank: a.bank },
        }),
      );
    case 'guidance':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/guidance', {
          ...path(saveId),
          body: { revenue_cents: a.revenueCents, margin_bp: a.marginBp },
        }),
      );
    case 'buyback':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/buyback', {
          ...path(saveId),
          body: { amount_cents: a.amountCents },
        }),
      );
    case 'dividend':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/dividend', {
          ...path(saveId),
          body: { per_share_cents: a.perShareCents },
        }),
      );
    case 'secondary':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/secondary', {
          ...path(saveId),
          body: { shares: a.shares },
        }),
      );
    case 'appointCeo':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/ceo', {
          ...path(saveId),
          body: { person_id: a.personId },
        }),
      );
    case 'dismissCeo':
      return unwrap(await api.POST('/api/saves/{save_id}/public/ceo/dismiss', path(saveId)));
    case 'authority':
      return unwrap(
        await api.PUT('/api/saves/{save_id}/public/ceo/authority', {
          ...path(saveId),
          body: { scopes: a.scopes },
        }),
      );
    case 'override':
      return unwrap(
        await api.POST('/api/saves/{save_id}/public/ceo/decisions/{decision_id}/override', {
          params: { path: { save_id: saveId, decision_id: a.decisionId } },
        }),
      );
  }
}

/** One public-company action: it applies at once and spends energy (ADR-0014). */
export function usePublicAction(saveId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: PublicAction) => applyPublic(saveId, a),
    onSuccess: (data) => {
      client.setQueryData(keys.public(saveId), data.public);
      void invalidate();
    },
  });
}

// --- Hardware (M12b, formulas.md 26.5) ------------------------------------------------------

export function useHardware(saveId: string) {
  return useQuery({
    queryKey: keys.hardware(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/hardware', path(saveId))),
  });
}

export function useManufacturing(saveId: string, productId: number, enabled = true) {
  return useQuery({
    queryKey: keys.manufacturing(saveId, productId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/products/{product_id}/manufacturing', {
          params: { path: { save_id: saveId, product_id: productId } },
        }),
      ),
    enabled,
  });
}

export type HardwareAction =
  | {
      kind: 'cm';
      productId: number;
      manufacturer: string;
      city: string;
      units: number;
      months: number;
    }
  | { kind: 'wafer'; productId: number; foundry: string; wafers: number; months: number }
  | { kind: 'plant'; city: string; units: number }
  | { kind: 'staff'; facilityId: number; unitId: number | null }
  | { kind: 'sell'; facilityId: number }
  | { kind: 'sell_capacity' };

async function applyHardware(saveId: string, a: HardwareAction) {
  switch (a.kind) {
    case 'cm':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/contracts', {
          ...path(saveId),
          body: {
            product_id: a.productId,
            manufacturer: a.manufacturer,
            city: a.city,
            units: a.units,
            months: a.months,
          },
        }),
      );
    case 'wafer':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/wafer-contracts', {
          ...path(saveId),
          body: { product_id: a.productId, foundry: a.foundry, wafers: a.wafers, months: a.months },
        }),
      );
    case 'plant':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/plants', {
          ...path(saveId),
          body: { city: a.city, units: a.units },
        }),
      );
    case 'staff':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/plants/{facility_id}/staff', {
          params: { path: { save_id: saveId, facility_id: a.facilityId } },
          body: { unit_id: a.unitId },
        }),
      );
    case 'sell':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/plants/{facility_id}/sell', {
          params: { path: { save_id: saveId, facility_id: a.facilityId } },
        }),
      );
    case 'sell_capacity':
      return unwrap(
        await api.POST('/api/saves/{save_id}/hardware/contract-manufacturing', path(saveId)),
      );
  }
}

export function useHardwareAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: (a: HardwareAction) => applyHardware(saveId, a),
    onSuccess: invalidate,
  });
}

// --- M17 (formulas.md 33): commodities, offtake and regional power ---------------------------

export function useCommodities(saveId: string) {
  return useQuery({
    queryKey: keys.commodities(saveId),
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/commodities', path(saveId))),
  });
}

export type OfftakeBody = Schemas['OfftakeIn'];
export type CommodityPlan = Schemas['CommodityPlanOut'];

/** The planning view (M23c): next year's need per commodity, its drivers and its cover. */
export function useCommodityPlan(saveId: string) {
  return useQuery({
    queryKey: [...keys.commodities(saveId), 'plan'],
    queryFn: async () =>
      unwrap(await api.GET('/api/saves/{save_id}/commodities/plan', path(saveId))),
  });
}

export function useOfftakeQuote(saveId: string) {
  return useMutation({
    mutationFn: async (body: OfftakeBody) =>
      unwrap(
        await api.POST('/api/saves/{save_id}/commodities/offtakes/quote', {
          ...path(saveId),
          body,
        }),
      ),
  });
}

export type CommodityAction =
  | ({ kind: 'offtake' } & OfftakeBody)
  | { kind: 'contract'; good: string; months: number; volume_year: number };

export function useCommodityAction(saveId: string) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({
    mutationFn: async (a: CommodityAction) => {
      if (a.kind === 'offtake') {
        const body = {
          good: a.good,
          supplier: a.supplier,
          years: a.years,
          volume_year: a.volume_year,
          prepay: a.prepay,
        };
        return unwrap(
          await api.POST('/api/saves/{save_id}/commodities/offtakes', { ...path(saveId), body }),
        );
      }
      return unwrap(
        await api.POST('/api/saves/{save_id}/commodities/contracts', {
          ...path(saveId),
          body: { good: a.good, months: a.months, volume_year: a.volume_year },
        }),
      );
    },
    onSuccess: invalidate,
  });
}
