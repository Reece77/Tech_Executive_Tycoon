import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { AttributeRange } from '../components/AttributeRange';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useCandidates,
  useCheckCandidate,
  useCloseSearch,
  useHiringMeta,
  useMakeOffer,
  useNewGameMeta,
  useOfferPreview,
  useOpenSearch,
  useSearches,
  useWithdrawOffer,
  type HiringMeta,
  type NewGameMeta,
  type Person,
  type Search,
} from '../hooks/api';
import { formatBpPercent, formatMoneyWhole, formatRatio, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

type Channel = HiringMeta['channels'][number];
const helper = createColumnHelper<GameTableFeatures, Person>();
const PREVIEW_DEBOUNCE_MS = 250;

// Channel flavour text (wireframe); the numbers beside it come from GET /api/meta/hiring.
const CHANNEL_TEXT: Record<string, string> = {
  network: 'People you know of; you start knowing them better.',
  job_post: 'Stays open until you close it.',
  recruiter: 'Recruiters screen each candidate twice.',
};
const SUBMIT_TEXT: Record<string, string> = {
  network: 'Search network',
  job_post: 'Post job',
  recruiter: 'Engage recruiter',
};

/** 2000 bp -> "20%", 250 bp -> "2.50%". */
function bpShort(bp: number): string {
  return bp % 100 === 0 ? `${bp / 100}%` : formatBpPercent(bp);
}

function channelCost(c: Channel): string {
  const size = `${c.batch_min}–${c.batch_max}`;
  if (c.monthly_cost_cents) {
    return `${formatMoneyWhole(c.monthly_cost_cents)} per month while open · ${size} each month`;
  }
  if (c.hire_fee_bp)
    return `${bpShort(c.hire_fee_bp)} of first-year salary, on hire · ${size}, one batch`;
  return `Free · ${size} candidates, one batch`;
}

/** "Mostly junior and mid level": the two largest shares of the channel's level mix. */
function levelText(c: Channel): string {
  const top = Object.entries(c.level_mix)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([level]) => level);
  return `Mostly ${top.join(' and ')} level.`;
}

function knownText(p: Person): string {
  const k = p.knowledge;
  const parts = [k.channel === 'network' ? 'Introduced' : 'Screened'];
  if (k.interviews) parts.push(k.interviews > 1 ? `Interviewed ×${k.interviews}` : 'Interviewed');
  if (k.reference_checks) parts.push('references');
  return parts.join(', ');
}

export function RecruitmentScreen() {
  const { saveId = '' } = useParams();
  const hiring = useHiringMeta();
  const meta = useNewGameMeta();
  const searches = useSearches(saveId);
  const candidates = useCandidates(saveId);
  const error = hiring.error ?? meta.error ?? searches.error ?? candidates.error;
  if (error) return <LoadError title="Could not load recruitment" error={error} />;
  if (!hiring.data || !meta.data || !searches.data || !candidates.data) return <Loading />;
  return (
    <RecruitmentBody
      saveId={saveId}
      hiring={hiring.data}
      meta={meta.data}
      searches={searches.data}
      candidates={candidates.data}
    />
  );
}

