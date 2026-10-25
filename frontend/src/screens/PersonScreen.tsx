import { Alert, Button, Group, Modal } from '@mantine/core';
import { useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts';
import { AttributeRange } from '../components/AttributeRange';
import { MoraleBar } from '../components/MoraleBar';
import { MoraleBreakdownPanel, PersonActions, UnitManagerLine } from '../components/PersonOrg';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { StatusChip } from '../components/StatusChip';
import {
  useFire,
  useHiringMeta,
  useNewGameMeta,
  useOverview,
  usePerson,
  type Attribute,
  type HiringMeta,
  type NewGameMeta,
  type Overview,
  type Profile,
} from '../hooks/api';
import {
  formatBpPercent,
  formatMoneyWhole,
  formatMonths,
  formatWhole,
  humanize,
} from '../lib/format';
import { statusOf } from '../lib/status';

const SPARK_MONTHS = 5;
const GROUPS = [
  ['technical', 'Technical'],
  ['business', 'Business'],
  ['leadership', 'Leadership'],
] as const;

export function PersonScreen() {
  const { saveId = '', personId = '' } = useParams();
  const person = usePerson(saveId, Number(personId));
  const meta = useNewGameMeta();
  const hiring = useHiringMeta();
  const overview = useOverview(saveId);

  const error = person.error ?? meta.error ?? hiring.error ?? overview.error;
  if (error) {
    return (
      <>
        <Link to={`/game/${saveId}/people`} style={{ fontSize: 13, textDecoration: 'none' }}>
          ← People
        </Link>
        <LoadError title="Could not load this person" error={error} />
      </>
    );
  }
  if (!person.data || !meta.data || !hiring.data || !overview.data) return <Loading />;
  return (
    <ProfileBody
      saveId={saveId}
      p={person.data}
      meta={meta.data}
      hiring={hiring.data}
      overview={overview.data}
    />
  );
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="tst-muted" style={{ fontSize: 12 }}>
        {label}
      </div>
      <div style={{ fontSize: 17 }}>{children}</div>
    </div>
  );
}

function AttrPanel({ title, attrs }: { title: string; attrs: Attribute[] }) {
  return (
    <Panel title={title} label={`${title} attributes`}>
      {attrs.map((a) => (
        <div key={a.key} className="tst-row" data-testid={`attr-${a.key}`}>
          <span style={{ color: 'var(--tst-text-2)' }}>{a.label}</span>
          <AttributeRange range={a.range} label={a.label} />
        </div>
      ))}
    </Panel>
  );
}

