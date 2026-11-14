// A rival's company page, the living world's part (M28, formulas.md 41.7): owner and group,
// named executives, facilities, public financials (listed) or estimated ranges (private),
// deals, offtakes and its World news. Every value comes from the API.
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import type { WorldCompany, WorldFacility } from '../hooks/world';
import { formatMoneyShort, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { CompanyLink } from './CompanyLink';
import { DataTable } from './DataTable';
import { Panel } from './ScreenState';

const facilityHelper = createColumnHelper<GameTableFeatures, WorldFacility>();
const whole = (v: number) => Math.round(v).toLocaleString('en-US');

export function WorldCompanyPanel({
  saveId,
  companyId,
  w,
}: {
  saveId: string;
  companyId: number;
  w: WorldCompany;
}) {
  const fin = w.financials;
  return (
    <Panel title="Company" testId="world-company">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
        {w.country_label && (
          <div data-testid="company-country">
            {w.kind === 'chain' ? 'A chain company' : 'A technology company'} in {w.country_label}
          </div>
        )}
        {w.owner && (
          <div data-testid="company-owner">
            Owned by{' '}
            <CompanyLink saveId={saveId} companyId={w.owner.company_id} name={w.owner.name} />
            {w.mandate ? `, run for ${humanize(w.mandate)}` : ''}
          </div>
        )}
        {w.subsidiaries.length > 0 && (
          <div data-testid="company-subsidiaries">
            Subsidiaries:{' '}
            {w.subsidiaries.map((s, i) => (
              <span key={s.company.company_id}>
                {i > 0 && ', '}
                <CompanyLink
                  saveId={saveId}
                  companyId={s.company.company_id}
                  name={s.company.name}
                />{' '}
                ({humanize(s.mandate)}, since {s.since_label})
              </span>
            ))}
          </div>
        )}
        {w.executives.length > 0 && (
          <div data-testid="company-executives">
            {w.executives.map((e) => `${e.role} ${e.name} (since ${e.since_label})`).join(' · ')}
          </div>
        )}
        {fin && (
          <div data-testid="company-financials">
            {fin.listed && fin.revenue_year_cents !== null && fin.ebitda_year_cents !== null
              ? `Revenue ${formatMoneyShort(fin.revenue_year_cents)} a year, EBITDA ${formatMoneyShort(fin.ebitda_year_cents)} (public)`
              : fin.revenue_range && fin.ebitda_range
                ? `Revenue ${formatMoneyShort(fin.revenue_range.low_cents)}–${formatMoneyShort(fin.revenue_range.high_cents)} a year, EBITDA ${formatMoneyShort(fin.ebitda_range.low_cents)}–${formatMoneyShort(fin.ebitda_range.high_cents)} (estimated: private)`
                : null}
          </div>
        )}
      </div>
      {w.facilities.length > 0 && <FacilitiesTable facilities={w.facilities} />}
      {w.deals.length > 0 && (
        <div style={{ fontSize: 13 }} data-testid="company-deals">
          {w.deals.map((d) => (
            <div key={`${d.date_label}-${d.target.company_id}`}>
              {d.date_label}:{' '}
              <CompanyLink saveId={saveId} companyId={d.buyer.company_id} name={d.buyer.name} />{' '}
              buys{' '}
              <CompanyLink saveId={saveId} companyId={d.target.company_id} name={d.target.name} />{' '}
              for {formatMoneyShort(d.price_cents)} ({d.kind}, {d.status})
            </div>
          ))}
        </div>
      )}
      {w.offtakes.length > 0 && (
        <div style={{ fontSize: 13 }} data-testid="company-offtakes">
          {w.offtakes.map((o) => (
            <div key={`${o.buyer.company_id}-${o.seller.company_id}-${o.good_label}`}>
              {o.buyer.name} buys {whole(o.volume)} {o.unit} of {o.good_label} a year from{' '}
              {o.seller.name} to {o.ends_label}
            </div>
          ))}
        </div>
      )}
      {w.news.length > 0 && (
        <div style={{ fontSize: 13 }} data-testid="company-news">
          {w.news.map((n) => (
            <div key={n.news_id}>
              <span className="tst-muted">{n.date_label}</span> {n.message}
            </div>
          ))}
          <Link
            to={`/game/${saveId}/competitors/world-news?company=${companyId}`}
            style={{ fontSize: 12 }}
          >
            All its news
          </Link>
        </div>
      )}
    </Panel>
  );
}

function FacilitiesTable({ facilities }: { facilities: WorldFacility[] }) {
  const columns = useMemo(
    () =>
      facilityHelper.columns([
        facilityHelper.accessor('good_label', { header: 'Good' }),
        facilityHelper.accessor('country_label', { header: 'Where' }),
        facilityHelper.accessor('capacity_year', {
          header: 'Capacity a year',
          cell: ({ row }) => `${whole(row.original.capacity_year)} ${row.original.unit}`,
        }),
        facilityHelper.accessor('status', {
          header: 'Status',
          cell: ({ row }) =>
            `${humanize(row.original.status)}${row.original.ready_label ? `, ready ${row.original.ready_label}` : ''}`,
        }),
        facilityHelper.accessor('cost_band', {
          header: 'Cost',
          cell: ({ getValue }) => humanize(getValue()),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: facilities,
    getRowId: (f) => String(f.facility_id),
  });
  return <DataTable table={table} label="Facilities" rowTestId="facility-row" />;
}
