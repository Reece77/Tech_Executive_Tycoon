import { Alert, Button } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { DilutionLine, RoundPreview } from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../lib/format';
import {
  formatFraction,
  formatPointChange,
  formatSharePrice,
  formatShares,
  holderName,
  seatsText,
} from '../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';

const helper = createColumnHelper<GameTableFeatures, DilutionLine>();

const right = { display: 'block', textAlign: 'right' } as const;

function PreviewLines({ lines }: { lines: DilutionLine[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('holder', {
          header: 'Holder',
          sortFn: 'alphanumeric',
          cell: ({ row }) => <span>{holderName(row.original)}</span>,
        }),
        helper.accessor('fraction_before', {
          header: 'Now',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num" style={right}>
              {row.original.new ? '—' : formatFraction(row.original.fraction_before)}
            </span>
          ),
        }),
        helper.accessor('fraction_after', {
          header: 'After',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span
              className="tst-num"
              style={{ ...right, fontWeight: 600 }}
              data-testid={row.original.is_founder ? 'preview-founder-after' : undefined}
            >
              {formatFraction(row.original.fraction_after)}
            </span>
          ),
        }),
        helper.display({
          id: 'change',
          header: 'Change',
          cell: ({ row }) => {
            const l = row.original;
            const up = l.new || l.fraction_after > l.fraction_before;
            return (
              <span
                className="tst-num"
                style={{ ...right, color: up ? 'var(--tst-good)' : 'var(--tst-warn)' }}
              >
                {formatPointChange(l.fraction_before, l.fraction_after, l.new)}
              </span>
            );
          },
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: lines,
    getRowId: (l) => `${l.holder_kind}:${l.holder}:${l.share_class}`,
  });
  return <DataTable table={table} label="Ownership before and after" rowTestId="preview-row" />;
}

interface Props {
  preview: RoundPreview;
  onAccept?: () => void;
  onCancel?: () => void;
  accepting?: boolean;
  error?: Error | null;
  disabledReason?: string | null;
}

/** Accepting a term sheet: every holder before and after, the pool top-up, the board after
 * closing, the fees and Accept. Every number is the API's preview (formulas.md 14.5). */
export function DilutionPreview({
  preview: p,
  onAccept,
  onCancel,
  accepting,
  error,
  disabledReason,
}: Props) {
  return (
    <section
      aria-label="Dilution preview"
      className="tst-panel"
      style={{
        borderColor: '#3b5a80',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxShadow: '0 12px 32px rgba(0,0,0,.45)',
      }}
      data-testid="dilution-preview"
    >
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>
        Accept {p.firm_name}&apos;s term sheet?
      </h2>
      <span className="tst-muted" style={{ fontSize: 13 }}>
        {formatMoneyWhole(p.amount_cents)} at {formatMoneyShort(p.pre_money_cents)} pre-money.{' '}
        {formatShares(p.new_shares)} new {p.series_label} shares at{' '}
        {formatSharePrice(p.share_price_dollars)}.
      </span>
      <PreviewLines lines={p.lines} />
      <div className="tst-row">
        <span>Option pool top-up</span>
        <span className="tst-num" data-testid="preview-pool">
          {formatShares(p.pool_top_up)} new options
        </span>
      </div>
      {p.safe_conversion > 0 && (
        <div className="tst-row">
          <span>SAFEs convert</span>
          <span className="tst-num">{formatShares(p.safe_conversion)} shares</span>
        </div>
      )}
      <div className="tst-row">
        <span>Board after closing</span>
        <span>
          {seatsText(p.board_after)} (
          {p.founder_keeps_tie ? 'you keep control on a tie' : 'investors can outvote you'})
        </span>
      </div>
      <div className="tst-row">
        <span>Legal fees</span>
        <span className="tst-num">{formatMoneyWhole(p.fees_cents)}</span>
      </div>
      <div className="tst-row" style={{ borderBottom: 0 }}>
        <span>Fully diluted shares</span>
        <span className="tst-num">
          {formatShares(p.fd_before)} → {formatShares(p.fd_after)}
        </span>
      </div>
      {p.down_round && (
        <Alert color="warn" title="Down round">
          The price is below your last round&apos;s: every director&apos;s confidence falls once.
        </Alert>
      )}
      {error && <Alert color="red">{error.message}</Alert>}
      {(onAccept || onCancel) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {onAccept && (
            <Button
              h={44}
              onClick={onAccept}
              loading={accepting}
              disabled={Boolean(disabledReason)}
              data-testid="accept-sheet"
            >
              Accept · {p.energy_cost} energy
            </Button>
          )}
          {onCancel && (
            <Button variant="default" h={44} onClick={onCancel}>
              Cancel
            </Button>
          )}
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {disabledReason ??
              'The round closes and the money arrives when you press Continue. The other sheets lapse.'}
          </span>
        </div>
      )}
    </section>
  );
}
