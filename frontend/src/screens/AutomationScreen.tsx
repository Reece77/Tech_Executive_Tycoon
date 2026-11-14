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
  useHeadcountTarget,
  useTakeBackArea,
  type Area,
  type Automation,
} from '../hooks/automation';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, Area>();
const CENTS = 100;
// M27b (formulas.md 40.7): what each guardrail means, for the settings dialog.
const RAIL_LABELS: Record<string, string> = {
  cover_low_weeks: 'Lowest cover (weeks of demand)',
  cover_high_weeks: 'Highest cover (weeks of demand)',
  order_weeks: 'An order brings cover to (weeks)',
  contract_months: 'An order runs (months)',
  cover_low: 'Lowest 12-month input cover (share)',
  cover_high: 'Highest 12-month input cover (share)',
  min_grade: 'Give up below (x the median grade)',
  projects: 'Live projects a front',
  safety: 'Mine safety (0 low, 1 normal, 2 high)',
  contract_share: 'Share of a mine contracted when the group needs none',
  margin: 'Foundry price at least (share over cost a start)',
  contracted_share: 'Most of a fab under contract (share)',
};

/** Automation (M27a, formulas.md 40.8): who runs each area, under what limit, and what they did. */
export function AutomationScreen() {
  const { saveId = '' } = useParams();
  const [companyId, setCompanyId] = useState<number | null>(null);
  const auto = useAutomation(saveId, companyId);
  if (auto.isPending) return <Loading />;
  if (auto.error) return <LoadError title="Could not load automation" error={auto.error} />;
  return <Body saveId={saveId} a={auto.data} onCompany={setCompanyId} />;
}

