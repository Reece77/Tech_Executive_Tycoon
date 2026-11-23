import { NativeSelect } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import type { Schemas } from '../../api/client';
import { DataTable } from '../../components/DataTable';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { Sparkline } from '../../components/Sparkline';
import { Term } from '../../components/Term';
import { useConglomerate, type IndustryFigures } from '../../hooks/group';
import { formatMoneyShort } from '../../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

type Figures = Schemas['FiguresOut'];
type CompanyRow = Schemas['CompanyFiguresOut'];
type CapitalYear = Schemas['CapitalYearOut'];
type Allocation = Schemas['AllocationOut'];
type Proposal = Schemas['WaitingProposalOut'];

/** 0.153 -> "15.3%"; null -> "—" (display only). */
function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;
}

function Money({ cents }: { cents: number }) {
  return (
    <span className="tst-num" style={{ color: cents < 0 ? 'var(--tst-warn)' : undefined }}>
      {formatMoneyShort(cents)}
    </span>
  );
}

const RISK_COLOUR: Record<string, string | undefined> = {
  high: 'var(--tst-warn)',
  moderate: undefined,
  low: 'var(--tst-good)',
  new: undefined,
};

/** Finance > Conglomerate (M43): the whole group by industry and by company, ten-year trends,
 * where capital went, the capital-allocation panel and the January letters. Read-only. */
export function ConglomerateTab({ saveId }: { saveId: string }) {
  const q = useConglomerate(saveId);
  const [letterIndex, setLetterIndex] = useState(0);
  if (q.error) return <LoadError title="Could not load the conglomerate view" error={q.error} />;
  if (!q.data) return <Loading />;
  const d = q.data;
  const yearLabel = d.months === 12 ? String(d.year) : `${d.year} to date (${d.months} months)`;
  const letter = d.letters[Math.min(letterIndex, Math.max(d.letters.length - 1, 0))];
  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      data-testid="conglomerate-tab"
    >
      <Panel title={`The group · ${yearLabel}`} testId="conglomerate-group">
        <GroupSummary figures={d.group} />
      </Panel>
      <Panel title="By industry" testId="conglomerate-industries">
        <IndustryTable rows={d.industries} />
        {d.corporate && (
          <p className="tst-muted" style={{ fontSize: 12 }}>
            Corporate (companies with no industry revenue, such as the holding company's office):
            operating profit {formatMoneyShort(d.corporate.operating_profit_cents)}, capital
            employed {formatMoneyShort(d.corporate.capital_employed_cents)}.
          </p>
        )}
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Lines that name a product, facility, plant or mine are its industry's; a company's other
          costs and capital are shared by its industries' revenue. Intercompany sales are left out.
        </p>
      </Panel>
      <Panel title="By company in the group" testId="conglomerate-companies">
        <CompanyTable rows={d.companies} />
      </Panel>
      <Panel title="Capital allocation" testId="conglomerate-allocation">
        <AllocationTable rows={d.allocation} />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Planned for next year: builds under way (capex still to pay) and subsidiaries' yearly
          capex limits. Change them on the Infrastructure and Group screens.
        </p>
        <ProposalTable rows={d.proposals} />
      </Panel>
      <Panel title="Where capital went" testId="conglomerate-capital">
        <CapitalTable rows={d.capital} />
      </Panel>
      <Panel title="Letter to shareholders" testId="conglomerate-letter">
        {letter ? (
          <>
            {d.letters.length > 1 && (
              <NativeSelect
                aria-label="Letter year"
                value={String(letterIndex)}
                data={d.letters.map((l, i) => ({ value: String(i), label: String(l.year) }))}
                onChange={(e) => setLetterIndex(Number(e.currentTarget.value))}
              />
            )}
            <div data-testid="letter-text" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
              {letter.text}
            </div>
            <p className="tst-muted" style={{ fontSize: 12 }}>
              Written in January about {letter.year}
              {letter.source === 'template' ? ' (from the template)' : ''}. Kept in History.
            </p>
          </>
        ) : (
          <p className="tst-muted">
            The first letter is written in January, about the year before.
          </p>
        )}
      </Panel>
    </div>
  );
}

