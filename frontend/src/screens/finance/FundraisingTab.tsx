import { Alert, Button, NumberInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState, type ReactNode } from 'react';
import { DataTable } from '../../components/DataTable';
import { DilutionPreview } from '../../components/DilutionPreview';
import { IpoPanel } from '../../components/IpoPanel';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import {
  useAcceptBridge,
  useAcceptTermSheet,
  useFinanceSummary,
  useRaiseSafe,
  useRounds,
  useSafeHint,
  useSafes,
  useStartRound,
  useTermSheetPreview,
  type FinanceSummary,
  type Round,
  type Rounds,
  type Safe,
  type Safes,
  type TermSheet,
} from '../../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../../lib/format';
import {
  SAFE_HINTS,
  STATUS_TEXT,
  formatFraction,
  formatSharePrice,
  formatShares,
} from '../../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const PREVIEW_DEBOUNCE_MS = 250;
const helper = createColumnHelper<GameTableFeatures, TermSheet>();
const right = { display: 'block', textAlign: 'right' } as const;

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="tst-muted" style={{ fontSize: 13 }}>
        {label}
      </div>
      <div className="tst-num" style={{ fontSize: 17 }}>
        {children}
      </div>
    </div>
  );
}

function typical(next: Rounds['next']): string {
  if (next.typical_min_cents === null || next.typical_max_cents === null) return '—';
  return `${formatMoneyShort(next.typical_min_cents)}–${formatMoneyShort(next.typical_max_cents)}`;
}

function OpenRound({ round, next }: { round: Round; next: Rounds['next'] }) {
  const accepted = round.status === 'accepted';
  return (
    <section
      className="tst-panel"
      aria-label="Open round"
      style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'center' }}
      data-testid="open-round"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 260px' }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          {round.series_label} · {accepted ? 'closing at Continue' : 'open'}
        </h2>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          Started {round.opened_label} with a {formatMoneyShort(round.target_cents)} target ·{' '}
          {accepted
            ? 'a term sheet is accepted; the money arrives when you press Continue'
            : round.term_sheets.length === 0
              ? 'term sheets arrive when you press Continue'
              : `closes without a deal at the end of ${round.expires_label}`}
        </span>
      </div>
      <Stat label="ARR">
        {formatMoneyShort(next.arr_cents)}
        {next.gate_arr_cents !== null && (
          <span className="tst-muted" style={{ fontSize: 12 }}>
            {' '}
            gate {formatMoneyShort(next.gate_arr_cents)}
          </span>
        )}
      </Stat>
      <Stat label={`Typical ${round.series_label}`}>{typical(next)}</Stat>
      <Stat label="Term sheets">
        {round.term_sheets.length} of {round.firms_asked} firms
      </Stat>
    </section>
  );
}

function TermSheets({
  round,
  selected,
  onSelect,
}: {
  round: Round;
  selected: number | null;
  onSelect: (sheetId: number) => void;
}) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('firm_name', {
          header: 'Firm',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <span style={{ fontWeight: 600 }}>{getValue()}</span>,
        }),
        helper.accessor('pre_money_cents', {
          header: 'Pre-money',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatMoneyShort(getValue())}
            </span>
          ),
        }),
        helper.accessor('amount_cents', {
          header: 'Amount',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatMoneyShort(getValue())}
            </span>
          ),
        }),
        helper.accessor('post_money_cents', {
          header: 'Post-money',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatMoneyShort(getValue())}
            </span>
          ),
        }),
        helper.accessor((t) => t.founder_fraction_after ?? undefined, {
          id: 'own',
          header: 'You own after',
          sortFn: 'basic',
          sortUndefined: 'last',
          cell: ({ getValue }) => {
            const v = getValue();
            return (
              <span className="tst-num" style={right} data-testid="sheet-own-after">
                {v === undefined ? '—' : formatFraction(v)}
              </span>
            );
          },
        }),
        helper.display({
          id: 'seat',
          header: 'Board seat',
          cell: () => <span style={{ color: 'var(--tst-text-2)' }}>Yes, one</span>,
        }),
        helper.accessor('expires_turn', {
          header: 'Expires',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num" style={{ color: 'var(--tst-text-2)' }}>
              {row.original.status === 'offered'
                ? row.original.expires_label
                : (STATUS_TEXT[row.original.status] ?? row.original.status)}
            </span>
          ),
        }),
        helper.display({
          id: 'preview',
          header: '',
          cell: ({ row }) =>
            row.original.status === 'offered' ? (
              <Button
                size="xs"
                variant={row.original.sheet_id === selected ? 'filled' : 'default'}
                onClick={() => onSelect(row.original.sheet_id)}
                data-testid="preview-sheet"
              >
                {row.original.sheet_id === selected ? 'Previewing' : 'Preview'}
              </Button>
            ) : null,
        }),
      ]),
    [selected, onSelect],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: round.term_sheets,
    getRowId: (t) => String(t.sheet_id),
  });
  return (
    <section aria-label="Term sheets" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Term sheets</h2>
      <DataTable
        table={table}
        label="Term sheets"
        rowTestId="sheet-row"
        selectedRowId={selected === null ? undefined : String(selected)}
        empty="No term sheets yet: firms answer when you press Continue."
      />
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Standard terms for every sheet: 1× non-participating liquidation preference, pro rata
        rights, one board seat for the lead, and an option pool top-up to 10% after the round.
      </p>
    </section>
  );
}

