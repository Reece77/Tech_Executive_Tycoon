import { Link, Navigate, useParams } from 'react-router';
import { ScreenTitle } from '../components/ScreenState';
import { usePublic } from '../hooks/api';
import { BoardTab } from './finance/BoardTab';
import { CapTableTab } from './finance/CapTableTab';
import { DealsTab } from './finance/DealsTab';
import { DebtTab } from './finance/DebtTab';
import { DivisionsTab } from './finance/DivisionsTab';
import { FundraisingTab } from './finance/FundraisingTab';
import { StatementsTab } from './finance/StatementsTab';
import { StockTab } from './finance/StockTab';

const FINANCE_TABS = [
  { key: 'statements', label: 'Statements' },
  { key: 'divisions', label: 'Divisions' },
  { key: 'captable', label: 'Cap table' },
  { key: 'fundraising', label: 'Fundraising' },
  { key: 'debt', label: 'Debt' }, // M10
  { key: 'stock', label: 'Stock' }, // M13: once public
  { key: 'board', label: 'Board' },
  { key: 'deals', label: 'Deals' }, // M14: acquisitions
] as const;
type TabKey = (typeof FINANCE_TABS)[number]['key'];

/** Finance (nav key 7, M4b): statements, divisions (M8), the cap table, fundraising, debt
 * (M10), the stock once public (M13) and the board. */
export function FinanceScreen() {
  const { saveId = '', tab = 'statements' } = useParams();
  const listed = Boolean(usePublic(saveId).data?.stock);
  const current = FINANCE_TABS.find((t) => t.key === tab);
  if (!current) return <Navigate to={`/game/${saveId}/finance/statements`} replace />;
  // The Stock tab shows once public; its route still answers (a short note) before then.
  const tabs = FINANCE_TABS.filter((t) => t.key !== 'stock' || listed || t.key === current.key);
  return (
    <>
      <ScreenTitle>Finance</ScreenTitle>
      <div role="tablist" aria-label="Finance" className="tst-tabs">
        {tabs.map((t) => (
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
    case 'divisions':
      return <DivisionsTab saveId={saveId} />;
    case 'captable':
      return <CapTableTab saveId={saveId} />;
    case 'fundraising':
      return <FundraisingTab saveId={saveId} />;
    case 'debt':
      return <DebtTab saveId={saveId} />;
    case 'stock':
      return <StockTab saveId={saveId} />;
    case 'board':
      return <BoardTab saveId={saveId} />;
    case 'deals':
      return <DealsTab saveId={saveId} />;
  }
}