function GroupSummary({ figures: f }: { figures: Figures }) {
  const rows: [string, string, React.ReactNode][] = [
    ['conglomerate.revenue', 'Revenue', <Money cents={f.revenue_cents} />],
    ['conglomerate.gross_margin', 'Gross margin', pct(f.gross_margin)],
    [
      'conglomerate.operating_profit',
      'Operating profit',
      <Money cents={f.operating_profit_cents} />,
    ],
    ['conglomerate.operating_margin', 'Operating margin', pct(f.operating_margin)],
    [
      'conglomerate.capital_employed',
      'Capital employed',
      <Money cents={f.capital_employed_cents} />,
    ],
    ['conglomerate.return_on_capital', 'Return on capital', pct(f.return_on_capital)],
  ];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
      {rows.map(([term, label, value]) => (
        <div key={term} className="tst-row" style={{ gap: 8 }}>
          <Term term={term}>{label}</Term>
          <span className="tst-num">{value}</span>
        </div>
      ))}
    </div>
  );
}

const industryHelper = createColumnHelper<GameTableFeatures, IndustryFigures>();

function IndustryTable({ rows }: { rows: IndustryFigures[] }) {
  const columns = useMemo(
    () =>
      industryHelper.columns([
        industryHelper.accessor('label', {
          header: 'Industry',
          meta: { term: 'conglomerate.industry' },
        }),
        industryHelper.accessor((r) => r.figures.revenue_cents, {
          id: 'revenue',
          header: 'Revenue',
          meta: { term: 'conglomerate.revenue' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        industryHelper.accessor('share_of_revenue', {
          header: 'Share',
          meta: { term: 'conglomerate.share' },
          cell: (c) => pct(c.getValue()),
        }),
        industryHelper.accessor((r) => r.figures.gross_margin ?? -9, {
          id: 'gross_margin',
          header: 'Gross margin',
          meta: { term: 'conglomerate.gross_margin' },
          cell: (c) => pct(c.row.original.figures.gross_margin),
        }),
        industryHelper.accessor((r) => r.figures.operating_profit_cents, {
          id: 'operating_profit',
          header: 'Operating profit',
          meta: { term: 'conglomerate.operating_profit' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        industryHelper.accessor((r) => r.figures.capital_employed_cents, {
          id: 'capital_employed',
          header: 'Capital employed',
          meta: { term: 'conglomerate.capital_employed' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        industryHelper.accessor((r) => r.figures.return_on_capital ?? -9, {
          id: 'return_on_capital',
          header: 'Return on capital',
          meta: { term: 'conglomerate.return_on_capital' },
          cell: (c) => pct(c.row.original.figures.return_on_capital),
        }),
        industryHelper.accessor((r) => r.growth ?? -9, {
          id: 'growth',
          header: 'Growth',
          meta: { term: 'conglomerate.growth' },
          cell: (c) => pct(c.row.original.growth),
        }),
        industryHelper.accessor('risk', {
          header: 'Risk',
          meta: { term: 'conglomerate.risk' },
          cell: (c) => <span style={{ color: RISK_COLOUR[c.getValue()] }}>{c.getValue()}</span>,
        }),
        industryHelper.display({
          id: 'trend',
          header: 'Revenue, ten years',
          meta: { term: 'conglomerate.trend' },
          cell: ({ row }) => (
            <Sparkline
              values={row.original.trend.map((p) => p.revenue_cents)}
              label={`${row.original.label} revenue by year`}
            />
          ),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => r.key,
  });
  return (
    <DataTable
      table={table}
      label="Industries"
      rowTestId="conglomerate-industry"
      empty="No industry has revenue or costs yet."
    />
  );
}

const companyHelper = createColumnHelper<GameTableFeatures, CompanyRow>();

function CompanyTable({ rows }: { rows: CompanyRow[] }) {
  const columns = useMemo(
    () =>
      companyHelper.columns([
        companyHelper.accessor('name', {
          header: 'Company',
          meta: { term: 'conglomerate.company' },
        }),
        companyHelper.accessor('role', { header: 'Role', meta: { term: 'conglomerate.role' } }),
        companyHelper.accessor((r) => r.industries.join(', '), {
          id: 'industries',
          header: 'Industries',
          meta: { term: 'conglomerate.industry' },
        }),
        companyHelper.accessor((r) => r.figures.revenue_cents, {
          id: 'revenue',
          header: 'Revenue',
          meta: { term: 'conglomerate.company_revenue' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        companyHelper.accessor('intercompany_cents', {
          header: 'To the group',
          meta: { term: 'conglomerate.intercompany' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        companyHelper.accessor((r) => r.figures.operating_profit_cents, {
          id: 'operating_profit',
          header: 'Operating profit',
          meta: { term: 'conglomerate.operating_profit' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        companyHelper.accessor((r) => r.figures.capital_employed_cents, {
          id: 'capital_employed',
          header: 'Capital employed',
          meta: { term: 'conglomerate.capital_employed' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        companyHelper.accessor((r) => r.figures.return_on_capital ?? -9, {
          id: 'return_on_capital',
          header: 'Return on capital',
          meta: { term: 'conglomerate.return_on_capital' },
          cell: (c) => pct(c.row.original.figures.return_on_capital),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => String(r.company_id),
  });
  return <DataTable table={table} label="Companies" rowTestId="conglomerate-company" />;
}

const allocationHelper = createColumnHelper<GameTableFeatures, Allocation>();

function AllocationTable({ rows }: { rows: Allocation[] }) {
  const columns = useMemo(
    () =>
      allocationHelper.columns([
        allocationHelper.accessor('label', {
          header: 'Industry',
          meta: { term: 'conglomerate.industry' },
        }),
        allocationHelper.accessor((r) => r.return_on_capital ?? -9, {
          id: 'return_on_capital',
          header: 'Return on capital',
          meta: { term: 'conglomerate.return_on_capital' },
          cell: (c) => pct(c.row.original.return_on_capital),
        }),
        allocationHelper.accessor((r) => r.growth ?? -9, {
          id: 'growth',
          header: 'Growth',
          meta: { term: 'conglomerate.growth' },
          cell: (c) => pct(c.row.original.growth),
        }),
        allocationHelper.accessor('risk', { header: 'Risk', meta: { term: 'conglomerate.risk' } }),
        allocationHelper.accessor((r) => r.planned.committed_cents, {
          id: 'committed',
          header: 'Builds under way',
          meta: { term: 'conglomerate.committed' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        allocationHelper.accessor((r) => r.planned.limits_cents, {
          id: 'limits',
          header: 'Capex limits',
          meta: { term: 'conglomerate.limits' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => r.key,
  });
  return (
    <DataTable table={table} label="Capital allocation" rowTestId="conglomerate-allocation-row" />
  );
}

const proposalHelper = createColumnHelper<GameTableFeatures, Proposal>();

function ProposalTable({ rows }: { rows: Proposal[] }) {
  const columns = useMemo(
    () =>
      proposalHelper.columns([
        proposalHelper.accessor('title', {
          header: 'Proposal waiting',
          meta: { term: 'conglomerate.proposal' },
        }),
        proposalHelper.accessor('company', {
          header: 'Company',
          meta: { term: 'conglomerate.company' },
        }),
        proposalHelper.accessor('who', { header: 'From', meta: { term: 'conglomerate.who' } }),
        proposalHelper.accessor((r) => r.amount_cents ?? -1, {
          id: 'amount',
          header: 'Cost',
          meta: { term: 'conglomerate.amount' },
          cell: (c) =>
            c.row.original.amount_cents === null ? '—' : <Money cents={c.getValue()} />,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => `${r.kind}-${r.turn}-${r.title}`,
  });
  return (
    <DataTable
      table={table}
      label="Proposals waiting"
      rowTestId="conglomerate-proposal"
      empty="No proposals waiting."
    />
  );
}

const capitalHelper = createColumnHelper<GameTableFeatures, CapitalYear>();

function CapitalTable({ rows }: { rows: CapitalYear[] }) {
  const columns = useMemo(
    () =>
      capitalHelper.columns([
        capitalHelper.accessor('year', { header: 'Year', meta: { term: 'conglomerate.year' } }),
        capitalHelper.accessor((r) => r.capex.reduce((s, c) => s + c.cents, 0), {
          id: 'capex',
          header: 'Capital spending',
          meta: { term: 'conglomerate.capex' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        capitalHelper.accessor((r) => r.capex.map((c) => c.label).join(', '), {
          id: 'where',
          header: 'Into',
          meta: { term: 'conglomerate.into' },
          cell: ({ row }) =>
            row.original.capex.map((c) => `${c.label} ${formatMoneyShort(c.cents)}`).join(' · ') ||
            '—',
        }),
        capitalHelper.accessor('acquisitions_cents', {
          header: 'Acquisitions and stakes',
          meta: { term: 'conglomerate.acquisitions' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
        capitalHelper.accessor('returned_cents', {
          header: 'Returned',
          meta: { term: 'conglomerate.returned' },
          cell: (c) => <Money cents={c.getValue()} />,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: [...rows].reverse(),
    getRowId: (r) => String(r.year),
  });
  return (
    <DataTable
      table={table}
      label="Where capital went"
      rowTestId="conglomerate-capital-year"
      empty="No capital spent yet."
    />
  );
}
