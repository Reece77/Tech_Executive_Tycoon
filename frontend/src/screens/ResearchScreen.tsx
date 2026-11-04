import { Alert, Button, Modal, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { EraTimeline } from '../components/EraTimeline';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useResearch,
  useResearchAction,
  type Research,
  type ResearchAction,
  type ResearchDomain,
  type ResearchLicense,
  type ResearchProject,
  type RivalLead,
} from '../hooks/api';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const domainHelper = createColumnHelper<GameTableFeatures, ResearchDomain>();
const projectHelper = createColumnHelper<GameTableFeatures, ResearchProject>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalLead>();
const licenseHelper = createColumnHelper<GameTableFeatures, ResearchLicense>();

/** Research (M11, formulas.md 21): levels, projects, rivals' leads, licences and eras. */
export function ResearchScreen() {
  const { saveId = '' } = useParams();
  const research = useResearch(saveId);
  if (research.isPending) return <Loading />;
  if (research.error) return <LoadError title="Could not load research" error={research.error} />;
  return <Body saveId={saveId} r={research.data} />;
}

function Body({ saveId, r }: { saveId: string; r: Research }) {
  const act = useResearchAction(saveId);
  const [starting, setStarting] = useState(false);
  const [domain, setDomain] = useState(r.domains[1]?.key ?? r.domains[0]?.key ?? '');
  const [licensing, setLicensing] = useState<{ rival: RivalLead; out: boolean } | null>(null);
  const run = (a: ResearchAction, done?: () => void) => act.mutate(a, { onSuccess: done });
  const rivals = r.rivals.find((d) => d.domain === domain);
  const lifts = r.categories.filter((c) => c.lead > 0 || c.first_mover);
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Research</h1>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          A <Term term="research.lead">lead</Term> is points ahead of the industry in this field;
          start a project to build one. Leads decay {r.decay_pct.toFixed(1)}% a month without
          research
        </span>
        <Button
          style={{ marginLeft: 'auto' }}
          onClick={() => setStarting(true)}
          disabled={r.units.length === 0}
          data-testid="project-open"
        >
          Start a project
        </Button>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="research-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Your levels" testId="levels-panel">
        <DomainsTable domains={r.domains} />
        <p className="tst-muted" style={{ fontSize: 12 }} data-testid="tech-lift">
          {lifts.length === 0
            ? 'No research lead yet (points ahead of the industry; start a project to build one): product teams reach what their skills allow.'
            : lifts
                .map(
                  (c) =>
                    `${c.label}: quality cap +${c.cap_lift_pct.toFixed(1)}%, features +${c.feature_lift_pct.toFixed(1)}%${c.first_mover ? ', first-mover head start' : ''}`,
                )
                .join(' · ')}
        </p>
      </Panel>
      <Panel title="Projects" testId="projects-panel">
        <ProjectsTable
          projects={r.projects}
          busy={act.isPending}
          onStop={(p) => run({ kind: 'stop', projectId: p.project_id })}
          onBudget={(p, cents) =>
            run({ kind: 'budget', projectId: p.project_id, budgetCents: cents })
          }
        />
      </Panel>
      <div
        style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 12 }}
      >
        <Panel
          title="Rivals' levels"
          testId="rivals-panel"
          action={
            <Select
              aria-label="Domain"
              data-testid="rival-domain"
              data={r.domains.map((d) => ({ value: d.key, label: d.label }))}
              value={domain}
              onChange={(v) => v && setDomain(v)}
              allowDeselect={false}
              size="xs"
            />
          }
        >
          <RivalsTable
            rivals={rivals?.rivals ?? []}
            onLicense={(rival, out) => setLicensing({ rival, out })}
          />
          <p className="tst-muted" style={{ fontSize: 12 }}>
            Leads show as ranges. A licensor keeps {r.margin} points ahead; licensing in costs{' '}
            {formatMoneyWhole(r.price_per_point_cents)} a point at your ARR, once. Licensing out
            earns {r.royalty_pct}% of their revenue in the domain&apos;s markets for{' '}
            {r.royalty_months} months.
          </p>
        </Panel>
        <Panel title="Licences" testId="licenses-panel">
          <LicensesTable licenses={r.licenses} />
        </Panel>
      </div>
      <Panel title="Eras" testId="eras-panel">
        <EraTimeline eras={r.eras} />
      </Panel>
      {starting && (
        <StartDialog
          r={r}
          busy={act.isPending}
          onClose={() => setStarting(false)}
          onStart={(unitId, d) =>
            run({ kind: 'start', unitId, domain: d, budgetCents: null }, () => setStarting(false))
          }
        />
      )}
      {licensing && (
        <LicenseDialog
          r={r}
          domain={domain}
          rival={licensing.rival}
          out={licensing.out}
          busy={act.isPending}
          onClose={() => setLicensing(null)}
          onLicense={(points) =>
            run(
              {
                kind: licensing.out ? 'licenseOut' : 'licenseIn',
                companyId: licensing.rival.company_id,
                domain,
                points,
              },
              () => setLicensing(null),
            )
          }
        />
      )}
    </>
  );
}