function RecruitmentBody({
  saveId,
  hiring,
  meta,
  searches,
  candidates,
}: {
  saveId: string;
  hiring: HiringMeta;
  meta: NewGameMeta;
  searches: Search[];
  candidates: Person[];
}) {
  const [params, setParams] = useSearchParams();
  const [offerTo, setOfferTo] = useState<number | null>(null);
  const check = useCheckCandidate(saveId);
  const withdraw = useWithdrawOffer(saveId);

  const paramSearch = Number(params.get('search'));
  const selected =
    searches.find((s) => s.search_id === paramSearch) ??
    searches.find((s) => s.open_candidates > 0) ??
    searches[0];
  const rows = useMemo(
    () => candidates.filter((c) => c.candidacy?.search_id === selected?.search_id),
    [candidates, selected],
  );
  const offerCandidate = rows.find((c) => c.person_id === offerTo) ?? null;
  const role = hiring.roles.find((r) => r.key === selected?.role);
  const keySkills = useMemo(
    () => (role ? [...role.primary_skills, ...role.secondary_skills.slice(0, 1)] : []),
    [role],
  );
  const interestLabel = useMemo(
    () => new Map(meta.interests.map((i) => [i.key, i.label])),
    [meta.interests],
  );

  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Name',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <Link
              to={`/game/${saveId}/people/${row.original.person_id}`}
              style={{ fontWeight: 600, textDecoration: 'none' }}
            >
              {row.original.name}
            </Link>
          ),
        }),
        helper.accessor((p) => p.level ?? '', {
          id: 'level',
          header: 'Level',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span style={{ color: 'var(--tst-text-2)' }}>{humanize(getValue())}</span>
          ),
        }),
        helper.accessor('age', {
          header: 'Age',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
        helper.accessor((p) => p.candidacy?.salary_expectation_cents ?? 0, {
          id: 'asks',
          header: 'Asks',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        ...keySkills.map((key) =>
          helper.accessor(
            (p) => {
              const r = p.skills.find((s) => s.key === key)?.range;
              return r ? r.min + r.max : 0; // midpoint order, display only
            },
            {
              id: key,
              header: meta.skills.find((s) => s.key === key)?.label ?? key,
              sortFn: 'basic',
              sortDescFirst: true,
              cell: ({ row }) => {
                const attr = row.original.skills.find((s) => s.key === key);
                return attr ? <AttributeRange range={attr.range} label={attr.label} /> : null;
              },
            },
          ),
        ),
        helper.display({
          id: 'interests',
          header: 'Interests',
          cell: ({ row }) =>
            row.original.interests === null ? (
              <span className="tst-muted" style={{ fontSize: 13, fontStyle: 'italic' }}>
                Interview to learn
              </span>
            ) : (
              <span style={{ fontSize: 13 }}>
                {row.original.interests.map((k) => interestLabel.get(k) ?? k).join(', ')}
              </span>
            ),
        }),
        helper.accessor((p) => knownText(p), {
          id: 'known',
          header: 'Known',
          sortFn: 'alphanumeric',
        }),
        helper.display({
          id: 'actions',
          header: 'Actions',
          cell: ({ row }) => {
            const p = row.original;
            const pending = p.candidacy?.pending_offer;
            if (pending) {
              return (
                <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span
                    style={{ fontSize: 13, color: 'var(--tst-link)' }}
                    data-testid="offer-pending"
                  >
                    Offer pending · answer in {pending.answer_date_label}
                  </span>
                  <Button
                    size="compact-sm"
                    variant="subtle"
                    onClick={() => withdraw.mutate(pending.offer_id)}
                  >
                    Withdraw
                  </Button>
                </span>
              );
            }
            return (
              <span style={{ display: 'flex', gap: 6 }}>
                <Button
                  size="compact-sm"
                  variant="default"
                  onClick={() => check.mutate({ candidateId: p.person_id, kind: 'interview' })}
                  data-testid="interview"
                >
                  Interview · {hiring.interview_energy}
                </Button>
                <Button
                  size="compact-sm"
                  variant="default"
                  onClick={() => check.mutate({ candidateId: p.person_id, kind: 'refs' })}
                  data-testid="references"
                >
                  References · {hiring.reference_check_energy}
                </Button>
                <Button
                  size="compact-sm"
                  variant="default"
                  style={{ borderColor: '#3B5A80' }}
                  onClick={() => setOfferTo(p.person_id)}
                  data-testid="offer"
                >
                  Offer
                </Button>
              </span>
            );
          },
        }),
      ]),
    [saveId, keySkills, meta.skills, hiring, check, withdraw, interestLabel],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (p) => String(p.person_id),
  });

  return (
    <>
      <ScreenTitle>Recruitment</ScreenTitle>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <OpenSearchPanel
          saveId={saveId}
          hiring={hiring}
          initialRole={params.get('role')}
          onOpened={(id) => setParams({ search: String(id) }, { replace: true })}
        />
        <Panel
          title="Your searches"
          style={{ flex: '2 1 460px', display: 'flex', flexDirection: 'column', gap: 10 }}
        >
          {searches.length === 0 ? (
            <p className="tst-muted" style={{ margin: 0, fontSize: 14 }}>
              No searches yet. Open one to find candidates.
            </p>
          ) : (
            searches.map((s) => (
              <SearchRow
                key={s.search_id}
                saveId={saveId}
                search={s}
                hiring={hiring}
                selected={s.search_id === selected?.search_id}
                onSelect={() => setParams({ search: String(s.search_id) }, { replace: true })}
              />
            ))
          )}
        </Panel>
      </div>
      {check.error && (
        <Alert color="red" title="Could not do that" withCloseButton onClose={check.reset}>
          {check.error.message}
        </Alert>
      )}
      {selected && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
          <section
            aria-label="Candidates"
            style={{
              flex: '3 1 640px',
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 10 }}>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>
                {selected.role_label} · {humanize(selected.channel)}
              </h2>
              <span className="tst-muted" style={{ fontSize: 13 }}>
                {rows.length} candidate{rows.length === 1 ? '' : 's'} · each stays{' '}
                {hiring.candidate_shelf_turns} months
              </span>
            </div>
            <DataTable
              table={table}
              label="Candidates"
              rowTestId="candidate-row"
              selectedRowId={offerTo === null ? undefined : String(offerTo)}
              empty={
                selected.next_batch_date_label
                  ? `Candidates arrive in ${selected.next_batch_date_label}. Press Continue.`
                  : 'No candidates left from this search.'
              }
            />
            <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
              Interviews narrow skill and personality ranges and reveal interests. References narrow
              personality. Asking salaries are exact.
            </p>
          </section>
          {offerCandidate && (
            <OfferPanel
              key={offerCandidate.person_id}
              saveId={saveId}
              hiring={hiring}
              candidate={offerCandidate}
              onClose={() => setOfferTo(null)}
            />
          )}
        </div>
      )}
    </>
  );
}

