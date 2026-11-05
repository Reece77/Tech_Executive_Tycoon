// Press on the Overview (M14b, formulas.md 29.2-29.3): credibility with its last five changes
// and causes, the Promises table (open, kept and broken, with progress and deadline from
// displayed values), and the make-a-promise dialog after a press moment answered this month.
import { Alert, Button, Modal, NativeSelect, NumberInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { usePress, useMakePromise, type Press, type PressPromise } from '../hooks/press';
import { formatWhole } from '../lib/format';
import {
  PROMISE_KINDS,
  PROMISE_LABELS,
  PROMISE_STATUS,
  signed,
  type PromiseKind,
} from '../lib/press';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Panel } from './ScreenState';
import { Term } from './Term';

const helper = createColumnHelper<GameTableFeatures, PressPromise>();
const HISTORY_SHOWN = 5; // 29.3: the last five changes

export function PressPanels({ saveId }: { saveId: string }) {
  const press = usePress(saveId);
  if (!press.data) return null; // the Overview loads without it
  return <PressBody saveId={saveId} press={press.data} />;
}

export function PressBody({ saveId, press }: { saveId: string; press: Press }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>
      <CredibilityPanel press={press} />
      <PromisesPanel press={press} onMake={() => setOpen(true)} />
      {open && <PromiseDialog saveId={saveId} press={press} onClose={() => setOpen(false)} />}
    </div>
  );
}

