import { Tooltip } from '@mantine/core';
import { createContext, useContext, useState, type ReactNode } from 'react';
import {
  useGlossary,
  useOverviewBreakdowns,
  type Breakdown,
  type OverviewBreakdowns,
} from '../hooks/api';
import { formatMoneyWhole, formatWhole } from '../lib/format';

// Tooltips (M7b; spec 13). A Term shows a glossary definition; a BreakdownTip shows the
// drivers of a number as the API built them. Both open on hover or keyboard focus.

const UNDERLINE = {
  textDecoration: 'underline dotted',
  textUnderlineOffset: 3,
  textDecorationColor: 'var(--tst-muted)',
  cursor: 'help',
} as const;

const TIP = {
  multiline: true,
  w: 300,
  withArrow: true,
  openDelay: 150,
  events: { hover: true, focus: true, touch: true },
  styles: {
    tooltip: {
      background: 'var(--tst-panel-active)',
      color: 'var(--tst-text)',
      border: '1px solid var(--tst-border)',
      fontSize: 13,
      lineHeight: 1.45,
    },
  },
} as const;

const GlossaryContext = createContext<Record<string, string>>({});

/** Loads the glossary once for every Term below it (the app root). */
export function GlossaryProvider({ children }: { children: ReactNode }) {
  const glossary = useGlossary();
  return (
    <GlossaryContext.Provider value={glossary.data ?? {}}>{children}</GlossaryContext.Provider>
  );
}

/** A label with its glossary definition (`term` is its id in backend/data/glossary.yaml). */
export function Term({ term, children }: { term: string; children: ReactNode }) {
  const text = useContext(GlossaryContext)[term];
  if (!text) return <>{children}</>;
  return (
    <Tooltip label={text} {...TIP}>
      <span tabIndex={0} style={UNDERLINE} data-term={term}>
        {children}
      </span>
    </Tooltip>
  );
}

function amount(item: Breakdown['items'][number]): string {
  switch (item.unit) {
    case 'cents':
      return formatMoneyWhole(item.amount);
    case 'percent':
      return `${item.amount.toFixed(1)}%`;
    case 'points':
      return item.amount.toFixed(1);
    default:
      return formatWhole(item.amount);
  }
}

/** The drivers of a number: its items and note, exactly as the API sent them. */
export function BreakdownBody({ breakdown, title }: { breakdown: Breakdown; title?: string }) {
  return (
    <div data-testid="breakdown">
      {title && <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>}
      {breakdown.items.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {breakdown.items.map((item) => (
              <tr key={item.label}>
                <td style={{ padding: '2px 12px 2px 0' }}>{item.label}</td>
                <td
                  className="tst-num"
                  style={{
                    padding: '2px 0',
                    textAlign: 'right',
                    color: item.amount < 0 ? 'var(--tst-warn)' : undefined,
                  }}
                >
                  {amount(item)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {breakdown.note && (
        <div className="tst-muted" style={{ marginTop: 6, fontSize: 12 }}>
          {breakdown.note}
        </div>
      )}
    </div>
  );
}

/** A number whose drivers show on hover or focus. */
export function BreakdownTip({
  breakdown,
  title,
  children,
  testId,
}: {
  breakdown: Breakdown | null | undefined;
  title?: string;
  children: ReactNode;
  testId?: string;
}) {
  if (!breakdown) return <>{children}</>;
  return (
    <Tooltip label={<BreakdownBody breakdown={breakdown} title={title} />} {...TIP}>
      <span tabIndex={0} style={UNDERLINE} data-testid={testId}>
        {children}
      </span>
    </Tooltip>
  );
}

type OverviewKey = keyof OverviewBreakdowns;

/** A top-bar or Overview number whose breakdown is fetched the first time it opens. */
export function OverviewTip({
  saveId,
  which,
  title,
  children,
  testId,
}: {
  saveId: string;
  which: OverviewKey;
  title?: string;
  children: ReactNode;
  testId?: string;
}) {
  const [wanted, setWanted] = useState(false);
  const data = useOverviewBreakdowns(saveId, wanted);
  const breakdown = data.data?.[which];
  return (
    <Tooltip
      label={
        breakdown ? (
          <BreakdownBody breakdown={breakdown} title={title} />
        ) : (
          <span className="tst-muted">Loading what drives this…</span>
        )
      }
      {...TIP}
    >
      <span
        tabIndex={0}
        style={UNDERLINE}
        onMouseEnter={() => setWanted(true)}
        onFocus={() => setWanted(true)}
        data-testid={testId}
      >
        {children}
      </span>
    </Tooltip>
  );
}
