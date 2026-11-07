import { Button } from '@mantine/core';
import { useState, type ReactNode } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router';
import { EventCard } from '../components/EventCard';
import { KindBadge } from '../components/KindBadge';
import { ApproachPanel } from './CompetitorsScreen';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import {
  useEventItem,
  useInboxItem,
  INBOX_PAGE,
  useApproaches,
  useArchive,
  useBookmark,
  useEvent,
  useEvents,
  useInbox,
  useInboxBulk,
  useOverview,
  usePerson,
  useSetRead,
  useStorylines,
  type InboxItem,
} from '../hooks/api';
import { formatMoney, formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import {
  financeTab,
  kindLabel,
  kindsFor,
  pageRange,
  preview,
  type InboxFilter,
} from '../lib/inbox';
import { moraleBand } from '../lib/attr';
import { useReplace, useReplaceable } from '../hooks/press';

const FILTERS: { key: InboxFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'unread', label: 'Unread' },
  { key: 'people', label: 'People' },
  { key: 'hiring', label: 'Hiring' },
  { key: 'products', label: 'Products' },
  { key: 'finance', label: 'Finance' },
  { key: 'archived', label: 'Archived' },
];

export function InboxScreen() {
  const { saveId = '', itemId } = useParams();
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<InboxFilter>('all');
  // Filters run in the API, so they apply across every page, not only the one shown (M3b).
  const inbox = useInbox(
    saveId,
    offset,
    kindsFor(filter),
    filter === 'unread',
    filter === 'archived',
  );
  const overview = useOverview(saveId);
  const setRead = useSetRead(saveId);
  const archive = useArchive(saveId);
  const bulk = useInboxBulk(saveId);
  const [params] = useSearchParams();
  // M7c: /inbox/:itemId (and the older ?item=) open that message even off the first page.
  const selectedId = Number(itemId ?? params.get('item'));
  const onPage = inbox.data?.items.some((m) => m.item_id === selectedId) ?? false;
  const pinned = useInboxItem(saveId, selectedId, !inbox.isPending && !onPage);

  if (inbox.isPending) return <Loading />;
  if (inbox.error) return <LoadError title="Could not load the inbox" error={inbox.error} />;

  const items = inbox.data.items;
  const selected =
    items.find((m) => m.item_id === selectedId) ??
    (pinned.data?.item_id === selectedId ? pinned.data : undefined) ??
    (selectedId > 0 && pinned.isPending && !onPage ? undefined : items[0]);

  const open = (item: InboxItem) => {
    navigate(`/game/${saveId}/inbox/${item.item_id}`, { replace: true });
    if (!item.read) setRead.mutate({ itemId: item.item_id, read: true });
  };

  return (
    <>
      <ScreenTitle
        aside={
          <>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="inbox-unread">
              {inbox.data.unread} unread{overview.data ? ` · ${overview.data.date_label}` : ''}
            </span>
            <Button
              size="compact-sm"
              variant="subtle"
              disabled={inbox.data.unread === 0}
              loading={bulk.isPending && bulk.variables === 'read-all'}
              onClick={() => bulk.mutate('read-all')}
              data-testid="inbox-read-all"
            >
              Mark all as read
            </Button>
            <Button
              size="compact-sm"
              variant="subtle"
              disabled={filter === 'archived'}
              loading={bulk.isPending && bulk.variables === 'archive-read'}
              onClick={() => bulk.mutate('archive-read')}
              data-testid="inbox-archive-read"
            >
              Archive all read
            </Button>
            <div
              role="group"
              aria-label="Filter messages"
              style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}
            >
              {FILTERS.map((f) => (
                <Button
                  key={f.key}
                  size="sm"
                  h={36}
                  variant="default"
                  fw={filter === f.key ? 600 : 400}
                  styles={{
                    root: {
                      background: filter === f.key ? 'var(--tst-panel-active)' : 'transparent',
                      color: filter === f.key ? 'var(--tst-text)' : 'var(--tst-text-2)',
                    },
                  }}
                  aria-pressed={filter === f.key}
                  onClick={() => {
                    setFilter(f.key);
                    setOffset(0);
                  }}
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </>
        }
      >
        Inbox
      </ScreenTitle>
      <EventsHeader saveId={saveId} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <section
          aria-label="Messages"
          className="tst-panel"
          style={{ flex: '1 1 420px', padding: 0, overflow: 'hidden' }}
        >
          {items.length === 0 ? (
            <p className="tst-muted" style={{ margin: 0, padding: 16 }}>
              {filter === 'all'
                ? 'Nothing in the inbox. Archived messages are under Archived.'
                : filter === 'archived'
                  ? 'Nothing archived yet.'
                  : 'No messages match this filter.'}
            </p>
          ) : (
            items.map((m) => (
              <button
                key={m.item_id}
                type="button"
                className="tst-msg"
                aria-current={m.item_id === selected?.item_id}
                onClick={() => open(m)}
                data-testid="inbox-item"
              >
                <KindBadge kind={m.kind} />
                <span
                  style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, flex: 1 }}
                >
                  <span
                    style={{
                      fontSize: 14,
                      fontWeight: m.read ? 400 : 600,
                      color: m.read ? 'var(--tst-text-2)' : 'var(--tst-text)',
                    }}
                  >
                    {m.bookmarked && (
                      <span aria-label="Bookmarked" title="Bookmarked: never auto-archived">
                        ★{' '}
                      </span>
                    )}
                    {m.title}
                  </span>
                  <span
                    className="tst-muted"
                    style={{
                      fontSize: 13,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {preview(m.body)}
                  </span>
                </span>
                <span className="tst-num tst-muted" style={{ flex: 'none', fontSize: 12 }}>
                  {m.date_label}
                </span>
              </button>
            ))
          )}
          {inbox.data.total > INBOX_PAGE && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 16px',
                borderTop: '1px solid var(--tst-rule)',
              }}
            >
              <span className="tst-num tst-muted" style={{ fontSize: 13 }} data-testid="inbox-page">
                {pageRange(offset, inbox.data.items.length, inbox.data.total)}
              </span>
              <Button
                size="compact-sm"
                variant="default"
                ml="auto"
                disabled={offset === 0}
                data-testid="inbox-newer"
                onClick={() => setOffset(Math.max(0, offset - INBOX_PAGE))}
              >
                Newer
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                disabled={offset + INBOX_PAGE >= inbox.data.total}
                data-testid="inbox-older"
                onClick={() => setOffset(offset + INBOX_PAGE)}
              >
                Older
              </Button>
            </div>
          )}
          <OngoingStories saveId={saveId} />
        </section>
        {selected && (
          <MessageDetail
            key={selected.item_id}
            saveId={saveId}
            item={selected}
            onMarkUnread={() => setRead.mutate({ itemId: selected.item_id, read: false })}
            onArchive={(archived) =>
              archive.mutate(
                { itemId: selected.item_id, archived },
                { onSuccess: () => navigate(`/game/${saveId}/inbox`, { replace: true }) },
              )
            }
          />
        )}
      </div>
    </>
  );
}

