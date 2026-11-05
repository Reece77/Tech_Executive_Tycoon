// Recruitment: the Hiring plans panel and the plan dialog (M2b). Values come from the API.
import {
  Alert,
  Button,
  Modal,
  NativeSelect,
  NumberInput,
  Radio,
  UnstyledButton,
} from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  useClosePlan,
  useCreatePlan,
  useNewGameMeta,
  useOrg,
  useOrgMeta,
  useOverview,
  usePeople,
  usePlans,
  useUpdatePlan,
  type HiringMeta,
  type HiringPlan,
  type Org,
  type OrgMeta,
  type Overview,
  type Person,
} from '../hooks/api';
import { formatRatio } from '../lib/format';
import { CHANNEL_LABELS, FOCUS_LABELS } from '../lib/org';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { useTableViews } from '../hooks/useTableViews';
import { AttributeRange } from './AttributeRange';
import { DataTable } from './DataTable';
import { LoadError } from './ScreenState';
import { RoleHelp } from './RoleHelp';
import { InterestFilter } from './ReplacePanel';

const helper = createColumnHelper<GameTableFeatures, HiringPlan>();
const BP = 10_000; // basis points in 1.0 (display and input conversion only)
const PLAN_CHANNELS = ['any', 'job_post', 'recruiter', 'network'] as const;

