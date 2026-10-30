import { Button, NumberInput, SegmentedControl, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useParams } from 'react-router';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import { useLlmSettings, useSaves, useUpdateLlmSettings, type LlmSettings } from '../hooks/api';
import { formatMoney } from '../lib/format';

/** Settings (M6 wireframe): AI writing (Claude or offline templates, this calendar month's
 * spend against the budget, the budget, the model ids, three counts, and what Claude can
 * and cannot see) and the game's difficulty. Never shows the API key. */
export function SettingsScreen() {
  const { saveId = '' } = useParams();
  const settings = useLlmSettings();
  const saves = useSaves();
  if (settings.isPending) return <Loading />;
  if (settings.error) return <LoadError title="Could not load settings" error={settings.error} />;
  const save = saves.data?.find((x) => x.save_id === saveId);
  return (
    <>
      <ScreenTitle>Settings</ScreenTitle>
      <AiWriting
        key={`${settings.data.adapter}-${settings.data.budget_cents}-${settings.data.model_events}-${settings.data.model_story}`}
        s={settings.data}
      />
      <section
        className="tst-panel"
        style={{ padding: '20px 24px', maxWidth: 760, marginTop: 16 }}
        aria-label="Game"
      >
        <h2 className="tst-ptitle" style={{ marginTop: 0 }}>
          Game
        </h2>
        <p style={{ margin: 0, fontSize: 14 }}>
          Difficulty: <strong>{save ? save.difficulty : '…'}</strong>. Saves are kept in the saves
          folder next to the game, one file per company.
        </p>
      </section>
    </>
  );
}

/** The AI writing form, seeded from the saved settings (re-keyed when they change). */
function AiWriting({ s }: { s: LlmSettings }) {
  const update = useUpdateLlmSettings();
  const [adapter, setAdapter] = useState(s.adapter);
  const [budget, setBudget] = useState(s.budget_cents);
  const [modelEvents, setModelEvents] = useState(s.model_events);
  const [modelStory, setModelStory] = useState(s.model_story);
  const pct = s.budget_cents > 0 ? Math.min(100, (s.spend_cents / s.budget_cents) * 100) : 100;
  const dirty =
    adapter !== s.adapter ||
    budget !== s.budget_cents ||
    modelEvents !== s.model_events ||
    modelStory !== s.model_story;

  return (
    <section
      className="tst-panel"
      style={{ padding: '20px 24px', maxWidth: 760 }}
      aria-label="AI writing"
    >
      <h2 className="tst-ptitle" style={{ marginTop: 0 }}>
        AI writing
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <SegmentedControl
            value={adapter}
            onChange={setAdapter}
            data={[
              { value: 'claude', label: 'Claude' },
              { value: 'templates', label: 'Offline templates' },
            ]}
            data-testid="adapter-choice"
          />
          <div className="tst-muted" style={{ fontSize: 13, marginTop: 6 }} data-testid="key-found">
            {s.key_found ? 'API key found.' : 'No API key found: events use templates.'} In use now:{' '}
            <strong data-testid="adapter-in-use">{s.in_use}</strong>.
          </div>
        </div>
        <div>
          <div style={{ fontSize: 13, marginBottom: 4 }} data-testid="ai-spend">
            {formatMoney(Math.round(s.spend_cents))} of {formatMoney(s.budget_cents)} this calendar
            month · {s.calls} calls · resets {s.reset_date}
          </div>
          <div
            role="meter"
            aria-label="AI spend this month"
            aria-valuemin={0}
            aria-valuemax={s.budget_cents}
            aria-valuenow={Math.round(s.spend_cents)}
            style={{ height: 8, background: 'var(--tst-track)', borderRadius: 4 }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: 8,
                borderRadius: 4,
                background: pct >= 100 ? 'var(--tst-warn)' : 'var(--tst-accent)',
              }}
            />
          </div>
        </div>
        <NumberInput
          label="Monthly budget (dollars; 0 plays offline)"
          min={0}
          max={1000}
          decimalScale={2}
          value={budget / 100}
          onChange={(v) => setBudget(Math.round(Number(v || 0) * 100))}
          style={{ maxWidth: 240 }}
          data-testid="budget-input"
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          <TextInput
            label="Model for events, headlines and minutes"
            value={modelEvents}
            onChange={(e) => setModelEvents(e.currentTarget.value)}
            style={{ flex: '1 1 240px' }}
          />
          <TextInput
            label="Model for storylines"
            value={modelStory}
            onChange={(e) => setModelStory(e.currentTarget.value)}
            style={{ flex: '1 1 240px' }}
          />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, fontSize: 13 }}>
          <span>
            Events written by Claude: <span className="tst-num">{s.events_by_claude}</span>
          </span>
          <span>
            Rejected drafts replaced by templates:{' '}
            <span className="tst-num">{s.rejected_drafts}</span>
          </span>
          <span>
            Average cost per event:{' '}
            <span className="tst-num">
              {s.average_cost_cents === null ? '—' : `${s.average_cost_cents.toFixed(2)}¢`}
            </span>
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, fontSize: 13 }}>
          <div style={{ flex: '1 1 300px' }}>
            <strong>Claude can see</strong>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {s.can_see.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          <div style={{ flex: '1 1 300px' }}>
            <strong>Claude cannot see</strong>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {s.cannot_see.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </div>
        <div>
          <Button
            h={44}
            disabled={!dirty || modelEvents === '' || modelStory === ''}
            loading={update.isPending}
            onClick={() =>
              update.mutate({
                adapter,
                monthly_budget_cents: budget,
                model_events: modelEvents,
                model_story: modelStory,
              })
            }
            data-testid="save-settings"
          >
            Save
          </Button>
          {update.error && (
            <span role="alert" style={{ color: 'var(--tst-warn)', marginLeft: 12 }}>
              {update.error.message}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
