import { formatMoneyWhole } from '../lib/format';
import { Term } from './Term';
import type { Nodes } from '../hooks/fabs';

/** The process-node timeline (M21, formulas.md 38.1, 38.3): each node's first volume and the
 * foundries running it, future nodes' public windows, and the rival foundries. Display only. */
export function NodeTimeline({ nodes }: { nodes: Nodes }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <p style={{ margin: 0, fontSize: 13 }} data-testid="node-edge">
        Leading edge {nodes.leading_label}; a typical chip is on {nodes.median_label}. Foundry
        prices ×{nodes.price_factor.toFixed(2)}, allocation ×{nodes.allocation_factor.toFixed(2)}.
        EUV tools from {nodes.euv_supplier}: {formatMoneyWhole(Math.round(nodes.euv_tool_cents))}{' '}
        each{nodes.euv_short ? ', in short supply' : ''}.
      </p>
      <table className="tst-table" style={{ fontSize: 13 }} aria-label="Process nodes">
        <thead>
          <tr>
            <th>
              <Term term="nodes.node">Node</Term>
            </th>
            <th>
              <Term term="nodes.first_volume">First volume</Term>
            </th>
            <th>
              <Term term="nodes.who">Who runs it</Term>
            </th>
            <th>
              <Term term="nodes.euv">EUV</Term>
            </th>
            <th>
              <Term term="nodes.wafer_price">Wafer price</Term>
            </th>
            <th>
              <Term term="nodes.research">Research needed</Term>
            </th>
          </tr>
        </thead>
        <tbody>
          {nodes.nodes.map((n) => (
            <tr key={n.key} data-testid={`node-${n.key}`}>
              <td>{n.label}</td>
              <td>{n.first_label ?? n.window_label ?? '—'}</td>
              <td>{n.reached.map((r) => `${r.name} (${r.label})`).join(', ') || '—'}</td>
              <td>{n.euv ? 'yes' : n.duv_route ? 'or DUV' : 'no'}</td>
              <td>{n.market_cents ? formatMoneyWhole(Math.round(n.market_cents)) : '—'}</td>
              <td>{n.need_level.toFixed(0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }} data-testid="foundries">
        Foundries:{' '}
        {nodes.foundries
          .map(
            (f) =>
              `${f.name} ${f.newest_label ?? '—'}, ${Math.round(f.capacity_k).toLocaleString()}k starts a month${f.stopped ? ' (stopped advancing)' : ''}`,
          )
          .join(' · ')}
      </p>
    </div>
  );
}
