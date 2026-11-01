import {
  Alert,
  Button,
  Collapse,
  NumberInput,
  Select,
  TextInput,
  UnstyledButton,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { LoadError, Loading } from '../components/ScreenState';
import {
  useCreateSave,
  useFounderPreview,
  useNewGameMeta,
  useScenarios,
  type FounderIn,
  type NewGameMeta,
  type Scenario,
} from '../hooks/api';
import { attributeTier } from '../lib/attr';
import { formatMoneyWhole, humanize } from '../lib/format';
import { toSaveSlug } from '../lib/slug';

const SEED_RE = /^\d*$/;
const SURPRISE = 'surprise';
const PREVIEW_DEBOUNCE_MS = 250;
const GROUPS = ['technical', 'business', 'leadership'] as const;

function Step({
  n,
  title,
  aside,
  children,
}: {
  n: number;
  title: string;
  aside?: string;
  children: ReactNode;
}) {
  return (
    <section
      className="tst-panel"
      aria-label={title}
      style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}
    >
      <h2
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 10,
          margin: 0,
          fontSize: 18,
          fontWeight: 600,
        }}
      >
        <span className="tst-key" style={{ fontSize: 12, padding: '1px 6px' }}>
          {n}
        </span>
        {title}
        {aside && (
          <span className="tst-muted" style={{ fontSize: 13, fontWeight: 400 }}>
            {aside}
          </span>
        )}
      </h2>
      {children}
    </section>
  );
}

