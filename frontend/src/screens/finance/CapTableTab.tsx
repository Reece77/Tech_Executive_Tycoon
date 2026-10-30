import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { CapTable, ShareBar } from '../../components/CapTable';
import { DataTable } from '../../components/DataTable';
import { KpiTile } from '../../components/KpiTile';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { useCapTable, type CapTable as CapTableData, type Grant } from '../../hooks/api';
import { useTableViews } from '../../hooks/useTableViews';
import { formatMoneyShort } from '../../lib/format';
import { formatFraction, formatSharePrice, formatShares } from '../../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, Grant>();
const right = { display: 'block', textAlign: 'right' } as const;

function Tiles({ cap }: { cap: CapTableData }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <KpiTile
        term="kpi.fd_shares"
        label="Fully diluted shares"
        value={formatShares(cap.fd_shares)}
        testId="kpi-fd"
      />
      <KpiTile
        term="kpi.share_price"
        label={cap.last_round_label ? `Share price (${cap.last_round_label})` : 'Share price'}
        value={formatSharePrice(cap.share_price_dollars)}
        note={cap.last_round_label ? undefined : 'Set by your first priced round'}
        testId="kpi-price"
      />
      <KpiTile
        term="kpi.post_money"
        label="Post-money valuation"
        value={cap.post_money_cents === null ? '—' : formatMoneyShort(cap.post_money_cents)}
        note={
          cap.last_round_label
            ? `${cap.last_round_label}, ${cap.last_round_date_label ?? ''}`
            : 'No priced round yet'
        }
        testId="kpi-post"
      />
      <KpiTile
        term="kpi.founder_owns"
        label="You own"
        value={formatFraction(cap.founder_fraction)}
        note={`${formatShares(cap.founder_shares)} common shares`}
        testId="kpi-founder"
      />
    </div>
  );
}

function History({ cap }: { cap: CapTableData }) {
  return (
    <Panel title="Your ownership over time" style={{ flex: '2 1 320px' }} label="Dilution history">
      {cap.ownership_history.map((e) => (
        <div
          key={`${e.event}-${e.turn}-${e.label}`}
          data-testid="ownership-event"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 70px',
            gap: 10,
            alignItems: 'center',
            padding: '7px 0',
            borderBottom: '1px solid var(--tst-rule)',
          }}
        >
          <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span style={{ fontSize: 14 }}>
              {e.label}, {e.date_label}
              {e.pending ? ' (converts at the next round)' : ''}
            </span>
            <ShareBar fraction={e.founder_fraction} color="var(--tst-accent)" width={220} />
          </span>
          <span className="tst-num" style={{ textAlign: 'right' }}>
            {formatFraction(e.founder_fraction)}
          </span>
        </div>
      ))}
    </Panel>
  );
}

function nextVesting(g: Grant) {
  if (!g.on_staff) return <span className="tst-muted">Left · unvested returned</span>;
  if (g.next_vest_label === null || g.next_vest_label === undefined) {
    return <span className="tst-muted">Fully vested</span>;
  }
  const amount = formatShares(g.next_vest_shares ?? 0);
  return g.next_vest_is_cliff ? (
    <span style={{ color: 'var(--tst-tier-4)', fontSize: 13 }} data-testid="vest-cliff">
      Cliff in {g.next_vest_label} · {amount}
    </span>
  ) : (
    <span style={{ color: 'var(--tst-text-2)', fontSize: 13 }}>
      {g.next_vest_label} · {amount}
    </span>
  );
}

function Grants({ saveId, cap }: { saveId: string; cap: CapTableData }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Person',
          sortFn: 'alphanumeric',
          cell: ({ row }) =>
            row.original.on_staff ? (
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
        helper.accessor('start_turn', {
          header: 'Granted',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num" style={{ color: 'var(--tst-text-2)' }}>
              {row.original.start_label}
            </span>
          ),
        }),
        helper.accessor('granted', {
          header: 'Options',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatShares(getValue())}
            </span>
          ),
        }),
        helper.accessor('vested', {
          header: 'Vested',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatShares(getValue())}
            </span>
          ),
        }),
        helper.accessor('unvested', {
          header: 'Unvested',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" style={right}>
              {formatShares(getValue())}
            </span>
          ),
        }),
        helper.accessor((g) => g.next_vest_turn ?? undefined, {
          id: 'next',
          header: 'Next vesting',
          sortFn: 'basic',
          sortUndefined: 'last',
          cell: ({ row }) => nextVesting(row.original),
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: cap.grants,
    getRowId: (g) => String(g.person_id),
  });
  return (
    <DataTable
      table={table}
      label="Employee options"
      rowTestId="grant-row"
      empty="No options granted yet. Offers with equity grant options when people join."
    />
  );
}

export function CapTableTab({ saveId }: { saveId: string }) {
  const { data: cap, error, isPending } = useCapTable(saveId);
  const views = useTableViews('captable');
  if (isPending) return <Loading />;
  if (error) return <LoadError title="Could not load the cap table" error={error} />;
  const years = cap.vesting_months / 12;
  return (
    <>
      <Tiles cap={cap} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <section
          aria-label="Holders"
          style={{
            flex: '3 1 560px',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Holders</h2>
          <CapTable cap={cap} views={views} />
          <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
            A SAFE converts at the next priced round: its holders get their share of the company as
            it stood just before the new money. Each priced round tops the unallocated pool back up
            to 10%.
          </p>
        </section>
        <History cap={cap} />
      </div>
      <section
        aria-label="Employee options"
        style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Employee options</h2>
          <span className="tst-muted" style={{ fontSize: 13 }} data-testid="options-summary">
            {formatShares(cap.granted_options)} granted · {formatShares(cap.vested_options)} vested
            · {formatShares(cap.unallocated_options)} unallocated · {years}-year vesting with a{' '}
            {cap.cliff_months / 12}-year cliff
          </span>
        </div>
        <Grants saveId={saveId} cap={cap} />
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          Unvested options are worth staying for: at the current share price they make people less
          likely to resign. {cap.grants.length} holder{cap.grants.length === 1 ? '' : 's'}.
        </p>
      </section>
    </>
  );
}
