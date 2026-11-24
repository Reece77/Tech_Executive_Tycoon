import { Alert, Badge, Button, Textarea } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import { useAnswerTalk, useSkipTalk, useTalk, type Talk } from '../hooks/talks';
import { formatWhole } from '../lib/format';
import { TALK_STATUS } from '../lib/talks';
import { LoadError, Loading } from './ScreenState';
import { Term } from './Term';

// The talk room (M49, formulas.md 61): a press interview, a crisis press conference or a
// one-to-one. The counterpart's public profile, the conversation, the current question with its
// facts and any promise on offer, three suggested answers (or the kind's moves as buttons in
// template mode), and the visible effects once the talk is over. The engine decides every
// effect; nothing here computes a game value.

/** At most this many moves count in one answer (balance talks.max_moves; the engine trims). */
const MAX_PICKED = 3;

export function TalkRoom({ saveId, id }: { saveId: string; id: number }) {
  const q = useTalk(saveId, id);
  if (q.isPending) return <Loading />;
  if (q.error || !q.data) return <LoadError title="Could not load the talk" error={q.error} />;
  return <TalkRoomBody saveId={saveId} t={q.data} />;
}

export function TalkRoomBody({ saveId, t }: { saveId: string; t: Talk }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="talk-room">
      <header>
        <h3 className="tst-ptitle" style={{ margin: 0 }} data-testid="talk-subject">
          {t.subject}
        </h3>
        <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
          <Badge variant="light" data-testid="talk-status">
            {TALK_STATUS[t.status] ?? t.status}
          </Badge>
          <Badge variant="outline" data-testid="talk-mode">
            {t.mode.mode === 'llm'
              ? 'Free text'
              : `Template mode${t.mode.reason ? ` (${t.mode.reason})` : ''}`}
          </Badge>
          <span className="tst-muted" style={{ fontSize: 12, alignSelf: 'center' }}>
            {t.date_label}
          </span>
        </div>
      </header>
      <Counterpart saveId={saveId} t={t} />
      <Log t={t} />
      {t.status === 'open' && t.next_question !== null ? (
        <Answer saveId={saveId} t={t} n={t.next_question} />
      ) : (
        <Effects t={t} />
      )}
    </div>
  );
}

function Counterpart({ saveId, t }: { saveId: string; t: Talk }) {
  const c = t.counterpart;
  const person = c.person_id !== null;
  return (
    <section
      aria-label="Who you are talking to"
      className="tst-muted"
      style={{ fontSize: 13 }}
      data-testid="talk-counterpart"
    >
      <strong style={{ color: 'var(--tst-text)' }}>
        {person ? <Link to={`/game/${saveId}/people/${c.person_id}`}>{c.name}</Link> : c.name}
      </strong>
      {c.role && `, ${c.role}`}
      {c.organisation && ` at ${c.organisation}`}
      {c.beat && ` · beat: ${c.beat}`}
      {c.stance && ` · stance: ${c.stance}`}
      {c.morale !== null && (
        <>
          {' '}
          · <Term term="morale">morale</Term> {formatWhole(c.morale)}
        </>
      )}
      {t.approached_by && (
        <span className="tst-negative" data-testid="talk-approached">
          {' '}
          · approached by {t.approached_by}
        </span>
      )}
      {t.delegated && <span data-testid="talk-delegated"> · held for you by a seat holder</span>}
    </section>
  );
}