function MessageDetail({
  saveId,
  item,
  onMarkUnread,
  onArchive,
}: {
  saveId: string;
  item: InboxItem;
  onMarkUnread: () => void;
  onArchive: (archived: boolean) => void;
}) {
  const linksPerson = item.link_kind === 'person' || item.link_kind === 'candidate';
  const person = usePerson(saveId, linksPerson && item.link_id ? item.link_id : 0);
  const p = person.data;
  const emp = p?.employment;
  const isNotice = kindLabel(item.kind) === 'Notice';
  const event = useEvent(saveId, item.link_kind === 'event' ? item.link_id : null);

  if (item.link_kind === 'event') {
    return (
      <article
        aria-label="Selected message"
        className="tst-panel"
        style={{ flex: '1 1 380px', padding: '20px 24px' }}
      >
        {event.data ? (
          <EventCard saveId={saveId} event={event.data} />
        ) : (
          <p className="tst-muted" style={{ margin: 0 }}>
            {event.error ? event.error.message : 'Loading the event…'}
          </p>
        )}
        <div style={{ display: 'flex', gap: 8, paddingTop: 12 }}>
          <Button
            variant="default"
            h={44}
            onClick={() => onArchive(!item.archived)}
            data-testid={item.archived ? 'inbox-unarchive' : 'inbox-archive'}
          >
            {item.archived ? 'Move to inbox' : 'Archive'}
          </Button>
          <BookmarkButton saveId={saveId} item={item} />
        </div>
      </article>
    );
  }

  return (
    <article
      aria-label="Selected message"
      className="tst-panel"
      style={{
        flex: '1 1 380px',
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <KindBadge kind={item.kind} />
        <span className="tst-num tst-muted" style={{ fontSize: 12 }}>
          {item.date_label}
        </span>
      </div>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }} data-testid="message-title">
        {item.title}
      </h2>
      <p
        style={{
          margin: 0,
          fontSize: 14,
          lineHeight: 1.55,
          color: 'var(--tst-text-2)',
          whiteSpace: 'pre-line',
        }}
        data-testid="message-body"
      >
        {item.body}
      </p>
      {(item.event_links ?? []).length > 0 && (
        <div data-testid="message-event-links">
          <div className="tst-muted" style={{ fontSize: 12 }}>
            Open an event:
          </div>
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
            {(item.event_links ?? []).map((e) => (
              <li key={e.event_id}>
                <Link to={`/game/${saveId}/events/${e.event_id}`} data-testid="message-event-link">
                  {e.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {item.quote && (
        <blockquote
          style={{ margin: 0, fontSize: 14, fontStyle: 'italic', color: 'var(--tst-text)' }}
          data-testid="exit-quote"
        >
          {item.quote}
        </blockquote>
      )}
      {p && (emp || p.candidacy) && (
        <dl
          style={{
            margin: 0,
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: '10px 16px',
            fontSize: 13,
          }}
        >
          <Fact label="Role">
            {[p.role_label, p.level ? humanize(p.level) : null].filter(Boolean).join(' · ')}
          </Fact>
          {p.morale !== null && (
            <Fact label="Morale" warn={moraleBand(p.morale) === 'low'} num>
              {formatWhole(p.morale)}
            </Fact>
          )}
          {emp?.end_date_label && (
            <Fact label="Last day" num>
              {emp.end_date_label}
            </Fact>
          )}
          {emp && !p.is_founder && (
            <Fact label="Salary" num>
              {formatMoneyWhole(emp.salary_cents)}
            </Fact>
          )}
          {p.candidacy && (
            <Fact label="Asks" num>
              {formatMoneyWhole(p.candidacy.salary_expectation_cents)}
            </Fact>
          )}
        </dl>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingTop: 4 }}>
        {p && (
          <Button component={Link} to={`/game/${saveId}/people/${p.person_id}`} h={44}>
            View profile
          </Button>
        )}
        {isNotice && item.link_id !== null && (
          <ReplaceButton saveId={saveId} personId={item.link_id} />
        )}
        {isNotice && p?.role && (
          <Button
            component={Link}
            to={`/game/${saveId}/recruitment?role=${p.role}`}
            variant="default"
            h={44}
          >
            Find a replacement
          </Button>
        )}
        {item.link_kind === 'rival' && item.link_id !== null && (
          <Button
            component={Link}
            to={`/game/${saveId}/competitors/${item.link_id}`}
            h={44}
            data-testid="view-rival"
          >
            Open the rival
          </Button>
        )}
        {item.kind.startsWith('promise_') && (
          <Button
            component={Link}
            to={`/game/${saveId}/overview`}
            h={44}
            variant="default"
            data-testid="view-promises"
          >
            Open Promises
          </Button>
        )}
        {item.link_kind === 'search' && (
          <Button component={Link} to={`/game/${saveId}/recruitment?search=${item.link_id}`} h={44}>
            View candidates
          </Button>
        )}
        {item.link_kind === 'rival' && item.link_id !== null && (
          <Button
            component={Link}
            to={`/game/${saveId}/competitors/${item.link_id}`}
            h={44}
            data-testid="view-company"
          >
            View company
          </Button>
        )}
        {item.link_kind === 'product' && item.link_id !== null && (
          <Button
            component={Link}
            to={`/game/${saveId}/products/${item.link_id}`}
            h={44}
            data-testid="view-product"
          >
            View product
          </Button>
        )}
        {kindLabel(item.kind) === 'Finance' && (
          <Button
            component={Link}
            to={`/game/${saveId}/finance/${financeTab(item.kind)}`}
            h={44}
            data-testid="view-finance"
          >
            {item.kind === 'bridge_offered' ? 'View the bridge offer' : 'Open Finance'}
          </Button>
        )}
        {item.link_kind === 'history' && (
          <Button component={Link} to={`/game/${saveId}/history`} h={44} data-testid="view-history">
            Open History
          </Button>
        )}
        {item.kind === 'rival_approach' && (
          <ApproachActions saveId={saveId} personId={item.link_id} />
        )}
        {(item.kind === 'market_news' || item.kind === 'rival_approach') && (
          <Button component={Link} to={`/game/${saveId}/competitors`} variant="default" h={44}>
            Open Competitors
          </Button>
        )}
        {item.read && !item.archived && (
          <Button variant="default" h={44} onClick={onMarkUnread}>
            Mark unread
          </Button>
        )}
        <Button
          variant="default"
          h={44}
          onClick={() => onArchive(!item.archived)}
          data-testid={item.archived ? 'inbox-unarchive' : 'inbox-archive'}
        >
          {item.archived ? 'Move to inbox' : 'Archive'}
        </Button>
        <BookmarkButton saveId={saveId} item={item} />
      </div>
    </article>
  );
}

/** Replace with a recruiter (M14b, 29.5): offered for a resignation or poach while a
 * recruiter is on staff and no replacement is being found yet. */
function ReplaceButton({ saveId, personId }: { saveId: string; personId: number }) {
  const rows = useReplaceable(saveId);
  const replace = useReplace(saveId);
  const row = rows.data?.find((r) => r.person_id === personId);
  if (replace.isSuccess) {
    return (
      <span className="tst-muted" style={{ fontSize: 13, alignSelf: 'center' }}>
        Your recruiter is finding a replacement.
      </span>
    );
  }
  if (!row?.can_replace) return null;
  return (
    <>
      <Button
        h={44}
        loading={replace.isPending}
        onClick={() => replace.mutate(personId)}
        data-testid={`replace-${personId}`}
      >
        Replace
      </Button>
      {replace.error && (
        <span role="alert" style={{ color: 'var(--tst-warn)', fontSize: 13, alignSelf: 'center' }}>
          {replace.error.message}
        </span>
      )}
    </>
  );
}

/** Events still to answer this month (M6): minor and major ones resolve to their first
 * choice at Continue; links the month's AI spend to Settings. */
function EventsHeader({ saveId }: { saveId: string }) {
  const events = useEvents(saveId);
  if (!events.data) return null;
  const n = events.data.to_answer;
  return (
    <p
      className="tst-muted"
      style={{ margin: '0 0 12px', fontSize: 13 }}
      data-testid="events-header"
    >
      {n === 0
        ? 'No events to answer this month.'
        : `${n} event${n === 1 ? '' : 's'} to answer. Minor and major ones take their first choice at Continue.`}{' '}
      <Link to={`/game/${saveId}/settings`}>
        AI writing: {formatMoney(Math.round(events.data.ai_spend_cents))} of{' '}
        {formatMoney(events.data.ai_budget_cents)} this month
      </Link>
    </p>
  );
}

/** "Ongoing stories" under the messages (M6): each active storyline and its step. */
function OngoingStories({ saveId }: { saveId: string }) {
  const stories = useStorylines(saveId);
  const active = (stories.data ?? []).filter((s) => s.status === 'active');
  if (active.length === 0) return null;
  return (
    <div style={{ padding: '12px 16px', borderTop: '1px solid var(--tst-rule)' }}>
      <h3 className="tst-ptitle" style={{ margin: '0 0 8px' }}>
        Ongoing stories
      </h3>
      {active.map((s) => (
        <div key={s.storyline_id} style={{ fontSize: 13, marginBottom: 6 }} data-testid="storyline">
          <strong>{s.title}</strong> <span className="tst-muted">· step {s.step}</span>
          <div className="tst-muted">{s.summary}</div>
        </div>
      ))}
    </div>
  );
}

/** A rival's approach (M5): counter it with a raise (the dialog shows the new band) or let
 * them decide at Continue. Once answered, the approach is gone and nothing shows. */
function ApproachActions({ saveId, personId }: { saveId: string; personId: number | null }) {
  const approaches = useApproaches(saveId);
  const open = approaches.data?.find((a) => a.person_id === personId);
  if (!open) return null;
  return <ApproachPanel saveId={saveId} approach={open} />;
}

function Fact({
  label,
  children,
  warn,
  num,
}: {
  label: string;
  children: ReactNode;
  warn?: boolean;
  num?: boolean;
}) {
  return (
    <div>
      <dt className="tst-muted">{label}</dt>
      <dd
        className={num ? 'tst-num' : undefined}
        style={{ margin: 0, color: warn ? 'var(--tst-warn)' : undefined }}
      >
        {children}
      </dd>
    </div>
  );
}

/** /game/:save/events/:eventId (M7c): the event's own inbox message, with its card. */
export function EventRedirect() {
  const { saveId = '', eventId = '' } = useParams();
  const item = useEventItem(saveId, Number(eventId));
  if (item.error) return <LoadError title="Could not find this event" error={item.error} />;
  if (!item.data) return <Loading />;
  return <Navigate to={`/game/${saveId}/inbox/${item.data.item_id}`} replace />;
}

/** Keep a message in the inbox: read messages older than three months archive themselves
 * unless starred (23.1, M10b). */
function BookmarkButton({ saveId, item }: { saveId: string; item: InboxItem }) {
  const bookmark = useBookmark(saveId);
  return (
    <Button
      variant="default"
      h={44}
      loading={bookmark.isPending}
      onClick={() => bookmark.mutate({ itemId: item.item_id, bookmarked: !item.bookmarked })}
      title="Bookmarked messages stay in the inbox; read ones archive after three months"
      data-testid={item.bookmarked ? 'inbox-unbookmark' : 'inbox-bookmark'}
    >
      {item.bookmarked ? '★ Bookmarked' : '☆ Bookmark'}
    </Button>
  );
}
