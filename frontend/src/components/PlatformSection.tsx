// A product's platform section (M31, formulas.md 44): a device line's platform and catalogue
// effect, or an app's store fees and listings, and open-sourcing. Read from the Platforms API;
// the actions live on the Platforms screen, which this links to.
import { Button } from '@mantine/core';
import { Link } from 'react-router';
import { formatShare, useOpenSource, usePlatforms } from '../hooks/platforms';
import { formatMoneyWhole } from '../lib/format';
import { Explain } from './Explain';
import { Panel } from './ScreenState';
import { Term } from './Term';

export function PlatformSection({ saveId, productId }: { saveId: string; productId: number }) {
  const q = usePlatforms(saveId);
  const open = useOpenSource(saveId);
  if (!q.data || q.data.platforms.length === 0) return null;
  const device = q.data.device_lines.find((d) => d.product_id === productId);
  const app = q.data.apps.find((a) => a.product_id === productId);
  const isOpen = q.data.open_products.includes(productId);
  const own = q.data.platforms.find((p) => p.product_id === productId && p.own);
  if (!device && !app && !own) return null;
  return (
    <Panel
      title="Platform"
      testId="product-platform"
      action={<Link to={`/game/${saveId}/competitors/platforms`}>Platforms</Link>}
    >
      {device && (
        <p style={{ margin: 0 }} data-testid="product-platform-device">
          Runs <strong>{device.platform_name}</strong>
          {device.previous_name
            ? ` (${formatShare(device.previous_share)} still on ${device.previous_name})`
            : ''}
          . <Term term="platform.catalogue">Catalogue effect</Term>:{' '}
          {Object.keys(device.catalogue_points).length === 0
            ? 'from 2026'
            : Object.entries(device.catalogue_points)
                .map(([r, v]) => `${r.replaceAll('_', ' ')} ${v.toFixed(1)}`)
                .join(', ')}
          <Explain metric="catalogue_effect" entity={productId} label="Catalogue effect" />
        </p>
      )}
      {own && (
        <p style={{ margin: 0 }} data-testid="product-platform-own">
          Your platform <strong>{own.store}</strong>:{' '}
          {own.regions
            .filter((r) => r.users > 0)
            .map(
              (r) =>
                `${r.label} ${formatShare(r.users)} users, catalogue ${r.catalogue_index.toFixed(0)}`,
            )
            .join(' · ') || 'no users yet'}
        </p>
      )}
      {app && (
        <p style={{ margin: 0 }} data-testid="product-platform-app">
          <Term term="platform.fees_month">Store fees this month</Term>:{' '}
          {formatMoneyWhole(app.fees_total_cents)}
          <Explain metric="platform_fees" entity={productId} label="Platform fees" />
          {app.listings.length > 0
            ? ` · ${app.listings.map((x) => `${x.platform_name} ${x.region_label}: ${x.status}`).join('; ')}`
            : ' · listed in every store'}
        </p>
      )}
      <div style={{ marginTop: 8 }}>
        <Button
          size="xs"
          variant="default"
          loading={open.isPending}
          data-testid="product-open-source"
          onClick={() => open.mutate({ product_id: productId, open: !isOpen })}
        >
          {isOpen ? 'Close the source again' : 'Open-source it (a one-off)'}
        </Button>
      </div>
    </Panel>
  );
}