function SheetPreview({
  saveId,
  sheetId,
  onCancel,
  disabledReason,
}: {
  saveId: string;
  sheetId: number;
  onCancel: () => void;
  disabledReason: string | null;
}) {
  const preview = useTermSheetPreview(saveId, sheetId);
  const accept = useAcceptTermSheet(saveId);
  if (preview.isPending) return <Loading label="Loading the dilution preview" />;
  if (preview.error)
    return <LoadError title="Could not preview the term sheet" error={preview.error} />;
  return (
    <DilutionPreview
      preview={preview.data}
      onAccept={(nomineeId) => accept.mutate({ sheetId, nomineeId }, { onSuccess: onCancel })}
      onCancel={onCancel}
      accepting={accept.isPending}
      error={accept.error}
      disabledReason={disabledReason}
    />
  );
}

function StartRound({ saveId, next }: { saveId: string; next: Rounds['next'] }) {
  const [targetDollars, setTargetDollars] = useState<number>(
    next.typical_min_cents === null ? 0 : Math.round(next.typical_min_cents / 100),
  );
  const start = useStartRound(saveId);
  if (next.series === null) {
    return (
      <Panel title="Start a priced round">
        <p className="tst-muted" style={{ margin: 0 }}>
          {next.problem ?? 'There is no round after Series B yet.'}
        </p>
      </Panel>
    );
  }
  return (
    <Panel title={`Start a ${next.series_label}`} label="Start a round">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          Typical {next.series_label}: {typical(next)}. ARR now {formatMoneyShort(next.arr_cents)}
          {next.gate_arr_cents !== null ? ` · needs ${formatMoneyShort(next.gate_arr_cents)}` : ''}.
        </span>
        <NumberInput
          label="Target amount"
          prefix="$"
          thousandSeparator=","
          allowDecimal={false}
          allowNegative={false}
          value={targetDollars}
          onChange={(v) => setTargetDollars(typeof v === 'number' ? v : 0)}
          classNames={{ input: 'tst-num' }}
          data-testid="round-target"
        />
        {!next.allowed && next.problem && (
          <Alert color="warn" data-testid="round-gate">
            {next.problem}
          </Alert>
        )}
        {start.error && <Alert color="red">{start.error.message}</Alert>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <Button
            h={44}
            disabled={!next.allowed || targetDollars <= 0}
            loading={start.isPending}
            onClick={() =>
              start.mutate({ series: next.series ?? '', target_cents: targetDollars * 100 })
            }
            data-testid="start-round"
          >
            Start {next.series_label} · {next.energy_cost} energy
          </Button>
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Firms answer with term sheets when you press Continue; the round stays open for{' '}
            {next.open_turns} months.
          </span>
        </div>
      </div>
    </Panel>
  );
}

function RaiseSafe({ saveId, safes }: { saveId: string; safes: Safes }) {
  const [amountDollars, setAmountDollars] = useState<number>(500_000);
  const [capDollars, setCapDollars] = useState<number>(5_000_000);
  const terms = useMemo(
    () => ({ amount: amountDollars * 100, cap: capDollars * 100 }),
    [amountDollars, capDollars],
  );
  const [debounced] = useDebouncedValue(terms, PREVIEW_DEBOUNCE_MS);
  const hint = useSafeHint(saveId, debounced.amount, debounced.cap);
  const raise = useRaiseSafe(saveId);
  const h = hint.data;
  const current = debounced === terms && !hint.isFetching && !hint.isPlaceholderData;
  const band = h ? SAFE_HINTS[h.hint] : undefined;
  const blocked =
    safes.blocked ?? (safes.open ? 'Investors answer your open SAFE at Continue.' : null);
  const canRaise = current && h !== undefined && h.problems.length === 0 && blocked === null;
  return (
    <Panel title="Raise on a SAFE" style={{ flex: '2 1 320px' }} label="Raise on a SAFE">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <NumberInput
          label="Amount"
          prefix="$"
          thousandSeparator=","
          allowDecimal={false}
          allowNegative={false}
          value={amountDollars}
          onChange={(v) => setAmountDollars(typeof v === 'number' ? v : 0)}
          classNames={{ input: 'tst-num' }}
          description={`${formatMoneyWhole(safes.min_cents)} to ${formatMoneyWhole(safes.max_cents)}`}
          inputWrapperOrder={['label', 'input', 'description', 'error']}
          data-testid="safe-amount"
        />
        <NumberInput
          label="Post-money valuation cap"
          prefix="$"
          thousandSeparator=","
          allowDecimal={false}
          allowNegative={false}
          value={capDollars}
          onChange={(v) => setCapDollars(typeof v === 'number' ? v : 0)}
          classNames={{ input: 'tst-num' }}
          description={
            h ? `The holders get ${formatFraction(h.fraction)} at your next priced round` : ' '
          }
          inputWrapperOrder={['label', 'input', 'description', 'error']}
          data-testid="safe-cap"
        />
        {band && h && (
          <div
            data-testid="safe-hint"
            data-hint={h.hint}
            style={{
              background: band.bg,
              border: `1px solid ${band.border}`,
              borderRadius: 8,
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              opacity: current ? 1 : 0.6,
            }}
          >
            <span className="tst-ptitle" style={{ margin: 0 }}>
              Your read
            </span>
            <span style={{ fontSize: 16, fontWeight: 700, color: band.color }}>{band.label}</span>
            <span style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>
              Angels answer once at Continue: all of it or nothing. A lower cap is likelier to fill
              and gives them more of the company.
            </span>
          </div>
        )}
        {hint.error && <LoadError title="Could not read the SAFE" error={hint.error} />}
        {h && h.problems.length > 0 && (
          <Alert color="warn" data-testid="safe-problems">
            {h.problems.join('; ')}
          </Alert>
        )}
        {raise.error && <Alert color="red">{raise.error.message}</Alert>}
        <Button
          h={44}
          style={{ alignSelf: 'flex-start' }}
          disabled={!canRaise}
          loading={raise.isPending}
          onClick={() => raise.mutate({ amount_cents: terms.amount, cap_cents: terms.cap })}
          data-testid="raise-safe"
        >
          Raise · {safes.energy_cost} energy
        </Button>
        {blocked && (
          <span className="tst-muted" style={{ fontSize: 12 }} data-testid="safe-blocked">
            {blocked}
          </span>
        )}
      </div>
    </Panel>
  );
}

function Bridge({ saveId, summary }: { saveId: string; summary: FinanceSummary }) {
  const accept = useAcceptBridge(saveId);
  if (summary.open_bridge_id === null || summary.open_bridge_id === undefined) return null;
  const bridgeId = summary.open_bridge_id;
  return (
    <section
      className="tst-panel"
      aria-label="Bridge offer"
      id="bridge"
      style={{ borderColor: 'var(--tst-warn)', display: 'flex', flexDirection: 'column', gap: 10 }}
      data-testid="bridge-offer"
    >
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Your investors offer a bridge</h2>
      <span style={{ fontSize: 14, color: 'var(--tst-text-2)' }}>
        A SAFE of{' '}
        <span className="tst-num" data-testid="bridge-amount">
          {formatMoneyWhole(summary.open_bridge_amount_cents ?? 0)}
        </span>{' '}
        if you accept now: three months of this month&apos;s burn plus what gets cash back to zero.
        Accept by {summary.open_bridge_expires_label}; the money arrives when you press Continue.
      </span>
      {accept.error && <Alert color="red">{accept.error.message}</Alert>}
      <Button
        h={44}
        color="warn"
        style={{ alignSelf: 'flex-start' }}
        loading={accept.isPending}
        onClick={() => accept.mutate(bridgeId)}
        data-testid="accept-bridge"
      >
        Accept the bridge · {summary.bridge_energy} energy
      </Button>
    </section>
  );
}

function safeLine(s: Safe, rounds: Round[]): { text: string; outcome: string } {
  const name = s.kind === 'bridge' ? 'Bridge SAFE' : 'SAFE';
  const converted = rounds.find((r) => r.round_id === s.converted_round_id);
  const outcome =
    s.status === 'converted' && converted
      ? `Converted at the ${converted.series_label.toLowerCase()}`
      : (STATUS_TEXT[s.status] ?? s.status);
  return {
    text: `${name} · ${formatMoneyWhole(s.amount_cents)} at a ${formatMoneyShort(s.cap_cents)} post-money cap · ${s.raised_label}`,
    outcome,
  };
}

function roundLine(r: Round): { text: string; outcome: string } {
  if (r.status !== 'closed') {
    return {
      text: `${r.series_label} · ${formatMoneyShort(r.target_cents)} target · ${r.opened_label}`,
      outcome: STATUS_TEXT[r.status] ?? r.status,
    };
  }
  return {
    text: `${r.series_label} · ${formatMoneyWhole(r.amount_cents ?? 0)} at ${formatMoneyShort(r.pre_money_cents ?? 0)} pre · ${r.lead_name ?? ''} · ${r.closed_label ?? ''}`,
    outcome: `${formatSharePrice(r.share_price_dollars)} a share · ${formatShares(r.new_shares ?? 0)} new shares${r.down_round ? ' · down round' : ''}`,
  };
}

function Past({ rounds, safes }: { rounds: Round[]; safes: Safe[] }) {
  const past = rounds.filter((r) => r.status !== 'open' && r.status !== 'accepted');
  const items = [
    ...past.map((r) => ({ key: `r${r.round_id}`, turn: r.opened_turn, ...roundLine(r) })),
    ...safes
      .filter((s) => s.status !== 'offered')
      .map((s) => ({ key: `s${s.safe_id}`, turn: s.raised_turn, ...safeLine(s, rounds) })),
  ].sort((a, b) => b.turn - a.turn);
  return (
    <Panel title="Past rounds and SAFEs" label="Past rounds">
      {items.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0 }}>
          Nothing raised yet.
        </p>
      ) : (
        items.map((item, i) => (
          <div
            key={item.key}
            className="tst-row"
            style={{ borderBottom: i === items.length - 1 ? 0 : undefined, flexWrap: 'wrap' }}
            data-testid="past-item"
          >
            <span>{item.text}</span>
            <span className="tst-muted">{item.outcome}</span>
          </div>
        ))
      )}
    </Panel>
  );
}

