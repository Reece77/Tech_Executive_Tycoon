import { Alert, Button } from '@mantine/core';
import { Link } from 'react-router';
import { useWorld, useWorldAction } from '../hooks/geopolitics';
import { Panel } from './ScreenState';

const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

/** A product's export controls (M22, 39.3): where rules close it, licence requests and the
 * compliant-variant action. Shown only when a rule touches the product. */
export function ExportPanel({ saveId, productId }: { saveId: string; productId: number }) {
  const world = useWorld(saveId);
  const act = useWorldAction(saveId);
  const x = world.data?.products.find((p) => p.product_id === productId);
  if (!x || (x.restricted.length === 0 && x.regions.length === 0)) return null;
  const licences = (world.data?.licences ?? []).filter((l) => l.product_id === productId);
  return (
    <Panel title="Export controls" testId="export-panel">
      {act.error && <Alert color="warn">{act.error.message}</Alert>}
      {x.regions.map((r) => (
        <div key={r.region} style={{ fontSize: 13 }}>
          {r.region}: {pct(r.blocked)} of demand closed
          {r.variant > 0 ? `, ${pct(r.variant)} served by the compliant variant` : ''}
        </div>
      ))}
      {licences.map((l) => (
        <div key={l.id} style={{ fontSize: 13 }} data-testid="product-licence">
          Licence to {l.country_label}: {l.status}
          {l.status === 'pending' ? ` (decision ${l.decision})` : ''}
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
        {x.licensable.map((c) => (
          <Button
            key={c}
            size="compact-sm"
            disabled={act.isPending}
            onClick={() => act.mutate({ kind: 'licence', productId, country: c })}
            data-testid="product-request-licence"
          >
            Request licence ({c})
          </Button>
        ))}
        {x.variant_possible && (
          <Button
            size="compact-sm"
            disabled={act.isPending}
            onClick={() => act.mutate({ kind: 'variant', productId })}
            data-testid="product-launch-variant"
          >
            {x.has_variant ? 'Relaunch' : 'Launch'} compliant variant
          </Button>
        )}
        <Link to={`/game/${saveId}/competitors/world`} style={{ fontSize: 13 }}>
          World screen
        </Link>
      </div>
    </Panel>
  );
}
