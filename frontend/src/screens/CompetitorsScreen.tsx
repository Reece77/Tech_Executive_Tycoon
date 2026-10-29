// Competitors (M5, nav key 8): every rival with its style, where it meets you, staff, money and
// last move; this month's market news; and rivals' open approaches to your people, with
// Counter with a raise (the raise dialog shows the new band) and Let them decide.
import { Button } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { RaiseDialog } from '../components/PersonOrg';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useApproaches,
  useNews,
  useOrgMeta,
  usePerson,
  useRivals,
  type Approach,
  type RivalRow,
  type RivalView,
} from '../hooks/api';
import { formatMoneyWhole, formatWhole } from '../lib/format';
import { MoveTag, StartupChip, StyleChip } from '../lib/rivals';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, RivalRow>();
const VIEWS: { key: RivalView; label: string }[] = [
  { key: 'markets', label: 'In your markets' },
  { key: 'all', label: 'All' },
  { key: 'startups', label: 'Startups' },
];

export function CompetitorsScreen() {
  const { saveId = '' } = useParams();
  const [view, setView] = useState<RivalView>('all');
  const rivals = useRivals(saveId, view);
  const news = useNews(saveId);
  const approaches = useApproaches(saveId);
  const error = rivals.error ?? news.error ?? approaches.error;
  if (error) return <LoadError title="Could not load competitors" error={error} />;
  if (!rivals.data || !news.data || !approaches.data) return <Loading />;
  const r = rivals.data;
  const month = news.data.months[0];
  return (
    <>
      <ScreenTitle
        aside={
          <>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="rival-counts">
              {r.established} established · {r.startups_alive} startups alive · {r.startups_failed}{' '}
              failed
            </span>
            <div
              role="group"
              aria-label="Filter rivals"
              style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}
            >
              {VIEWS.map((v) => (
                <Button
                  key={v.key}
                  size="sm"
                  variant={view === v.key ? 'filled' : 'default'}
                  aria-pressed={view === v.key}
                  onClick={() => setView(v.key)}
                >
                  {v.label}
                </Button>
              ))}
            </div>
          </>
        }
      >
        Competitors
      </ScreenTitle>
      {approaches.data.map((a) => (
        <ApproachPanel key={a.approach_id} saveId={saveId} approach={a} />
      ))}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <section aria-label="Rivals" style={{ flex: '3 1 640px', minWidth: 0 }}>
          <RivalTable saveId={saveId} rows={r.rivals} />
        </section>
        <Panel
          title="Market news"
          style={{ flex: '1 1 320px', display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {(news.data?.headlines ?? []).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {(news.data?.headlines ?? []).map((h) => (
                <strong key={h} style={{ fontSize: 13 }} data-testid="headline">
                  {h}
                </strong>
              ))}
            </div>
          )}
          {month ? (
            <>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {month.date_label}
              </span>
              {month.moves.map((m, i) => (
                <span
                  key={i}
                  style={{ fontSize: 13, display: 'flex', gap: 8 }}
                  data-testid="news-line"
                >
                  <MoveTag tag={m.tag} />
                  {m.detail}
                </span>
              ))}
            </>
          ) : (
            <span className="tst-muted" style={{ fontSize: 13 }}>
              No rival has moved yet.
            </span>
          )}
          <Link to={`/game/${saveId}/inbox`} style={{ fontSize: 12 }}>
            Earlier months in the inbox
          </Link>
        </Panel>
      </div>
    </>
  );
}

function RivalTable({ saveId, rows }: { saveId: string; rows: RivalRow[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Company',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Link
                to={`/game/${saveId}/competitors/${row.original.company_id}`}
                style={{ fontWeight: 600, textDecoration: 'none' }}
                data-testid="rival-link"
              >
                {row.original.name}
              </Link>
              {row.original.is_startup && <StartupChip />}
              {row.original.failed && <span className="tst-muted">(closed)</span>}
            </span>
          ),
        }),
        helper.accessor('personality_label', {
          header: 'Style',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <StyleChip
              personality={row.original.personality}
              label={row.original.personality_label}
            />
          ),
        }),
        helper.accessor((r) => r.competes_in.join(', '), {
          id: 'competes',
          header: 'Meets you in',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => getValue() || <span className="tst-muted">—</span>,
        }),
        helper.accessor('staff_estimate', {
          header: 'Staff',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">~{formatWhole(getValue())}</span>,
        }),
        helper.accessor((r) => r.money_label ?? '', {
          id: 'money',
          header: 'Money',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => getValue() || <span className="tst-muted">—</span>,
        }),
        helper.accessor('stance', { header: 'Stance', sortFn: 'alphanumeric' }),
        helper.accessor((r) => r.last_move ?? '', {
          id: 'last',
          header: 'Last move',
          sortFn: 'alphanumeric',
          cell: ({ row }) =>
            row.original.last_move ? (
              <span style={{ fontSize: 13 }}>
                {row.original.last_move}{' '}
                <span className="tst-muted">({row.original.last_move_date_label})</span>
              </span>
            ) : (
              <span className="tst-muted">—</span>
            ),
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => String(r.company_id),
  });
  return (
    <DataTable table={table} label="Rivals" rowTestId="rival-row" empty="No rivals in this view." />
  );
}

/** A rival's open offer to one of your people (15.6): the band, never the chance. */
export function ApproachPanel({ saveId, approach: a }: { saveId: string; approach: Approach }) {
  const [counter, setCounter] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const person = usePerson(saveId, a.person_id);
  const meta = useOrgMeta();
  if (dismissed) return null;
  return (
    <aside
      className="tst-panel"
      aria-label={`Approach to ${a.name}`}
      data-testid="approach-panel"
      style={{ borderColor: 'var(--tst-warn)', display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <strong>
        {a.rival_name} is trying to hire {a.name}
      </strong>
      <span style={{ fontSize: 13 }}>
        {a.role_label}: offered {formatMoneyWhole(a.offer_cents)} a year against{' '}
        {formatMoneyWhole(a.salary_cents)} now
        {a.unvested_options > 0 ? `, with ${formatWhole(a.unvested_options)} unvested options` : ''}
        . They decide when you press Continue ({a.answer_date_label}).
      </span>
      <span style={{ fontSize: 14 }} data-testid="approach-band">
        Your read: <strong style={{ color: 'var(--tst-warn)' }}>{a.band}</strong>
      </span>
      <span style={{ display: 'flex', gap: 8 }}>
        <Button size="compact-sm" onClick={() => setCounter(true)} data-testid="counter-approach">
          Counter with a raise
        </Button>
        <Button size="compact-sm" variant="default" onClick={() => setDismissed(true)}>
          Let them decide
        </Button>
      </span>
      {counter && person.data && meta.data && (
        <RaiseDialog
          saveId={saveId}
          p={person.data}
          meta={meta.data}
          initialCents={a.offer_cents}
          approachId={a.approach_id}
          onClose={() => setCounter(false)}
        />
      )}
    </aside>
  );
}
