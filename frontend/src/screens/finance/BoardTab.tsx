import { Alert, Button, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { BoardMemberCard } from '../../components/BoardMemberCard';
import { DataTable } from '../../components/DataTable';
import { Sparkline } from '../../components/Sparkline';
import { KpiTile } from '../../components/KpiTile';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { useBoard, useNameNominee, type Board, type Director } from '../../hooks/api';
import { confidenceColor, formatGrowth, labelText, seatsText } from '../../lib/finance';
import { formatWhole } from '../../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, Director>();

function seatText(d: Director): string {
  if (d.kind === 'common') {
    if (d.is_founder) return 'Common · founder';
    return d.vacant ? 'Common · empty' : 'Common · your nominee';
  }
  if (d.kind === 'independent') return 'Independent';
  return `Investor · ${d.firm_name ?? ''}`;
}

function Confidence({ d, board }: { d: Director; board: Board }) {
  if (d.confidence === null || d.confidence === undefined) {
    return <span className="tst-muted">—</span>;
  }
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="tst-num" style={{ width: 24 }} data-testid="director-confidence">
        {formatWhole(d.confidence)}
      </span>
      <span
        aria-hidden="true"
        style={{ width: 90, height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
      >
        <span
          style={{
            display: 'block',
            height: 6,
            borderRadius: 3,
            width: `${Math.min(100, d.confidence)}%`,
            background: confidenceColor(d.confidence, board.removal_below, board.warning_below),
          }}
        />
      </span>
      <span style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>{labelText(d.label)}</span>
    </span>
  );
}

/** Name an employee to an empty common seat (M4c). */
function NameNominee({ saveId, board, seatId }: { saveId: string; board: Board; seatId: number }) {
  const name = useNameNominee(saveId);
  const first = board.nominee_choices.find((c) => c.default) ?? board.nominee_choices[0];
  const [person, setPerson] = useState<string | null>(first ? String(first.person_id) : null);
  if (board.nominee_choices.length === 0) {
    return (
      <span className="tst-muted" style={{ fontSize: 13 }}>
        Hire someone to name them to this seat. Until then it still votes with you.
      </span>
    );
  }
  return (
    <span style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
      <Select
        aria-label="Nominee"
        size="xs"
        value={person}
        onChange={setPerson}
        allowDeselect={false}
        data={board.nominee_choices.map((c) => ({
          value: String(c.person_id),
          label: `${c.name} · ${c.role_label}, ${c.level}`,
        }))}
        data-testid="name-nominee-select"
      />
      <Button
        size="compact-sm"
        disabled={!person}
        loading={name.isPending}
        onClick={() => person && name.mutate({ seatId, personId: Number(person) })}
        data-testid="name-nominee"
      >
        Name nominee · {board.nominee_energy} energy
      </Button>
      {name.error && (
        <Alert color="red" style={{ flexBasis: '100%' }}>
          {name.error.message}
        </Alert>
      )}
    </span>
  );
}

function Directors({ saveId, board }: { saveId: string; board: Board }) {
  const [cardSeat, setCardSeat] = useState<number | null>(null);
  const card = board.directors.find((d) => d.seat_id === cardSeat && !d.is_employee && !d.vacant);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Director',
          sortFn: 'alphanumeric',
          cell: ({ row }) => {
            const d = row.original;
            if (d.is_founder) return <span style={{ fontWeight: 600 }}>{d.name} (you)</span>;
            if (d.vacant) {
              return (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span className="tst-muted" style={{ fontStyle: 'italic' }}>
                    {d.name}
                  </span>
                  <NameNominee saveId={saveId} board={board} seatId={d.seat_id} />
                </span>
              );
            }
            if (d.is_employee) {
              return (
                <Link
                  to={`/game/${saveId}/people/${d.person_id}`}
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  {d.name}
                </Link>
              );
            }
            // Investor and independent directors are not employees: a card, not a profile.
            return (
              <button
                type="button"
                onClick={() => setCardSeat(d.seat_id)}
                data-testid="director-name"
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  fontWeight: 600,
                  color: 'var(--tst-link)',
                }}
              >
                {d.name}
              </button>
            );
          },
        }),
        helper.accessor((d) => seatText(d), {
          id: 'seat',
          header: 'Seat',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <span style={{ color: 'var(--tst-text-2)' }}>{getValue()}</span>,
        }),
        helper.accessor('seated_label', {
          header: 'Since',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span className="tst-num" style={{ color: 'var(--tst-text-2)' }}>
              {getValue()}
            </span>
          ),
        }),
        helper.accessor((d) => d.confidence ?? undefined, {
          id: 'confidence',
          header: 'Confidence',
          sortFn: 'basic',
          sortUndefined: 'last',
          cell: ({ row }) => <Confidence d={row.original} board={board} />,
        }),
        helper.display({
          id: 'trend',
          header: 'Recent months',
          meta: { term: 'trend_board' },
          cell: ({ row }) =>
            row.original.confidence === null || row.original.confidence === undefined ? (
              <span className="tst-muted">—</span>
            ) : (
              <Sparkline
                values={row.original.history}
                label={`${row.original.name}'s confidence over the last ${row.original.history.length} month ends, now ${formatWhole(row.original.confidence)}`}
              />
            ),
        }),
        helper.accessor('months_below', {
          header: `Months below ${formatWhole(board.removal_below)}`,
          sortFn: 'basic',
          cell: ({ row }) =>
            row.original.confidence === null || row.original.confidence === undefined ? (
              <span className="tst-muted">—</span>
            ) : (
              <span
                className="tst-num"
                style={{
                  color: row.original.months_below > 0 ? 'var(--tst-warn)' : undefined,
                }}
              >
                {row.original.months_below}
              </span>
            ),
        }),
      ]),
    [saveId, board],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: board.directors,
    getRowId: (d) => String(d.seat_id),
  });
  return (
    <>
      <DataTable table={table} label="Directors" rowTestId="director-row" />
      {card && <BoardMemberCard director={card} onClose={() => setCardSeat(null)} />}
    </>
  );
}

