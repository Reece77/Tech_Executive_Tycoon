// The Group screen (M16, formulas.md 31.2 and 31.10): the entity tree from the listed entity
// (the holding company once formed) down, each company's stake, treatment and public numbers,
// and the holding company's gate. Numbers come from the API; nothing is computed here.
import { Alert, Button, SegmentedControl } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../../components/DataTable';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { Term } from '../../components/Term';
import { useFormHolding, useGroup, useGroupAction, type GroupEntity } from '../../hooks/group';
import { formatBpPercent, formatMoneyShort } from '../../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, GroupEntity>();
const ROLE: Record<string, string> = {
  holding: 'Holding company',
  operating: 'Operating company',
  subsidiary: 'Subsidiary',
  company: 'Company',
};
const TREATMENT: Record<string, string> = {
  root: '—',
  consolidated: 'Consolidated',
  equity: 'Associate',
  fair_value: 'Fair value',
};

function value(e: GroupEntity): string {
  if (e.market_cap_cents !== null && e.market_cap_cents !== undefined)
    return formatMoneyShort(e.market_cap_cents);
  if (e.value_low_cents !== null && e.value_low_cents !== undefined && e.value_high_cents)
    return `${formatMoneyShort(e.value_low_cents)}–${formatMoneyShort(e.value_high_cents)}`;
  return '—';
}

export function GroupTab({ saveId }: { saveId: string }) {
  const group = useGroup(saveId);
  const form = useFormHolding(saveId);
  const act = useGroupAction(saveId);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Company',
          enableSorting: false,
          cell: ({ row }) => (
            <span style={{ paddingLeft: row.original.depth * 16 }}>
              <Link
                to={`/game/${saveId}/finance/statements?company=${row.original.company_id}`}
                data-testid="group-entity-link"
              >
                {row.original.name}
              </Link>
            </span>
          ),
        }),
        helper.accessor('role', {
          header: 'Role',
          meta: { term: 'group.role' },
          enableSorting: false,
          cell: ({ getValue }) => ROLE[getValue()] ?? getValue(),
        }),
        helper.accessor('stake_bp', {
          header: 'Stake',
          meta: { term: 'group.stake' },
          enableSorting: false,
          cell: ({ row }) =>
            row.original.depth === 0 ? (
              '—'
            ) : (
              <span className="tst-num">{formatBpPercent(row.original.stake_bp)}</span>
            ),
        }),
        helper.accessor('treatment', {
          header: 'Treatment',
          meta: { term: 'group.treatment' },
          enableSorting: false,
          cell: ({ getValue }) => TREATMENT[getValue()] ?? getValue(),
        }),
        helper.accessor('revenue_cents', {
          header: 'Revenue (12 months)',
          meta: { term: 'group.revenue' },
          enableSorting: false,
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        helper.accessor('operating_margin', {
          header: 'Operating margin',
          meta: { term: 'group.margin' },
          enableSorting: false,
          cell: ({ getValue }) => {
            const m = getValue();
            return (
              <span className="tst-num">
                {m === null || m === undefined ? '—' : `${(m * 100).toFixed(1)}%`}
              </span>
            );
          },
        }),
        helper.accessor('cash_cents', {
          header: 'Cash',
          meta: { term: 'group.cash' },
          enableSorting: false,
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        helper.display({
          id: 'value',
          header: 'Value',
          meta: { term: 'group.value' },
          cell: ({ row }) => <span className="tst-num">{value(row.original)}</span>,
        }),
        helper.accessor('ceo', {
          header: 'CEO',
          meta: { term: 'group.ceo' },
          enableSorting: false,
          cell: ({ getValue }) => getValue() ?? '—',
        }),
        helper.display({
          id: 'mandate',
          header: 'Mandate',
          meta: { term: 'group.mandate' },
          cell: ({ row }) =>
            row.original.ceo ? (
              <div>
                <SegmentedControl
                  size="xs"
                  data-testid="group-mandate"
                  value={row.original.mandate ?? ''}
                  onChange={(v) =>
                    act.mutate({
                      kind: 'mandate',
                      body: { company_id: row.original.company_id, mandate: v },
                    })
                  }
                  data={[
                    { value: 'grow', label: 'Grow' },
                    { value: 'margin', label: 'Margin' },
                    { value: 'return_cash', label: 'Return cash' },
                  ]}
                />
                {row.original.review && (
                  <div className="tst-muted" style={{ fontSize: 12 }} data-testid="group-review">
                    {row.original.review}
                  </div>
                )}
                {row.original.replacement_proposed && (
                  <Button
                    size="xs"
                    mt={4}
                    color="orange"
                    data-testid="group-replace-ceo"
                    onClick={() =>
                      act.mutate({ kind: 'replace', companyId: row.original.company_id })
                    }
                  >
                    Replace the CEO
                  </Button>
                )}
              </div>
            ) : (
              '—'
            ),
        }),
      ]),
    [saveId, act],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: group.data?.entities ?? [],
    getRowId: (e) => String(e.company_id),
  });
  if (group.error) return <LoadError title="Could not load the group" error={group.error} />;
  if (!group.data) return <Loading />;
  const g = group.data;
  return (
    <>
      {!g.formed && (
        <Panel title="Holding company" testId="group-gate">
          <Term term="group.holding">
            <span className="tst-muted" style={{ fontSize: 12 }}>
              What a holding company does
            </span>
          </Term>
          {g.can_form ? (
            <p>
              Form a holding company: it takes the listing, the cap table and the board, and your
              company and its brands become its subsidiaries. You chair it. Energy {g.form_energy};
              legal fees about {formatMoneyShort(g.form_fee_cents)}; its group office costs{' '}
              {formatMoneyShort(g.office_monthly_cents)} a month.
            </p>
          ) : (
            <ul data-testid="group-reasons">
              {g.reasons.map((r) => (
                <li key={r}>Not yet: {r}.</li>
              ))}
            </ul>
          )}
          <Button
            disabled={!g.can_form || form.isPending}
            loading={form.isPending}
            onClick={() => form.mutate()}
            data-testid="group-form"
          >
            Form the holding company
          </Button>
          {form.error && (
            <Alert color="red" role="alert" mt="sm">
              {form.error.message}
            </Alert>
          )}
        </Panel>
      )}
      <Panel title="Group" testId="group-tree">
        <DataTable table={table} label="Group" rowTestId="group-row" empty="No companies." />
        {act.error && (
          <Alert color="red" role="alert" mt="sm">
            {act.error.message}
          </Alert>
        )}
      </Panel>
      {(g.pitches ?? []).length > 0 && (
        <Panel title="Requests from subsidiaries" testId="group-pitches">
          {(g.pitches ?? []).map((p) => (
            <div
              key={p.id}
              data-testid="group-pitch"
              style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}
            >
              <span>
                {p.ceo} ({p.company}) asks for {formatMoneyShort(p.amount_cents)}:{' '}
                {p.fits_mandate ? 'fits its mandate' : 'does not fit its mandate'}.
              </span>
              <Button
                size="xs"
                onClick={() => act.mutate({ kind: 'pitch', pitchId: p.id, approve: true })}
              >
                Approve
              </Button>
              <Button
                size="xs"
                variant="default"
                onClick={() => act.mutate({ kind: 'pitch', pitchId: p.id, approve: false })}
              >
                Decline
              </Button>
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}