/** "How well you know them": built from how the company met and checked this person. */
function knowledgeLine(p: Profile): string {
  if (p.is_founder)
    return 'You know yourself exactly; your potential stays a phrase, as for anyone.';
  const k = p.knowledge;
  const parts: string[] = [];
  if (k.channel === 'network') parts.push('Introduced through your network');
  if (k.channel === 'job_post') parts.push('Screened from a job post');
  if (k.channel === 'recruiter') parts.push('Screened by a recruiter');
  if (k.interviews > 0) {
    parts.push(
      `interviewed in ${k.first_interview_date_label}${k.interviews > 1 ? ` (${k.interviews} interviews)` : ''}`,
    );
  }
  if (k.reference_checks > 0) parts.push('references checked');
  if (p.employment) parts.push(`${formatMonths(p.employment.tenure_months)} working together`);
  const text = parts.length ? parts.join('; ') : 'You know little about them yet';
  const tail = p.employment
    ? ' Ranges narrow each month they stay.'
    : ' Interviews and references narrow the ranges.';
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.${tail}`;
}

function ProfileBody({
  saveId,
  p,
  meta,
  hiring,
  overview,
}: {
  saveId: string;
  p: Profile;
  meta: NewGameMeta;
  hiring: HiringMeta;
  overview: Overview;
}) {
  const mission = overview.mission;
  const navigate = useNavigate();
  const fire = useFire(saveId);
  const [confirming, setConfirming] = useState(false);
  const label = (list: { key: string; label: string }[], key: string) =>
    list.find((x) => x.key === key)?.label ?? humanize(key);
  const emp = p.employment;
  const firstName = p.name.split(' ')[0];
  const backTo = p.candidacy ? 'recruitment' : 'people';
  const spark = p.morale_history.slice(-SPARK_MONTHS);

  return (
    <>
      <Link to={`/game/${saveId}/${backTo}`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← {p.candidacy ? 'Recruitment' : 'People'}
      </Link>
      <section
        className="tst-panel"
        aria-label="Summary"
        style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'center' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 260px' }}>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }} data-testid="profile-name">
            {p.name}
          </h1>
          <span style={{ fontSize: 14, color: 'var(--tst-text-2)' }}>
            {[
              p.role_label,
              p.level && humanize(p.level),
              `Age ${p.age}`,
              label(meta.regions, p.region),
            ]
              .filter(Boolean)
              .join(' · ')}{' '}
            {emp && <StatusChip status={statusOf(p)} />}
          </span>
          <UnitManagerLine saveId={saveId} p={p} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 28 }}>
          {emp && !p.is_founder && (
            <Stat label="Salary">
              <span className="tst-num">{formatMoneyWhole(emp.salary_cents)}</span>
            </Stat>
          )}
          {p.candidacy && (
            <Stat label="Asks">
              <span className="tst-num">
                {formatMoneyWhole(p.candidacy.salary_expectation_cents)}
              </span>
            </Stat>
          )}
          {emp && (
            <Stat label="Tenure">
              <span className="tst-num">{formatMonths(emp.tenure_months)}</span>
            </Stat>
          )}
          <Stat label="Potential">{p.potential_phrase}</Stat>
          {p.morale !== null && (
            <div style={{ minWidth: 160 }}>
              <div className="tst-muted" style={{ fontSize: 12 }}>
                Morale
              </div>
              <MoraleBar morale={p.morale} height={8} large />
            </div>
          )}
        </div>
        <PersonActions saveId={saveId} p={p} />
      </section>
      <MoraleBreakdownPanel saveId={saveId} p={p} overview={overview} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(260px, 100%), 1fr))',
          gap: 16,
        }}
      >
        {GROUPS.map(([group, title]) => (
          <AttrPanel key={group} title={title} attrs={p.skills.filter((s) => s.group === group)} />
        ))}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(260px, 100%), 1fr))',
          gap: 16,
        }}
      >
        <AttrPanel title="Personality" attrs={p.personality} />
        <section
          className="tst-panel"
          aria-label="Interests and traits"
          style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          <div>
            <h2 className="tst-ptitle">Interests</h2>
            {p.interests === null ? (
              <span className="tst-muted" style={{ fontSize: 13, fontStyle: 'italic' }}>
                Interview to learn
              </span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }} data-testid="interests">
                {p.interests.map((k) => (
                  <span key={k} className="tst-chip">
                    {label(meta.interests, k)}
                    {mission.includes(k) && (
                      <span style={{ color: 'var(--tst-good)' }}> ✓ mission</span>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div>
            <h2 className="tst-ptitle">Work style</h2>
            {p.work_style === null ? (
              <span className="tst-muted" style={{ fontSize: 13, fontStyle: 'italic' }}>
                Interview to learn
              </span>
            ) : (
              <>
                <span className="tst-chip">{label(meta.work_styles, p.work_style)}</span>{' '}
                {p.work_style_matches_role !== null && (
                  <span className="tst-muted" style={{ fontSize: 13 }}>
                    {p.work_style_matches_role ? 'matches their role' : 'differs from their role'}
                  </span>
                )}
              </>
            )}
          </div>
          <div>
            <h2 className="tst-ptitle">Noticed traits</h2>
            {p.noticed_tags.length === 0 ? (
              <span className="tst-muted" style={{ fontSize: 13 }}>
                Nothing noticed yet.
              </span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {p.noticed_tags.map((t) => (
                  <span
                    key={t.key}
                    className="tst-chip"
                    title={`${firstName} ${t.text}`}
                    style={{
                      background: 'var(--tst-gold-bg)',
                      borderColor: '#4A4520',
                      color: 'var(--tst-tier-4)',
                    }}
                  >
                    {t.label} · noticed {t.noticed_date_label}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div>
            <h2 className="tst-ptitle">How well you know them</h2>
            <p
              style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--tst-text-2)' }}
              data-testid="knowledge"
            >
              {knowledgeLine(p)}
            </p>
          </div>
        </section>

        <section
          className="tst-panel"
          aria-label="Contract and morale"
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          {emp ? (
            <>
              <h2 className="tst-ptitle" style={{ margin: 0 }}>
                Contract
              </h2>
              <Row label="Salary" value={p.is_founder ? '—' : formatMoneyWhole(emp.salary_cents)} />
              {emp.market_rate_cents !== null && (
                <Row label="Market rate" value={formatMoneyWhole(emp.market_rate_cents)} />
              )}
              <Row
                label="Equity"
                value={`${emp.equity_bp} bp (${formatBpPercent(emp.equity_bp)})`}
              />
              <Row label="Joined" value={emp.start_date_label} />
              {emp.end_date_label && <Row label="Leaves" value={emp.end_date_label} warn />}
              <Row
                label="Monthly cost"
                value={formatMoneyWhole(emp.monthly_cost_cents)}
                testId="monthly-cost"
              />
              {!p.is_founder && (
                <>
                  <h2 className="tst-ptitle" style={{ margin: '6px 0 0' }}>
                    Morale, last {SPARK_MONTHS} months
                  </h2>
                  {spark.length === 0 ? (
                    <span className="tst-muted" style={{ fontSize: 13 }}>
                      No month closed yet.
                    </span>
                  ) : (
                    <>
                      <div
                        role="img"
                        aria-label={`Morale from ${formatWhole(spark[0].morale)} in ${spark[0].date_label} to ${formatWhole(spark[spark.length - 1].morale)} in ${spark[spark.length - 1].date_label}`}
                      >
                        <ResponsiveContainer width="100%" height={60}>
                          <LineChart data={spark} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                            <YAxis hide domain={[0, 100]} />
                            <Line
                              dataKey="morale"
                              stroke="var(--tst-accent)"
                              strokeWidth={2}
                              dot={false}
                              isAnimationActive={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div
                        className="tst-num tst-muted"
                        style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}
                      >
                        <span>
                          {spark[0].date_label.split(' ')[0]} {formatWhole(spark[0].morale)}
                        </span>
                        <span>
                          {spark[spark.length - 1].date_label.split(' ')[0]}{' '}
                          {formatWhole(spark[spark.length - 1].morale)}
                        </span>
                      </div>
                    </>
                  )}
                  <Button
                    variant="default"
                    h={44}
                    mt={8}
                    styles={{
                      root: {
                        color: 'var(--tst-warn)',
                        borderColor: '#6A4426',
                        background: 'transparent',
                      },
                    }}
                    onClick={() => setConfirming(true)}
                    data-testid="fire"
                  >
                    Fire {firstName}…
                  </Button>
                  <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
                    Asks to confirm. Severance {formatMoneyWhole(emp.severance_cents)}; everyone
                    else&apos;s morale drops.
                  </p>
                </>
              )}
            </>
          ) : p.candidacy ? (
            <>
              <h2 className="tst-ptitle" style={{ margin: 0 }}>
                Candidacy
              </h2>
              <Row label="Asks" value={formatMoneyWhole(p.candidacy.salary_expectation_cents)} />
              <Row label="Found by" value={humanize(p.candidacy.channel)} />
              <Row label="Available until" value={p.candidacy.expires_date_label} />
              {p.candidacy.pending_offer && (
                <Row
                  label="Offer pending"
                  value={`${formatMoneyWhole(p.candidacy.pending_offer.salary_cents)} · answer in ${p.candidacy.pending_offer.answer_date_label}`}
                />
              )}
              <Button
                component={Link}
                to={`/game/${saveId}/recruitment?search=${p.candidacy.search_id}`}
                h={44}
              >
                Back to candidates
              </Button>
            </>
          ) : null}
        </section>
      </div>

      {emp && (
        <Modal
          opened={confirming}
          onClose={() => setConfirming(false)}
          title={`Fire ${p.name}?`}
          centered
        >
          <p
            style={{ marginTop: 0, fontSize: 14, lineHeight: 1.5 }}
            data-testid="fire-confirm-text"
          >
            {p.name} leaves today. Severance of{' '}
            <span className="tst-num">{formatMoneyWhole(emp.severance_cents)}</span> is paid at
            once, and everyone else&apos;s morale will drop by at least{' '}
            {hiring.fire_morale_penalty_min} points.
          </p>
          {fire.error && (
            <Alert color="red" mb="sm" title="Could not fire">
              {fire.error.message}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" h={44} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              color="warn"
              h={44}
              loading={fire.isPending}
              data-testid="fire-confirm"
              onClick={
                () =>
                  void fire
                    .mutateAsync(p.person_id)
                    .then(() => navigate(`/game/${saveId}/people`))
                    .catch(() => undefined) // the error shows in the dialog
              }
            >
              Fire {firstName}
            </Button>
          </Group>
        </Modal>
      )}
    </>
  );
}

function Row({
  label,
  value,
  warn,
  testId,
}: {
  label: string;
  value: string;
  warn?: boolean;
  testId?: string;
}) {
  return (
    <div className="tst-row">
      <span style={{ color: 'var(--tst-text-2)' }}>{label}</span>
      <span
        className="tst-num"
        style={{ color: warn ? 'var(--tst-warn)' : undefined }}
        data-testid={testId}
      >
        {value}
      </span>
    </div>
  );
}
