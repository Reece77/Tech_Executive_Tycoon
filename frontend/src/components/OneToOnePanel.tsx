import { Alert, Badge, Button } from '@mantine/core';
import { useSearchParams } from 'react-router';
import { useOpenTalk, useTalks, type TalkList, type TalkPerson } from '../hooks/talks';
import { Panel } from './ScreenState';
import { FLAG_LABEL, TALK_STATUS } from '../lib/talks';
import { TalkRoom } from './TalkRoom';
import { Term } from './Term';

// One-to-ones on a person's profile (M49, formulas.md 61.2): why they are flagged, hold a
// one-to-one (or ask a seat holder above them to hold it), the talk room, past one-to-ones, and
// the promotions promised to them with their status. The engine decides every effect.

/** A person's flags as badges (unhappy, approached by a rival). */
export function TalkFlags({ person }: { person: TalkPerson }) {
  const shown = person.flags.filter((f) => f !== 'seat');
  if (shown.length === 0) return null;
  return (
    <span style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
      {shown.map((f) => (
        <Badge
          key={f}
          size="xs"
          color={f === 'approached' ? 'red' : 'yellow'}
          variant="light"
          data-testid={`person-flag-${f}`}
          title={f === 'approached' && person.approached_by ? person.approached_by : undefined}
        >
          {f === 'approached' && person.approached_by
            ? `Approached by ${person.approached_by}`
            : (FLAG_LABEL[f] ?? f)}
        </Badge>
      ))}
    </span>
  );
}

export function OneToOnePanel({ saveId, personId }: { saveId: string; personId: number }) {
  const q = useTalks(saveId);
  if (!q.data) return null; // the profile loads without it
  return <OneToOneBody saveId={saveId} personId={personId} list={q.data} />;
}

export function OneToOneBody({
  saveId,
  personId,
  list,
}: {
  saveId: string;
  personId: number;
  list: TalkList;
}) {
  const [params, setParams] = useSearchParams();
  const open = useOpenTalk(saveId);
  const person = list.people.find((p) => p.person_id === personId);
  const promises = list.promises.filter((p) => p.person_id === personId);
  const past = list.items.filter((t) => t.kind === 'one_to_one' && t.person_id === personId);
  if (!person && promises.length === 0) return null;
  const raw = params.get('talk');
  const shownId = raw !== null && /^\d+$/.test(raw) ? Number(raw) : null;
  const select = (id: number) => setParams({ talk: String(id) }, { replace: true });
  const hold = (delegateId?: number) =>
    open.mutate(
      {
        kind: 'one_to_one',
        params:
          delegateId === undefined
            ? { person_id: personId }
            : { person_id: personId, delegate_id: delegateId },
      },
      { onSuccess: (t) => select(t.talk_id) },
    );
  const names = new Map(list.people.map((p) => [p.person_id, p.name]));
  const firstName = person?.name.split(' ')[0] ?? '';
  const held = person?.held ?? '';
  const resumable = held === 'open';
  const blocked = held !== '' && !resumable;
  return (
    <Panel title="One-to-ones and promises" label="One-to-one" testId="one-to-one-panel">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="one-to-one">
        {person && (
          <>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <TalkFlags person={person} />
              <Button
                size="xs"
                data-testid="one-to-one-open"
                disabled={blocked}
                loading={open.isPending && open.variables?.params?.delegate_id === undefined}
                onClick={() => hold()}
              >
                {resumable ? (
                  'Resume the one-to-one'
                ) : (
                  <>
                    Hold a <Term term="talk.one_to_one">one-to-one</Term> with {firstName}
                  </>
                )}
              </Button>
              {!blocked &&
                !resumable &&
                person.delegates.map((d) => (
                  <Button
                    key={d}
                    size="xs"
                    variant="default"
                    data-testid="one-to-one-delegate"
                    loading={open.isPending && open.variables?.params?.delegate_id === d}
                    onClick={() => hold(d)}
                  >
                    Ask {names.get(d) ?? 'their executive'} to hold it
                  </Button>
                ))}
              <span className="tst-muted" style={{ fontSize: 12 }} data-testid="one-to-one-note">
                {blocked
                  ? `Already held this month (${TALK_STATUS[held] ?? held}); one a month.`
                  : `Costs your founder ${list.one_to_one_energy} energy when it ends${
                      list.energy !== null ? ` (you have ${list.energy})` : ''
                    }; skipping costs nothing.`}
              </span>
            </div>
            {open.error && (
              <Alert color="red" data-testid="one-to-one-error">
                {open.error.message}
              </Alert>
            )}
          </>
        )}
        {shownId !== null && <TalkRoom key={shownId} saveId={saveId} id={shownId} />}
        {past.length > 0 && (
          <div style={{ fontSize: 13 }} data-testid="one-to-one-past">
            <span className="tst-muted">Past one-to-ones: </span>
            {past.map((t, i) => (
              <span key={t.talk_id}>
                {i > 0 && ' · '}
                <Button size="compact-xs" variant="subtle" onClick={() => select(t.talk_id)}>
                  {t.date_label}: {TALK_STATUS[t.status] ?? t.status}
                </Button>
                {t.effects.length > 0 && (
                  <span className="tst-muted"> ({t.effects.join('; ')})</span>
                )}
              </span>
            ))}
          </div>
        )}
        <section aria-label="Promises made to them" data-testid="talk-promises">
          <h4 className="tst-ptitle" style={{ margin: '4px 0' }}>
            <Term term="talk.promise">Promises</Term>
          </h4>
          {promises.length === 0 ? (
            <span className="tst-muted" style={{ fontSize: 13 }}>
              No promises made to {firstName || 'them'}.
            </span>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
              {promises.map((p) => (
                <li key={p.promise_id} data-testid="talk-promise" data-status={p.status}>
                  {p.words} · made {p.made_label}, due {p.deadline_label} ·{' '}
                  <strong
                    data-testid="talk-promise-status"
                    className={p.status === 'broken' ? 'tst-negative' : undefined}
                  >
                    {p.status}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Panel>
  );
}