function Body({
  saveId,
  a,
  onCompany,
}: {
  saveId: string;
  a: Automation;
  onCompany: (id: number | null) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState<Area | null>(null);
  const company = a.subsidiary ? a.company_id : null;
  const setOwner = useSetAreaOwner(saveId);
  const takeBack = useTakeBackArea(saveId, company);
  const error = setOwner.error ?? takeBack.error;
  const open = a.areas.filter((x) => x.status === 'manage').length;
  const companies = a.companies ?? [];
  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Automation</h1>
        {companies.length > 1 && (
          <Select
            size="xs"
            aria-label="Company"
            data-testid="automation-company"
            data={companies.map((c) => ({
              value: String(c.company_id),
              label: c.subsidiary ? `${c.name} (subsidiary)` : c.name,
            }))}
            value={String(a.company_id)}
            allowDeselect={false}
            onChange={(v) => {
              if (!v) return;
              const chosen = companies.find((c) => String(c.company_id) === v);
              onCompany(chosen && chosen.subsidiary ? chosen.company_id : null);
            }}
            comboboxProps={{ withinPortal: true }}
          />
        )}
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
          onOwner={(area, personId) =>
            setOwner.mutate({ area, person_id: personId, company_id: company })
          }
          onTakeBack={(area) => takeBack.mutate(area)}
          onEdit={setEditing}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          An owner acts under their money limit; at or above it, and for every one-off (buying,
          selling, rounds, loans, facilities, sunsets, big layoffs, appointments), they propose and
          you decide. Each person has a month&apos;s energy: areas past it get no time. Fit comes
          from what you know of them.
          {a.subsidiary
            ? ' Inside a subsidiary its CEO comes first, its mandate is the guardrail, and the decisions are in its own books.'
            : ''}
        </p>
      </Panel>
      <HeadcountPanel saveId={saveId} a={a} company={company} />
      <DigestPanel saveId={saveId} />
      {confirming && (
        <ConfirmAll saveId={saveId} company={company} onClose={() => setConfirming(false)} />
      )}
      {editing && (
        <EditArea
          saveId={saveId}
          area={editing}
          company={company}
          onClose={() => setEditing(null)}
        />
      )}
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

function ConfirmAll({
  saveId,
  company,
  onClose,
}: {
  saveId: string;
  company: number | null;
  onClose: () => void;
}) {
  const plan = useAutomatePlan(saveId, true, company);
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
                  company_id: company,
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

function EditArea({
  saveId,
  area,
  company,
  onClose,
}: {
  saveId: string;
  area: Area;
  company: number | null;
  onClose: () => void;
}) {
  const save = useAreaSettings(saveId);
  const [limit, setLimit] = useState<number>((area.limit_cents ?? 0) / CENTS);
  const [priority, setPriority] = useState<number>(area.priority ?? 0);
  const [events, setEvents] = useState(area.answer_events);
  const [bold, setBold] = useState(area.allow_bold);
  const [budget, setBudget] = useState<number>((area.budget_cents ?? 0) / CENTS);
  const [rails, setRails] = useState<Record<string, number>>(
    Object.fromEntries((area.guardrails ?? []).map((g) => [g.key, g.value])),
  );
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
        {area.budgeted && (
          <NumberInput
            label="Yearly budget ($; 0 keeps it off)"
            value={budget}
            min={0}
            thousandSeparator=","
            onChange={(v) => setBudget(Number(v) || 0)}
            data-testid="budget-input"
          />
        )}
        {(area.guardrails ?? []).map((g) => (
          <NumberInput
            key={g.key}
            label={`${RAIL_LABELS[g.key] ?? g.key} (default ${g.default})`}
            value={rails[g.key] ?? g.value}
            min={0}
            decimalScale={2}
            onChange={(v) => setRails({ ...rails, [g.key]: Number(v) || 0 })}
            data-testid={`rail-${g.key}`}
          />
        ))}
        {save.error && <Alert color="warn">{save.error.message}</Alert>}
        <Button
          loading={save.isPending}
          data-testid="settings-save"
          onClick={() =>
            save.mutate(
              {
                area: area.area,
                limit_cents: Math.round(limit * CENTS),
                priority,
                answer_events: events,
                allow_bold: bold,
                company_id: company,
                budget_cents: area.budgeted ? Math.round(budget * CENTS) : null,
                guardrails: Object.entries(rails).map(([key, value]) => ({ key, value })),
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

/** M27b sub-task 9: headcount targets per unit, which the Hiring owner fills. */
function HeadcountPanel({
  saveId,
  a,
  company,
}: {
  saveId: string;
  a: Automation;
  company: number | null;
}) {
  const set = useHeadcountTarget(saveId);
  const [unit, setUnit] = useState<string | null>(null);
  const [role, setRole] = useState<string>('software_engineer');
  const [target, setTarget] = useState<number>(1);
  const units = a.units ?? [];
  const targets = a.headcount_targets ?? [];
  const hiring = a.areas.find((x) => x.area === 'hiring');
  if (units.length === 0 && targets.length === 0) return null;
  return (
    <Panel title="Headcount targets" testId="headcount-panel">
      <p className="tst-muted" style={{ marginTop: 0, fontSize: 12 }}>
        {hiring?.status === 'automated'
          ? `${hiring.owner?.name ?? 'Hiring'} opens plans to keep each unit at its target.`
          : 'Give Hiring to someone and they open plans to keep each unit at its target.'}
      </p>
      {targets.length > 0 && (
        <table className="tst-table" aria-label="Headcount targets">
          <tbody>
            {targets.map((t) => (
              <tr key={`${t.unit_id}-${t.role}`} data-testid="headcount-row">
                <td>{t.unit_name}</td>
                <td>{t.role_label}</td>
                <td className="tst-num">
                  {t.staff} of {t.target}
                  {t.gap > 0 ? ` (${t.gap} to plan)` : ''}
                </td>
                <td>
                  <Button
                    size="xs"
                    variant="subtle"
                    onClick={() =>
                      set.mutate({
                        unit_id: t.unit_id,
                        role: t.role,
                        target: 0,
                        company_id: company,
                      })
                    }
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {units.length > 0 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <Select
            size="xs"
            label="Unit"
            data-testid="headcount-unit"
            data={units.map((u) => ({ value: String(u.unit_id), label: u.name }))}
            value={unit}
            onChange={setUnit}
            comboboxProps={{ withinPortal: true }}
          />
          <Select
            size="xs"
            label="Role"
            searchable
            data={(a.roles ?? []).map((r) => ({ value: r.key, label: r.label }))}
            value={role}
            onChange={(v) => v && setRole(v)}
            comboboxProps={{ withinPortal: true }}
          />
          <NumberInput
            size="xs"
            label="Target"
            min={0}
            value={target}
            onChange={(v) => setTarget(Number(v) || 0)}
          />
          <Button
            size="xs"
            disabled={unit === null}
            loading={set.isPending}
            data-testid="headcount-set"
            onClick={() =>
              unit !== null &&
              set.mutate({ unit_id: Number(unit), role, target, company_id: company })
            }
          >
            Set target
          </Button>
        </div>
      )}
      {set.error && <Alert color="warn">{set.error.message}</Alert>}
    </Panel>
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