function CredibilityPanel({ press }: { press: Press }) {
  const { value, history } = press.credibility;
  const recent = history.slice(-HISTORY_SHOWN).reverse();
  return (
    <Panel
      title="Credibility"
      testId="credibility-panel"
      style={{ flex: '1 1 260px', display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <Term term="credibility">
          <span
            className="tst-num"
            style={{ fontSize: 26, fontWeight: 600 }}
            data-testid="credibility-value"
          >
            {formatWhole(value)}
          </span>
        </Term>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          of 100 · drifts toward 50
        </span>
      </div>
      <div data-testid="credibility-history" style={{ display: 'flex', flexDirection: 'column' }}>
        {recent.length === 0 ? (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            No changes yet: press answers and promises move it.
          </span>
        ) : (
          recent.map((c, i) => (
            <div key={`${c.turn}-${i}`} className="tst-row" data-testid="credibility-change">
              <span style={{ color: 'var(--tst-text-2)', fontSize: 13 }}>{c.cause}</span>
              <span style={{ display: 'flex', gap: 8, flex: 'none' }}>
                <span
                  className="tst-num"
                  style={{ color: c.change < 0 ? 'var(--tst-warn)' : 'var(--tst-good)' }}
                >
                  {signed(c.change)}
                </span>
                <span className="tst-num tst-muted" style={{ fontSize: 12 }}>
                  {c.label}
                </span>
              </span>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = PROMISE_STATUS[status] ?? PROMISE_STATUS.open;
  return (
    <span
      data-testid="promise-status"
      data-status={status}
      style={{
        color: s.color,
        background: s.background,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        borderRadius: 4,
        padding: '2px 7px',
      }}
    >
      {s.label}
    </span>
  );
}

function PromisesPanel({ press, onMake }: { press: Press; onMake: () => void }) {
  const form = press.form;
  const full = form.open_count >= form.max_open;
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('words', {
          id: 'promise',
          header: 'Promise',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <span style={{ fontWeight: 600 }}>{getValue()}</span>,
        }),
        helper.accessor((p) => PROMISE_LABELS[p.kind] ?? p.kind, {
          id: 'promise.kind',
          header: 'Kind',
          sortFn: 'alphanumeric',
        }),
        helper.accessor('progress', {
          id: 'promise.progress',
          header: 'Progress',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span style={{ color: 'var(--tst-text-2)' }} data-testid="promise-progress">
              {getValue() || '—'}
            </span>
          ),
        }),
        helper.accessor('made', { id: 'promise.made', header: 'Made', enableSorting: false }),
        helper.accessor('months_left', {
          id: 'promise.deadline',
          header: 'Deadline',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num" data-testid="promise-deadline">
              {row.original.deadline}
              {row.original.status === 'open' && (
                <span className="tst-muted">
                  {' '}
                  · {row.original.months_left} month{row.original.months_left === 1 ? '' : 's'}
                </span>
              )}
            </span>
          ),
        }),
        helper.accessor('status', {
          id: 'promise.status',
          header: 'Status',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <StatusBadge status={getValue()} />,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: press.promises,
    getRowId: (p) => String(p.promise_id),
  });
  return (
    <Panel
      title="Public promises"
      testId="promises-panel"
      style={{ flex: '3 1 560px', display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}
      action={
        form.moment_id !== null && (
          <Button
            size="compact-sm"
            onClick={onMake}
            disabled={full}
            title={full ? `At most ${form.max_open} promises open at once` : undefined}
            data-testid="promise-open"
          >
            Make a promise · {form.energy} energy
          </Button>
        )
      }
    >
      <span className="tst-muted" style={{ fontSize: 12 }} data-testid="promise-count">
        {form.open_count} of {form.max_open} open.{' '}
        {form.moment_id === null
          ? 'A promise is made in a press moment: answer one boldly or measured, then promise in the same month.'
          : "This month's press answer can carry a promise."}
      </span>
      <DataTable
        table={table}
        label="Promises"
        rowTestId="promise-row"
        empty="No public promises yet."
      />
    </Panel>
  );
}

function PromiseDialog({
  saveId,
  press,
  onClose,
}: {
  saveId: string;
  press: Press;
  onClose: () => void;
}) {
  const form = press.form;
  const make = useMakePromise(saveId);
  const [lo, hi] = form.months;
  const [kind, setKind] = useState<PromiseKind>(form.in_development.length ? 'ship' : 'no_layoffs');
  const spec = PROMISE_KINDS.find((k) => k.key === kind) ?? PROMISE_KINDS[0];
  const products = spec.product === 'in_development' ? form.in_development : form.live;
  const [productChoice, setProduct] = useState<string>('');
  const product = productChoice || String(products[0]?.id ?? '');
  const [rivalChoice, setRival] = useState<string>('');
  const rival = rivalChoice || String(form.rival_products[0]?.id ?? '');
  const [domainChoice, setDomain] = useState<string>('');
  const domain = domainChoice || String(form.domains[0]?.id ?? '');
  const [level, setLevel] = useState<number>(1);
  const [months, setMonths] = useState<number>(Math.min(hi, Math.max(lo, 6)));
  const missing =
    (spec.product !== null && !product) ||
    (kind === 'beat' && !rival) ||
    (kind === 'research' && !domain);
  const submit = () =>
    make.mutate(
      {
        promise: kind,
        product_id: spec.product !== null ? Number(product) : null,
        rival_product_id: kind === 'beat' ? Number(rival) : null,
        domain: kind === 'research' ? domain : null,
        level: kind === 'research' ? level : null,
        months: spec.timed ? months : null,
      },
      { onSuccess: onClose },
    );
  return (
    <Modal opened onClose={onClose} title="Make a public promise" size="lg" centered>
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        data-testid="promise-dialog"
      >
        <span className="tst-muted" style={{ fontSize: 13 }}>
          The press holds you to it. Kept, the brand and your credibility gain (more for a bigger
          promise); broken, both fall harder, and the press reminds readers what you said.
        </span>
        <NativeSelect
          label="Promise"
          value={kind}
          data-testid="promise-kind"
          onChange={(e) => {
            setKind(e.currentTarget.value as PromiseKind);
            setProduct('');
          }}
          data={PROMISE_KINDS.map((k) => ({ value: k.key, label: k.label }))}
        />
        {spec.product !== null && (
          <NativeSelect
            label={spec.product === 'in_development' ? 'Product in development' : 'Product'}
            value={product}
            data-testid="promise-product"
            onChange={(e) => setProduct(e.currentTarget.value)}
            data={products.map((p) => ({ value: String(p.id), label: p.name }))}
            error={products.length === 0 ? 'No product to promise about' : undefined}
          />
        )}
        {kind === 'beat' && (
          <NativeSelect
            label="Rival's product"
            value={rival}
            data-testid="promise-rival-product"
            onChange={(e) => setRival(e.currentTarget.value)}
            data={form.rival_products.map((p) => ({ value: String(p.id), label: p.name }))}
          />
        )}
        {kind === 'research' && (
          <>
            <NativeSelect
              label="Domain"
              value={domain}
              data-testid="promise-domain"
              onChange={(e) => setDomain(e.currentTarget.value)}
              data={form.domains.map((d) => ({ value: String(d.id), label: d.name }))}
            />
            <NumberInput
              label="Lead to reach"
              min={1}
              value={level}
              data-testid="promise-level"
              onChange={(v) => setLevel(typeof v === 'number' ? v : 1)}
            />
          </>
        )}
        {spec.timed ? (
          <NumberInput
            label="Months from now"
            min={lo}
            max={hi}
            value={months}
            data-testid="promise-months"
            onChange={(v) => setMonths(typeof v === 'number' ? v : lo)}
            description={`${lo} to ${hi} months. A shorter deadline pays more if kept.`}
          />
        ) : (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Runs 12 months from now.
          </span>
        )}
        {make.error && <Alert color="red">{make.error.message}</Alert>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <Button
            onClick={submit}
            loading={make.isPending}
            disabled={missing}
            data-testid="promise-submit"
          >
            Make the promise · {form.energy} energy
          </Button>
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {form.open_count} of {form.max_open} promises open
          </span>
        </div>
      </div>
    </Modal>
  );
}
