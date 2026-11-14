// The Family screen (M36, formulas.md 45): the head of the family, family time, the partner
// and the relationship, the children with their ratings as revealed ranges, education and
// readiness, the adviser's opinions, the dynasty and the family's history. Every value comes
// from the API; a child's potential is only ever a phrase (CLAUDE.md 8).
import { Alert, Button, NativeSelect, NumberInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState, type HTMLAttributes } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import { useHiringMeta } from '../hooks/api';
import {
  useEducate,
  useFamily,
  useOfferFamilyJob,
  useRetireAdviser,
  useSetFamilyTime,
  useSetMentoring,
  type Family,
  type FamilyMember,
} from '../hooks/family';
import { useGroup } from '../hooks/group';
import { formatMoney, formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const COL = { display: 'flex', flexDirection: 'column', gap: 8 } as const;

const DEGREES = ['engineering', 'business', 'design', 'science', 'medicine'] as const;
const LEVELS = ['junior', 'mid', 'senior', 'staff', 'principal', 'exec'] as const;

function headModeText(mode: string): string {
  return mode === 'family_head'
    ? 'Head of the family (a professional CEO runs the company)'
    : 'Founder';
}

function Line({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span className="tst-muted">{label}</span>
      <span className="tst-num" data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

function Problem({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <Alert color="orange" role="alert" data-testid="family-error">
      {error.message}
    </Alert>
  );
}

export function FamilyScreen() {
  const { saveId = '' } = useParams();
  const family = useFamily(saveId);
  if (family.isPending) return <Loading />;
  if (family.error) return <LoadError title="Could not load the family" error={family.error} />;
  return <FamilyBody saveId={saveId} family={family.data} />;
}

/** The screen's body for a loaded family (exported for render tests). */
export function FamilyBody({ saveId, family }: { saveId: string; family: Family }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="family-screen">
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Family</h1>
        {family.exists && (
          <span className="tst-muted" style={{ fontSize: 13 }} data-testid="family-head">
            {family.head_name} · {headModeText(family.head_mode)}
          </span>
        )}
        <Link
          to={`/game/${saveId}/people/${family.head_id ?? ''}?tab=family`}
          style={{ marginLeft: 'auto', fontSize: 13 }}
        >
          Succession and estate planning: the founder&apos;s Family tab
        </Link>
      </div>
      {!family.exists ? (
        <Panel style={COL} testId="family-none">
          <span className="tst-muted">No family in this game (Family was set to none).</span>
        </Panel>
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <TimePanel saveId={saveId} family={family} />
            <PartnerPanel family={family} />
            {family.dynasty && <DynastyPanel family={family} />}
          </div>
          <ChildrenPanel saveId={saveId} family={family} />
          {family.adviser && <AdviserPanel saveId={saveId} family={family} />}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <OthersPanel family={family} />
            <NotesPanel family={family} />
          </div>
        </>
      )}
    </div>
  );
}

function TimePanel({ saveId, family }: { saveId: string; family: Family }) {
  const set = useSetFamilyTime(saveId);
  const [time, setTime] = useState<number | string>(family.family_time);
  return (
    <Panel title="Family time" style={{ ...COL, flex: '1 1 260px' }} testId="family-time-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="family.time">Energy you give your family</Term> each month.
      </span>
      <Line label="This month" value={String(family.time_now)} testId="family-time" />
      <Line
        label="Energy cost (with mentoring)"
        value={String(family.energy_cost)}
        testId="family-energy-cost"
      />
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <NumberInput
          label={`Family time (0-${family.max_time})`}
          value={time}
          onChange={setTime}
          min={0}
          max={family.max_time}
          allowDecimal={false}
          data-testid="family-time-input"
          style={{ flex: 1 }}
        />
        <Button
          onClick={() => set.mutate(Number(time) || 0)}
          loading={set.isPending}
          data-testid="family-time-save"
        >
          Set
        </Button>
      </div>
      <Problem error={set.error} />
    </Panel>
  );
}

function PartnerPanel({ family }: { family: Family }) {
  const p = family.partner;
  return (
    <Panel title="Partner" style={{ ...COL, flex: '1 1 260px' }} testId="partner-panel">
      {p === null ? (
        <span className="tst-muted" data-testid="family-relationship">
          Single
        </span>
      ) : (
        <>
          <strong data-testid="partner-name">{p.name}</strong>
          <Line label="Age" value={String(p.age)} />
          <Line label="Married" value={family.married ? 'Yes' : 'No'} />
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
            <span className="tst-muted">
              <Term term="family.relationship">Relationship</Term>
            </span>
            <span className="tst-num" data-testid="family-relationship">
              {family.relationship === null ? '—' : Math.round(family.relationship)}
            </span>
          </div>
          {p.interests.length > 0 && (
            <span className="tst-muted" style={{ fontSize: 12 }}>
              Interests: {p.interests.map(humanize).join(', ')}
            </span>
          )}
        </>
      )}
    </Panel>
  );
}

function stageLabel(key: string): string {
  return key === 'mba' ? 'MBA' : humanize(key);
}

function education(m: FamilyMember): string {
  const parts = [
    m.school ? `${humanize(m.school)} school` : null,
    m.university ? `${humanize(m.university)} university` : null,
    m.degree ? humanize(m.degree) : null,
    m.mba ? 'MBA' : null,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : '—';
}

function SkillRanges({ m }: { m: FamilyMember }) {
  if (m.skills.length === 0) return <span className="tst-muted">—</span>;
  return (
    <span style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 8px', fontSize: 12 }}>
      {m.skills.map((s) => (
        <span key={s.key} title={s.label} style={{ whiteSpace: 'nowrap' }}>
          <span className="tst-muted">{s.short_label} </span>
          <span className="tst-num" data-testid="member-skill-range">
            {`${s.range.min}-${s.range.max}`}
          </span>
        </span>
      ))}
    </span>
  );
}

const helper = createColumnHelper<GameTableFeatures, FamilyMember>();

function ChildrenPanel({ saveId, family }: { saveId: string; family: Family }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          id: 'family.name',
          header: 'Name',
          sortFn: 'alphanumeric',
          cell: ({ row }) => <strong>{row.original.name}</strong>,
        }),
        helper.accessor('age', { id: 'family.age', header: 'Age', sortFn: 'basic' }),
        helper.accessor((m) => m.closeness ?? 0, {
          id: 'family.closeness',
          header: 'Closeness',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num" data-testid="member-closeness">
              {row.original.closeness === null ? '—' : Math.round(row.original.closeness)}
            </span>
          ),
        }),
        helper.accessor((m) => education(m), {
          id: 'family.education',
          header: 'Education',
          enableSorting: false,
        }),
        helper.accessor((m) => m.role ?? '', {
          id: 'family.role',
          header: 'Role',
          enableSorting: false,
          cell: ({ row }) => {
            const m = row.original;
            if (m.company_name === null) return <span className="tst-muted">—</span>;
            const job = [m.level, m.role].filter(Boolean).map((s) => humanize(s ?? ''));
            return (
              <span>
                {job.join(' ')} at {m.company_name}
                {m.mentored ? ' · mentored' : ''}
              </span>
            );
          },
        }),
        helper.accessor((m) => m.readiness?.points ?? -1, {
          id: 'family.readiness',
          header: 'Readiness',
          sortFn: 'basic',
          cell: ({ row }) => {
            const r = row.original.readiness;
            if (r === null) return <span className="tst-muted">—</span>;
            return (
              <span style={{ whiteSpace: 'nowrap' }}>
                <span data-testid="readiness-band" data-band={r.band}>
                  {humanize(r.band)}
                </span>{' '}
                <Explain
                  metric="heir_readiness"
                  entity={row.original.person_id}
                  label="Readiness"
                />
              </span>
            );
          },
        }),
        helper.accessor('potential', {
          id: 'family.potential',
          header: 'Potential',
          enableSorting: false,
          cell: ({ getValue }) => <span data-testid="member-potential">{getValue()}</span>,
        }),
        helper.display({
          id: 'family.skills',
          header: 'Skills',
          cell: ({ row }) => <SkillRanges m={row.original} />,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: family.children,
    getRowId: (m) => String(m.person_id),
  });
  return (
    <Panel style={COL} title="Children" testId="children-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Ratings are what you can see of them, as ranges; they narrow with time together.{' '}
        <Term term="family.readiness">Readiness</Term> shows for children in the group.
      </span>
      <DataTable
        table={table}
        label="Children"
        rowTestId="family-member"
        empty="No children."
        rowProps={(m) => ({ 'data-person-id': m.person_id }) as HTMLAttributes<HTMLTableRowElement>}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {family.children
          .filter((m) => m.choices.length > 0 || m.company_id !== null || m.can_join)
          .map((m) => (
            <ChildActions key={m.person_id} saveId={saveId} m={m} />
          ))}
      </div>
    </Panel>
  );
}

