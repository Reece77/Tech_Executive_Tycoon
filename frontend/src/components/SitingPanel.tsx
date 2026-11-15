// The siting panel (M32, formulas.md 46.6) on the data-centre and fab build screens: each
// region's grid price, queue wait (a range), carbon price, outage rate, whether a plant can sit
// behind the meter, and the cheapest new plant there. Formatting only.
import { useSiting } from '../hooks/power';
import { Term } from './Term';

const PLANTS: Record<string, string> = {
  gas: 'gas',
  solar_storage: 'solar + storage',
  wind: 'wind',
};

export function SitingPanel({
  saveId,
  kind,
  size,
  region,
}: {
  saveId: string;
  kind: string;
  size: number;
  region?: string;
}) {
  const q = useSiting(saveId, kind, size);
  if (!q.data) return null;
  const byRegion = new Map<string, (typeof q.data.sites)[number]>();
  for (const s of q.data.sites) if (!byRegion.has(s.region)) byRegion.set(s.region, s);
  const rows = [...byRegion.values()];
  return (
    <div data-testid="siting-panel" style={{ fontSize: 13 }}>
      <div className="tst-muted" style={{ marginBottom: 4 }}>
        <Term term="power.grid_price">Power</Term> for about {q.data.mw.toFixed(0)} MW by region
      </div>
      <table className="tst-table" style={{ width: '100%' }}>
        <thead>
          <tr>
            <th>
              <Term term="power.region">Region</Term>
            </th>
            <th>
              <Term term="power.grid_price">$/MWh</Term>
            </th>
            <th>
              <Term term="power.queue">Queue</Term>
            </th>
            <th>
              <Term term="power.carbon_price">Carbon</Term>
            </th>
            <th>
              <Term term="power.outages">Outages</Term>
            </th>
            <th>
              <Term term="power.behind_the_meter">Own plant</Term>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr
              key={s.region}
              data-testid={`siting-${s.region}`}
              style={s.region === region ? { fontWeight: 600 } : undefined}
            >
              <td>{s.region_label}</td>
              <td className="tst-num">{s.price_usd_mwh.toFixed(1)}</td>
              <td className="tst-num" data-testid={`siting-queue-${s.region}`}>
                {s.queue_lo_months !== null && s.queue_hi_months !== null
                  ? `${s.queue_lo_months.toFixed(0)}–${s.queue_hi_months.toFixed(0)} mo`
                  : 'none'}
              </td>
              <td className="tst-num">${s.carbon_usd_t.toFixed(0)}/t</td>
              <td className="tst-num">{s.outages_a_year.toFixed(1)} a year</td>
              <td>
                {s.behind_meter
                  ? `${PLANTS[s.cheapest_plant] ?? s.cheapest_plant} $${s.cheapest_usd_mwh.toFixed(0)}`
                  : 'from stage 4'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