function OpenSearchPanel({
  saveId,
  hiring,
  initialRole,
  onOpened,
}: {
  saveId: string;
  hiring: HiringMeta;
  initialRole: string | null;
  onOpened: (searchId: number) => void;
}) {
  const open = useOpenSearch(saveId);
  const [role, setRole] = useState<string | null>(
    hiring.roles.find((r) => r.key === initialRole)?.key ?? hiring.roles[0]?.key ?? null,
  );
  const [channel, setChannel] = useState('job_post');
  const chosen = hiring.channels.find((c) => c.key === channel);
  return (
    <Panel
      title="Open a search"
      style={{ flex: '1 1 340px', display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      <Select
        label="Role"
        value={role}
        onChange={setRole}
        allowDeselect={false}
        data={[...hiring.roles]
          .sort((a, b) => a.label.localeCompare(b.label))
          .map((r) => ({ value: r.key, label: r.label }))}
        data-testid="search-role"
      />
      <div
        role="radiogroup"
        aria-label="Channel"
        style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        <span style={{ fontSize: 14, fontWeight: 500 }}>Channel</span>
        {hiring.channels.map((c) => (
          <button
            key={c.key}
            type="button"
            role="radio"
            aria-checked={channel === c.key}
            className="tst-card"
            onClick={() => setChannel(c.key)}
            data-testid={`channel-${c.key}`}
            style={{ padding: '10px 12px', gap: 2 }}
          >
            <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontWeight: 600 }}>{c.label}</span>
              <span className="tst-num tst-muted" style={{ fontSize: 12 }}>
                {c.energy} energy
              </span>
            </span>
            <span style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>{channelCost(c)}</span>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {levelText(c)} {CHANNEL_TEXT[c.key] ?? ''}
            </span>
          </button>
        ))}
      </div>
      {open.error && (
        <Alert color="red" title="Could not open the search" withCloseButton onClose={open.reset}>
          {open.error.message}
        </Alert>
      )}
      <Button
        h={44}
        disabled={!role || !chosen}
        loading={open.isPending}
        data-testid="open-search"
        onClick={() => {
          if (role) {
            open.mutate({ role, channel }, { onSuccess: (search) => onOpened(search.search_id) });
          }
        }}
      >
        {SUBMIT_TEXT[channel] ?? 'Open search'} · {chosen?.energy ?? 0} energy
      </Button>
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        {open.isSuccess ? 'Search opened. ' : ''}Candidates arrive next month.
      </p>
    </Panel>
  );
}

