import { Link, Navigate, useParams } from 'react-router';
import { ScreenTitle } from '../components/ScreenState';
import { BoardTab } from './finance/BoardTab';
import { CapTableTab } from './finance/CapTableTab';
import { FundraisingTab } from './finance/FundraisingTab';
import { StatementsTab } from './finance/StatementsTab';

const FINANCE_TABS = [
  { key: 'statements', label: 'Statements' },
  { key: 'captable', label: 'Cap table' },
  { key: 'fundraising', label: 'Fundraising' },
  { key: 'board', label: 'Board' },
] as const;
type TabKey = (typeof FINANCE_TABS)[number]['key'];

/** Finance (nav key 7, M4b): statements, the cap table, fundraising and the board. */
export function FinanceScreen() {
  const { saveId = '', tab = 'statements' } = useParams();
  const current = FINANCE_TABS.find((t) => t.key === tab);
  if (!current) return <Navigate to={`/game/${saveId}/finance/statements`} replace />;
  return (
    <>
      <ScreenTitle>Finance</ScreenTitle>
      <div role="tablist" aria-label="Finance" className="tst-tabs">
        {FINANCE_TABS.map((t) => (
          <Link
            key={t.key}
            role="tab"
            aria-selected={t.key === current.key}
            className="tst-tab"
            to={`/game/${saveId}/finance/${t.key}`}
            data-testid={`finance-tab-${t.key}`}
          >
            {t.label}
          </Link>
        ))}
      </div>
      <TabBody tab={current.key} saveId={saveId} />
    </>
  );
}

function TabBody({ tab, saveId }: { tab: TabKey; saveId: string }) {
  switch (tab) {
    case 'statements':
      return <StatementsTab saveId={saveId} />;
    case 'captable':
      return <CapTableTab saveId={saveId} />;
    case 'fundraising':
      return <FundraisingTab saveId={saveId} />;
    case 'board':
      return <BoardTab saveId={saveId} />;
  }
}
