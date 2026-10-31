import { NavLink } from 'react-router';
import { NAV_ITEMS } from '../lib/nav';

export function LeftNav({ saveId, unread }: { saveId: string; unread: number }) {
  return (
    <nav className="tst-nav" aria-label="Game screens">
      {NAV_ITEMS.map((item, index) => (
        <NavLink
          key={item.path}
          to={`/game/${saveId}/${item.path}`}
          className="tst-navlink"
          data-dimmed={item.arrivesIn ? 'true' : undefined}
        >
          <span className="tst-key">{(index + 1) % 10}</span>
          {item.label}
          {item.arrivesIn && (
            <span className="tst-muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
              {item.arrivesIn}
            </span>
          )}
          {item.path === 'inbox' && unread > 0 && (
            <span
              className="tst-num"
              data-testid="unread-count"
              aria-label={`${unread} unread`}
              style={{
                marginLeft: 'auto',
                fontSize: 12,
                background: 'var(--tst-accent)',
                color: 'var(--tst-bg)',
                borderRadius: 9,
                padding: '0 7px',
              }}
            >
              {unread}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
