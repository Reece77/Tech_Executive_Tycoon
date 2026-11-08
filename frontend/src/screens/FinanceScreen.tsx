import { NativeSelect } from '@mantine/core';
import { Link, Navigate, useParams, useSearchParams } from 'react-router';
import { ScreenTitle } from '../components/ScreenState';
import { usePublic } from '../hooks/api';
import { useGroup } from '../hooks/group';
import { BoardTab } from './finance/BoardTab';
import { CapTableTab } from './finance/CapTableTab';
import { DealsTab } from './finance/DealsTab';
import { DebtTab } from './finance/DebtTab';
import { DivisionsTab } from './finance/DivisionsTab';
import { FundraisingTab } from './finance/FundraisingTab';
import { GroupTab } from './finance/GroupTab';
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
  { key: 'group', label: 'Group' }, // M16: the holding company and its subsidiaries
] as const;
// M16 (31.2): the company switcher scopes these tabs to one company of the group
const SCOPED: readonly string[] = ['statements', 'captable', 'board'];
type TabKey = (typeof FINANCE_TABS)[number]['key'];

/** Finance (nav key 7, M4b): statements, divisions (M8), the cap table, fundraising, debt
 * (M10), the stock once public (M13), the board, deals (M14) and the group (M16), with a
 * company switcher for the statements, the cap table and the board. */
export function FinanceScreen() {
  const { saveId = '', tab = 'statements' } = useParams();
  const [search, setSearch] = useSearchParams();
  const listed = Boolean(usePublic(saveId).data?.stock);
  const group = useGroup(saveId).data;
  const raw = search.get('company');
  const companyId = raw === null ? undefined : Number(raw);
  const current = FINANCE_TABS.find((t) => t.key === tab);
  if (!current) return <Navigate to={`/game/${saveId}/finance/statements`} replace />;
  // The Stock tab shows once public; its route still answers (a short note) before then.
  const tabs = FINANCE_TABS.filter((t) => t.key !== 'stock' || listed || t.key === current.key);
  return (
    <>
      <ScreenTitle
        aside={
          group &&
          group.entities.length > 1 &&
          SCOPED.includes(current.key) && (
            <NativeSelect
              aria-label="Company"
              data-testid="company-switcher"
              style={{ marginLeft: 'auto' }}
              value={String(companyId ?? group.entities[0]?.company_id ?? '')}
              onChange={(e) => setSearch({ company: e.currentTarget.value })}
              data={group.entities.map((e) => ({
                value: String(e.company_id),
                label: `${'  '.repeat(e.depth)}${e.name}${e.depth === 0 && group.entities.length > 1 ? ' (group)' : ''}`,
              }))}
            />
          )
        }
      >
        Finance
      </ScreenTitle>
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
      <TabBody tab={current.key} saveId={saveId} companyId={companyId} />
    </>
  );
}

function TabBody({
  tab,
  saveId,
  companyId,
}: {
  tab: TabKey;
  saveId: string;
  companyId: number | undefined;
}) {
  switch (tab) {
    case 'statements':
      return <StatementsTab saveId={saveId} companyId={companyId} />;
    case 'divisions':
      return <DivisionsTab saveId={saveId} />;
    case 'captable':
      return <CapTableTab saveId={saveId} companyId={companyId} />;
    case 'fundraising':
      return <FundraisingTab saveId={saveId} />;
    case 'debt':
      return <DebtTab saveId={saveId} />;
    case 'stock':
      return <StockTab saveId={saveId} />;
    case 'board':
      return <BoardTab saveId={saveId} companyId={companyId} />;
    case 'deals':
      return <DealsTab saveId={saveId} />;
    case 'group':
      return <GroupTab saveId={saveId} />;
  }
}
