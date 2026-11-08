import { Alert, Button, Drawer, Textarea } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { useAskExplain, useExplain, type Explain as ExplainData } from '../hooks/explain';
import { formatUnit } from '../lib/explain';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { LoadError, Loading } from './ScreenState';
import { Sparkline } from './Sparkline';
import { Term } from './Term';

// Explain this (M25 section 1): any number's driver breakdown with its last 12 months, the
// chief of staff's template explanation, and Ask why. Read-only: it never changes the game.

type Item = ExplainData['items'][number];

interface Props {
  metric: string;
  entity?: string | number | null;
  label?: string; // what the button's tooltip names
}

/** The Explain affordance: a small button beside a number that opens its panel. */
export function Explain({ metric, entity, label }: Props) {
  const { saveId = '' } = useParams();
  const [open, setOpen] = useState(false);
  const key = entity === undefined || entity === null ? null : String(entity);
  return (
    <>
      <button
        type="button"
        className="tst-explain"
        aria-label={`Explain ${label ?? metric}`}
        title={`Explain ${label ?? 'this number'}`}
        data-testid={`explain-${metric}${key === null ? '' : `-${key}`}`}
        onClick={(e) => {
          e.preventDefault(); // inside a link tile, open the panel rather than navigate
          e.stopPropagation();
          setOpen(true);
        }}
      >
        ?
      </button>
      {open && (
        <ExplainPanel saveId={saveId} metric={metric} entity={key} onClose={() => setOpen(false)} />
      )}
    </>
  );
}

const helper = createColumnHelper<GameTableFeatures, Item>();

function Breakdown({ items }: { items: Item[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', { header: 'Driver', meta: { term: 'explain.driver' } }),
        helper.accessor('amount', {
          header: 'Amount',
          meta: { term: 'explain.amount' },
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num">{formatUnit(row.original.amount, row.original.unit)}</span>
          ),
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: items });
  return (
    <DataTable
      table={table}
      label="Breakdown"
      rowTestId="explain-item"
      empty="Nothing to break down yet."
    />
  );
}

export function ExplainPanel({
  saveId,
  metric,
  entity,
  onClose,
}: {
  saveId: string;
  metric: string;
  entity: string | null;
  onClose: () => void;
}) {
  const explain = useExplain(saveId, metric, entity, true);
  const ask = useAskExplain(saveId, metric, entity);
  const [question, setQuestion] = useState('');
  const e = explain.data;
  return (
    <Drawer
      opened
      onClose={onClose}
      position="right"
      size="lg"
      title={e ? `${e.label}: ${e.subject}` : 'Explain'}
    >
      {explain.isPending ? (
        <Loading />
      ) : explain.error || !e ? (
        <LoadError title="Could not explain this number" error={explain.error} />
      ) : (
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
          data-testid="explain-panel"
        >
          <div>
            <div className="tst-num" style={{ fontSize: 22, fontWeight: 600 }}>
              {e.value === null || e.value === undefined ? '—' : formatUnit(e.value, e.unit)}
            </div>
            <div className="tst-muted" style={{ fontSize: 12 }}>
              {e.trend.length >= 2
                ? `${e.trend[0].date_label} to ${e.trend[e.trend.length - 1].date_label}`
                : (e.trend_note ?? 'Not enough months for a trend yet.')}
            </div>
            <Sparkline values={e.trend.map((p) => p.value)} label={`${e.label} trend`} />
            {e.trend_note && e.trend.length >= 2 && (
              <div className="tst-muted" style={{ fontSize: 12 }}>
                {e.trend_note}
              </div>
            )}
          </div>
          <p style={{ margin: 0 }} data-testid="explain-template">
            {e.explanation}
          </p>
          <section aria-label="Breakdown">
            <h3 className="tst-ptitle">Breakdown</h3>
            <Breakdown items={e.items} />
            {e.note && (
              <p className="tst-muted" style={{ fontSize: 12, margin: '6px 0 0' }}>
                {e.note}
              </p>
            )}
          </section>
          {e.drivers.length > 0 && (
            <section aria-label="What moved it">
              <h3 className="tst-ptitle">What moved it last month</h3>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {e.drivers.map((d) => (
                  <li key={d.label} data-testid="explain-driver">
                    {d.label}
                    {d.change !== null && d.change !== undefined && d.unit
                      ? ` ${formatUnit(d.change, d.unit, true)}`
                      : ''}
                    {d.effect !== null && d.effect !== undefined && (
                      <span className="tst-muted">
                        {' '}
                        (
                        {formatUnit(
                          d.effect,
                          d.kind === 'level' ? (d.unit ?? e.unit) : e.unit,
                          true,
                        )}
                        {d.kind === 'level' ? ' now' : ''})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {e.related.length > 0 && (
            <section aria-label="Related events">
              <h3 className="tst-ptitle">Related events</h3>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {e.related.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          )}
          <form
            onSubmit={(ev) => {
              ev.preventDefault();
              if (question.trim()) ask.mutate(question.trim());
            }}
          >
            <Textarea
              label={`Ask ${e.speaker} why`}
              placeholder={`Why is ${e.label.toLowerCase()} where it is?`}
              value={question}
              maxLength={e.max_question_chars}
              onChange={(ev) => setQuestion(ev.currentTarget.value)}
              data-testid="explain-question"
              autosize
              minRows={2}
            />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
              <Button
                type="submit"
                size="compact-md"
                loading={ask.isPending}
                disabled={!question.trim()}
                data-testid="explain-ask"
              >
                Ask why
              </Button>
              {e.offline && (
                <span className="tst-muted" style={{ fontSize: 12 }}>
                  Offline: the answer is the explanation above.
                </span>
              )}
            </div>
          </form>
          {ask.error && <Alert color="warn">{ask.error.message}</Alert>}
          {ask.data && (
            <blockquote style={{ margin: 0 }} data-testid="explain-answer">
              <strong>{ask.data.speaker}:</strong> {ask.data.answer}
            </blockquote>
          )}
        </div>
      )}
    </Drawer>
  );
}

/** A tile whose value is the explained number itself (M25): for numbers a screen has no
 * field of its own for, such as a product's overall churn. */
export function ExplainTile({
  metric,
  entity,
  label,
  term,
  testId,
}: {
  metric: string;
  entity?: string | number;
  label: string;
  term: string;
  testId?: string;
}) {
  const { saveId = '' } = useParams();
  const key = entity === undefined ? null : String(entity);
  const e = useExplain(saveId, metric, key, true).data;
  const value = e?.value;
  return (
    <div className="tst-panel" style={{ padding: '12px 16px', flex: '1 1 150px' }}>
      <div className="tst-muted" style={{ fontSize: 12 }}>
        <Term term={term}>{label}</Term>
        <Explain metric={metric} entity={entity} label={label} />
      </div>
      <div className="tst-num" style={{ fontSize: 22, fontWeight: 600 }} data-testid={testId}>
        {e === undefined
          ? '…'
          : value === null || value === undefined
            ? '—'
            : formatUnit(value, e.unit)}
      </div>
      <div className="tst-muted" style={{ fontSize: 12 }}>
        {e?.trend.length ? `${e.trend[e.trend.length - 1].date_label}` : 'No month closed yet'}
      </div>
    </div>
  );
}
