import { TeamMoodLine } from '../components/Relationships';
import { Alert, Button, Menu, NativeSelect } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState, type DragEvent } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { MoraleBar } from '../components/MoraleBar';
import { LeadershipFit } from '../components/LeadershipFit';
import { LeadsChip, OrgNode, UnitKindBadge } from '../components/OrgNode';
import { WorksOn } from '../components/WorksOn';
import { ChangeDialog, type Pending } from '../components/OrgChangeDialog';
import { ScaleupPanels } from '../components/ScaleupPanels';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useOrg,
  useOrgGuide,
  useOrgMeta,
  usePeople,
  type Org,
  type OrgManager,
  type OrgMeta,
  type OrgUnit,
  type Person,
} from '../hooks/api';
import { humanize } from '../lib/format';
import { MANAGER_LABELS, POLICY_LABELS, type UnitKind } from '../lib/org';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const ROOT = 'root'; // selection key of the company root (unit_id null)
const DRAG_PERSON = 'application/x-tst-person';
const DRAG_UNIT = 'application/x-tst-unit';

type Member = OrgUnit['members'][number] & { morale: number | null };
const helper = createColumnHelper<GameTableFeatures, Member>();

const keyOf = (unitId: number | null) => (unitId === null ? ROOT : String(unitId));

export function OrgScreen() {
  const { saveId = '' } = useParams();
  const org = useOrg(saveId);
  const meta = useOrgMeta();
  const people = usePeople(saveId);
  const error = org.error ?? meta.error ?? people.error;
  if (error) return <LoadError title="Could not load the org" error={error} />;
  if (!org.data || !meta.data || !people.data) return <Loading />;
  return <OrgBody saveId={saveId} org={org.data} meta={meta.data} people={people.data} />;
}