function DomainsTable({ domains }: { domains: ResearchDomain[] }) {
  const columns = useMemo(
    () =>
      domainHelper.columns([
        domainHelper.accessor('label', { header: 'Domain', meta: { term: 'research.domain' } }),
        domainHelper.accessor('baseline', {
          header: 'Baseline',
          meta: { term: 'research.baseline' },
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(1)}</span>,
        }),
        domainHelper.accessor('lead', {
          header: 'Lead',
          meta: { term: 'research.lead' },
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(1)}</span>,
        }),
        domainHelper.accessor('level', {
          header: 'Level',
          meta: { term: 'research.level' },
          cell: ({ row }) => <LevelBar d={row.original} />,
        }),
        domainHelper.accessor('next_threshold', {
          header: 'Next era',
          meta: { term: 'research.threshold' },
          cell: ({ row }) =>
            row.original.next_era
              ? `${row.original.next_era} at ${row.original.next_threshold?.toFixed(1)}`
              : '—',
        }),
        domainHelper.display({
          id: 'research.domain_feeds',
          header: 'Feeds',
          meta: { term: 'research.domain' },
          cell: ({ row }) => row.original.feeds.join(', ') || 'Nothing yet (M12b)',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: domains,
    getRowId: (d) => d.key,
  });
  return <DataTable table={table} label="Your levels" rowTestId="domain-row" />;
}

function LevelBar({ d }: { d: ResearchDomain }) {
  const max = Math.max(d.level, d.next_threshold ?? 0, 1) * 1.1;
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 160 }}>
      <span className="tst-num" style={{ width: 36 }}>
        {d.level.toFixed(1)}
      </span>
      <div
        style={{ position: 'relative', flex: 1, height: 8, background: 'var(--tst-track)' }}
        aria-hidden
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: pct(d.baseline),
            background: 'var(--tst-muted)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: pct(d.baseline),
            width: `calc(${pct(d.level)} - ${pct(d.baseline)})`,
            background: 'var(--tst-accent)',
          }}
        />
        {d.next_threshold !== null && (
          <div
            style={{
              position: 'absolute',
              top: -3,
              bottom: -3,
              width: 2,
              left: pct(d.next_threshold),
              background: 'var(--tst-gold-bg)',
              outline: '1px solid var(--tst-accent)',
            }}
          />
        )}
      </div>
    </div>
  );
}

