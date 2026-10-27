import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../../components/DataTable';
import { KpiTile } from '../../components/KpiTile';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { useBoard, type Board, type Director } from '../../hooks/api';
import {
  confidenceColor,
  formatGrowth,
  labelText,
  seatsText,
  sparkPoints,
} from '../../lib/finance';
import { formatWhole } from '../../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, Director>();

/** A director's confidence over the last month ends (0-100). */
export function Sparkline({ values, label }: { values: readonly number[]; label: string }) {
  if (values.length < 2) return <span className="tst-muted">—</span>;
  return (
    <svg viewBox="0 0 100 24" role="img" aria-label={label} style={{ width: 100, height: 24 }}>
      <polyline
        points={sparkPoints(values)}
        fill="none"
        stroke="var(--tst-accent)"
        strokeWidth={2}
      />
    </svg>
  );
}

function seatText(d: Director): string {
  if (d.kind === 'common') return d.is_founder ? 'Common · founder' : 'Common · your nominee';
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

function Directors({ saveId, board }: { saveId: string; board: Board }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Director',
          sortFn: 'alphanumeric',
          cell: ({ row }) =>
            row.original.is_founder ? (
              <span style={{ fontWeight: 600 }}>{row.original.name} (you)</span>
            ) : row.original.kind === 'common' ? (
              <Link
                to={`/game/${saveId}/people/${row.original.person_id}`}
                style={{ fontWeight: 600, textDecoration: 'none' }}
              >
                {row.original.name}
              </Link>
            ) : (
              <span style={{ fontWeight: 600 }}>{row.original.name}</span>
            ),
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
  return <DataTable table={table} label="Directors" rowTestId="director-row" />;
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
        label="Board confidence"
        value={avg === null ? '—' : `${labelText(board.label)} ${formatWhole(avg)}`}
        note={`Average of the investor directors${trend ? ` · ${trend}` : ''}`}
        warn={avg !== null && avg < board.warning_below}
        testId="kpi-confidence"
      />
      <KpiTile
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
        label="Next meeting"
        value={board.next_meeting_label ?? '—'}
        note="Quarterly"
        testId="kpi-next-meeting"
      />
    </div>
  );
}

export function BoardTab({ saveId }: { saveId: string }) {
  const { data: board, error, isPending } = useBoard(saveId);
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
