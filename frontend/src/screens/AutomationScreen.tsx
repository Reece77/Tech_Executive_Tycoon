import { Alert, Button, Modal, NumberInput, Select, Switch } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import {
  useAreaSettings,
  useAutomateEverything,
  useAutomatePlan,
  useAutomation,
  useDigest,
  useSetAreaOwner,
  useTakeBackArea,
  type Area,
  type Automation,
} from '../hooks/automation';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, Area>();
const CENTS = 100;

/** Automation (M27a, formulas.md 40.8): who runs each area, under what limit, and what they did. */
export function AutomationScreen() {
  const { saveId = '' } = useParams();
  const auto = useAutomation(saveId);
  if (auto.isPending) return <Loading />;
  if (auto.error) return <LoadError title="Could not load automation" error={auto.error} />;
  return <Body saveId={saveId} a={auto.data} />;
}

function Body({ saveId, a }: { saveId: string; a: Automation }) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState<Area | null>(null);
  const setOwner = useSetAreaOwner(saveId);
  const takeBack = useTakeBackArea(saveId);
  const error = setOwner.error ?? takeBack.error;
  const open = a.areas.filter((x) => x.status === 'manage').length;
  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Automation</h1>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {a.company_name} · default limit {formatMoneyWhole(a.default_limit_cents)} a decision ·
          one-offs always come to you
          {a.stop_for_approvals ? ' and stop a holiday' : ''}
        </span>
        <Button
          style={{ marginLeft: 'auto' }}
          disabled={open === 0}
          onClick={() => setConfirming(true)}
          data-testid="automate-all"
        >
          Automate everything
        </Button>
      </div>
      {error && (
        <Alert color="warn" data-testid="automation-error">
          {error.message}
        </Alert>
      )}
      <Panel title="Areas" testId="automation-panel">
        <AreasTable
          areas={a.areas}
          busy={setOwner.isPending || takeBack.isPending}
          onOwner={(area, personId) => setOwner.mutate({ area, person_id: personId })}
          onTakeBack={(area) => takeBack.mutate(area)}
          onEdit={setEditing}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          An owner acts under their money limit; at or above it, and for every one-off (buying,
          selling, rounds, loans, facilities, sunsets, big layoffs, appointments), they propose and
          you decide. Each person has a month&apos;s energy: areas past it get no time. Fit comes
          from what you know of them.
        </p>
      </Panel>
      <DigestPanel saveId={saveId} />
      {confirming && <ConfirmAll saveId={saveId} onClose={() => setConfirming(false)} />}
      {editing && <EditArea saveId={saveId} area={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function AreasTable({
  areas,
  busy,
  onOwner,
  onTakeBack,
  onEdit,
}: {
  areas: Area[];
  busy: boolean;
  onOwner: (area: string, personId: number) => void;
  onTakeBack: (area: string) => void;
  onEdit: (a: Area) => void;
}) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', { header: 'Area', meta: { term: 'automation.area' } }),
        helper.display({
          id: 'owner',
          header: 'Owner',
          meta: { term: 'automation.owner' },
          cell: ({ row }) => {
            const x = row.original;
            if (x.status === 'cant') return <span className="tst-muted">—</span>;
            const data = x.candidates.map((c) => ({
              value: String(c.person_id),
              label: `${c.name}${c.role ? ` (${c.role})` : ''}: ${c.fit}`,
            }));
            return (
              <Select
                size="xs"
                aria-label={`Owner of ${x.label}`}
                data-testid={`owner-${x.area}`}
                placeholder="Manage myself"
                data={data}
                value={x.owner ? String(x.owner.person_id) : null}
                disabled={busy}
                allowDeselect={false}
                onChange={(v) => v && onOwner(x.area, Number(v))}
                comboboxProps={{ withinPortal: true }}
              />
            );
          },
        }),
        helper.display({
          id: 'status',
          header: 'Status',
          meta: { term: 'automation.status' },
          cell: ({ row }) => {
            const x = row.original;
            if (x.status === 'cant')
              return (
                <span data-testid={`cant-${x.area}`} style={{ color: 'var(--tst-warn)' }}>
                  Can&apos;t automate yet: {x.reason}
                </span>
              );
            if (x.status === 'manage') return 'Manage myself';
            const notes = [
              x.owner ? x.owner.fit : '',
              x.no_time ? 'no time last month' : '',
              x.over_budget ? 'over budget last month' : '',
            ].filter(Boolean);
            return `Automated${notes.length ? ` (${notes.join(', ')})` : ''}`;
          },
        }),
        helper.accessor('limit_cents', {
          header: 'Limit',
          meta: { term: 'automation.limit' },
          cell: ({ getValue }) => {
            const v = getValue();
            return (
              <span className="tst-num">
                {v === null || v === undefined ? '—' : formatMoneyWhole(v)}
              </span>
            );
          },
        }),
        helper.accessor('priority', {
          header: 'Priority',
          meta: { term: 'automation.priority' },
          cell: ({ getValue }) => <span className="tst-num">{getValue() ?? '—'}</span>,
        }),
        helper.accessor('decisions', {
          header: 'Decisions',
          meta: { term: 'automation.decisions' },
          cell: ({ row }) => (
            <span className="tst-num">
              {row.original.decisions}
              {row.original.mistakes ? ` (${row.original.mistakes} missteps)` : ''}
            </span>
          ),
        }),
        helper.accessor('proposals_waiting', {
          header: 'Waiting',
          meta: { term: 'automation.waiting' },
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
        helper.accessor('energy', {
          header: 'Energy',
          meta: { term: 'automation.energy' },
          cell: ({ row }) => (
            <span className="tst-num">
              {row.original.energy}
              {row.original.owner ? ` (${row.original.owner.energy_left} left)` : ''}
            </span>
          ),
        }),
        helper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) =>
            row.original.status === 'automated' ? (
              <span style={{ display: 'flex', gap: 4 }}>
                <Button size="xs" variant="subtle" onClick={() => onEdit(row.original)}>
                  Settings
                </Button>
                <Button
                  size="xs"
                  variant="subtle"
                  data-testid={`take-back-${row.original.area}`}
                  disabled={busy}
                  onClick={() => onTakeBack(row.original.area)}
                >
                  Take back
                </Button>
              </span>
            ) : null,
        }),
      ]),
    [busy, onOwner, onTakeBack, onEdit],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: areas,
    getRowId: (x) => x.area,
  });
  return <DataTable table={table} label="Areas" rowTestId="area-row" />;
}

