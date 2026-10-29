import { Button, Modal } from '@mantine/core';
import { Link } from 'react-router';
import { useChooseEvent, useEvents, type GameEventOut } from '../hooks/api';

const SEVERITY_STYLE: Record<string, { color: string; background: string; label: string }> = {
  minor: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)', label: 'Minor' },
  major: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)', label: 'Major' },
  critical: { color: 'var(--tst-bg)', background: 'var(--tst-warn)', label: 'Critical' },
};

/** One event (M6, wireframe "Events"): category and severity, its storyline, the title and
 * body, and two or three choices as full-width buttons with their effects in words. Effects
 * apply at once; the text is written by AI (or a template) within the game's rules. */
export function EventCard({ saveId, event }: { saveId: string; event: GameEventOut }) {
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
                {c.effects.length ? c.effects.join(' · ') : 'Nothing else changes'}
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

/** A critical event opens as a modal that cannot be dismissed; Continue waits for it. */
export function CriticalEventModal({ saveId }: { saveId: string }) {
  const events = useEvents(saveId);
  const blocking = events.data?.open.find((e) => e.event_id === events.data?.blocking_event_id);
  return (
    <Modal
      opened={blocking !== undefined}
      onClose={() => undefined}
      withCloseButton={false}
      closeOnClickOutside={false}
      closeOnEscape={false}
      size="lg"
      centered
      title="Critical decision"
      data-testid="critical-modal"
    >
      {blocking && <EventCard saveId={saveId} event={blocking} />}
    </Modal>
  );
}