function SearchRow({
  saveId,
  search,
  hiring,
  selected,
  onSelect,
}: {
  saveId: string;
  search: Search;
  hiring: HiringMeta;
  selected: boolean;
  onSelect: () => void;
}) {
  const close = useCloseSearch(saveId);
  const channel = hiring.channels.find((c) => c.key === search.channel);
  const isOpen = search.status === 'open';
  let detail: string;
  if (!isOpen) {
    detail = channel?.repeats
      ? `Closed in ${search.closed_date_label ?? ''}; candidates stay until they expire`
      : 'Closed after one batch';
  } else if (channel?.repeats) {
    detail = `Open since ${search.opened_date_label} · ${formatMoneyWhole(search.monthly_cost_cents)} per month`;
  } else {
    detail = `Batch arrives in ${search.next_batch_date_label ?? ''}`;
  }
  let count = isOpen ? 'pending' : 'none left';
  if (search.open_candidates > 0) {
    count = `${search.open_candidates} candidate${search.open_candidates === 1 ? '' : 's'}`;
  }
  return (
    <div
      data-testid="search-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        border: `1px solid ${selected ? '#3B5A80' : 'var(--tst-rule)'}`,
        background: selected ? 'var(--tst-accent-bg)' : undefined,
        borderRadius: 8,
      }}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        style={{
          all: 'unset',
          cursor: 'pointer',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          flex: 1,
          minWidth: 0,
        }}
      >
        <span style={{ fontWeight: 600 }}>
          {humanize(search.channel)} · {search.role_label}
        </span>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          {detail}
        </span>
      </button>
      <span className="tst-num" style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>
        {count}
      </span>
      {isOpen && channel?.repeats && (
        <Button
          size="compact-sm"
          variant="default"
          loading={close.isPending}
          onClick={() => close.mutate(search.search_id)}
        >
          Close
        </Button>
      )}
    </div>
  );
}

const HINTS = {
  likely: {
    text: 'Likely to accept',
    color: 'var(--tst-good)',
    bg: 'var(--tst-good-bg)',
    border: '#2B5A3A',
  },
  uncertain: {
    text: 'Uncertain',
    color: 'var(--tst-text)',
    bg: 'var(--tst-grey-bg)',
    border: 'var(--tst-border)',
  },
  unlikely: {
    text: 'Unlikely to accept',
    color: 'var(--tst-warn)',
    bg: 'var(--tst-warn-bg)',
    border: '#6A4426',
  },
} as const;