function ProjectsTable({
  projects,
  busy,
  onStop,
  onBudget,
}: {
  projects: ResearchProject[];
  busy: boolean;
  onStop: (p: ResearchProject) => void;
  onBudget: (p: ResearchProject, cents: number | null) => void;
}) {
  const columns = useMemo(
    () =>
      projectHelper.columns([
        projectHelper.accessor('unit_name', { header: 'Team', meta: { term: 'geo.units' } }),
        projectHelper.accessor('domain_label', {
          header: 'Domain',
          meta: { term: 'research.domain' },
        }),
        projectHelper.accessor('researchers', {
          header: 'Researchers',
          meta: { term: 'research.researchers' },
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
        projectHelper.accessor('needed_cents', {
          header: 'Budget',
          meta: { term: 'research.budget' },
          cell: ({ row }) => (
            <span className="tst-num">
              {formatMoneyWhole(row.original.budget_cents ?? row.original.needed_cents)} /{' '}
              {formatMoneyWhole(row.original.needed_cents)}
            </span>
          ),
        }),
        projectHelper.accessor('funded_pct', {
          header: 'Funded',
          meta: { term: 'research.funded' },
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(0)}%</span>,
        }),
        projectHelper.accessor('gain_per_month', {
          header: 'Lead a month',
          meta: { term: 'research.gain' },
          cell: ({ getValue }) => (
            <span className="tst-num" data-testid="project-gain">
              +{getValue().toFixed(2)}
            </span>
          ),
        }),
        projectHelper.accessor('months_to_era', {
          header: 'Next era',
          meta: { term: 'research.months_to_era' },
          cell: ({ row }) => {
            const p = row.original;
            if (!p.next_era) return '—';
            if (p.months_to_era === null) return `${p.next_era}: not within 10 years`;
            const early =
              p.months_before_history !== null
                ? `, about ${p.months_before_history} months before history`
                : '';
            return `${p.next_era} in ~${p.months_to_era} months${early}`;
          },
        }),
        projectHelper.accessor('last_event', {
          header: 'Last',
          meta: { term: 'research.gain' },
          cell: ({ getValue }) => getValue() ?? '—',
        }),
        projectHelper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) => (
            <span style={{ display: 'flex', gap: 4 }}>
              <Button
                size="xs"
                variant="subtle"
                disabled={busy}
                onClick={() =>
                  onBudget(
                    row.original,
                    row.original.budget_cents === null
                      ? Math.round(row.original.needed_cents / 2)
                      : null,
                  )
                }
              >
                {row.original.budget_cents === null ? 'Half budget' : 'Fund fully'}
              </Button>
              <Button
                size="xs"
                variant="subtle"
                disabled={busy}
                onClick={() => onStop(row.original)}
              >
                Stop
              </Button>
            </span>
          ),
        }),
      ]),
    [busy, onStop, onBudget],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: projects,
    getRowId: (p) => String(p.project_id),
  });
  return <DataTable table={table} label="Projects" rowTestId="project-row" />;
}

function RivalsTable({
  rivals,
  onLicense,
}: {
  rivals: RivalLead[];
  onLicense: (r: RivalLead, out: boolean) => void;
}) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', {
          header: 'Rival',
          meta: { term: 'research.rival_range' },
          cell: ({ row }) =>
            row.original.is_startup
              ? `${row.original.name} (founded ${row.original.founded})`
              : row.original.name,
        }),
        rivalHelper.accessor('high', {
          header: 'Lead',
          meta: { term: 'research.rival_range' },
          cell: ({ row }) => (
            <span className="tst-num">
              {row.original.low}–{row.original.high}
            </span>
          ),
        }),
        rivalHelper.display({
          id: 'research.licence',
          header: 'Licence',
          meta: { term: 'research.licence' },
          cell: ({ row }) => (
            <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              {row.original.can_license_in ? (
                <Button
                  size="xs"
                  variant="subtle"
                  data-testid="license-in-open"
                  onClick={() => onLicense(row.original, false)}
                >
                  License in
                </Button>
              ) : (
                <span className="tst-muted" style={{ fontSize: 12 }}>
                  {row.original.why_not}
                </span>
              )}
              {row.original.can_license_out && (
                <Button size="xs" variant="subtle" onClick={() => onLicense(row.original, true)}>
                  License out
                </Button>
              )}
            </span>
          ),
        }),
      ]),
    [onLicense],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rivals,
    getRowId: (r) => String(r.company_id),
  });
  return <DataTable table={table} label="Rivals' levels" rowTestId="rival-lead-row" />;
}