function ConfirmAll({ saveId, onClose }: { saveId: string; onClose: () => void }) {
  const plan = useAutomatePlan(saveId, true);
  const apply = useAutomateEverything(saveId);
  return (
    <Modal opened onClose={onClose} title="Automate everything" size="lg">
      {plan.isPending ? (
        <Loading />
      ) : plan.error ? (
        <LoadError title="Could not plan" error={plan.error} />
      ) : (
        <>
          <p style={{ marginTop: 0 }}>
            Each area goes to the person with the best fit you can see, seat holders first, never
            more than their month&apos;s energy covers. Limits start at the default.
          </p>
          <table className="tst-table" aria-label="Automate everything" data-testid="plan-table">
            <tbody>
              {plan.data.assignments.map((x) => (
                <tr key={x.area} data-testid="plan-row">
                  <td>{x.label}</td>
                  <td>{x.name}</td>
                  <td>{x.fit}</td>
                  <td className="tst-num">{formatMoneyWhole(x.limit_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.data.left_out.length > 0 && (
            <p className="tst-muted" style={{ fontSize: 12 }}>
              Nobody can run yet: {plan.data.left_out.join(', ')}.
            </p>
          )}
          {apply.error && <Alert color="warn">{apply.error.message}</Alert>}
          <Button
            data-testid="automate-confirm"
            disabled={plan.data.assignments.length === 0}
            loading={apply.isPending}
            onClick={() =>
              apply.mutate(
                plan.data.assignments.map((x) => ({
                  area: x.area,
                  person_id: x.person_id,
                  limit_cents: x.limit_cents,
                })),
                { onSuccess: onClose },
              )
            }
          >
            Hand them over
          </Button>
        </>
      )}
    </Modal>
  );
}

function EditArea({ saveId, area, onClose }: { saveId: string; area: Area; onClose: () => void }) {
  const save = useAreaSettings(saveId);
  const [limit, setLimit] = useState<number>((area.limit_cents ?? 0) / CENTS);
  const [priority, setPriority] = useState<number>(area.priority ?? 0);
  const [events, setEvents] = useState(area.answer_events);
  const [bold, setBold] = useState(area.allow_bold);
  return (
    <Modal opened onClose={onClose} title={area.label}>
      <div style={{ display: 'grid', gap: 12 }}>
        <NumberInput
          label="Money limit a decision ($)"
          value={limit}
          min={0}
          thousandSeparator=","
          onChange={(v) => setLimit(Number(v) || 0)}
          data-testid="limit-input"
        />
        <NumberInput
          label="Priority (lower runs first)"
          value={priority}
          min={0}
          onChange={(v) => setPriority(Number(v) || 0)}
        />
        {area.events && (
          <Switch
            label="Let them answer routine events"
            checked={events}
            onChange={(e) => setEvents(e.currentTarget.checked)}
          />
        )}
        {area.area === 'press' && (
          <Switch
            label="Allow bold claims"
            checked={bold}
            onChange={(e) => setBold(e.currentTarget.checked)}
          />
        )}
        {save.error && <Alert color="warn">{save.error.message}</Alert>}
        <Button
          loading={save.isPending}
          onClick={() =>
            save.mutate(
              {
                area: area.area,
                limit_cents: Math.round(limit * CENTS),
                priority,
                answer_events: events,
                allow_bold: bold,
              },
              { onSuccess: onClose },
            )
          }
        >
          Save
        </Button>
      </div>
    </Modal>
  );
}

/** The last month's digest (40.4): what each owner did and what is worth your attention. */
export function DigestPanel({ saveId, compact = false }: { saveId: string; compact?: boolean }) {
  const digest = useDigest(saveId);
  const d = digest.data;
  if (!d) return null;
  const items = d.items ?? [];
  return (
    <Panel title={`Your month: ${d.month}`} testId="digest-panel">
      <p style={{ marginTop: 0 }}>{d.opening}</p>
      {d.attention.length > 0 && (
        <>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Worth your attention</div>
          <ul data-testid="digest-attention" style={{ marginTop: 4 }}>
            {d.attention.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </>
      )}
      {!compact &&
        d.areas.map((x) => (
          <div key={x.area} style={{ marginBottom: 8 }} data-testid="digest-area">
            <div style={{ fontWeight: 600, fontSize: 13 }}>
              {x.label}: {x.owner} · {x.did} decision{x.did === 1 ? '' : 's'} ·{' '}
              {formatMoneyWhole(x.committed_cents)} committed
            </div>
            <ul style={{ margin: '2px 0' }}>
              {x.lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
              {x.mistakes.map((l) => (
                <li key={`m-${l}`} style={{ color: 'var(--tst-warn)' }}>
                  Misstep: {l}
                </li>
              ))}
              {x.kpis.map((k) => (
                <li key={k.key} className="tst-muted">
                  {k.text}
                </li>
              ))}
              {x.notes.map((n) => (
                <li key={n} style={{ color: 'var(--tst-warn)' }}>
                  {n}
                </li>
              ))}
            </ul>
          </div>
        ))}
      <div style={{ fontSize: 12 }}>
        {d.inbox_item_id !== null && d.inbox_item_id !== undefined && (
          <Link to={`/game/${saveId}/inbox/${d.inbox_item_id}`} data-testid="digest-open">
            Open the digest
          </Link>
        )}
        {items.length > 0 && (
          <span className="tst-muted">
            {' '}
            · {items.length} message{items.length === 1 ? '' : 's'} from your team are filed with it
          </span>
        )}
        {compact && (
          <>
            {' '}
            · <Link to={`/game/${saveId}/automation`}>Automation</Link>
          </>
        )}
      </div>
    </Panel>
  );
}