function OrgBody({
  saveId,
  org,
  meta,
  people,
}: {
  saveId: string;
  org: Org;
  meta: OrgMeta;
  people: Person[];
}) {
  const [selected, setSelected] = useState<string>(ROOT);
  const [pending, setPending] = useState<Pending | null>(null);
  const [dropOn, setDropOn] = useState<string | null>(null);

  const units = useMemo(() => new Map(org.units.map((u) => [keyOf(u.unit_id), u])), [org.units]);
  const managers = useMemo(
    () => new Map(org.managers.map((m) => [m.person_id, m])),
    [org.managers],
  );
  const morale = useMemo(() => new Map(people.map((p) => [p.person_id, p.morale])), [people]);
  const root = units.get(ROOT);
  const unit = units.get(selected) ?? root;
  if (!root || !unit) return <LoadError title="The org has no company root" error={null} />;
  const costs = meta.energy_costs;
  const personHref = (id: number) => `/game/${saveId}/people/${id}`;
  const unitName = (id: number | null) => units.get(keyOf(id))?.name ?? root.name;

  const open = (p: Pending) => setPending(p);

  // --- Drag and drop: people onto units, teams onto departments or the company ---
  const dropHandlers = (target: OrgUnit) => ({
    onDragOver: (event: DragEvent) => {
      const types = event.dataTransfer.types;
      const isUnit = types.includes(DRAG_UNIT);
      if (types.includes(DRAG_PERSON) || (isUnit && target.kind !== 'team')) {
        event.preventDefault();
        setDropOn(keyOf(target.unit_id));
      }
    },
    onDragLeave: () => setDropOn(null),
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      setDropOn(null);
      const person = event.dataTransfer.getData(DRAG_PERSON);
      const team = event.dataTransfer.getData(DRAG_UNIT);
      if (person) {
        const member = org.units
          .flatMap((u) => u.members)
          .find((m) => String(m.person_id) === person);
        if (member) open(movePersonChange(member.person_id, member.name, target.unit_id));
      } else if (team && target.kind !== 'team') {
        const moving = units.get(team);
        if (moving?.unit_id != null) open(moveUnitChange(moving, target));
      }
    },
  });

  const movePersonChange = (personId: number, name: string, to: number | null): Pending => ({
    change: { change: 'move_person', person_id: personId, unit_id: to },
    title: `Move ${name} to ${unitName(to)}?`,
    confirmLabel: `Move ${name.split(' ')[0]}`,
    note: 'Their manager changes, so their monthly morale and growth follow the new manager from next month.',
  });
  const moveUnitChange = (team: OrgUnit, to: OrgUnit): Pending => ({
    change: { change: 'move_unit', unit_id: team.unit_id ?? 0, parent_id: to.unit_id },
    title: `Move ${team.name} under ${to.name}?`,
    subtitle: 'Its members and leader go with it.',
    confirmLabel: `Move ${team.name}`,
  });

  const nodeFor = (u: OrgUnit) => {
    const leader = u.leader_id === null ? undefined : managers.get(u.leader_id);
    const k = keyOf(u.unit_id);
    return (
      <OrgNode
        key={k}
        kind={u.kind as UnitKind}
        name={u.name}
        leaderName={u.leader_name}
        leaderHref={u.leader_id === null ? null : personHref(u.leader_id)}
        isFounderLed={u.unit_id === null}
        policy={u.policy}
        effectivePolicy={u.effective_policy}
        headcount={u.headcount}
        span={
          leader
            ? { reports: leader.reports.length, limit: leader.span_limit, over: leader.over_span }
            : null
        }
        product={u.product_name}
        selected={selected === k}
        dropActive={dropOn === k}
        draggable={u.kind === 'team' || u.kind === 'department'}
        onSelect={() => setSelected(k)}
        onDragStart={(event) => event.dataTransfer.setData(DRAG_UNIT, k)}
        {...dropHandlers(u)}
      />
    );
  };

  const childrenOf = (u: OrgUnit) =>
    u.child_unit_ids.map((id) => units.get(String(id))).filter((c): c is OrgUnit => !!c);
  // Divisions add a level (M8): division > department > team.
  const subtree = (u: OrgUnit): React.ReactNode => (
    <div key={keyOf(u.unit_id)} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {nodeFor(u)}
      {u.child_unit_ids.length > 0 && <Branch>{childrenOf(u).map(subtree)}</Branch>}
    </div>
  );
  const direct = root.members.filter((m) => !m.is_founder);
  const founderFirst = root.leader_name?.split(' ')[0] ?? 'the founder';
  const unitCount = org.units.length - 1;

  return (
    <>
      <ScreenTitle
        aside={
          <>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="org-summary">
              {org.headcount} people · {unitCount} {unitCount === 1 ? 'unit' : 'units'} ·{' '}
              {org.managers_over_span} {org.managers_over_span === 1 ? 'manager' : 'managers'} over
              span
            </span>
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginLeft: 'auto' }}>
              <Button
                variant="default"
                h={36}
                data-testid="new-team"
                onClick={() =>
                  open({
                    change: {
                      change: 'create_unit',
                      kind: 'team',
                      name: '',
                      parent_id:
                        unit.kind === 'department' || unit.kind === 'division'
                          ? unit.unit_id
                          : null,
                    },
                    title: 'New team',
                    confirmLabel: 'Create team',
                    nameInput: true,
                  })
                }
              >
                New team · {costs.create_unit}
              </Button>
              {org.departments_unlocked && (
                <Button
                  variant="default"
                  h={36}
                  data-testid="new-department"
                  onClick={() =>
                    open({
                      change: {
                        change: 'create_unit',
                        kind: 'department',
                        name: '',
                        parent_id: unit.kind === 'division' ? unit.unit_id : null,
                      },
                      title: 'New department',
                      confirmLabel: 'Create department',
                      nameInput: true,
                    })
                  }
                >
                  New department · {costs.create_unit}
                </Button>
              )}
              {org.divisions_unlocked && (
                <Button
                  variant="default"
                  h={36}
                  data-testid="new-division"
                  onClick={() =>
                    open({
                      change: { change: 'create_unit', kind: 'division', name: '' },
                      title: 'New division',
                      subtitle:
                        'A division has a president and its own P&L. Move departments and teams into it.',
                      confirmLabel: 'Create division',
                      nameInput: true,
                    })
                  }
                >
                  New division · {costs.create_unit}
                </Button>
              )}
            </span>
          </>
        }
      >
        Org
      </ScreenTitle>
      <p className="tst-muted" style={{ margin: '-6px 0 0', fontSize: 12 }} data-testid="org-help">
        {org.departments_unlocked
          ? `Departments unlocked at ${meta.department_unlock_headcount} staff. `
          : `Departments unlock at ${meta.department_unlock_headcount} staff (you have ${org.headcount}) or once the company is venture-backed. `}
        Drag a person onto a unit to move them, or drag a team onto a department or division. Every
        change shows its morale cost before you confirm. Numbers after an action are its energy
        cost.{' '}
        <Link to={`/game/${saveId}/org/offices`} data-testid="offices-link">
          Offices and cities
        </Link>
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <section
          aria-label="Org chart"
          style={{
            flex: '3 1 560px',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {nodeFor(root)}
          <Branch>
            {childrenOf(root).map(subtree)}
            {direct.length > 0 && (
              <div
                data-testid="direct-reports"
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 14px',
                  border: '1px dashed var(--tst-border)',
                  borderRadius: 8,
                }}
              >
                <span className="tst-muted" style={{ fontSize: 13 }}>
                  Reporting to {founderFirst} directly, no unit:
                </span>
                {direct.map((m) => (
                  <span
                    key={m.person_id}
                    draggable
                    onDragStart={(event) =>
                      event.dataTransfer.setData(DRAG_PERSON, String(m.person_id))
                    }
                    data-testid="direct-chip"
                    style={{
                      fontSize: 13,
                      background: 'var(--tst-panel-active)',
                      border: '1px solid var(--tst-border)',
                      borderRadius: 14,
                      padding: '4px 12px',
                      cursor: 'grab',
                    }}
                  >
                    {m.name} · {m.role_label}
                  </span>
                ))}
              </div>
            )}
          </Branch>
          <p className="tst-muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
            Reports shows direct reports against the leader&apos;s comfortable span. A team lead
            reports to the leader of the unit above.
          </p>
        </section>
        <UnitPanel
          unit={unit}
          org={org}
          units={units}
          managers={managers}
          morale={morale}
          meta={meta}
          personHref={personHref}
          onChange={open}
          movePerson={movePersonChange}
          moveUnit={moveUnitChange}
        />
      </div>
      <ScaleupPanels saveId={saveId} org={org} />
      <StructureGuide saveId={saveId} />
      {pending && (
        <ChangeDialog
          saveId={saveId}
          pending={pending}
          onDone={(created) => {
            setPending(null);
            if (created !== undefined) setSelected(created);
          }}
        />
      )}
    </>
  );
}

