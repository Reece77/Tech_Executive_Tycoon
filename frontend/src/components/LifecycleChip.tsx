import type { Product } from '../hooks/api';
import { lifecycleStyle, lifecycleText } from '../lib/products';

/** A product's status chip: Live · growth, In development, Sunset. */
export function LifecycleChip({ product }: { product: Product }) {
  return (
    <span
      data-testid="product-status"
      data-status={product.status}
      style={{
        ...lifecycleStyle(product.status),
        fontSize: 12,
        fontWeight: 600,
        borderRadius: 4,
        padding: '2px 8px',
      }}
    >
      {lifecycleText(product)}
    </span>
  );
}
