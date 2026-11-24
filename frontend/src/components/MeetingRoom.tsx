import { Alert, Badge, Button, Select, Textarea } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import {
  useAnswerMeeting,
  useMeeting,
  useSkipMeeting,
  type Meeting,
  type MeetingMoveIn,
} from '../hooks/meetings';
import { formatMoney } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { LoadError, Loading } from './ScreenState';
import { Term } from './Term';

// The meeting room (M48, formulas.md 59): a board meeting, an earnings call or an investor day.
// The agenda, the speaker's profile, the conversation, three suggested answers (or the kind's
// moves as buttons in template mode), and the visible effects once the meeting is over. The
// engine decides every effect; nothing here computes a game value.

const STATUS: Record<string, string> = {
  open: 'In session',
  done: 'Over',
  skipped: 'Skipped: today’s outcome',
  lapsed: 'Lapsed at the month end',
  failed: 'Over, but its outcome could not be applied',
};

export function MeetingRoom({ saveId, id }: { saveId: string; id: number }) {
  const q = useMeeting(saveId, id);
  if (q.isPending) return <Loading />;
  if (q.error || !q.data) return <LoadError title="Could not load the meeting" error={q.error} />;
  return <Room saveId={saveId} m={q.data} />;
}

function Room({ saveId, m }: { saveId: string; m: Meeting }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="meeting-room">
      <header>
        <h3 className="tst-ptitle" style={{ margin: 0 }} data-testid="meeting-subject">
          {m.subject}
        </h3>
        <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
          <Badge variant="light" data-testid="meeting-status">
            {STATUS[m.status] ?? m.status}
          </Badge>
          <Badge variant="outline" data-testid="meeting-mode">
            {m.mode.mode === 'llm'
              ? 'Free text'
              : `Template mode${m.mode.reason ? ` (${m.mode.reason})` : ''}`}
          </Badge>
          <Badge variant="outline" data-testid="meeting-credibility">
            <Term term="credibility">Credibility</Term> {m.credibility.toFixed(0)}
          </Badge>
        </div>
        {m.plan_subject && (
          <ul className="tst-muted" style={{ fontSize: 13, margin: '6px 0 0' }}>
            {m.plan_facts.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
      </header>
      <Agenda m={m} />
      <Log m={m} />
      {m.status === 'open' && m.next_item !== null ? (
        <Answer saveId={saveId} m={m} item={m.next_item} />
      ) : (
        <Effects m={m} />
      )}
    </div>
  );
}

function Agenda({ m }: { m: Meeting }) {
  return (
    <section aria-label="Agenda" data-testid="meeting-agenda">
      <h4 className="tst-ptitle" style={{ margin: '0 0 4px' }}>
        Agenda
      </h4>
      <ol style={{ margin: 0, paddingLeft: 18 }}>
        {m.items.map((it) => (
          <li
            key={it.n}
            data-testid="meeting-item"
            style={{ fontWeight: it.n === m.next_item ? 600 : 400 }}
          >
            {it.title}
            {it.problem && (
              <span className="tst-negative" style={{ fontSize: 12 }}>
                {' '}
                (a real problem)
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Speaker({ m, index }: { m: Meeting; index: number }) {
  const s = m.speakers[index];
  if (!s) return null;
  return (
    <div className="tst-muted" style={{ fontSize: 13 }} data-testid="meeting-speaker">
      <strong>{s.name}</strong>, {s.role}
      {s.organisation ? ` at ${s.organisation}` : ''}
      {s.confidence !== null && s.confidence !== undefined && (
        <>
          {' '}
          · <Term term="kpi.board_confidence">confidence</Term> {s.confidence.toFixed(0)}
        </>
      )}
      {s.rating && ` · rated ${s.rating}, target ${formatMoney(s.target_cents)}`}
      {s.focus && ` · focus: ${s.focus}`}
    </div>
  );
}

function Log({ m }: { m: Meeting }) {
  const first = m.items[0];
  return (
    <section aria-label="Conversation" data-testid="meeting-log">
      {first && (
        <p style={{ margin: '0 0 8px' }}>
          <strong>{m.speakers[first.speaker]?.name}:</strong> {m.opening_line}
        </p>
      )}
      {m.answers.map((a) => {
        const next = m.items[a.n + 1];
        const speaker = next ? m.speakers[next.speaker] : m.speakers[m.items[a.n]?.speaker ?? 0];
        return (
          <div key={a.n} data-testid="meeting-answer" style={{ marginBottom: 8 }}>
            <p style={{ margin: 0 }}>
              <strong>You:</strong> {a.message}{' '}
              <span className="tst-muted" style={{ fontSize: 12 }}>
                ({a.moves.map((x) => x.words).join(', ')}; {a.reaction})
              </span>
            </p>
            {a.commitment && (
              <p style={{ margin: 0, fontSize: 12 }} data-testid="meeting-commitment">
                <Term term="meeting.commitment">Commitment</Term>: {a.commitment}
              </p>
            )}
            <p style={{ margin: 0 }}>
              <strong>{speaker?.name}:</strong> {a.reply}
            </p>
          </div>
        );
      })}
    </section>
  );
}

function Answer({ saveId, m, item }: { saveId: string; m: Meeting; item: number }) {
  const answer = useAnswerMeeting(saveId, m.meeting_id);
  const skip = useSkipMeeting(saveId, m.meeting_id);
  const [message, setMessage] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [fact, setFact] = useState<string | null>('0');
  const it = m.items[item];
  if (!it) return null;
  const template = m.mode.mode === 'template';
  const moves: MeetingMoveIn[] = picked.map((kind) =>
    kind === 'explain' ? { kind, fact: Number(fact ?? 0) } : { kind },
  );
  const send = () => {
    if (template) {
      answer.mutate({ moves, source: 'template' }, { onSuccess: () => setPicked([]) });
    } else {
      answer.mutate(
        { message, source: m.suggestions.includes(message) ? 'suggested' : 'free' },
        { onSuccess: () => setMessage('') },
      );
    }
  };
  const error = answer.error ?? skip.error;
  return (
    <section aria-label="Your answer" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Speaker m={m} index={it.speaker} />
      <p style={{ margin: 0 }} data-testid="meeting-question">
        <strong>{it.title}:</strong> {it.question}
      </p>
      {it.facts.length > 0 && (
        <ul style={{ margin: 0, fontSize: 13 }} data-testid="meeting-facts">
          {it.facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      {it.figure && (
        <p style={{ margin: 0, fontSize: 13 }} data-testid="meeting-figure">
          {it.guidance ? <Term term="public.guidance">Guidance</Term> : 'Plan figure'}: {it.figure}
        </p>
      )}
      {template ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'end' }}>
          {m.move_choices
            .filter((c) => c.kind !== 'neutral')
            .map((c) => (
              <Button
                key={c.kind}
                size="xs"
                variant={picked.includes(c.kind) ? 'filled' : 'default'}
                data-testid={`meeting-move-${c.kind}`}
                onClick={() =>
                  setPicked(
                    picked.includes(c.kind)
                      ? picked.filter((k) => k !== c.kind)
                      : [...picked, c.kind].slice(-3),
                  )
                }
              >
                {c.label}
              </Button>
            ))}
          {picked.includes('explain') && it.facts.length > 0 && (
            <Select
              size="xs"
              data-testid="meeting-move-fact"
              label="Citing"
              value={fact}
              onChange={setFact}
              data={it.facts.map((f, i) => ({ value: String(i), label: f }))}
              style={{ width: 320 }}
            />
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {m.suggestions.map((s) => (
              <Button
                key={s}
                size="xs"
                variant="subtle"
                justify="flex-start"
                data-testid="meeting-suggestion"
                onClick={() => setMessage(s)}
                style={{ whiteSpace: 'normal', height: 'auto', textAlign: 'left' }}
              >
                {s}
              </Button>
            ))}
          </div>
          <Textarea
            label="Your answer"
            data-testid="meeting-message"
            value={message}
            onChange={(e) => setMessage(e.currentTarget.value)}
            autosize
            minRows={2}
            maxLength={600}
          />
        </>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button
          size="xs"
          data-testid="meeting-send"
          loading={answer.isPending}
          disabled={template ? picked.length === 0 : !message.trim()}
          onClick={send}
        >
          {template ? 'Answer with these moves' : 'Answer'}
        </Button>
        <Button
          size="xs"
          variant="default"
          data-testid="meeting-skip"
          loading={skip.isPending}
          onClick={() => skip.mutate()}
        >
          Skip the meeting (today’s outcome)
        </Button>
      </div>
      {error && (
        <Alert color="red" data-testid="meeting-error">
          {error.message}
        </Alert>
      )}
    </section>
  );
}

type Row = Meeting['effects'][number];
const helper = createColumnHelper<GameTableFeatures, Row>();

function Effects({ m }: { m: Meeting }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('who', { header: 'Who', meta: { term: 'meeting.who' } }),
        helper.accessor('what', { header: 'What moved', meta: { term: 'meeting.what' } }),
        helper.accessor('words', { header: 'Effect', meta: { term: 'meeting.effect' } }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: m.effects });
  return (
    <section aria-label="What the meeting did" data-testid="meeting-effects">
      <h4 className="tst-ptitle">What the meeting did</h4>
      {m.error && (
        <Alert color="red" data-testid="meeting-error">
          {m.error}
        </Alert>
      )}
      <DataTable
        table={table}
        label="Effects"
        rowTestId="meeting-effect"
        empty={m.status === 'skipped' ? 'Skipped: nothing moved.' : 'Nothing moved.'}
      />
      {m.votes.length > 0 && (
        <p style={{ margin: '6px 0 0' }} data-testid="meeting-votes">
          <Term term="meeting.vote">The plan</Term>:{' '}
          {m.votes.map((v) => `${v.name} ${v.backs_plan ? 'backs it' : 'does not'}`).join('; ')}
        </p>
      )}
    </section>
  );
}
