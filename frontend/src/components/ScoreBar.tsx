// One score (quality, features, brand, price or appeal) with a bar per product in a segment:
// the player's products in accent blue, competitors in greys (Product profile wireframe).
import { barColors } from '../lib/products';

export interface ScoreBarItem {
  key: string;
  name: string;
  value: number; // 0-100 from the API
  text: string; // what is printed beside the bar, e.g. "$40 · 62"
  mine: boolean;
}

export function ScoreBar({
  label,
  items,
  strong,
}: {
  label: string;
  items: readonly ScoreBarItem[];
  strong?: boolean; // appeal is the headline row
}) {
  const colors = barColors(items);
  return (
    <div
      data-testid={`score-${label.toLowerCase()}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '110px 1fr',
        gap: 12,
        alignItems: 'center',
        padding: '6px 0',
        borderBottom: '1px solid var(--tst-rule)',
      }}
    >
      <span
        style={{
          fontSize: 14,
          color: strong ? 'var(--tst-text)' : 'var(--tst-text-2)',
          fontWeight: strong ? 600 : undefined,
        }}
      >
        {label}
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {items.map((item, i) => (
          <span
            key={item.key}
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            title={item.name}
            data-mine={item.mine}
          >
            <span
              style={{ flex: 1, height: 8, background: 'var(--tst-hover)', borderRadius: 4 }}
              aria-hidden="true"
            >
              <span
                style={{
                  display: 'block',
                  height: 8,
                  borderRadius: 4,
                  background: colors[i],
                  width: `${Math.max(0, Math.min(100, item.value))}%`,
                }}
              />
            </span>
            <span
              className="tst-num"
              style={{ width: 72, fontSize: 12, color: 'var(--tst-text-2)', textAlign: 'right' }}
              aria-label={`${item.name}: ${item.text}`}
            >
              {item.text}
            </span>
          </span>
        ))}
      </span>
    </div>
  );
}

/** The colour key above a set of score bars. */
export function ScoreLegend({
  items,
}: {
  items: readonly { key: string; name: string; mine: boolean }[];
}) {
  const colors = barColors(items);
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 16,
        fontSize: 12,
        color: 'var(--tst-text-2)',
      }}
    >
      {items.map((item, i) => (
        <span key={item.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{ width: 12, height: 12, borderRadius: 2, background: colors[i] }}
            aria-hidden="true"
          />
          {item.name}
        </span>
      ))}
    </div>
  );
}
