import { Link, useLocation } from 'react-router';
import { useUnlockedKeys } from '../hooks/onboarding';
import { hotkeyOf, screenOf, sideGroups } from '../lib/nav';

// The side bar (M29, 42.4): screens grouped as Company, People, Products, Markets, Chain,
// Finance, World and Automation. Locked screens are hidden (42.1) until they unlock or
// Settings' Show everything is on; an empty group is left out.
export function LeftNav({
  saveId,
  unread,
  onSearch,
}: {
  saveId: string;
  unread: number;
  onSearch?: () => void;
}) {
  const unlocked = useUnlockedKeys(saveId);
  const { pathname } = useLocation();
  const here = pathname.replace(`/game/${saveId}/`, '');
  const current = screenOf(here);
  // A screen not in the side bar (a finance tab, a product) highlights its parent.
  const active = current && !current.side ? current.parent : current?.path;
  return (
    <nav className="tst-nav" aria-label="Game screens">
      {onSearch && (
        <button
          type="button"
          className="tst-navlink"
          onClick={onSearch}
          data-testid="palette-open"
          style={{
            border: '1px solid var(--tst-rule)',
            background: 'transparent',
            cursor: 'pointer',
          }}
        >
          Go to…
          <span className="tst-muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
            Ctrl+K
          </span>
        </button>
      )}
      {sideGroups(unlocked).map((group) => (
        <div key={group.key} className="tst-navgroup" data-testid={`nav-group-${group.key}`}>
          <div className="tst-navgroup-title" aria-hidden="true">
            {group.label}
          </div>
          {group.screens.map((item) => {
            const key = hotkeyOf(item.path);
            return (
              <Link
                key={item.path}
                to={`/game/${saveId}/${item.path}`}
                className="tst-navlink"
                aria-current={active === item.path ? 'page' : undefined}
                data-testid={`nav-${item.path.replace('/', '-')}`}
              >
                <span className="tst-key">{key ?? ''}</span>
                {item.label}
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
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
