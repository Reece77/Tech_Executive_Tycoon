import { Alert, Button, Drawer, Textarea } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import { useAskCoo, useCoo, type Coo } from '../hooks/api';
import { LoadError, Loading } from './ScreenState';

// Ask my COO (M7b; formulas.md 17.3): the briefing (engine, always available), a question
// answered within the AI budget, and the last answers. It never changes the game.

function issueHref(saveId: string, issue: Coo['briefing'][number]): string {
  const base = `/game/${saveId}`;
  switch (issue.link_kind) {
    case 'event':
      return issue.link_id != null ? `${base}/events/${issue.link_id}` : `${base}/inbox`;
    case 'product':
      return `${base}/products/${issue.link_id}`;
    case 'person':
      return `${base}/people/${issue.link_id}`;
    case 'org':
      return `${base}/org`;
    case 'recruitment':
      return `${base}/recruitment`;
    case 'board':
      return `${base}/finance/board`;
    case 'rival':
      return `${base}/competitors/${issue.link_id}`;
    default:
      return `${base}/finance`;
  }
}

function cents(value: number): string {
  return value >= 100 ? `$${(value / 100).toFixed(2)}` : `${value.toFixed(2)}¢`;
}

export function CooPanel({ saveId, onClose }: { saveId: string; onClose: () => void }) {
  const coo = useCoo(saveId, true);
  const ask = useAskCoo(saveId);
  const [question, setQuestion] = useState('');
  const c = coo.data;
  const title = c ? (c.role_label ? `Ask ${c.name}, ${c.role_label}` : c.name) : 'Ask my COO';
  const first = c?.name.split(' ')[0] ?? 'They';
  return (
    <Drawer opened onClose={onClose} title={title} position="right" size="lg">
      {coo.isPending ? (
        <Loading />
      ) : coo.error || !c ? (
        <LoadError title="Could not load the briefing" error={coo.error} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="coo-panel">
          <section aria-label="Briefing">
            <h3 className="tst-ptitle">Briefing</h3>
            {c.briefing.length === 0 ? (
              <p style={{ margin: 0 }} data-testid="coo-nothing">
                Nothing urgent.
              </p>
            ) : (
              <ol
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                {c.briefing.map((issue) => (
                  <li
                    key={`${issue.key}-${issue.link_id ?? ''}-${issue.text}`}
                    data-testid="coo-issue"
                  >
                    <Link to={issueHref(saveId, issue)} onClick={onClose}>
                      {issue.text}
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (question.trim()) ask.mutate(question, { onSuccess: () => setQuestion('') });
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            <Textarea
              label="Your question"
              autosize
              minRows={2}
              maxLength={c.max_question_chars}
              value={question}
              onChange={(e) => setQuestion(e.currentTarget.value)}
              description={`${question.length} / ${c.max_question_chars} characters`}
              data-testid="coo-question"
            />
            {ask.error && (
              <Alert color="red" title="No answer">
                {ask.error.message}
              </Alert>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                AI this month {cents(c.spend_cents)} of {cents(c.budget_cents)}
              </span>
              <Button
                type="submit"
                ml="auto"
                h={44}
                loading={ask.isPending}
                disabled={!question.trim()}
                data-testid="coo-ask"
              >
                Ask
              </Button>
            </div>
          </form>
          <section
            aria-label="Answers"
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            {c.answers.map((a) => (
              <article
                key={a.answer_id}
                className="tst-panel"
                style={{ padding: '12px 14px' }}
                data-testid="coo-answer"
              >
                <div className="tst-muted" style={{ fontSize: 12 }}>
                  {a.date_label} · you asked: {a.question}
                </div>
                <p style={{ margin: '6px 0', whiteSpace: 'pre-line' }}>{a.answer}</p>
                <div className="tst-muted" style={{ fontSize: 12 }}>
                  {a.speaker}
                  {a.source === 'offline' ? ' · offline' : ` · cost ${cents(a.cost_cents)}`}
                </div>
              </article>
            ))}
          </section>
          <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
            {c.person_id === null
              ? 'Your notebook only knows what you know.'
              : `${first} only knows what you know: the numbers and people you can see.`}{' '}
            Offline you still get the briefing{c.offline ? ', and that is what answers now' : ''}.
          </p>
        </div>
      )}
    </Drawer>
  );
}
