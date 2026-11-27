// Media (M55, formulas.md 65): the Studio (the slate in development with budget, lead and stage;
// released titles' audience against cost; the catalogue's value; creative leads and leads on
// offer), Streaming (subscribers by region, churn, engagement, content spend, ad tiers, cash),
// Games (titles by platform, players and decay, in-app revenue, generations) and Social (users by
// region, network effect, format, moderation, ad revenue, the ad market). One view feeds all four.
// No game values are computed here: figures are formatted.
import { Alert, Button, Checkbox, NumberInput, Select, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useCancelTitle,
  useCutBudget,
  useDivest,
  useGreenlight,
  useLicense,
  useLiveService,
  useMedia,
  useMoveRelease,
  useOverrule,
  useSetMediaLine,
  useSignLead,
  type AdMarket,
  type GameTitle,
  type Lead,
  type LeadOffer,
  type Media,
  type Network,
  type RegionCustomers,
  type Service,
  type ServiceMonth,
  type Title,
} from '../hooks/media';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const titleHelper = createColumnHelper<GameTableFeatures, Title>();
const leadHelper = createColumnHelper<GameTableFeatures, Lead>();
const offerHelper = createColumnHelper<GameTableFeatures, LeadOffer>();
const regionHelper = createColumnHelper<GameTableFeatures, RegionCustomers>();
const monthHelper = createColumnHelper<GameTableFeatures, ServiceMonth>();
const gameHelper = createColumnHelper<GameTableFeatures, GameTitle>();
const adHelper = createColumnHelper<GameTableFeatures, AdMarket>();

const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;
const big = (x: number) => Math.round(x).toLocaleString();
const millions = (x: number | null | undefined) =>
  x === null || x === undefined ? '—' : `${x.toFixed(1)}M`;
const range = (r: { lo: number; hi: number }) => (r.lo === r.hi ? `${r.lo}` : `${r.lo}-${r.hi}`);

function useMediaScreen(): { saveId: string; q: ReturnType<typeof useMedia> } {
  const { saveId = '' } = useParams();
  return { saveId, q: useMedia(saveId) };
}

function ErrorLine({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <Alert color="red" mt="xs" data-testid="media-error">
      {error.message}
    </Alert>
  );
}

// --- Studio ----------------------------------------------------------------------------------

export function StudioScreen() {
  const { saveId, q } = useMediaScreen();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load the studio" error={q.error} />;
  const m = q.data;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="media.content_asset">Content assets</Term>{' '}
            {formatMoneyShort(m.studio.catalogue_book_cents)} · catalogue value{' '}
            {formatMoneyShort(m.studio.catalogue_value_cents)}
            {m.studio.strikes.length > 0 ? ` · on strike: ${m.studio.strikes.join(', ')}` : ''}
          </span>
        }
      >
        Studio
      </ScreenTitle>
      <Panel title="Green-light a title" testId="studio-greenlight">
        <Greenlight saveId={saveId} m={m} />
      </Panel>
      <Panel title="The slate in development" testId="studio-slate">
        <Slate saveId={saveId} titles={m.studio.slate} />
      </Panel>
      <Panel title="Released titles" testId="studio-released">
        <Released titles={m.studio.released} />
      </Panel>
      <Panel title="Creative leads" testId="studio-leads">
        <Leads leads={m.studio.leads} />
      </Panel>
      <Panel title="Leads on offer" testId="studio-offers">
        <Offers saveId={saveId} m={m} />
      </Panel>
    </>
  );
}

