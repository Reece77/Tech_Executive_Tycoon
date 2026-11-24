import { Alert, Badge, Button } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import { TalkRoom } from '../components/TalkRoom';
import { TALK_KIND_LABEL, TALK_STATUS } from '../lib/talks';
import { Term } from '../components/Term';
import { useOpenTalk, useTalks, type TalkAvailable, type TalkList } from '../hooks/talks';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// The press room (M49, formulas.md 61.1): this month's interview (on the open press event) and
// press conferences (a class I recall, a robotaxi incident), the talk room, and past
// interviews and conferences. Every talk can be skipped; skipping is today's outcome.

const PRESS_KINDS = new Set(['interview', 'crisis']);

export function PressScreen() {
  const { saveId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const q = useTalks(saveId);
  const raw = params.get('talk');
  const id = raw === null ? null : Number(raw);
  const select = (talkId: number) => setParams({ talk: String(talkId) }, { replace: true });
  if (q.isPending) return <Loading />;
  if (q.error || !q.data)
    return <LoadError title="Could not load the press room" error={q.error} />;
  const list = q.data;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="press-room">
      <ScreenTitle>Press room</ScreenTitle>
      <ModeLine list={list} />
      <ThisMonth saveId={saveId} list={list} onOpen={select} />
      {id !== null && Number.isFinite(id) && <TalkRoom key={id} saveId={saveId} id={id} />}
      <Past list={list} onOpen={select} />
    </div>
  );
}

/** How this month's talks run: free text, or template moves (and why). */
function ModeLine({ list }: { list: TalkList }) {
  return (
    <div className="tst-muted" style={{ fontSize: 13 }} data-testid="talks-mode">
      <Badge variant="outline" mr={6}>
        {list.mode.mode === 'llm'
          ? 'Free text'
          : `Template mode${list.mode.reason ? ` (${list.mode.reason})` : ''}`}
      </Badge>
      {list.mode.mode === 'llm'
        ? 'Answer in your own words, or pick a suggested reply.'
        : 'Pick your moves from the buttons; the engine is the same.'}
    </div>
  );
}

function ThisMonth({
  saveId,
  list,
  onOpen,
}: {
  saveId: string;
  list: TalkList;
  onOpen: (id: number) => void;
}) {
  const open = useOpenTalk(saveId);
  const take = (a: TalkAvailable) =>
    open.mutate(
      { kind: a.kind, params: { source: a.source, key: a.key } },
      { onSuccess: (t) => onOpen(t.talk_id) },
    );
  return (
    <section aria-label="This month" data-testid="press-this-month">
      <h3 className="tst-ptitle">This month</h3>
      {list.available.length === 0 && (
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          No interview or press conference this month. A{' '}
          <Term term="press_moment">press moment</Term> brings an interview; a class I recall or a
          robotaxi incident, a press conference.
        </p>
      )}
      {list.available.map((a) => (
        <div
          key={`${a.source}-${a.key}`}
          className="tst-row"
          data-testid={`press-slot-${a.source}`}
          style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <strong style={{ minWidth: 130 }}>
            {a.kind === 'crisis' ? (
              <Term term="talk.crisis">{TALK_KIND_LABEL.crisis}</Term>
            ) : (
              <Term term="talk.interview">{TALK_KIND_LABEL.interview}</Term>
            )}
          </strong>
          <span>{a.subject}</span>
          {a.status && (
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {TALK_STATUS[a.status] ?? a.status}
            </span>
          )}
          <span style={{ marginLeft: 'auto' }}>
            {a.talk_id !== null && a.status !== 'open' ? (
              <Button
                size="xs"
                variant="light"
                data-testid={`press-view-${a.source}`}
                onClick={() => onOpen(a.talk_id ?? 0)}
              >
                View
              </Button>
            ) : (
              <Button
                size="xs"
                data-testid={`press-take-${a.source}`}
                loading={open.isPending && open.variables?.params?.source === a.source}
                onClick={() => take(a)}
              >
                {a.talk_id !== null
                  ? 'Resume'
                  : a.kind === 'crisis'
                    ? 'Hold the press conference'
                    : 'Take the interview'}
              </Button>
            )}
          </span>
        </div>
      ))}
      {open.error && (
        <Alert color="red" data-testid="press-open-error">
          {open.error.message}
        </Alert>
      )}
    </section>
  );
}

type PastRow = TalkList['items'][number];
const helper = createColumnHelper<GameTableFeatures, PastRow>();

function Past({ list, onOpen }: { list: TalkList; onOpen: (id: number) => void }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('date_label', { header: 'Month', meta: { term: 'month' } }),
        helper.accessor('subject', {
          header: 'Talk',
          meta: { term: 'press_moment' },
          cell: (c) => (
            <Button
              size="compact-xs"
              variant="subtle"
              onClick={() => onOpen(c.row.original.talk_id)}
            >
              {c.getValue()}
            </Button>
          ),
        }),
        helper.accessor((r) => TALK_STATUS[r.status] ?? r.status, {
          id: 'status',
          header: 'Status',
          meta: { term: 'status' },
        }),
        helper.accessor((r) => r.effects.join('; '), {
          id: 'effects',
          header: 'Effects',
          meta: { term: 'what' },
        }),
      ]),
    [onOpen],
  );
  const data = useMemo(() => list.items.filter((t) => PRESS_KINDS.has(t.kind)), [list.items]);
  const table = useTable({ features: gameTableFeatures, columns, data });
  return (
    <section aria-label="Past interviews and conferences">
      <h3 className="tst-ptitle">
        <Term term="talk.interview">Interviews</Term> and{' '}
        <Term term="talk.crisis">press conferences</Term>
      </h3>
      <DataTable
        table={table}
        label="Interviews and press conferences"
        rowTestId="press-row"
        empty="No interviews or press conferences yet."
      />
    </section>
  );
}
