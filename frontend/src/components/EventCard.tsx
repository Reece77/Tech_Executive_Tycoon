import { Button, Modal } from '@mantine/core';
import { Link } from 'react-router';
import { useChooseEvent, useEvents, type GameEventOut } from '../hooks/api';
import { IpoEventPricing } from './IpoPanel';
import { Term } from './Term';
import { usePress } from '../hooks/press';
import { returnToDecision, setAside, useSetAside } from '../lib/setAside';

const SEVERITY_STYLE: Record<string, { color: string; background: string; label: string }> = {
  minor: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)', label: 'Minor' },
  major: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)', label: 'Major' },
  critical: { color: 'var(--tst-bg)', background: 'var(--tst-warn)', label: 'Critical' },
};

/** One event (M6, wireframe "Events"): category and severity, its storyline, the title and
 * body, and two or three choices as full-width buttons with their effects in words. Effects
 * apply at once; the text is written by AI (or a template) within the game's rules. */
export function EventCard({
  saveId,
  event,
  onLook,
}: {
  saveId: string;
  event: GameEventOut;
  /** Called before following one of the event's links (the critical modal sets it aside). */
  onLook?: () => void;
}) {
  const choose = useChooseEvent(saveId);
  const severity = SEVERITY_STYLE[event.severity] ?? SEVERITY_STYLE.minor;
  const open = event.status === 'open';
  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      data-testid="event-card"
      data-event-id={event.event_id}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          {event.category_label}
        </span>
        <span
          style={{
            ...severity,
            fontSize: 11,
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '.04em',
            padding: '2px 6px',
            borderRadius: 4,
          }}
          data-testid="event-severity"
        >
          {severity.label}
        </span>
        {event.storyline && (
          <span className="tst-muted" style={{ fontSize: 12 }} data-testid="event-storyline">
            {event.storyline.title} · step {event.storyline.step}
          </span>
        )}
        <span className="tst-num tst-muted" style={{ fontSize: 12, marginLeft: 'auto' }}>
          {event.date_label}
        </span>
      </div>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }} data-testid="event-title">
        {event.title}
      </h2>
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--tst-text-2)' }}>
        {event.body}
      </p>
      {open && event.links.length > 0 && (
        <div
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', fontSize: 13 }}
          data-testid="event-links"
        >
          <span className="tst-muted" style={{ fontSize: 12 }}>
            Look first:
          </span>
          {event.links.map((l) => (
            <Link
              key={l.path}
              to={`/game/${saveId}/${l.path}`}
              onClick={onLook}
              data-testid="event-link"
              style={{ textDecoration: 'none' }}
            >
              {l.label}
            </Link>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {event.choices.map((c) => {
          const chosen = event.chosen === c.key;
          return (
            <div key={c.key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <Button
                fullWidth
                h={44}
                justify="flex-start"
                variant={chosen ? 'filled' : 'default'}
                disabled={!open || choose.isPending}
                loading={choose.isPending && choose.variables?.choice === c.key}
                onClick={() => choose.mutate({ eventId: event.event_id, choice: c.key })}
                data-testid="event-choice"
                data-choice={c.key}
              >
                {c.key}. {c.label}
              </Button>
              <span className="tst-muted" style={{ fontSize: 12, paddingLeft: 4 }}>
                {c.effects.length ? c.effects.join(' · ') : 'Nothing changes'}
              </span>
            </div>
          );
        })}
      </div>
      {choose.error && (
        <span role="alert" style={{ color: 'var(--tst-warn)', fontSize: 13 }}>
          {choose.error.message}
        </span>
      )}
      {!open && event.chosen && (
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="event-answered">
          {event.status === 'auto' ? 'Answered at Continue with' : 'You chose'} {event.chosen}.
        </span>
      )}
      {event.category === 'press' && <PressNote saveId={saveId} event={event} />}
      {event.template_id === 'founder_burnout' && (
        <span className="tst-muted" style={{ fontSize: 12 }} data-testid="burnout-note">
          A takes this month off; B: open the{' '}
          <Link to={`/game/${saveId}/org`} data-testid="burnout-exec-link">
            Executive team panel
          </Link>{' '}
          and hand more to your executives; C pushes on.
        </span>
      )}
      {event.follow_up_note && (
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {event.follow_up_note}
        </span>
      )}
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Effects apply at once. Written by {event.written_by === 'Claude' ? 'AI' : 'a template'}{' '}
        within the game&apos;s rules (<Link to={`/game/${saveId}/settings`}>AI writing</Link>).
      </span>
    </div>
  );
}

/** A press moment (M14b, 29.1): the tones behind its choices, and once answered bold or
 * measured, the way to a public promise this month. */
function PressNote({ saveId, event }: { saveId: string; event: GameEventOut }) {
  const press = usePress(saveId);
  const promising =
    (event.chosen === 'A' || event.chosen === 'B') && press.data?.form.moment_id != null;
  return (
    <span className="tst-muted" style={{ fontSize: 12 }} data-testid="press-note">
      <Term term="press_moment">Press moment</Term>: A is{' '}
      <Term term="press.measured">measured</Term>, B is <Term term="press.bold">bold</Term>, C is{' '}
      <Term term="press.no_comment">no comment</Term>.{' '}
      {promising && (
        <Link to={`/game/${saveId}/overview`} data-testid="press-promise-link">
          Make a public promise this month on the Overview
        </Link>
      )}
      {!event.chosen && event.template_id === 'press_launch' && (
        // playtest 3 addendum 14 (M15b): promises went unnoticed, so the launch card says so
        <strong data-testid="press-promise-hint">
          Answer measured or bold, then you can make a public promise about this launch (ship, beat
          a rival, research) on the Overview.
        </strong>
      )}
    </span>
  );
}

/** A critical event opens as a modal; Continue waits for it. It can be set aside to look
 * around read only (M23c), with a banner back to it (SetAsideBanner). */
export function CriticalEventModal({ saveId }: { saveId: string }) {
  const events = useEvents(saveId);
  const blockingId = events.data?.blocking_event_id ?? null;
  const blocking = events.data?.open.find((e) => e.event_id === blockingId);
  const aside = useSetAside(saveId, blockingId);
  const look = () => {
    if (blockingId !== null) setAside(saveId, blockingId);
  };
  return (
    <Modal
      opened={blocking !== undefined && !aside}
      onClose={look}
      withCloseButton={false}
      closeOnClickOutside={false}
      closeOnEscape={false}
      size="lg"
      centered
      title="Critical decision"
      data-testid="critical-modal"
    >
      {blocking && <EventCard saveId={saveId} event={blocking} onLook={look} />}
      {blocking?.category === 'public' && (
        <div style={{ marginTop: 16 }}>
          <IpoEventPricing saveId={saveId} />
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
        <Button variant="subtle" size="xs" onClick={look} data-testid="set-aside">
          Set aside and look around (read only)
        </Button>
      </div>
    </Modal>
  );
}

/** While a critical decision is set aside: a banner that stays above the working pane, its
 * links, and the way back. Continue stays blocked. */
export function SetAsideBanner({ saveId }: { saveId: string }) {
  const events = useEvents(saveId);
  const blockingId = events.data?.blocking_event_id ?? null;
  const blocking = events.data?.open.find((e) => e.event_id === blockingId);
  const aside = useSetAside(saveId, blockingId);
  if (!aside || !blocking) return null;
  return (
    <div
      role="status"
      data-testid="set-aside-banner"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 10,
        padding: '8px 16px',
        background: 'var(--tst-gold-bg)',
        borderBottom: '1px solid var(--tst-border)',
        fontSize: 13,
      }}
    >
      <strong style={{ color: 'var(--tst-warn)' }}>Critical decision waiting:</strong>
      <span>{blocking.title}</span>
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Looking around read only; Continue waits for your answer.
      </span>
      {blocking.links.map((l) => (
        <Link key={l.path} to={`/game/${saveId}/${l.path}`} style={{ textDecoration: 'none' }}>
          {l.label}
        </Link>
      ))}
      <Button
        size="xs"
        color="warn"
        style={{ marginLeft: 'auto' }}
        onClick={() => returnToDecision(saveId)}
        data-testid="back-to-decision"
      >
        Back to the decision
      </Button>
    </div>
  );
}