const STATUS_STYLE: Record<string, { color: string; background: string }> = {
  active: { color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
  paused: { color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
  filled: { color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
};

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function HiringPlansPanel({ saveId, hiring }: { saveId: string; hiring: HiringMeta }) {
  const plans = usePlans(saveId);
  const meta = useOrgMeta();
  const close = useClosePlan(saveId);
  const [editing, setEditing] = useState<HiringPlan | 'new' | null>(null);

  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('owner_name', {
          header: 'Owner',
          sortFn: 'alphanumeric',
          cell: ({ row }) => {
            const p = row.original;
            return p.owner_on_staff ? (
              <span>
                <Link
                  to={`/game/${saveId}/people/${p.owner_id}`}
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  {p.owner_name}
                </Link>
                <div className="tst-muted" style={{ fontSize: 12 }}>
                  {p.owner_role_label}
                </div>
              </span>
            ) : (
              <span>
                <span style={{ fontWeight: 600 }}>No owner</span>
                <div className="tst-muted" style={{ fontSize: 12 }}>
                  {p.owner_name} left
                </div>
              </span>
            );
          },
        }),
        helper.accessor('unit_name', { header: 'Unit', sortFn: 'alphanumeric' }),
        helper.accessor('role_label', { header: 'Role', sortFn: 'alphanumeric' }),
        helper.accessor('focus', {
          header: 'Focus',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span
              style={{
                color: getValue() === 'potential' ? 'var(--tst-tier-4)' : 'var(--tst-text-2)',
              }}
            >
              {FOCUS_LABELS[getValue()] ?? getValue()}
            </span>
          ),
        }),
        helper.accessor('hired', {
          header: 'Progress',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span data-testid="plan-progress">
              <span className="tst-num">
                {row.original.hired} / {row.original.target}
              </span>
              <div
                style={{
                  width: 80,
                  height: 6,
                  background: 'var(--tst-track)',
                  borderRadius: 3,
                  marginTop: 6,
                }}
              >
                <div
                  style={{
                    height: 6,
                    borderRadius: 3,
                    background: 'var(--tst-accent)',
                    width: `${Math.min(100, (100 * row.original.hired) / row.original.target)}%`,
                  }}
                />
              </div>
            </span>
          ),
        }),
        helper.accessor('channel', {
          header: 'Channel',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => CHANNEL_LABELS[getValue()] ?? getValue(),
        }),
        helper.accessor('ratio_bp', {
          header: 'Max pay',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatRatio(getValue() / BP)}</span>,
        }),
        helper.accessor('equity_bp', {
          header: 'Equity',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue()} bp</span>,
        }),
        helper.display({
          id: 'activity',
          header: 'Last month',
          cell: ({ row }) => {
            const p = row.original;
            const text =
              p.status === 'paused'
                ? 'Paused until you choose a new owner'
                : p.last_activity
                  ? `${p.last_activity.date_label}: ${capitalize(p.last_activity.summary)}`
                  : 'Starts at the next Continue';
            return (
              <span
                style={{
                  fontSize: 13,
                  color: 'var(--tst-text-2)',
                  whiteSpace: 'normal',
                  minWidth: 220,
                  display: 'block',
                }}
                data-testid="plan-activity"
              >
                {text}
              </span>
            );
          },
        }),
        helper.accessor('status', {
          header: 'Status',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (
            <span
              data-testid="plan-status"
              style={{
                ...STATUS_STYLE[getValue()],
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 4,
                padding: '2px 8px',
              }}
            >
              {capitalize(getValue())}
            </span>
          ),
        }),
        helper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) => (
            <span style={{ display: 'flex', gap: 6 }}>
              <Button
                size="compact-sm"
                variant="default"
                data-testid="edit-plan"
                onClick={() => setEditing(row.original)}
              >
                {row.original.owner_on_staff ? 'Edit' : 'Choose owner'}
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                data-testid="close-plan"
                onClick={() => close.mutate(row.original.plan_id)}
              >
                Close
              </Button>
            </span>
          ),
        }),
      ]),
    [saveId, close],
  );
  const views = useTableViews('recruitment.plans');
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: plans.data ?? [],
    getRowId: (p) => String(p.plan_id),
    ...views.tableProps,
  });

  if (plans.error) return <LoadError title="Could not load hiring plans" error={plans.error} />;
  return (
    <section
      aria-label="Hiring plans"
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Hiring plans</h2>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          Delegates search, interview and make offers for you each month, using their own energy.
        </span>
        <Button
          variant="default"
          h={36}
          ml="auto"
          data-testid="new-plan"
          onClick={() => setEditing('new')}
        >
          New plan · {meta.data?.energy_costs.hiring_plan ?? ''}
        </Button>
      </div>
      <DataTable
        views={views}
        table={table}
        label="Hiring plans"
        rowTestId="plan-row"
        empty="No hiring plans yet."
      />
      {close.error && <Alert color="red">{close.error.message}</Alert>}
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Hires join the plan&apos;s unit. When a plan fills or closes, its delegate closes the job
        posts it opened. Each plan&apos;s monthly summary also arrives in the inbox with a Delegate
        badge.
      </p>
      {editing && meta.data && (
        <PlanDialog
          saveId={saveId}
          hiring={hiring}
          meta={meta.data}
          plan={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}

function ownerLabel(p: Person, org: Org | undefined): string {
  const led = p.org?.leads_unit_id;
  const unit = led == null ? undefined : org?.units.find((u) => u.unit_id === led);
  return unit ? `${p.name} · leads ${unit.name}` : `${p.name} · ${p.role_label ?? ''}`;
}

function PlanDialog({
  saveId,
  hiring,
  meta,
  plan,
  onClose,
}: {
  saveId: string;
  hiring: HiringMeta;
  meta: OrgMeta;
  plan: HiringPlan | null;
  onClose: () => void;
}) {
  const people = usePeople(saveId);
  const org = useOrg(saveId);
  const overview = useOverview(saveId);
  const create = useCreatePlan(saveId);
  const update = useUpdatePlan(saveId);
  const staff = (people.data ?? []).filter((p) => !p.is_founder && p.employment);
  const [ownerChoice, setOwner] = useState<string>(
    plan && plan.owner_on_staff ? String(plan.owner_id) : '',
  );
  // Until the player picks, the first staff member (the list may load after the dialog opens).
  const owner = ownerChoice || String(staff[0]?.person_id ?? '');
  const [unit, setUnit] = useState<string>(plan?.unit_id == null ? 'root' : String(plan.unit_id));
  const [role, setRole] = useState<string>(plan?.role ?? hiring.roles[0]?.key ?? '');
  const [target, setTarget] = useState<number>(plan?.target ?? 2);
  const [focus, setFocus] = useState<string>(plan?.focus ?? 'current');
  const [channel, setChannel] = useState<string>(plan?.channel ?? 'any');
  const [ratio, setRatio] = useState<number>((plan?.ratio_bp ?? 11_000) / BP);
  const [equity, setEquity] = useState<number>(plan?.equity_bp ?? 0);
  const [interest, setInterest] = useState<string | null>(null); // M14b (29.5): new plans only
  const interests = useNewGameMeta().data?.interests ?? [];
  const chosen = staff.find((p) => String(p.person_id) === owner);
  const skill = (key: string) => chosen?.skills.find((s) => s.key === key);
  const judgment = skill('judgment_of_talent');
  const recruiting = skill('recruiting');
  const mutation = plan ? update : create;
  const maxRatio = meta.max_ratio_bp / BP;
  const pool = (overview.data as Overview | undefined)?.option_pool_left_bp;
  const body = {
    owner_id: Number(owner),
    unit_id: unit === 'root' ? null : Number(unit),
    role,
    target,
    focus,
    channel,
    ratio_bp: Math.round(ratio * BP),
    equity_bp: equity,
  };
  const submit = () => {
    if (plan) {
      update.mutate({ planId: plan.plan_id, body }, { onSuccess: onClose });
    } else {
      create.mutate({ ...body, interest }, { onSuccess: onClose });
    }
  };
  const units = org.data?.units ?? [];
  const unitLabel = (u: Org['units'][number]) => {
    if (u.unit_id === null) return `${u.name} (no unit)`;
    const parent = units.find((x) => x.unit_id === u.parent_id);
    return parent && parent.unit_id !== null ? `${u.name} (${parent.name})` : u.name;
  };
  return (
    <Modal
      opened
      onClose={onClose}
      title={plan ? 'Edit hiring plan' : 'New hiring plan'}
      size="xl"
      centered
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="plan-dialog">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 12,
          }}
        >
          <div>
            <NativeSelect
              label="Owner"
              value={owner}
              data-testid="plan-owner"
              onChange={(e) => setOwner(e.currentTarget.value)}
              data={staff.map((p) => ({
                value: String(p.person_id),
                label: ownerLabel(p, org.data),
              }))}
            />
            {chosen && (
              <span className="tst-muted" style={{ fontSize: 12 }} data-testid="plan-owner-info">
                Judgment of talent {judgment && <AttributeRange range={judgment.range} />} ·
                Recruiting {recruiting && <AttributeRange range={recruiting.range} />} ·{' '}
                {chosen.energy ?? meta.delegate_energy_per_month} energy a month of their own
              </span>
            )}
          </div>
          <NativeSelect
            label="Hires join"
            value={unit}
            data-testid="plan-unit"
            onChange={(e) => setUnit(e.currentTarget.value)}
            data={units.map((u) => ({
              value: u.unit_id === null ? 'root' : String(u.unit_id),
              label: unitLabel(u),
            }))}
          />
          <NativeSelect
            label="Role"
            value={role}
            data-testid="plan-role"
            onChange={(e) => setRole(e.currentTarget.value)}
            data={[...hiring.roles]
              .sort((a, b) => a.label.localeCompare(b.label))
              .map((r) => ({ value: r.key, label: r.label }))}
          />
          <RoleHelp role={hiring.roles.find((r) => r.key === role)} />
          <NumberInput
            label="How many"
            min={1}
            value={target}
            data-testid="plan-target"
            onChange={(v) => setTarget(typeof v === 'number' ? v : 1)}
          />
        </div>
        <fieldset
          style={{
            border: 0,
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <legend style={{ fontSize: 14, fontWeight: 500, padding: '0 0 6px' }}>Focus</legend>
          <div
            role="group"
            aria-label="Focus"
            style={{
              display: 'flex',
              border: '1px solid var(--tst-border)',
              borderRadius: 6,
              overflow: 'hidden',
              alignSelf: 'flex-start',
            }}
          >
            {(['current', 'potential'] as const).map((f, i) => (
              <UnstyledButton
                key={f}
                aria-pressed={focus === f}
                data-testid={`focus-${f}`}
                onClick={() => setFocus(f)}
                style={{
                  fontSize: 13,
                  padding: '8px 14px',
                  minHeight: 36,
                  color: focus === f ? 'var(--tst-text)' : 'var(--tst-text-2)',
                  background: focus === f ? 'var(--tst-panel-active)' : 'transparent',
                  borderLeft: i ? '1px solid var(--tst-border)' : 0,
                }}
              >
                {FOCUS_LABELS[f]}
              </UnstyledButton>
            ))}
          </div>
          <span className="tst-muted" style={{ fontSize: 12 }}>
            {focus === 'potential'
              ? 'Spot potential looks only at juniors and mids and ranks them by how good they could become. A recruiter with better judgment of talent reads potential far better.'
              : 'Best now ranks candidates by the skills the company can see today.'}
          </span>
        </fieldset>
        {!plan && <InterestFilter interests={interests} value={interest} onChange={setInterest} />}
        <Radio.Group label="Channel" value={channel} onChange={setChannel}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 6 }}>
            {PLAN_CHANNELS.map((c) => (
              <Radio
                key={c}
                value={c}
                label={c === 'any' ? 'Any (job post first)' : CHANNEL_LABELS[c]}
                data-testid={`plan-channel-${c}`}
              />
            ))}
          </div>
        </Radio.Group>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 12,
          }}
        >
          <NumberInput
            label="Highest offer, times the ask"
            min={0.01}
            max={maxRatio}
            step={0.05}
            decimalScale={2}
            value={ratio}
            data-testid="plan-ratio"
            onChange={(v) => setRatio(typeof v === 'number' ? v : 1)}
            description={`Up to ${maxRatio.toFixed(2)}. Higher offers are accepted more often.`}
          />
          <NumberInput
            label="Equity per offer (basis points)"
            min={0}
            max={meta.max_offer_equity_bp}
            value={equity}
            data-testid="plan-equity"
            onChange={(v) => setEquity(typeof v === 'number' ? v : 0)}
            description={`Up to ${meta.max_offer_equity_bp}${
              pool === undefined ? '' : ` · ${pool} bp left in the option pool`
            }`}
          />
        </div>
        {mutation.error && <Alert color="red">{mutation.error.message}</Alert>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <Button
            size="md"
            onClick={submit}
            loading={mutation.isPending}
            disabled={!owner || !role}
            data-testid="save-plan"
          >
            {plan ? 'Save plan' : 'Start plan'} · {meta.energy_costs.hiring_plan} energy
          </Button>
          <Button size="md" variant="default" onClick={onClose}>
            Cancel
          </Button>
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {chosen ? chosen.name.split(' ')[0] : 'The owner'} works it each month from the next
            Continue. Searches and recruiter fees are charged as usual.
          </span>
        </div>
      </div>
    </Modal>
  );
}