export function FundraisingTab({ saveId }: { saveId: string }) {
  const rounds = useRounds(saveId);
  const safes = useSafes(saveId);
  const summary = useFinanceSummary(saveId);
  const [selected, setSelected] = useState<number | null>(null);
  if (rounds.isPending || safes.isPending || summary.isPending) return <Loading />;
  if (rounds.error || safes.error || summary.error) {
    return (
      <LoadError
        title="Could not load fundraising"
        error={rounds.error ?? safes.error ?? summary.error}
      />
    );
  }
  const open = rounds.data.rounds.find((r) => r.status === 'open' || r.status === 'accepted');
  const offered = open?.term_sheets.filter((t) => t.status === 'offered') ?? [];
  const sheetId = offered.some((t) => t.sheet_id === selected) ? selected : null;
  const ended = summary.data.game_state !== 'active' ? 'The game is over.' : null;
  return (
    <>
      <Bridge saveId={saveId} summary={summary.data} />
      <IpoPanel saveId={saveId} />
      {open && <OpenRound round={open} next={rounds.data.next} />}
      {open && open.term_sheets.length > 0 && (
        <TermSheets round={open} selected={sheetId} onSelect={setSelected} />
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <div
          style={{
            flex: '3 1 520px',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {sheetId !== null && (
            <SheetPreview
              saveId={saveId}
              sheetId={sheetId}
              onCancel={() => setSelected(null)}
              disabledReason={ended}
            />
          )}
          {!open && <StartRound saveId={saveId} next={rounds.data.next} />}
          {open && sheetId === null && open.status === 'open' && offered.length > 0 && (
            <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
              Preview a term sheet to see what you would own after it closes.
            </p>
          )}
        </div>
        <RaiseSafe saveId={saveId} safes={safes.data} />
      </div>
      <Past rounds={rounds.data.rounds} safes={safes.data.safes} />
    </>
  );
}