function Greenlight({ saveId, m }: { saveId: string; m: Media }) {
  const go = useGreenlight(saveId);
  const [kind, setKind] = useState<string>('series');
  const k = m.studio.kinds.find((x) => x.key === kind);
  const [name, setName] = useState('');
  const [budget, setBudget] = useState<number | string>('');
  const [lead, setLead] = useState<string | null>(null);
  const [own, setOwn] = useState(false);
  const free = m.studio.leads.filter((l) => !l.busy);
  const video = m.streaming.services.filter((s) => s.category === 'streaming');
  const dollars = typeof budget === 'number' ? budget : (k?.typical_budget_cents ?? 0) / 100;
  return (
    <>
      <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
        <Select
          label="Kind"
          size="xs"
          data={m.studio.kinds.map((x) => x.key)}
          value={kind}
          onChange={(v) => setKind(v ?? 'series')}
          allowDeselect={false}
          data-testid="greenlight-kind"
        />
        <TextInput
          label="Name"
          size="xs"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          data-testid="greenlight-name"
        />
        <NumberInput
          label="Budget ($)"
          size="xs"
          value={budget}
          placeholder={k ? String(k.typical_budget_cents / 100) : ''}
          onChange={setBudget}
          data-testid="greenlight-budget"
        />
        <Select
          label="Creative lead"
          size="xs"
          data={free.map((l) => ({ value: String(l.person_id), label: l.name }))}
          value={lead}
          onChange={setLead}
          placeholder="none"
          data-testid="greenlight-lead"
        />
        {kind !== 'game' && video.length > 0 ? (
          <Checkbox
            label="On your own service"
            checked={own}
            onChange={(e) => setOwn(e.currentTarget.checked)}
            data-testid="greenlight-own"
          />
        ) : null}
        <Button
          size="xs"
          loading={go.isPending}
          data-testid="greenlight-submit"
          onClick={() =>
            go.mutate({
              name: name || `Untitled ${kind}`,
              kind,
              budget_cents: Math.round(dollars * 100),
              lead_person_id: lead ? Number(lead) : null,
              platforms: kind === 'game' ? ['pc', 'console'] : [],
              window: own ? 'own' : 'licensed',
              service_product_id: own ? (video[0]?.product_id ?? null) : null,
            })
          }
        >
          Green-light
        </Button>
      </div>
      {k ? (
        <p className="tst-muted" style={{ fontSize: 13 }}>
          A typical {kind} costs {formatMoneyShort(k.typical_budget_cents)} (from{' '}
          {formatMoneyShort(k.min_budget_cents)} to {formatMoneyShort(k.max_budget_cents)}) over{' '}
          {k.dev_months} months, <Term term="media.content_asset">capitalised</Term> as it is spent
          and <Term term="media.amortisation">amortised</Term> from release.
        </p>
      ) : null}
      <ErrorLine error={go.error} />
    </>
  );
}

function Slate({ saveId, titles }: { saveId: string; titles: Title[] }) {
  const overrule = useOverrule(saveId);
  const cancel = useCancelTitle(saveId);
  const cut = useCutBudget(saveId);
  const move = useMoveRelease(saveId);
  const columns = useMemo(
    () =>
      titleHelper.columns([
        titleHelper.accessor('name', { header: 'Title', meta: { term: 'media.content_asset' } }),
        titleHelper.accessor('kind', { header: 'Kind', meta: { term: 'media.content_asset' } }),
        titleHelper.accessor('budget_cents', {
          header: 'Budget',
          meta: { term: 'media.content_asset' },
          cell: (c) =>
            `${formatMoneyShort(c.row.original.spent_cents)} of ${formatMoneyShort(c.getValue())}`,
        }),
        titleHelper.accessor('lead_name', {
          header: 'Lead',
          meta: { term: 'media.creative_lead' },
          cell: (c) =>
            c.row.original.lead_walked ? `${c.getValue() ?? ''} (walked)` : (c.getValue() ?? '—'),
        }),
        titleHelper.accessor('months_done', {
          header: 'Stage',
          meta: { term: 'media.content_asset' },
          cell: (c) => `${c.getValue()} of ${c.row.original.dev_months} months`,
        }),
        titleHelper.accessor('release', {
          header: 'Release',
          meta: { term: 'media.content_asset' },
        }),
        titleHelper.accessor('overrules', {
          header: 'Overrules',
          meta: { term: 'media.creative_lead' },
        }),
        titleHelper.display({
          id: 'actions',
          header: 'Actions',
          meta: { term: 'media.creative_lead' },
          cell: (c) => {
            const t = c.row.original;
            return (
              <span style={{ display: 'flex', gap: 4 }}>
                <Button
                  size="compact-xs"
                  variant="light"
                  disabled={t.lead_person_id === null || t.lead_walked}
                  data-testid={`overrule-${t.id}`}
                  onClick={() => overrule.mutate(t.id)}
                >
                  Overrule
                </Button>
                <Button
                  size="compact-xs"
                  variant="light"
                  data-testid={`cut-${t.id}`}
                  onClick={() =>
                    cut.mutate({
                      titleId: t.id,
                      budget_cents: Math.max(t.spent_cents, Math.round(t.budget_cents * 0.8)),
                    })
                  }
                >
                  Cut 20%
                </Button>
                <Button
                  size="compact-xs"
                  variant="light"
                  data-testid={`move-${t.id}`}
                  onClick={() => move.mutate({ titleId: t.id, months: 3 })}
                >
                  +3 months
                </Button>
                <Button
                  size="compact-xs"
                  variant="light"
                  color="red"
                  data-testid={`cancel-${t.id}`}
                  onClick={() => cancel.mutate(t.id)}
                >
                  Cancel
                </Button>
              </span>
            );
          },
        }),
      ]),
    [overrule, cut, move, cancel],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: titles });
  return (
    <>
      <DataTable
        table={table}
        label="Slate"
        rowTestId="slate-row"
        empty="Nothing in development."
      />
      <ErrorLine error={overrule.error ?? cut.error ?? move.error ?? cancel.error} />
    </>
  );
}