function CardGrid({ min, children, label }: { min: number; children: ReactNode; label?: string }) {
  return (
    <div
      role={label ? 'group' : undefined}
      aria-label={label}
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))`,
        gap: 10,
      }}
    >
      {children}
    </div>
  );
}

export function NewGameScreen() {
  const meta = useNewGameMeta();
  const scenarios = useScenarios();
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 16,
          padding: '16px 24px',
          background: 'var(--tst-panel)',
          borderBottom: '1px solid var(--tst-border)',
        }}
      >
        <span style={{ fontSize: 16, fontWeight: 700 }}>Tech Startup Tycoon</span>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          New game · January 2010
        </span>
        <Link to="/" style={{ marginLeft: 'auto', fontSize: 14, textDecoration: 'none' }}>
          ← Saved games
        </Link>
      </header>
      <main
        style={{
          width: '100%',
          maxWidth: 1180,
          margin: '0 auto',
          boxSizing: 'border-box',
          padding: '24px 16px 48px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {meta.error || scenarios.error ? (
          <LoadError
            title="Could not load the setup options"
            error={meta.error ?? scenarios.error}
          />
        ) : meta.isPending || scenarios.isPending ? (
          <Loading />
        ) : (
          <SetupForm meta={meta.data} scenarios={scenarios.data} />
        )}
      </main>
    </div>
  );
}

function SetupForm({ meta, scenarios }: { meta: NewGameMeta; scenarios: Scenario[] }) {
  const navigate = useNavigate();
  const create = useCreateSave();
  const rules = meta.founder_rules;
  const firstBackground = meta.backgrounds.find((b) => b.selectable) ?? meta.backgrounds[0];

  const [companyName, setCompanyName] = useState('');
  const [difficulty, setDifficulty] = useState('standard');
  const [scenario, setScenario] = useState(scenarios.find((s) => s.selectable)?.id ?? '');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [age, setAge] = useState<number>(rules.default_age);
  const [background, setBackground] = useState(firstBackground.key);
  const [allocation, setAllocation] = useState<Record<string, number>>(
    firstBackground.default_allocation,
  );
  const [preset, setPreset] = useState(meta.personality_presets[0]?.key ?? SURPRISE);
  const [mission, setMission] = useState<string[]>([]);
  const [hq, setHq] = useState<string | null>(meta.default_hq_city ?? null); // M9
  const [seed, setSeed] = useState('');
  const [showSeed, setShowSeed] = useState(false);

  const backgroundDef = meta.backgrounds.find((b) => b.key === background) ?? firstBackground;
  const skillLabel = useMemo(
    () => new Map(meta.skills.map((s) => [s.key, s.label])),
    [meta.skills],
  );

  const founder: FounderIn = useMemo(
    () => ({
      background,
      allocation,
      age,
      first_name: firstName.trim() || null,
      last_name: lastName.trim() || null,
      personality_preset: preset === SURPRISE ? null : preset,
    }),
    [background, allocation, age, firstName, lastName, preset],
  );
  const [debounced] = useDebouncedValue(founder, PREVIEW_DEBOUNCE_MS);
  const preview = useFounderPreview(debounced);
  const previewCurrent = debounced === founder && !preview.isFetching && !preview.isPlaceholderData;
  const values = new Map(preview.data?.skills.map((s) => [s.key, s.value]));

  const slug = toSaveSlug(companyName);
  const seedValid = SEED_RE.test(seed) && (seed === '' || Number.isSafeInteger(Number(seed)));
  const founderOk =
    previewCurrent && preview.data !== undefined && preview.data.errors.length === 0;
  // No mission is allowed: the API then uses the founder's first two interests.
  const missionOk = mission.length === 0 || mission.length === rules.mission_size;
  const canStart =
    slug !== '' && scenario !== '' && seedValid && founderOk && missionOk && !create.isPending;

  const chooseBackground = (key: string) => {
    const def = meta.backgrounds.find((b) => b.key === key);
    if (!def?.selectable) return;
    setBackground(key);
    setAllocation(def.default_allocation);
  };
  const step = (key: string, delta: number) =>
    setAllocation((a) => {
      const next = { ...a, [key]: Math.max(0, (a[key] ?? 0) + delta) };
      return Object.fromEntries(Object.entries(next).filter(([, points]) => points > 0));
    });
  const toggleInterest = (key: string) =>
    setMission((m) =>
      m.includes(key)
        ? m.filter((k) => k !== key)
        : m.length < rules.mission_size
          ? [...m, key]
          : m,
    );

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!canStart) return;
    create.mutate(
      {
        name: slug,
        company_name: companyName.trim(),
        scenario,
        difficulty,
        seed: seed === '' ? null : Number(seed),
        founder,
        mission: mission.length ? mission : null,
        hq_city: hq,
      },
      { onSuccess: (save) => void navigate(`/game/${save.save_id}`) },
    );
  };

  const interestLabel = new Map(meta.interests.map((i) => [i.key, i.label]));
  const summary = [
    companyName.trim() || 'Unnamed company',
    scenarios.find((s) => s.id === scenario)?.name,
    humanize(difficulty),
    backgroundDef.label,
    preset === SURPRISE
      ? 'Surprise personality'
      : meta.personality_presets.find((p) => p.key === preset)?.label,
    mission.length
      ? mission.map((k) => interestLabel.get(k)).join(' and ')
      : "mission: your founder's interests",
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Step n={1} title="Company">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          <TextInput
            style={{ flex: '1 1 260px' }}
            label="Company name"
            value={companyName}
            onChange={(e) => setCompanyName(e.currentTarget.value)}
            description={slug ? `Save file: ${slug}` : undefined}
            maxLength={80}
            required
            data-testid="company-name-input"
          />
          <fieldset style={{ flex: '1 1 360px', border: 0, margin: 0, padding: 0 }}>
            <legend style={{ fontSize: 14, fontWeight: 500, paddingBottom: 4 }}>Difficulty</legend>
            <div
              role="group"
              style={{
                display: 'flex',
                border: '1px solid var(--tst-border)',
                borderRadius: 6,
                overflow: 'hidden',
              }}
            >
              {meta.difficulties.map((d, i) => (
                <UnstyledButton
                  key={d}
                  type="button"
                  aria-pressed={difficulty === d}
                  onClick={() => setDifficulty(d)}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    fontSize: 13,
                    padding: 10,
                    minHeight: 40,
                    color: difficulty === d ? 'var(--tst-text)' : 'var(--tst-text-2)',
                    background: difficulty === d ? 'var(--tst-panel-active)' : 'transparent',
                    borderLeft: i ? '1px solid var(--tst-border)' : 0,
                  }}
                >
                  {humanize(d)}
                </UnstyledButton>
              ))}
            </div>
          </fieldset>
        </div>
        <CardGrid min={220} label="Scenario">
          {scenarios.map((s) => (
            <button
              key={s.id}
              type="button"
              className="tst-card"
              aria-pressed={scenario === s.id}
              disabled={!s.selectable}
              onClick={() => setScenario(s.id)}
              data-testid={`scenario-${s.id}`}
            >
              <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontWeight: 600 }}>{s.name}</span>
                <span className="tst-num" style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>
                  {formatMoneyWhole(
                    s.starting_cash_by_difficulty[difficulty] ?? s.starting_cash_cents,
                  )}
                </span>
              </span>
              <span className="tst-muted" style={{ fontSize: 13, lineHeight: 1.45 }}>
                {s.selectable ? s.description : `Unlocks in ${s.available_in}.`}
              </span>
            </button>
          ))}
        </CardGrid>
        <UnstyledButton
          type="button"
          onClick={() => setShowSeed((v) => !v)}
          style={{ fontSize: 13, color: 'var(--tst-link)', alignSelf: 'flex-start' }}
          aria-expanded={showSeed}
        >
          {showSeed ? 'Hide seed' : 'Set a seed (optional)'}
        </UnstyledButton>
        <Collapse expanded={showSeed}>
          <TextInput
            label="Seed"
            value={seed}
            maw={320}
            onChange={(e) => setSeed(e.currentTarget.value.trim())}
            error={seedValid ? undefined : 'Whole number up to 9007199254740991'}
            description="Leave blank for a random game; reuse a seed to replay the same world."
            data-testid="seed-input"
          />
        </Collapse>
      </Step>

      <Step n={2} title="Founder">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          <TextInput
            style={{ flex: '1 1 200px' }}
            label="First name"
            placeholder="Leave blank to draw one"
            value={firstName}
            onChange={(e) => setFirstName(e.currentTarget.value)}
            data-testid="first-name"
          />
          <TextInput
            style={{ flex: '1 1 200px' }}
            label="Last name"
            placeholder="Leave blank to draw one"
            value={lastName}
            onChange={(e) => setLastName(e.currentTarget.value)}
            data-testid="last-name"
          />
          <NumberInput
            style={{ flex: '0 1 120px' }}
            label="Age"
            value={age}
            min={rules.age_min}
            max={rules.age_max}
            allowDecimal={false}
            onChange={(v) => setAge(typeof v === 'number' ? v : rules.default_age)}
            classNames={{ input: 'tst-num' }}
            data-testid="age"
          />
        </div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>Background</div>
        <CardGrid min={200} label="Background">
          {meta.backgrounds.map((b) => (
            <button
              key={b.key}
              type="button"
              className="tst-card"
              aria-pressed={background === b.key}
              disabled={!b.selectable}
              onClick={() => chooseBackground(b.key)}
              data-testid={`background-${b.key}`}
            >
              <span style={{ fontWeight: 600 }}>{b.label}</span>
              <span className="tst-muted" style={{ fontSize: 12, lineHeight: 1.45 }}>
                {b.description}
                {!b.selectable && ` Unlocks in ${b.available_in}.`}
              </span>
              <span
                className="tst-num"
                style={{ fontSize: 12, color: 'var(--tst-good)', whiteSpace: 'normal' }}
              >
                {Object.entries(b.bonuses)
                  .map(([k, v]) => `+${v} ${skillLabel.get(k) ?? k}`)
                  .join(' · ')}
              </span>
            </button>
          ))}
        </CardGrid>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 12,
            paddingTop: 4,
          }}
        >
          <span style={{ fontSize: 13, color: 'var(--tst-text-2)' }}>
            Skills: every skill starts at {rules.skill_base}; spend {rules.skill_points} points; no
            skill above {rules.skill_cap}.
          </span>
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span
              className="tst-num"
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: preview.data?.points_remaining === 0 ? 'var(--tst-good)' : 'var(--tst-warn)',
              }}
              data-testid="points-left"
            >
              {preview.data?.points_remaining ?? '…'}
            </span>
            <span className="tst-muted" style={{ fontSize: 13 }}>
              of {rules.skill_points} points left
            </span>
          </span>
          <Button
            variant="default"
            size="sm"
            onClick={() => setAllocation(backgroundDef.default_allocation)}
            data-testid="reset-skills"
          >
            Reset to {backgroundDef.label} default
          </Button>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))',
            gap: 16,
          }}
        >
          {GROUPS.map((group) => (
            <div key={group} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div className="tst-ptitle" style={{ margin: 0, paddingBottom: 6 }}>
                {humanize(group)}
              </div>
              {meta.skills
                .filter((s) => s.group === group)
                .map((s) => {
                  const bonus = backgroundDef.bonuses[s.key];
                  const value = values.get(s.key);
                  return (
                    <div
                      key={s.key}
                      data-testid={`skill-${s.key}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '4px 0',
                        borderBottom: '1px solid var(--tst-rule)',
                        fontSize: 14,
                      }}
                    >
                      <span style={{ flex: 1, color: 'var(--tst-text-2)' }}>{s.label}</span>
                      <span
                        className="tst-num"
                        style={{
                          fontSize: 11,
                          color: 'var(--tst-good)',
                          width: 22,
                          textAlign: 'right',
                        }}
                      >
                        {bonus ? `+${bonus}` : ''}
                      </span>
                      <StepButton
                        label={`Remove a point from ${s.label}`}
                        onClick={() => step(s.key, -1)}
                        disabled={!allocation[s.key]}
                      >
                        −
                      </StepButton>
                      <span
                        className={`tst-num ${value === undefined ? 'tst-muted' : `tst-tier-${attributeTier({ min: value, max: value })}`}`}
                        style={{ width: 28, textAlign: 'center' }}
                        data-testid={`skill-value-${s.key}`}
                      >
                        {value === undefined ? '…' : Math.round(value)}
                      </span>
                      <StepButton
                        label={`Add a point to ${s.label}`}
                        onClick={() => step(s.key, 1)}
                      >
                        +
                      </StepButton>
                    </div>
                  );
                })}
            </div>
          ))}
        </div>
        {preview.data && preview.data.errors.length > 0 && (
          <Alert color="warn" title="Founder build" data-testid="founder-errors">
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {preview.data.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </Alert>
        )}
        {preview.error && (
          <LoadError title="Could not check the founder build" error={preview.error} />
        )}
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          Green numbers are your background&apos;s bonus. Values and points come from the server as
          you edit; your ability and potential stay hidden, as for everyone else.
        </p>
      </Step>

      <Step n={3} title="Personality">
        <CardGrid min={200} label="Personality">
          {[
            ...meta.personality_presets.map((p) => ({
              key: p.key,
              label: p.label,
              text: p.description,
            })),
            {
              key: SURPRISE,
              label: 'Surprise me',
              text: 'Random traits; you see them once the game starts.',
            },
          ].map((p) => (
            <button
              key={p.key}
              type="button"
              className="tst-card"
              aria-pressed={preset === p.key}
              onClick={() => setPreset(p.key)}
              data-testid={`preset-${p.key}`}
            >
              <span style={{ fontWeight: 600 }}>{p.label}</span>
              <span className="tst-muted" style={{ fontSize: 12, lineHeight: 1.45 }}>
                {p.text}
              </span>
            </button>
          ))}
        </CardGrid>
      </Step>

      <Step
        n={4}
        title="Mission"
        aside={`choose ${rules.mission_size} · people who share them are happier and easier to hire`}
      >
        <div
          role="group"
          aria-label="Mission interests"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}
        >
          {meta.interests.map((i) => {
            const on = mission.includes(i.key);
            return (
              <button
                key={i.key}
                type="button"
                aria-pressed={on}
                onClick={() => toggleInterest(i.key)}
                data-testid={`interest-${i.key}`}
                style={{
                  fontFamily: 'inherit',
                  fontSize: 13,
                  borderRadius: 16,
                  padding: '8px 14px',
                  minHeight: 36,
                  cursor: 'pointer',
                  color: on ? 'var(--tst-bg)' : 'var(--tst-text-2)',
                  background: on ? 'var(--tst-accent)' : 'transparent',
                  border: `1px solid ${on ? 'var(--tst-accent)' : 'var(--tst-border)'}`,
                  fontWeight: on ? 600 : 400,
                }}
              >
                {i.label}
              </button>
            );
          })}
        </div>
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }} data-testid="mission-note">
          {mission.length === 0
            ? "Optional: with none chosen, the mission is your founder's first two interests."
            : mission.length < rules.mission_size
              ? `Choose ${rules.mission_size - mission.length} more, or clear your choice to use your founder's interests.`
              : 'Click a chosen interest to swap it.'}
        </p>
      </Step>

      {(meta.cities ?? []).length > 0 && (
        <Step n={5} title="Headquarters" aside="your home market is the HQ city's region">
          <Select
            label="HQ city"
            data-testid="hq-city"
            data={(meta.cities ?? []).map((c) => ({ value: c.key, label: c.label }))}
            value={hq}
            onChange={setHq}
            allowDeselect={false}
            style={{ maxWidth: 360 }}
          />
        </Step>
      )}

      {create.error && (
        <Alert color="red" title="Could not create the game" role="alert">
          {create.error.message}
        </Alert>
      )}
      <div
        style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 16, paddingTop: 4 }}
      >
        <span style={{ fontSize: 14, color: 'var(--tst-text-2)' }} data-testid="setup-summary">
          {summary}
        </span>
        <Button
          type="submit"
          size="lg"
          h={48}
          px={32}
          ml="auto"
          disabled={!canStart}
          loading={create.isPending}
          data-testid="start-game"
        >
          Start in January 2010
        </Button>
      </div>
    </form>
  );
}

function StepButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="tst-num"
      style={{
        fontSize: 14,
        color: 'var(--tst-text)',
        background: 'var(--tst-panel-active)',
        border: '1px solid var(--tst-border)',
        borderRadius: 5,
        width: 28,
        height: 28,
        padding: 0,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  );
}