function Log({ t }: { t: Talk }) {
  const name = t.counterpart.name;
  return (
    <section aria-label="Conversation" data-testid="talk-log">
      {t.opening_line && (
        <p style={{ margin: '0 0 8px' }}>
          <strong>{name}:</strong> {t.opening_line}
        </p>
      )}
      {t.answers.map((a) => (
        <div key={a.n} data-testid="talk-answer" style={{ marginBottom: 8 }}>
          <p style={{ margin: 0 }}>
            <strong>You:</strong> {a.message}{' '}
            <span className="tst-muted" style={{ fontSize: 12 }}>
              ({a.moves.map((m) => m.words).join(', ') || 'nothing that counted'}
              {a.reaction ? `; ${a.reaction}` : ''})
            </span>
          </p>
          {a.reply && (
            <p style={{ margin: 0 }}>
              <strong>{name}:</strong> {a.reply}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}

function Answer({ saveId, t, n }: { saveId: string; t: Talk; n: number }) {
  const answer = useAnswerTalk(saveId, t.talk_id);
  const skip = useSkipTalk(saveId, t.talk_id);
  const [message, setMessage] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const q = t.questions.find((x) => x.n === n);
  if (!q) return null;
  const template = t.mode.mode === 'template';
  const send = () => {
    if (template) {
      answer.mutate(
        { moves: picked.map((kind) => ({ kind })), source: 'template' },
        { onSuccess: () => setPicked([]) },
      );
    } else {
      answer.mutate(
        { message, source: t.suggestions.includes(message) ? 'suggested' : 'free' },
        { onSuccess: () => setMessage('') },
      );
    }
  };
  const error = answer.error ?? skip.error;
  return (
    <section aria-label="Your answer" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <p style={{ margin: 0 }} data-testid="talk-question">
        <strong>{q.title}:</strong> {q.question}
      </p>
      {q.facts.length > 0 && (
        <ul style={{ margin: 0, fontSize: 13 }} data-testid="talk-facts">
          {q.facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      {q.offer && (
        <p style={{ margin: 0, fontSize: 13 }} data-testid="talk-offer">
          <Term term="promise">A promise you can make here</Term>: {q.offer}
        </p>
      )}
      {template ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {t.move_choices
            .filter((c) => c.kind !== 'neutral')
            .map((c) => (
              <Button
                key={c.kind}
                size="xs"
                variant={picked.includes(c.kind) ? 'filled' : 'default'}
                data-testid={`talk-move-${c.kind}`}
                aria-pressed={picked.includes(c.kind)}
                onClick={() =>
                  setPicked(
                    picked.includes(c.kind)
                      ? picked.filter((k) => k !== c.kind)
                      : [...picked, c.kind].slice(-MAX_PICKED),
                  )
                }
              >
                {c.label}
              </Button>
            ))}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {t.suggestions.map((s) => (
              <Button
                key={s}
                size="xs"
                variant="subtle"
                justify="flex-start"
                data-testid="talk-suggestion"
                onClick={() => setMessage(s)}
                style={{ whiteSpace: 'normal', height: 'auto', textAlign: 'left' }}
              >
                {s}
              </Button>
            ))}
          </div>
          <Textarea
            label="Your answer"
            data-testid="talk-message"
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
          data-testid="talk-send"
          loading={answer.isPending}
          disabled={template ? picked.length === 0 : !message.trim()}
          onClick={send}
        >
          {template ? 'Answer with these moves' : 'Send'}
        </Button>
        <Button
          size="xs"
          variant="default"
          data-testid="talk-skip"
          loading={skip.isPending}
          onClick={() => skip.mutate()}
        >
          Skip (today’s outcome: nothing changes)
        </Button>
      </div>
      {error && (
        <Alert color="red" data-testid="talk-error">
          {error.message}
        </Alert>
      )}
    </section>
  );
}

function Effects({ t }: { t: Talk }) {
  return (
    <section aria-label="What the talk did" data-testid="talk-effects">
      <h4 className="tst-ptitle">What the talk did</h4>
      {t.error && (
        <Alert color="red" data-testid="talk-error">
          {t.error}
        </Alert>
      )}
      {t.effects.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          {t.status === 'skipped' ? 'Skipped: nothing changed.' : 'Nothing moved.'}
        </p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {t.effects.map((e) => (
            <li key={`${e.what}-${e.words}`} data-testid="talk-effect">
              {e.words}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