function ChildActions({ saveId, m }: { saveId: string; m: FamilyMember }) {
  const educate = useEducate(saveId);
  const mentor = useSetMentoring(saveId);
  const first = m.name.split(' ')[0];
  const [degree, setDegree] = useState('');
  const error = educate.error ?? mentor.error;
  return (
    <section
      className="tst-panel"
      aria-label={`Choices for ${m.name}`}
      style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 8 }}
      data-testid="family-child-actions"
      data-person-id={m.person_id}
    >
      <strong style={{ fontSize: 14 }}>{m.name}</strong>
      {m.choices.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
          <span className="tst-muted" style={{ fontSize: 12, width: '100%' }}>
            Education for {first} ({stageLabel(m.choices[0].stage)}), paid from your personal
            account
          </span>
          {m.choices.some((c) => c.stage === 'university') && (
            <NativeSelect
              label="Degree"
              value={degree}
              onChange={(e) => setDegree(e.currentTarget.value)}
              data={[
                { value: '', label: 'Any field' },
                ...DEGREES.map((d) => ({ value: d, label: humanize(d) })),
              ]}
              data-testid="educate-degree"
            />
          )}
          {m.choices.map((c) => (
            <Button
              key={`${c.stage}-${c.tier}`}
              variant="default"
              onClick={() =>
                educate.mutate({
                  person_id: m.person_id,
                  stage: c.stage,
                  tier: c.tier,
                  degree: c.stage === 'university' && degree ? degree : null,
                })
              }
              loading={educate.isPending}
              data-testid="educate-choice"
              data-person-id={m.person_id}
              data-stage={c.stage}
              data-tier={c.tier}
            >
              {stageLabel(c.tier)} · {formatMoney(c.cost_cents)}
            </Button>
          ))}
        </div>
      )}
      {m.company_id !== null && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          <Term term="family.mentoring">Mentoring</Term>
          <Button
            size="xs"
            variant={m.mentored ? 'filled' : 'default'}
            onClick={() => mentor.mutate({ person_id: m.person_id, on: !m.mentored })}
            loading={mentor.isPending}
            data-testid="mentor-toggle"
            data-person-id={m.person_id}
            data-on={m.mentored}
          >
            {m.mentored ? 'On: stop mentoring' : 'Off: mentor'}
          </Button>
        </div>
      )}
      {m.can_join && <JobForm saveId={saveId} m={m} />}
      <Problem error={error} />
    </section>
  );
}