function OfferPanel({
  saveId,
  hiring,
  candidate,
  onClose,
}: {
  saveId: string;
  hiring: HiringMeta;
  candidate: Person;
  onClose: () => void;
}) {
  const ask = candidate.candidacy?.salary_expectation_cents ?? 0;
  const [salaryDollars, setSalaryDollars] = useState(Math.round(ask / 100));
  const [equityBp, setEquityBp] = useState(0);
  const salaryCents = salaryDollars * 100;
  const terms = useMemo(() => ({ salaryCents, equityBp }), [salaryCents, equityBp]);
  const [debounced] = useDebouncedValue(terms, PREVIEW_DEBOUNCE_MS);
  const preview = useOfferPreview(
    saveId,
    candidate.person_id,
    debounced.salaryCents,
    debounced.equityBp,
  );
  const offer = useMakeOffer(saveId);
  const current = debounced === terms && !preview.isFetching && !preview.isPlaceholderData;
  const p = preview.data;
  const hint = p && p.hint in HINTS ? HINTS[p.hint as keyof typeof HINTS] : undefined;
  const canSend = current && p !== undefined && p.problems.length === 0 && salaryCents > 0;
  const lowballPct = Math.round(hiring.lowball_ratio * 100);

  return (
    <aside
      className="tst-panel"
      aria-label="Make an offer"
      style={{
        flex: '1 1 300px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        borderColor: '#3B5A80',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Offer to {candidate.name}</h2>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {candidate.role_label} · {humanize(candidate.level ?? '')} · asks {formatMoneyWhole(ask)}
        </span>
      </div>
      <NumberInput
        label="Annual salary"
        prefix="$"
        thousandSeparator=","
        allowDecimal={false}
        allowNegative={false}
        value={salaryDollars}
        onChange={(v) => setSalaryDollars(typeof v === 'number' ? v : 0)}
        classNames={{ input: 'tst-num' }}
        data-testid="offer-salary"
        description={
          p
            ? `${formatRatio(p.ratio)} their ask. Below ${formatMoneyWhole(p.floor_cents)} (${lowballPct}%) they always decline.`
            : ' '
        }
        inputWrapperOrder={['label', 'input', 'description', 'error']}
      />
      <NumberInput
        label="Equity (basis points)"
        allowDecimal={false}
        allowNegative={false}
        value={equityBp}
        onChange={(v) => setEquityBp(typeof v === 'number' ? v : 0)}
        classNames={{ input: 'tst-num' }}
        data-testid="offer-equity"
        description={`${equityBp} bp = ${formatBpPercent(equityBp)} of the company${p ? ` · ${p.option_pool_left_bp} bp left in the pool` : ''}`}
        inputWrapperOrder={['label', 'input', 'description', 'error']}
      />
      {hint && p && (
        <div
          data-testid="offer-hint"
          data-hint={p.hint}
          style={{
            background: hint.bg,
            border: `1px solid ${hint.border}`,
            borderRadius: 8,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            opacity: current ? 1 : 0.6,
          }}
        >
          <span className="tst-ptitle" style={{ margin: 0 }}>
            Your read
          </span>
          <span style={{ fontSize: 18, fontWeight: 700, color: hint.color }}>{hint.text}</span>
          <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--tst-text-2)' }}>
            {p.reasons.join(' ')} Based only on what you have learned.
          </span>
        </div>
      )}
      {preview.error && <LoadError title="Could not preview the offer" error={preview.error} />}
      {p && p.problems.length > 0 && (
        <Alert color="warn" title="This offer breaks a rule" data-testid="offer-problems">
          {p.problems.join('; ')}
        </Alert>
      )}
      {offer.error && (
        <Alert color="red" title="Could not send the offer">
          {offer.error.message}
        </Alert>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Button
          h={44}
          disabled={!canSend}
          loading={offer.isPending}
          data-testid="send-offer"
          onClick={() =>
            offer.mutate(
              { candidateId: candidate.person_id, salaryCents, equityBp },
              { onSuccess: onClose },
            )
          }
        >
          Send offer
        </Button>
        <Button h={44} variant="default" onClick={onClose}>
          Cancel
        </Button>
      </div>
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        They answer when you press Continue.{' '}
        {hiring.offer_energy === 0
          ? 'Offers cost no energy.'
          : `Offers cost ${hiring.offer_energy} energy.`}
      </p>
    </aside>
  );
}