const TREND_TEXT: Record<string, string> = {
  rising: 'rising',
  steady: 'steady',
  slipping: 'slipping',
};

function Tiles({ board }: { board: Board }) {
  const avg = board.average_confidence;
  const trend = board.trend ? TREND_TEXT[board.trend] : null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <KpiTile
        term="kpi.board_confidence"
        label="Board confidence"
        value={avg === null ? '—' : `${labelText(board.label)} ${formatWhole(avg)}`}
        note={`Average of the investor directors${trend ? ` · ${trend}` : ''}`}
        warn={avg !== null && avg < board.warning_below}
        testId="kpi-confidence"
      />
      <KpiTile
        term="kpi.board_seats"
        label="Seats"
        value={seatsText(board.seats_by_kind)}
        note={
          board.removal_possible
            ? 'Investors and the independent outnumber the common seats'
            : 'A tie keeps you in charge'
        }
        testId="kpi-seats"
      />
      <KpiTile
        term="kpi.board_expects"
        label="They expect"
        value={
          board.expected_growth === null ? '—' : `${formatGrowth(board.expected_growth)} a year`
        }
        note={
          board.actual_growth === null
            ? `MRR growth after the ${board.last_round_label ?? 'round'} · under 6 months of revenue`
            : `MRR growth after the ${board.last_round_label ?? 'round'} · you are at ${formatGrowth(board.actual_growth)}`
        }
        testId="kpi-expected"
      />
      <KpiTile
        term="kpi.next_meeting"
        label="Next meeting"
        value={board.next_meeting_label ?? '—'}
        note="Quarterly"
        testId="kpi-next-meeting"
      />
    </div>
  );
}

export function BoardTab({ saveId, companyId }: { saveId: string; companyId?: number }) {
  const { data: board, error, isPending } = useBoard(saveId, companyId);
  if (isPending) return <Loading />;
  if (error) return <LoadError title="Could not load the board" error={error} />;
  if (board.directors.length === 0) {
    return (
      <Panel title="Board">
        <p className="tst-muted" style={{ margin: 0 }} data-testid="no-board">
          You have no board yet. Your first priced round seats one: the lead investor takes a seat
          beside you.
        </p>
      </Panel>
    );
  }
  const m = board.last_meeting;
  return (
    <>
      <Tiles board={board} />
      <section aria-label="Directors" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Directors</h2>
        <Directors saveId={saveId} board={board} />
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          Confidence follows your growth against what the board expects and how much runway you
          have. A director below {formatWhole(board.removal_below)} for {board.removal_months}{' '}
          months votes to remove you, and a majority of all seats removes you.{' '}
          {board.removal_possible
            ? 'Investors and the independent director now outnumber the common seats, so removal is possible.'
            : 'That is possible only once investors and an independent director outnumber the common seats, after a Series B.'}{' '}
          {board.votes_to_remove > 0
            ? `${board.votes_to_remove} of ${board.seats} directors would vote to remove you today.`
            : ''}
        </p>
      </section>
      <Panel
        title={m ? `Last board meeting · ${m.date_label}` : 'Last board meeting'}
        label="Last board meeting"
      >
        {m ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }} data-testid="meeting-body">
              {m.body}
            </p>
            {m.minutes && (
              <p
                style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--tst-text-2)' }}
                data-testid="meeting-minutes"
              >
                {m.minutes}
              </p>
            )}
            <span className="tst-muted" style={{ fontSize: 13 }}>
              {m.previous_title ? `Before: ${m.previous_title}. ` : ''}
              {m.warning_body ? '' : 'No warning.'}
            </span>
            {m.warning_body && (
              <p
                style={{ margin: 0, fontSize: 14, color: 'var(--tst-warn)' }}
                data-testid="meeting-warning"
              >
                {m.warning_body}
              </p>
            )}
          </div>
        ) : (
          <p className="tst-muted" style={{ margin: 0 }}>
            The board meets at the end of each quarter. The first meeting is in{' '}
            {board.next_meeting_label}.
          </p>
        )}
      </Panel>
    </>
  );
}
