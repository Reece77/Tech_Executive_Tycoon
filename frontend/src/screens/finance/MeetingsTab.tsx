import { Alert, Button, NativeSelect } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { DataTable } from '../../components/DataTable';
import { MeetingRoom } from '../../components/MeetingRoom';
import { LoadError, Loading } from '../../components/ScreenState';
import { Term } from '../../components/Term';
import { useMeetings, useOpenMeeting, type MeetingList } from '../../hooks/meetings';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

// Finance > Meetings (M48, formulas.md 59): this month's board meeting, earnings call and
// investor day (with its planner), the meeting room, past meetings and the commitments made in
// them. Every meeting can be skipped; skipping is today's outcome.

const KIND_LABEL: Record<string, string> = {
  board: 'Board meeting',
  call: 'Earnings call',
  investor_day: 'Investor day',
};
const PLANS = [
  { value: 'new_industry', label: 'Enter a new industry' },
  { value: 'capital_plan', label: 'A capital plan' },
  { value: 'restructuring', label: 'A restructuring' },
];

export function MeetingsTab({ saveId }: { saveId: string }) {
  const q = useMeetings(saveId);
  const [id, setId] = useState<number | null>(null);
  if (q.isPending) return <Loading />;
  if (q.error || !q.data) return <LoadError title="Could not load meetings" error={q.error} />;
  const list = q.data;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="meetings-tab">
      <p style={{ margin: 0 }} data-testid="meetings-credibility">
        <Term term="credibility">Credibility</Term>: <strong>{list.credibility.toFixed(0)}</strong>
      </p>
      <ThisMonth saveId={saveId} list={list} onOpen={setId} />
      {id !== null && <MeetingRoom saveId={saveId} id={id} />}
      <Past list={list} onOpen={setId} />
      <Commitments list={list} />
    </div>
  );
}

function ThisMonth({
  saveId,
  list,
  onOpen,
}: {
  saveId: string;
  list: MeetingList;
  onOpen: (id: number) => void;
}) {
  const open = useOpenMeeting(saveId);
  const [plan, setPlan] = useState('new_industry');
  const [industry, setIndustry] = useState(list.industries[0]?.kind ?? '');
  const hold = (kind: string) =>
    open.mutate(
      {
        kind,
        params: kind === 'investor_day' ? { plan_kind: plan, industry } : {},
      },
      { onSuccess: (m) => onOpen(m.meeting_id) },
    );
  return (
    <section aria-label="This month" data-testid="meetings-this-month">
      <h3 className="tst-ptitle">This month</h3>
      {list.available.map((a) => (
        <div
          key={a.kind}
          className="tst-row"
          data-testid={`meeting-slot-${a.kind}`}
          style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <strong style={{ minWidth: 130 }}>
            {a.kind === 'investor_day' ? (
              <Term term="meeting.investor_day">{KIND_LABEL[a.kind]}</Term>
            ) : (
              KIND_LABEL[a.kind]
            )}
          </strong>
          {a.kind === 'investor_day' && a.available && (
            <>
              <NativeSelect
                size="xs"
                aria-label="Plan"
                data-testid="investor-day-plan"
                value={plan}
                onChange={(e) => setPlan(e.currentTarget.value)}
                data={PLANS}
              />
              {plan === 'new_industry' && (
                <NativeSelect
                  size="xs"
                  aria-label="Industry"
                  data-testid="investor-day-industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.currentTarget.value)}
                  data={list.industries.map((i) => ({ value: i.kind, label: i.label }))}
                />
              )}
            </>
          )}
          {a.meeting_id !== null ? (
            <Button
              size="xs"
              variant="light"
              data-testid={`meeting-view-${a.kind}`}
              onClick={() => (a.available ? hold(a.kind) : onOpen(a.meeting_id ?? 0))}
            >
              {a.available ? 'Resume' : 'View'}
            </Button>
          ) : (
            <Button
              size="xs"
              data-testid={`meeting-hold-${a.kind}`}
              disabled={!a.available}
              loading={open.isPending && open.variables?.kind === a.kind}
              onClick={() => hold(a.kind)}
            >
              {a.kind === 'investor_day' ? 'Hold an investor day' : 'Attend'}
            </Button>
          )}
          {!a.available && (
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {a.reason}
            </span>
          )}
        </div>
      ))}
      {open.error && (
        <Alert color="red" data-testid="meeting-open-error">
          {open.error.message}
        </Alert>
      )}
    </section>
  );
}

type PastRow = MeetingList['items'][number];
const pastHelper = createColumnHelper<GameTableFeatures, PastRow>();

function Past({ list, onOpen }: { list: MeetingList; onOpen: (id: number) => void }) {
  const columns = useMemo(
    () =>
      pastHelper.columns([
        pastHelper.accessor('date_label', { header: 'Month', meta: { term: 'meeting.month' } }),
        pastHelper.accessor('subject', {
          header: 'Meeting',
          meta: { term: 'meeting.subject' },
          cell: (c) => (
            <Button
              size="compact-xs"
              variant="subtle"
              onClick={() => onOpen(c.row.original.meeting_id)}
            >
              {c.getValue()}
            </Button>
          ),
        }),
        pastHelper.accessor('status', { header: 'Status', meta: { term: 'meeting.status' } }),
        pastHelper.accessor((r) => r.effects.join('; '), {
          id: 'effects',
          header: 'Effects',
          meta: { term: 'meeting.effect' },
        }),
      ]),
    [onOpen],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: list.items });
  return (
    <section aria-label="Past meetings">
      <h3 className="tst-ptitle">Meetings</h3>
      <DataTable table={table} label="Meetings" rowTestId="meeting-row" empty="No meetings yet." />
    </section>
  );
}

type CommitmentRow = MeetingList['commitments'][number];
const cHelper = createColumnHelper<GameTableFeatures, CommitmentRow>();

function Commitments({ list }: { list: MeetingList }) {
  const columns = useMemo(
    () =>
      cHelper.columns([
        cHelper.accessor('words', {
          header: 'Commitment',
          meta: { term: 'meeting.commitment' },
        }),
        cHelper.accessor('kind', { header: 'Made to', meta: { term: 'meeting.made_to' } }),
        cHelper.accessor('made_label', { header: 'Made', meta: { term: 'meeting.month' } }),
        cHelper.accessor('deadline_label', { header: 'Due', meta: { term: 'meeting.due' } }),
        cHelper.accessor('status', { header: 'Status', meta: { term: 'meeting.status' } }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: list.commitments });
  return (
    <section aria-label="Commitments">
      <h3 className="tst-ptitle">Commitments</h3>
      <DataTable
        table={table}
        label="Commitments"
        rowTestId="meeting-commitment-row"
        empty="No commitments made in meetings."
      />
    </section>
  );
}