function JobForm({ saveId, m }: { saveId: string; m: FamilyMember }) {
  const hiring = useHiringMeta();
  const group = useGroup(saveId);
  const offer = useOfferFamilyJob(saveId);
  const roles = [...(hiring.data?.roles ?? [])].sort((a, b) => a.label.localeCompare(b.label));
  const companies = group.data?.entities ?? [];
  const [role, setRole] = useState<string | null>(null);
  const [level, setLevel] = useState<string>('junior');
  const [company, setCompany] = useState<string | null>(null);
  const roleKey = role ?? roles[0]?.key ?? '';
  const companyId = company ?? (companies[0] ? String(companies[0].company_id) : '');
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
      <NativeSelect
        label="Role"
        value={roleKey}
        onChange={(e) => setRole(e.currentTarget.value)}
        data={roles.map((r) => ({ value: r.key, label: r.label }))}
        data-testid="offer-job-role"
      />
      <NativeSelect
        label="Level"
        value={level}
        onChange={(e) => setLevel(e.currentTarget.value)}
        data={LEVELS.map((l) => ({ value: l, label: humanize(l) }))}
        data-testid="offer-job-level"
      />
      {companies.length > 1 && (
        <NativeSelect
          label="Company"
          value={companyId}
          onChange={(e) => setCompany(e.currentTarget.value)}
          data={companies.map((c) => ({ value: String(c.company_id), label: c.name }))}
          data-testid="offer-job-company"
        />
      )}
      <Button
        onClick={() =>
          offer.mutate({
            person_id: m.person_id,
            company_id: Number(companyId),
            role: roleKey,
            level,
          })
        }
        disabled={!roleKey || !companyId}
        loading={offer.isPending}
        data-testid="offer-job"
        data-person-id={m.person_id}
      >
        Offer a job
      </Button>
      <Problem error={offer.error} />
    </div>
  );
}