function LicensesTable({ licenses }: { licenses: ResearchLicense[] }) {
  const columns = useMemo(
    () =>
      licenseHelper.columns([
        licenseHelper.accessor('company', {
          header: 'With',
          meta: { term: 'research.licence' },
          cell: ({ row }) =>
            `${row.original.direction === 'in' ? 'From' : 'To'} ${row.original.company}`,
        }),
        licenseHelper.accessor('domain_label', {
          header: 'Domain',
          meta: { term: 'research.domain' },
        }),
        licenseHelper.accessor('points', {
          header: 'Points',
          meta: { term: 'research.licence' },
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(1)}</span>,
        }),
        licenseHelper.accessor('royalty_months_left', {
          header: 'Terms',
          meta: { term: 'research.royalty' },
          cell: ({ row }) =>
            row.original.direction === 'in'
              ? `${formatMoneyWhole(row.original.price_cents)} once`
              : `${row.original.royalty_pct}% royalty, ${row.original.royalty_months_left} months left`,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: licenses,
    getRowId: (x) => String(x.license_id),
  });
  return <DataTable table={table} label="Licences" rowTestId="license-row" />;
}

function StartDialog({
  r,
  busy,
  onClose,
  onStart,
}: {
  r: Research;
  busy: boolean;
  onClose: () => void;
  onStart: (unitId: number, domain: string) => void;
}) {
  const [unit, setUnit] = useState(String(r.units[0]?.unit_id ?? ''));
  const [domain, setDomain] = useState(r.domains[1]?.key ?? '');
  const chosen = r.units.find((u) => String(u.unit_id) === unit);
  return (
    <Modal opened onClose={onClose} title="Start a research project">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Select
          label="Team"
          data-testid="project-unit"
          data={r.units.map((u) => ({
            value: String(u.unit_id),
            label: `${u.name} (${u.researchers} researchers)`,
          }))}
          value={unit}
          onChange={(v) => v && setUnit(v)}
          allowDeselect={false}
        />
        <Select
          label="Domain"
          data-testid="project-domain"
          data={r.domains.map((d) => ({ value: d.key, label: d.label }))}
          value={domain}
          onChange={(v) => v && setDomain(v)}
          allowDeselect={false}
        />
        <p className="tst-muted" style={{ margin: 0 }}>
          The team stops working on products while it researches. Fully funded by default; set a
          budget on the project after it starts. Energy {r.start_energy}.
        </p>
        <Button
          data-testid="project-confirm"
          loading={busy}
          disabled={!chosen}
          onClick={() => chosen && onStart(chosen.unit_id, domain)}
        >
          Start
        </Button>
      </div>
    </Modal>
  );
}

function LicenseDialog({
  r,
  domain,
  rival,
  out,
  busy,
  onClose,
  onLicense,
}: {
  r: Research;
  domain: string;
  rival: RivalLead;
  out: boolean;
  busy: boolean;
  onClose: () => void;
  onLicense: (points: number) => void;
}) {
  const max = out ? rival.max_out_points : rival.max_points;
  const [points, setPoints] = useState<number>(Math.max(1, Math.min(max, 5)));
  const label = r.domains.find((d) => d.key === domain)?.label ?? domain;
  return (
    <Modal
      opened
      onClose={onClose}
      title={out ? `License ${label} to ${rival.name}` : `License ${label} from ${rival.name}`}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <NumberInput
          label={`Points (up to ${max})`}
          data-testid="license-points"
          min={1}
          max={max}
          value={points}
          onChange={(v) => setPoints(Number(v) || 1)}
        />
        <p style={{ margin: 0 }} data-testid="license-terms">
          {out
            ? `${rival.name} pays ${r.royalty_pct}% of its revenue in ${label}'s markets each month for ${r.royalty_months} months.`
            : `${formatMoneyWhole(r.price_per_point_cents)} a point at your ARR, paid once.`}
        </p>
        <p className="tst-muted" style={{ margin: 0 }}>
          Energy {r.license_energy}
        </p>
        <Button data-testid="license-confirm" loading={busy} onClick={() => onLicense(points)}>
          {out ? 'License out' : 'License in'}
        </Button>
      </div>
    </Modal>
  );
}
