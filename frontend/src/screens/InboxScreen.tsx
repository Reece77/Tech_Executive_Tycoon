import { Button } from '@mantine/core';
import { useState, type ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { KindBadge } from '../components/KindBadge';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import {
  INBOX_PAGE,
  useInbox,
  useOverview,
  usePerson,
  useSetRead,
  type InboxItem,
} from '../hooks/api';
import { formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import {
  financeTab,
  kindLabel,
  kindsFor,
  pageRange,
  preview,
  type InboxFilter,
} from '../lib/inbox';
import { moraleBand } from '../lib/attr';

const FILTERS: { key: InboxFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'unread', label: 'Unread' },
  { key: 'people', label: 'People' },
  { key: 'hiring', label: 'Hiring' },
  { key: 'products', label: 'Products' },
  { key: 'finance', label: 'Finance' },
];

export function InboxScreen() {
  const { saveId = '' } = useParams();
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<InboxFilter>('all');
  // Filters run in the API, so they apply across every page, not only the one shown (M3b).
  const inbox = useInbox(saveId, offset, kindsFor(filter), filter === 'unread');
  const overview = useOverview(saveId);
  const setRead = useSetRead(saveId);
  const [params, setParams] = useSearchParams();

  if (inbox.isPending) return <Loading />;
  if (inbox.error) return <LoadError title="Could not load the inbox" error={inbox.error} />;

  const items = inbox.data.items;
  const selectedId = Number(params.get('item'));
  const selected = items.find((m) => m.item_id === selectedId) ?? items[0];

  const open = (item: InboxItem) => {
    setParams({ item: String(item.item_id) }, { replace: true });
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
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <section
          aria-label="Messages"
          className="tst-panel"
          style={{ flex: '1 1 420px', padding: 0, overflow: 'hidden' }}
        >
          {items.length === 0 ? (
            <p className="tst-muted" style={{ margin: 0, padding: 16 }}>
              {filter === 'all'
                ? 'No messages yet. Open a search on Recruitment, then press Continue.'
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
        </section>
        {selected && (
          <MessageDetail
            key={selected.item_id}
            saveId={saveId}
            item={selected}
            onMarkUnread={() => setRead.mutate({ itemId: selected.item_id, read: false })}
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
}: {
  saveId: string;
  item: InboxItem;
  onMarkUnread: () => void;
}) {
  const linksPerson = item.link_kind === 'person' || item.link_kind === 'candidate';
  const person = usePerson(saveId, linksPerson && item.link_id ? item.link_id : 0);
  const p = person.data;
  const emp = p?.employment;
  const isNotice = kindLabel(item.kind) === 'Notice';

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
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--tst-text-2)' }}>
        {item.body}
      </p>
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
        {item.link_kind === 'search' && (
          <Button component={Link} to={`/game/${saveId}/recruitment?search=${item.link_id}`} h={44}>
            View candidates
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
        {item.read && (
          <Button variant="default" h={44} onClick={onMarkUnread}>
            Mark unread
          </Button>
        )}
      </div>
    </article>
  );
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
