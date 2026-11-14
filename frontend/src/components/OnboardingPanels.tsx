import { Alert, Button } from '@mantine/core';
import { Link } from 'react-router';
import { Panel } from './ScreenState';
import { useEvents, useInbox, type Overview } from '../hooks/api';
import { useDigest } from '../hooks/automation';
import { useDismissGettingStarted, useGettingStarted, useWhatNext } from '../hooks/onboarding';
import { GUIDES, whatNextHref } from '../lib/guides';

// The Overview's onboarding panels (M29, formulas.md 42.2-42.4): Getting started in the first
// year, What next, alerts and the latest digest. Everything shown comes from the API.

export function GettingStartedPanel({ saveId }: { saveId: string }) {
  const gs = useGettingStarted(saveId);
  const dismiss = useDismissGettingStarted(saveId);
  if (!gs.data?.visible) return null;
  const done = gs.data.steps.filter((s) => s.done).length;
  return (
    <Panel
      title={`Getting started · ${done} of ${gs.data.steps.length}`}
      label="Getting started"
      testId="getting-started"
      action={
        <Button
          size="compact-sm"
          variant="subtle"
          loading={dismiss.isPending}
          onClick={() => dismiss.mutate()}
          data-testid="getting-started-dismiss"
        >
          Dismiss
        </Button>
      }
    >
      <p className="tst-muted" style={{ margin: '0 0 8px', fontSize: 13 }}>
        Your first year, {gs.data.months_left} month{gs.data.months_left === 1 ? '' : 's'} left.
        {gs.data.speaker === 'Your notes'
          ? 'Your own notes until a chief of staff writes them.'
          : `Notes from ${gs.data.speaker}.`}
      </p>
      {gs.data.steps.map((s) => (
        <div
          key={s.key}
          className="tst-row"
          data-testid={`step-${s.key}`}
          data-done={s.done ? 'true' : 'false'}
          style={{ alignItems: 'flex-start' }}
        >
          <span style={{ display: 'flex', gap: 8 }}>
            <span aria-label={s.done ? 'Done' : 'To do'} style={{ width: 16 }}>
              {s.done ? '✓' : '○'}
            </span>
            <span>
              <Link
                to={`/game/${saveId}/${GUIDES[s.screen]?.path ?? s.screen}`}
                style={s.done ? { color: 'var(--tst-muted)' } : undefined}
              >
                {s.label}
              </Link>
              <span className="tst-muted" style={{ display: 'block', fontSize: 12 }}>
                {s.note}
              </span>
            </span>
          </span>
        </div>
      ))}
    </Panel>
  );
}

export function WhatNextPanel({ saveId }: { saveId: string }) {
  const next = useWhatNext(saveId);
  return (
    <Panel title="What next" label="What next" testId="what-next">
      {next.isPending ? (
        <p className="tst-muted" style={{ margin: 0 }}>
          Loading…
        </p>
      ) : !next.data || next.data.items.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0, fontSize: 14 }}>
          Nothing urgent. Press Continue when you are ready.
        </p>
      ) : (
        <ol style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 4 }}>
          {next.data.items.map((item, i) => (
            <li key={`${item.key}-${i}`} data-testid="what-next-item" data-key={item.key}>
              <Link to={whatNextHref(saveId, item)}>{item.text}</Link>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

/** Alerts: runway short, and events that stop Continue (23.1, 42.4). */
export function OverviewAlerts({ saveId, overview }: { saveId: string; overview: Overview }) {
  const events = useEvents(saveId).data;
  const blocking = events?.blocking_event_ids.length ?? 0;
  if (!overview.runway_low && blocking === 0) return null;
  return (
    <div style={{ display: 'grid', gap: 8 }} data-testid="overview-alerts">
      {overview.runway_low && (
        <Alert color="red" title="Runway is short">
          At this month&apos;s costs the cash runs out soon.{' '}
          <Link to={`/game/${saveId}/finance/fundraising`}>Raise money</Link> or cut costs.
        </Alert>
      )}
      {blocking > 0 && (
        <Alert color="yellow" title={`${blocking} event${blocking === 1 ? '' : 's'} to answer`}>
          They stop Continue until answered.{' '}
          <Link to={`/game/${saveId}/inbox?tab=needs_you`}>Open Needs you</Link>
        </Alert>
      )}
    </div>
  );
}

/** The latest monthly digest (kind `digest`, 40.4); it appears once M27a writes them. */
export function LatestDigest({ saveId }: { saveId: string }) {
  const item = useInbox(saveId, 0, ['digest']).data?.items[0];
  const digest = useDigest(saveId).data; // M27a (40.4): the attention lines, from its structure
  if (!item) return null;
  const lines = digest?.attention ?? [];
  return (
    <Panel title="Your month" label="Latest digest" testId="latest-digest">
      <Link to={`/game/${saveId}/inbox/${item.item_id}`}>{item.title}</Link>
      {lines.length > 0 ? (
        <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }} data-testid="digest-lines">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : (
        <p
          className="tst-muted"
          style={{ margin: '6px 0 0', fontSize: 13, whiteSpace: 'pre-line' }}
        >
          {digest?.opening ?? item.body.split('\n').slice(0, 4).join('\n')}
        </p>
      )}
    </Panel>
  );
}
