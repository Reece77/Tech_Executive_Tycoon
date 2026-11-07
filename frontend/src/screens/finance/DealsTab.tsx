// Finance > Deals (M14, formulas.md 28): open offers and antitrust reviews (with a remedy or
// walking away), closed acquisitions with integration progress (people kept, let go and
// departed), and kept brands with their directive. Every value comes from the API.
import { Button, SegmentedControl, Table } from '@mantine/core';
import { Link } from 'react-router';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { useMna, useMnaAction, type MnaDeal } from '../../hooks/api';
import { formatMoneyWhole, humanize } from '../../lib/format';

export function DealsTab({ saveId }: { saveId: string }) {
  const mna = useMna(saveId);
  if (mna.error) return <LoadError title="Could not load deals" error={mna.error} />;
  if (!mna.data) return <Loading />;
  const open = mna.data.deals.filter((d) => ['accepted', 'review', 'blocked'].includes(d.status));
  const past = mna.data.deals.filter((d) => !open.includes(d));
  return (
    <>
      <Panel title="Open deals">
        {open.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            No deal under way. Open a company from Competitors to see its value and make an offer.
          </p>
        ) : (
          open.map((d) => (
            <OpenDeal
              key={d.deal_id}
              saveId={saveId}
              d={d}
              allowed={
                mna.data.targets.find((t) => t.company_id === d.target_id)?.integrate_allowed ??
                true
              }
            />
          ))
        )}
      </Panel>
      <Panel title="Acquisitions">
        {mna.data.acquisitions.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            Nothing bought yet.
          </p>
        ) : (
          <Table data-testid="acquisitions">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Company</Table.Th>
                <Table.Th>Mode</Table.Th>
                <Table.Th>Price</Table.Th>
                <Table.Th>Key people (left)</Table.Th>
                <Table.Th>Staff kept / let go</Table.Th>
                <Table.Th>Problems found</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {mna.data.acquisitions.map((a) => (
                <Table.Tr key={a.deal_id} data-testid="acquisition-row">
                  <Table.Td>{a.name}</Table.Td>
                  <Table.Td>{a.mode === 'brand' ? 'Brand' : 'Integrated'}</Table.Td>
                  <Table.Td>{formatMoneyWhole(a.price_cents)}</Table.Td>
                  <Table.Td>
                    {a.key_people} ({a.departed} left
                    {a.clash_months_left > 0 ? `; clash ${a.clash_months_left} more months` : ''})
                  </Table.Td>
                  <Table.Td>
                    {a.mode === 'integrate' ? `${a.pool_kept} / ${a.let_go}` : '—'}
                  </Table.Td>
                  <Table.Td>{a.problems.map(humanize).join(', ') || 'none'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Panel>
      <Panel title="Brands">
        {mna.data.subsidiaries.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            No kept brands. A brand keeps its own books; its results consolidate into Statements.
          </p>
        ) : (
          <Brands saveId={saveId} />
        )}
      </Panel>
      {past.length > 0 && (
        <Panel title="Past deals">
          {past.map((d) => (
            <p key={d.deal_id} style={{ margin: '0 0 4px' }}>
              {d.target_name}: {formatMoneyWhole(d.price_cents)}, {humanize(d.status)}
            </p>
          ))}
        </Panel>
      )}
    </>
  );
}

function OpenDeal({ saveId, d, allowed }: { saveId: string; d: MnaDeal; allowed: boolean }) {
  const act = useMnaAction(saveId);
  const share = `${Math.round(d.combined_share * 100)}%`;
  return (
    <div data-testid="open-deal" style={{ marginBottom: 12 }}>
      <p style={{ margin: '0 0 4px' }}>
        <Link to={`/game/${saveId}/competitors/${d.target_id}`}>{d.target_name}</Link> for{' '}
        {formatMoneyWhole(d.price_cents)} ({Math.round(d.cash_share * 100)}% cash):{' '}
        <strong data-testid="open-deal-status">{humanize(d.status)}</strong>
        {d.status === 'review' && d.review_end_turn != null
          ? `, review of a ${share} combined share in ${d.market}`
          : ''}
        {d.status === 'blocked' ? `, blocked at a ${share} combined share in ${d.market}` : ''}
        {d.status === 'accepted' ? ', closes at the end of this month' : ''}
      </p>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <SegmentedControl
          size="xs"
          value={d.mode ?? 'integrate'}
          onChange={(v) =>
            act.mutate({ kind: 'mode', dealId: d.deal_id, mode: v as 'brand' | 'integrate' })
          }
          data={[
            { value: 'integrate', label: 'Integrate', disabled: !allowed },
            { value: 'brand', label: 'Keep as a brand' },
          ]}
        />
        {!allowed && (
          <span className="tst-muted" style={{ fontSize: 12 }}>
            Too big to integrate: it stays a brand.
          </span>
        )}
        {d.status === 'blocked' && d.remedy_product && (
          <Button
            size="xs"
            data-testid="accept-remedy"
            onClick={() => act.mutate({ kind: 'remedy', dealId: d.deal_id })}
          >
            Accept the remedy: divest {d.remedy_product}
          </Button>
        )}
        {d.status === 'blocked' && d.own_remedy_product && (
          <Button
            size="xs"
            variant="light"
            data-testid="accept-own-remedy"
            onClick={() => act.mutate({ kind: 'remedy', dealId: d.deal_id, own: true })}
          >
            Or divest your own {d.own_remedy_product}
          </Button>
        )}
        <Button
          size="xs"
          variant="subtle"
          color="red"
          onClick={() => act.mutate({ kind: 'abandon', dealId: d.deal_id })}
        >
          Walk away
        </Button>
      </div>
    </div>
  );
}

function Brands({ saveId }: { saveId: string }) {
  const mna = useMna(saveId);
  const act = useMnaAction(saveId);
  return (
    <Table data-testid="brands">
      <Table.Tbody>
        {(mna.data?.subsidiaries ?? []).map((s) => (
          <Table.Tr key={s.company_id} data-testid="brand-row">
            <Table.Td>{s.name}</Table.Td>
            <Table.Td>{formatMoneyWhole(s.mrr_cents)} a month</Table.Td>
            <Table.Td>{formatMoneyWhole(s.cash_cents)} cash</Table.Td>
            <Table.Td>
              <SegmentedControl
                size="xs"
                data-testid="brand-directive"
                value={s.directive}
                onChange={(v) =>
                  act.mutate({
                    kind: 'directive',
                    companyId: s.company_id,
                    directive: v as 'grow' | 'harvest' | 'defend',
                  })
                }
                data={[
                  { value: 'grow', label: 'Grow' },
                  { value: 'harvest', label: 'Harvest' },
                  { value: 'defend', label: 'Defend' },
                ]}
              />
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

/** Org's view of kept brands (M14, 28.5): each brand's directive, when there are any. */
export function OrgBrands({ saveId }: { saveId: string }) {
  const mna = useMna(saveId);
  if (!mna.data || mna.data.subsidiaries.length === 0) return null;
  return (
    <Panel title="Brands you own">
      <Brands saveId={saveId} />
    </Panel>
  );
}