function Released({ titles }: { titles: Title[] }) {
  const columns = useMemo(
    () =>
      titleHelper.columns([
        titleHelper.accessor('name', { header: 'Title', meta: { term: 'media.content_asset' } }),
        titleHelper.accessor('kind', { header: 'Kind', meta: { term: 'media.content_asset' } }),
        titleHelper.accessor('release', { header: 'Released', meta: { term: 'media.audience' } }),
        titleHelper.accessor('audience', {
          header: 'Audience',
          meta: { term: 'media.audience' },
          cell: (c) => (
            <span data-testid={`audience-${c.row.original.id}`}>
              {millions(c.getValue())} of {millions(c.row.original.expected)} expected{' '}
              <Explain metric="title_result" entity={c.row.original.id} label="its result" />
            </span>
          ),
        }),
        titleHelper.accessor('quality', {
          header: 'Quality',
          meta: { term: 'media.quality' },
          cell: (c) => (c.getValue() ?? 0).toFixed(2),
        }),
        titleHelper.accessor('revenue_cents', {
          header: 'Revenue',
          meta: { term: 'media.audience' },
          cell: (c) =>
            `${formatMoneyShort(c.getValue() + c.row.original.attributed_cents)} on ${formatMoneyShort(c.row.original.spent_cents)}`,
        }),
        titleHelper.accessor('book_cents', {
          header: 'Book',
          meta: { term: 'media.amortisation' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        titleHelper.accessor('earned_back', {
          header: 'Earned back',
          meta: { term: 'media.audience' },
          cell: (c) => (c.getValue() ? 'yes' : 'not yet'),
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: titles });
  return (
    <DataTable table={table} label="Released" rowTestId="released-row" empty="No titles out yet." />
  );
}

function Leads({ leads }: { leads: Lead[] }) {
  const columns = useMemo(
    () =>
      leadHelper.columns([
        leadHelper.accessor('name', { header: 'Lead', meta: { term: 'media.creative_lead' } }),
        leadHelper.accessor((l) => l.creative.lo, {
          id: 'creative',
          header: 'Creative',
          meta: { term: 'media.creative_lead' },
          cell: (c) => range(c.row.original.creative),
        }),
        leadHelper.accessor((l) => l.vision.lo, {
          id: 'vision',
          header: 'Vision',
          meta: { term: 'media.creative_lead' },
          cell: (c) => range(c.row.original.vision),
        }),
        leadHelper.accessor('reputation', {
          header: 'Reputation',
          meta: { term: 'media.creative_lead' },
          cell: (c) => c.getValue().toFixed(2),
        }),
        leadHelper.accessor('morale', {
          header: 'Morale',
          meta: { term: 'media.creative_lead' },
          cell: (c) => (
            <span data-testid={`lead-morale-${c.row.original.person_id}`}>
              {c.getValue() ?? '—'}
            </span>
          ),
        }),
        leadHelper.accessor('fee_cents', {
          header: 'Fee a year',
          meta: { term: 'media.overall_deal' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        leadHelper.accessor('deal_to', { header: 'Deal to', meta: { term: 'media.overall_deal' } }),
        leadHelper.accessor('busy', {
          header: 'Busy',
          meta: { term: 'media.creative_lead' },
          cell: (c) => (c.getValue() ? 'leading a title' : 'free'),
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: leads });
  return (
    <DataTable table={table} label="Leads" rowTestId="lead-row" empty="No creative leads signed." />
  );
}

function Offers({ saveId, m }: { saveId: string; m: Media }) {
  const sign = useSignLead(saveId);
  const years = m.studio.deal_years[1] ?? 3;
  const columns = useMemo(
    () =>
      offerHelper.columns([
        offerHelper.accessor('name', { header: 'Lead', meta: { term: 'media.creative_lead' } }),
        offerHelper.accessor('region', { header: 'From', meta: { term: 'media.creative_lead' } }),
        offerHelper.accessor((o) => o.creative.lo, {
          id: 'creative',
          header: 'Creative',
          meta: { term: 'media.creative_lead' },
          cell: (c) => range(c.row.original.creative),
        }),
        offerHelper.accessor((o) => o.vision.lo, {
          id: 'vision',
          header: 'Vision',
          meta: { term: 'media.creative_lead' },
          cell: (c) => range(c.row.original.vision),
        }),
        offerHelper.accessor('fee_cents', {
          header: 'Fee a year',
          meta: { term: 'media.overall_deal' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        offerHelper.accessor('expires', { header: 'Until', meta: { term: 'media.overall_deal' } }),
        offerHelper.display({
          id: 'sign',
          header: 'Sign',
          meta: { term: 'media.overall_deal' },
          cell: (c) => (
            <Button
              size="compact-xs"
              data-testid={`sign-${c.row.original.year}-${c.row.original.n}`}
              onClick={() => sign.mutate({ year: c.row.original.year, n: c.row.original.n, years })}
            >
              Sign for {years} years
            </Button>
          ),
        }),
      ]),
    [sign, years],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: m.studio.offers });
  return (
    <>
      <DataTable
        table={table}
        label="Offers"
        rowTestId="offer-row"
        empty="No leads on offer now."
      />
      <ErrorLine error={sign.error} />
    </>
  );
}

// --- Streaming -------------------------------------------------------------------------------

export function StreamingScreen() {
  const { saveId, q } = useMediaScreen();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load streaming" error={q.error} />;
  const s = q.data.streaming;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="media.ad_tier">Ad tiers</Term>{' '}
            {s.ad_tier_open ? 'open' : `from ${s.ad_tier_from}`} · music pays {pct(s.music_payout)}{' '}
            to rights holders
          </span>
        }
      >
        Streaming
      </ScreenTitle>
      {s.services.length === 0 ? (
        <Panel title="Your services" testId="streaming-none">
          <p className="tst-muted">
            No video or music service yet: make a Video streaming or Music streaming line on
            Products, then green-light titles for it on the Studio screen.
          </p>
        </Panel>
      ) : (
        s.services.map((x) => (
          <ServicePanel key={x.product_id} saveId={saveId} s={x} adOpen={s.ad_tier_open} />
        ))
      )}
    </>
  );
}

function RegionTable({ rows, label }: { rows: RegionCustomers[]; label: string }) {
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region', meta: { term: 'media.engagement' } }),
        regionHelper.accessor('customers', {
          header: label,
          meta: { term: 'media.engagement' },
          cell: (c) => `${big(c.getValue())} of ${big(c.row.original.market)}`,
        }),
        regionHelper.accessor('share', {
          header: 'Share',
          meta: { term: 'media.network_effect' },
          cell: (c) => pct(c.getValue(), 1),
        }),
        regionHelper.accessor('price_cents', {
          header: 'Price a month',
          meta: { term: 'media.arpu' },
          cell: (c) => (c.getValue() === null ? '—' : formatMoney(c.getValue() ?? 0)),
        }),
      ]),
    [label],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: rows });
  return <DataTable table={table} label="Regions" rowTestId="media-region-row" />;
}

function ServicePanel({ saveId, s, adOpen }: { saveId: string; s: Service; adOpen: boolean }) {
  const set = useSetMediaLine(saveId);
  const license = useLicense(saveId);
  const [fee, setFee] = useState<number | string>(1000000);
  const video = s.category === 'streaming';
  const columns = useMemo(
    () =>
      monthHelper.columns([
        monthHelper.accessor('month', { header: 'Month', meta: { term: 'media.cash' } }),
        monthHelper.accessor('customers', {
          header: 'Subscribers',
          meta: { term: 'media.engagement' },
          cell: (c) => big(c.getValue()),
        }),
        monthHelper.accessor('revenue_cents', {
          header: 'Revenue',
          meta: { term: 'media.cash' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        monthHelper.accessor('ad_revenue_cents', {
          header: 'Ad revenue',
          meta: { term: 'media.ad_tier' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        monthHelper.accessor('content_cents', {
          header: 'Content',
          meta: { term: 'media.content_asset' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        monthHelper.accessor('cash_cents', {
          header: 'Cash since launch',
          meta: { term: 'media.cash' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
      ]),
    [],
  );
  const recent = useMemo(() => [...s.months].reverse().slice(0, 12), [s.months]);
  const table = useTable({ features: gameTableFeatures, columns, data: recent });
  return (
    <Panel title={`${s.name} (${video ? 'video' : 'music'})`} testId={`service-${s.product_id}`}>
      <p style={{ margin: 0 }}>
        {big(s.customers)} subscribers · <Term term="media.engagement">engagement</Term>{' '}
        {s.engagement.toFixed(2)} · churn x {s.churn_mult.toFixed(2)} · content last month{' '}
        {formatMoneyShort(s.content_cents)} ·{' '}
        <span data-testid={`ad-revenue-${s.product_id}`}>
          ad revenue {formatMoneyShort(s.ad_revenue_cents)}
        </span>{' '}
        · <Term term="media.cash">cash since launch</Term> {formatMoneyShort(s.cash_cents)}
        {s.paid_back ? `, paid back in ${s.paid_back}` : ''}
      </p>
      <RegionTable rows={s.regions} label="Subscribers" />
      <DataTable
        table={table}
        label="Months"
        rowTestId="service-month-row"
        empty="No months yet."
      />
      {video ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'end', marginTop: 6 }}>
          <Checkbox
            label="Ad tier"
            disabled={!adOpen}
            checked={s.ad_tier}
            onChange={(e) =>
              set.mutate({ productId: s.product_id, body: { ad_tier: e.currentTarget.checked } })
            }
            data-testid={`ad-tier-${s.product_id}`}
          />
          <NumberInput
            label="License titles in ($ a year)"
            size="xs"
            value={fee}
            onChange={setFee}
            data-testid={`licence-fee-${s.product_id}`}
          />
          <Button
            size="xs"
            variant="light"
            data-testid={`licence-${s.product_id}`}
            onClick={() =>
              license.mutate({
                product_id: s.product_id,
                fee_cents: Math.round(Number(fee) * 100),
                years: 2,
              })
            }
          >
            License for 2 years
          </Button>
        </div>
      ) : null}
      {s.licences.length > 0 ? (
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Licensed in:{' '}
          {s.licences
            .map((l) => `${formatMoneyShort(l.fee_cents)} a year, ${l.from_month}-${l.to_month}`)
            .join('; ')}
        </p>
      ) : null}
      <ErrorLine error={set.error ?? license.error} />
    </Panel>
  );
}

// --- Games -----------------------------------------------------------------------------------

export function GamesScreen() {
  const { saveId, q } = useMediaScreen();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load games" error={q.error} />;
  const g = q.data.games;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Store fee {pct(g.store_fee)}
            {g.epic_open ? ` (Epic's ${pct(g.epic_fee)} on PC)` : ''} · generations:{' '}
            {g.generations.map((x) => `${x.label} ${x.month}`).join(', ') || 'none yet'}
          </span>
        }
      >
        Games
      </ScreenTitle>
      <Panel title="Your games" testId="games-titles">
        <GameTable saveId={saveId} rows={g.titles} />
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Green-light a game on the Studio screen. A free-to-play game earns in-app spending from a
          share of its players; <Term term="media.live_service">live service</Term> slows their
          decline.
        </p>
      </Panel>
    </>
  );
}

function GameTable({ saveId, rows }: { saveId: string; rows: GameTitle[] }) {
  const live = useLiveService(saveId);
  const columns = useMemo(
    () =>
      gameHelper.columns([
        gameHelper.accessor((r) => r.title.name, {
          id: 'name',
          header: 'Game',
          meta: { term: 'media.content_asset' },
        }),
        gameHelper.accessor((r) => r.title.platforms.join(', '), {
          id: 'platforms',
          header: 'Platforms',
          meta: { term: 'media.content_asset' },
        }),
        gameHelper.accessor((r) => r.title.monetisation, {
          id: 'model',
          header: 'Model',
          meta: { term: 'media.live_service' },
        }),
        gameHelper.accessor((r) => r.title.stage, {
          id: 'stage',
          header: 'Stage',
          meta: { term: 'media.content_asset' },
        }),
        gameHelper.accessor((r) => r.title.players, {
          id: 'players',
          header: 'Players',
          meta: { term: 'media.live_service' },
          cell: (c) =>
            c.row.original.title.monetisation === 'free_to_play'
              ? `${millions(c.getValue())} (-${pct(c.row.original.decay, 1)} a month)`
              : millions(c.row.original.title.audience),
        }),
        gameHelper.accessor((r) => r.title.revenue_cents, {
          id: 'revenue',
          header: 'Revenue',
          meta: { term: 'media.audience' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        gameHelper.display({
          id: 'live',
          header: 'Live service',
          meta: { term: 'media.live_service' },
          cell: (c) =>
            c.row.original.title.monetisation === 'free_to_play' ? (
              <Checkbox
                checked={c.row.original.title.live_service}
                onChange={(e) =>
                  live.mutate({ titleId: c.row.original.title.id, on: e.currentTarget.checked })
                }
                data-testid={`live-${c.row.original.title.id}`}
              />
            ) : (
              '—'
            ),
        }),
      ]),
    [live],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: rows });
  return <DataTable table={table} label="Games" rowTestId="game-row" empty="No games yet." />;
}

// --- Social ----------------------------------------------------------------------------------

export function SocialScreen() {
  const { saveId, q } = useMediaScreen();
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load social" error={q.error} />;
  const s = q.data.social;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="media.format_era">Formats</Term>:{' '}
            {s.formats.map((f) => `${f.label} (${f.month})`).join(', ')}
          </span>
        }
      >
        Social
      </ScreenTitle>
      {s.networks.length === 0 ? (
        <Panel title="Your networks" testId="social-none">
          <p className="tst-muted">
            No social network yet: make a Social networks line on Products.
          </p>
        </Panel>
      ) : (
        s.networks.map((n) => <NetworkPanel key={n.product_id} saveId={saveId} n={n} m={s} />)
      )}
      <Panel title="Consumer apps and ad pricing" testId="social-apps">
        <Apps saveId={saveId} m={s} />
      </Panel>
      <Panel title="The ad market" testId="social-ads">
        <AdTable rows={s.ads} />
      </Panel>
    </>
  );
}

function NetworkPanel({ saveId, n, m }: { saveId: string; n: Network; m: Media['social'] }) {
  const set = useSetMediaLine(saveId);
  const divest = useDivest(saveId);
  const [load, setLoad] = useState<number | string>(n.ad_load);
  const body = (
    patch: Partial<{ ad_load: number; format: string | null; moderation: string }>,
  ) => ({
    productId: n.product_id,
    body: { ad_load: Number(load), moderation: n.moderation, format: null, ...patch },
  });
  return (
    <Panel title={n.name} testId={`network-${n.product_id}`}>
      <p style={{ margin: 0 }}>
        {big(n.users)} users · <Term term="media.network_effect">network effect</Term> x{' '}
        {n.network_effect.toFixed(2)} · <Term term="media.format_era">format</Term>{' '}
        {n.format_label ?? '—'}
        {n.advantage ? ' (newest: an advantage)' : ''} · ad revenue{' '}
        {formatMoneyShort(n.ad_revenue_cents)} a month
      </p>
      <RegionTable rows={n.regions} label="Users" />
      <div style={{ display: 'flex', gap: 8, alignItems: 'end', marginTop: 6 }}>
        <NumberInput
          label="Ad load"
          size="xs"
          step={0.1}
          min={m.load_range[0]}
          max={m.load_range[1]}
          value={load}
          onChange={setLoad}
          data-testid={`ad-load-${n.product_id}`}
        />
        <Button size="xs" variant="light" onClick={() => set.mutate(body({}))}>
          Set <Term term="media.ad_load">ad load</Term>
        </Button>
        <Select
          label="Moderation"
          size="xs"
          data={['light', 'standard', 'strong']}
          value={n.moderation}
          onChange={(v) => set.mutate(body({ moderation: v ?? 'standard' }))}
          allowDeselect={false}
          data-testid={`moderation-${n.product_id}`}
        />
        <Select
          label="Format"
          size="xs"
          data={m.formats.map((f) => ({ value: f.key, label: f.label }))}
          value={n.format}
          onChange={(v) => set.mutate(body({ format: v }))}
          allowDeselect={false}
          data-testid={`format-${n.product_id}`}
        />
      </div>
      {n.laws.map((l) => (
        <p key={l.id} data-testid={`law-${l.id}`}>
          {l.label}: divest or be banned by {l.deadline} ({l.status}){' '}
          {l.status === 'pending' ? (
            <Button size="compact-xs" color="red" onClick={() => divest.mutate(l.id)}>
              Divest
            </Button>
          ) : null}
        </p>
      ))}
      <ErrorLine error={set.error ?? divest.error} />
    </Panel>
  );
}

function Apps({ saveId, m }: { saveId: string; m: Media['social'] }) {
  const set = useSetMediaLine(saveId);
  if (m.consumer_apps.length === 0) {
    return <p className="tst-muted">No consumer apps.</p>;
  }
  return (
    <>
      {m.consumer_apps.map((a) => (
        <Checkbox
          key={a.product_id}
          label={`${a.name}: ad pricing (revenue a user from the ad market)`}
          disabled={!m.ad_pricing_open}
          checked={a.ad_pricing}
          onChange={(e) =>
            set.mutate({ productId: a.product_id, body: { ad_pricing: e.currentTarget.checked } })
          }
          data-testid={`ad-pricing-${a.product_id}`}
        />
      ))}
      {!m.ad_pricing_open ? (
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Consumer apps may move to ad pricing from 2026.
        </p>
      ) : null}
      <ErrorLine error={set.error} />
    </>
  );
}

function AdTable({ rows }: { rows: AdMarket[] }) {
  const columns = useMemo(
    () =>
      adHelper.columns([
        adHelper.accessor('label', { header: 'Region', meta: { term: 'media.arpu' } }),
        adHelper.accessor('spend_cents', {
          header: 'Ad spend a month',
          meta: { term: 'media.arpu' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        adHelper.accessor('digital_cents', {
          header: 'Digital',
          meta: { term: 'media.arpu' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        adHelper.accessor('cpm_cents', {
          header: 'Price a thousand',
          meta: { term: 'media.ad_load' },
          cell: (c) => formatMoney(Math.round(c.getValue())),
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: rows });
  return <DataTable table={table} label="Ad market" rowTestId="ad-row" />;
}