function Branch({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        marginLeft: 22,
        paddingLeft: 18,
        borderLeft: '1px solid var(--tst-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {children}
    </div>
  );
}

function UnitPanel({
  unit,
  org,
  units,
  managers,
  morale,
  meta,
  personHref,
  onChange,
  movePerson,
  moveUnit,
}: {
  unit: OrgUnit;
  org: Org;
  units: Map<string, OrgUnit>;
  managers: Map<number, OrgManager>;
  morale: Map<number, number | null>;
  meta: OrgMeta;
  personHref: (id: number) => string;
  onChange: (p: Pending) => void;
  movePerson: (personId: number, name: string, to: number | null) => Pending;
  moveUnit: (team: OrgUnit, to: OrgUnit) => Pending;
}) {
  const costs = meta.energy_costs;
  const isRoot = unit.unit_id === null;
  const leader = unit.leader_id === null ? undefined : managers.get(unit.leader_id);
  const parent = unit.parent_id === null ? undefined : units.get(String(unit.parent_id));
  const root = units.get(ROOT);
  const members: Member[] = unit.members.map((m) => ({
    ...m,
    morale: morale.get(m.person_id) ?? null,
  }));
  const destinations = org.units.filter((u) => u.unit_id !== unit.unit_id);
  // Where a team or department may go: the company or a division, and teams also a
  // department (M8 adds divisions). The API still refuses anything else.
  const departments = org.units.filter(
    (u) =>
      (u.unit_id === null ||
        u.kind === 'division' ||
        (unit.kind === 'team' && u.kind === 'department')) &&
      u.unit_id !== unit.parent_id &&
      u.unit_id !== unit.unit_id,
  );
  const inheritFrom = parent ?? root;

  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Member',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Link
                to={personHref(row.original.person_id)}
                style={{ fontWeight: 600, textDecoration: 'none' }}
              >
                {row.original.name}
              </Link>
              {row.original.is_leader && <LeadsChip />}
            </span>
          ),
        }),
        helper.accessor('role_label', { header: 'Role', sortFn: 'alphanumeric' }),
        helper.accessor('level', {
          header: 'Level',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => humanize(getValue()),
        }),
        helper.accessor((m) => m.morale ?? undefined, {
          id: 'morale',
          header: 'Morale',
          sortFn: 'basic',
          sortUndefined: 'last',
          cell: ({ row }) => <MoraleBar morale={row.original.morale} width={48} />,
        }),
        helper.accessor((m) => m.leadership_fit_high, {
          id: 'leadership_fit',
          header: 'Lead fit',
          sortFn: 'basic',
          cell: ({ row }) => (
            <LeadershipFit
              low={row.original.leadership_fit_low}
              high={row.original.leadership_fit_high}
            />
          ),
        }),
        helper.display({
          id: 'move',
          header: '',
          cell: ({ row }) =>
            row.original.is_founder ? null : (
              <Menu position="bottom-end">
                <Menu.Target>
                  <Button
                    size="compact-sm"
                    variant="default"
                    data-testid="move-to"
                    disabled={row.original.is_leader && !isRoot}
                    title={
                      row.original.is_leader && !isRoot
                        ? 'Replace or remove them as leader first'
                        : undefined
                    }
                  >
                    Move to… · {costs.move_person}
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  {destinations.map((d) => (
                    <Menu.Item
                      key={keyOf(d.unit_id)}
                      onClick={() =>
                        onChange(movePerson(row.original.person_id, row.original.name, d.unit_id))
                      }
                    >
                      {d.name}
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            ),
        }),
      ]),
    [personHref, destinations, onChange, movePerson, costs.move_person, isRoot],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: members,
    getRowId: (m) => String(m.person_id),
  });

  const policyValue = isRoot ? (unit.policy ?? 'office') : (unit.policy ?? 'inherit');
  const leaderOptions = unit.members.filter((m) => !m.is_founder && m.person_id !== unit.leader_id);

  return (
    <aside
      className="tst-panel"
      aria-label="Selected unit"
      data-testid="unit-panel"
      style={{ flex: '2 1 380px', display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }} data-testid="unit-title">
          {unit.name}
        </h2>
        <UnitKindBadge kind={unit.kind as UnitKind} />
        {parent && <span className="tst-muted">in {parent.name}</span>}
      </div>
      <TeamMoodLine unitId={unit.unit_id} />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 10,
        }}
      >
        <div>
          <div className="tst-muted">Leader</div>
          <div style={{ fontSize: 15 }}>
            {unit.leader_id === null ? (
              'None'
            ) : (
              <Link to={personHref(unit.leader_id)}>{unit.leader_name}</Link>
            )}
          </div>
        </div>
        <div>
          <div className="tst-muted">Reports</div>
          <div
            className="tst-num"
            style={{ fontSize: 15, color: leader?.over_span ? 'var(--tst-warn)' : undefined }}
            data-testid="unit-reports"
          >
            {leader ? `${leader.reports.length} of ${leader.span_limit} comfortable` : '—'}
          </div>
        </div>
        <div>
          <div className="tst-muted">As a manager</div>
          <div style={{ fontSize: 15 }} data-testid="manager-label">
            {leader ? (MANAGER_LABELS[leader.label] ?? leader.label) : '—'}
          </div>
        </div>
      </div>
      <WorksOn unit={unit} />
      {leader?.over_span && (
        <Alert color="warn" data-testid="over-span-note">
          {unit.leader_name} has more reports than they can handle well, so their team&apos;s morale
          and growth suffer. Move someone out, split the team, or appoint a stronger lead.
        </Alert>
      )}
      <NativeSelect
        label="Work location"
        value={policyValue}
        data-testid="policy-select"
        data={[
          ...(isRoot
            ? []
            : [
                {
                  value: 'inherit',
                  label: `Inherit from ${inheritFrom?.name ?? 'the company'} (${
                    POLICY_LABELS[inheritFrom?.effective_policy ?? 'office'] ?? ''
                  })`,
                },
              ]),
          { value: 'office', label: 'Office' },
          { value: 'remote', label: 'Remote' },
        ]}
        onChange={(event) => {
          const value = event.currentTarget.value;
          const policy = value === 'inherit' ? null : (value as 'office' | 'remote');
          onChange({
            change: { change: 'set_policy', unit_id: unit.unit_id, policy },
            title: `Set ${unit.name}'s work location to ${
              policy ? POLICY_LABELS[policy] : 'inherit'
            }?`,
            confirmLabel: 'Set work location',
            note: 'Remote staff cost no office fee; sociable people dislike remote work and solitary ones like it.',
          });
        }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {!isRoot && (
          <Menu>
            <Menu.Target>
              <Button variant="default" h={36} data-testid="set-leader">
                Set leader · {costs.set_leader}
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              {leaderOptions.length === 0 && unit.leader_id === null && (
                <Menu.Label>Move someone into {unit.name} first</Menu.Label>
              )}
              {leaderOptions.map((m) => (
                <Menu.Item
                  key={m.person_id}
                  data-testid="leader-option"
                  onClick={() =>
                    onChange({
                      change: {
                        change: 'set_leader',
                        unit_id: unit.unit_id ?? 0,
                        person_id: m.person_id,
                      },
                      title: `Make ${m.name} the leader of ${unit.name}?`,
                      confirmLabel: 'Appoint',
                    })
                  }
                >
                  {m.name} · {m.role_label}
                </Menu.Item>
              ))}
              {unit.leader_id !== null && (
                <Menu.Item
                  color="warn"
                  onClick={() =>
                    onChange({
                      change: { change: 'set_leader', unit_id: unit.unit_id ?? 0, person_id: null },
                      title: `Remove ${unit.leader_name} as leader of ${unit.name}?`,
                      confirmLabel: 'Remove leader',
                    })
                  }
                >
                  Remove the current leader
                </Menu.Item>
              )}
            </Menu.Dropdown>
          </Menu>
        )}
        {!isRoot && (
          <Button
            variant="default"
            h={36}
            data-testid="rename"
            onClick={() =>
              onChange({
                change: { change: 'rename_unit', unit_id: unit.unit_id ?? 0, name: unit.name },
                title: `Rename ${unit.name}`,
                confirmLabel: 'Rename',
                nameInput: true,
              })
            }
          >
            Rename
          </Button>
        )}
        {(unit.kind === 'team' || unit.kind === 'department') && (
          <Menu>
            <Menu.Target>
              <Button variant="default" h={36} data-testid="move-team">
                Move {unit.kind} · {costs.move_unit}
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              {departments.map((d) => (
                <Menu.Item key={keyOf(d.unit_id)} onClick={() => onChange(moveUnit(unit, d))}>
                  Under {d.name}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
        )}
        {!isRoot && (
          <Button
            variant="default"
            h={36}
            data-testid="dissolve"
            style={{ color: 'var(--tst-warn)', borderColor: '#6A4426' }}
            onClick={() =>
              onChange({
                change: { change: 'dissolve_unit', unit_id: unit.unit_id ?? 0 },
                title: `Dissolve ${unit.name}?`,
                subtitle: `Its members and teams move to ${parent?.name ?? root?.name ?? 'the company'}.`,
                confirmLabel: 'Dissolve',
              })
            }
          >
            Dissolve · {costs.dissolve_unit}
          </Button>
        )}
      </div>
      <DataTable
        table={table}
        label={`Members of ${unit.name}`}
        rowTestId="member-row"
        empty="No members yet."
        rowProps={(m) =>
          m.is_founder
            ? {}
            : {
                draggable: true,
                style: { cursor: 'grab' },
                onDragStart: (event) =>
                  event.dataTransfer.setData(DRAG_PERSON, String(m.person_id)),
              }
        }
      />
    </aside>
  );
}

/** What the structure does and this company's numbers (23.4, M10b). */
function StructureGuide({ saveId }: { saveId: string }) {
  const guide = useOrgGuide(saveId);
  if (!guide.data) return null;
  return (
    <Panel title="How structure helps" label="Structure guide">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))',
          gap: 16,
        }}
        data-testid="structure-guide"
      >
        {guide.data.sections.map((s) => (
          <section key={s.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{s.title}</h3>
            <p className="tst-muted" style={{ margin: 0, fontSize: 13, lineHeight: 1.45 }}>
              {s.text}
            </p>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
              {s.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Panel>
  );
}