function OthersPanel({ family }: { family: Family }) {
  return (
    <Panel title="Others" style={{ ...COL, flex: '1 1 260px' }} testId="family-others">
      {family.others.length === 0 && <span className="tst-muted">Nobody else.</span>}
      {family.others.map((o) => (
        <div
          key={o.person_id}
          style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}
          data-testid="family-other"
        >
          <span>{o.name}</span>
          <span className="tst-muted">
            {o.relation === 'ex_partner' ? 'Former partner' : humanize(o.relation)}, {o.age}
          </span>
        </div>
      ))}
    </Panel>
  );
}

function AdviserPanel({ saveId, family }: { saveId: string; family: Family }) {
  const retire = useRetireAdviser(saveId);
  const a = family.adviser;
  if (!a) return null;
  return (
    <Panel
      style={COL}
      title="The adviser"
      testId="adviser-panel"
      action={
        <Button
          size="xs"
          variant="default"
          onClick={() => retire.mutate(undefined)}
          loading={retire.isPending}
          data-testid="adviser-retire"
        >
          Ask them to retire
        </Button>
      }
    >
      <Problem error={retire.error} />
      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="family.adviser">{a.name}</Term>, {a.age}, on the board; retires at{' '}
        {a.retires_at}.
      </span>
      {a.opinions.length === 0 && <span className="tst-muted">No opinions yet.</span>}
      {a.opinions.map((o, i) => (
        <div
          key={`${o.turn}-${i}`}
          style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 13 }}
          data-testid="adviser-opinion"
          data-stance={o.stance}
        >
          <span>
            <span className="tst-muted">{o.date_label}</span> ·{' '}
            <strong>{humanize(o.stance)}</strong> · {o.title}
            {o.overruled ? ' (overruled)' : ''}
          </span>
          <span>{o.text}</span>
        </div>
      ))}
    </Panel>
  );
}

function DynastyPanel({ family }: { family: Family }) {
  const d = family.dynasty;
  if (!d) return null;
  return (
    <Panel title="Dynasty" style={{ ...COL, flex: '1 1 260px' }} testId="dynasty-panel">
      <span
        style={{ fontSize: 22, fontWeight: 700 }}
        className="tst-num"
        data-testid="dynasty-total"
      >
        <Term term="family.dynasty">{formatWhole(d.total)}</Term>
      </span>
      {d.generations.map((g) => (
        <Line
          key={g.person_id}
          label={`${g.name}, ${g.from_label}–${g.to_label ?? 'now'}${g.how ? ` (${humanize(g.how)})` : ''}`}
          value={formatWhole(g.legacy)}
        />
      ))}
      <Line label="Family-held value" value={formatMoneyWhole(d.family_value_cents)} />
      <Line label="Value points" value={formatWhole(d.value_points)} />
      <Line label={`Control losses (${d.control_losses})`} value={formatWhole(-d.loss_points)} />
    </Panel>
  );
}

function NotesPanel({ family }: { family: Family }) {
  return (
    <Panel
      title="History of the family"
      style={{ ...COL, flex: '2 1 380px' }}
      testId="family-notes"
    >
      {family.notes.length === 0 && <span className="tst-muted">Nothing yet.</span>}
      {family.notes.map((n, i) => (
        <span key={`${n.turn}-${i}`} style={{ fontSize: 13 }} data-testid="family-note">
          <span className="tst-muted">{n.date_label}</span> {n.text}
        </span>
      ))}
    </Panel>
  );
}
