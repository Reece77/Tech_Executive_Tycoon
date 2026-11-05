import { Alert, Button, Checkbox, Modal, NumberInput, SegmentedControl } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  useHoliday,
  useScaleup,
  useScaleupAction,
  useStartHoliday,
  useStopHoliday,
  type Holiday,
} from '../hooks/api';
import { formatMoneyWhole } from '../lib/format';
import { Term } from './Term';

// Holiday (formulas.md 17.1): the dialog, and the strip under the top bar while it runs and
// once it ends. Every number here comes from the API's holiday job.

const STOP_LABELS: Record<string, string> = {
  minor: 'Any event',
  major: 'Major and critical',
  critical: 'Critical only',
};

function alwaysStops(h: Holiday): string[] {
  return [
    'the game ends',
    'a critical event arrives',
    `runway falls below ${h.stop_runway_months} months (or below 3)`,
    'a term sheet, SAFE or bridge offer arrives',
  ];
}

export function HolidayDialog({
  saveId,
  holiday,
  onClose,
}: {
  saveId: string;
  holiday: Holiday;
  onClose: () => void;
}) {
  const [months, setMonths] = useState<number>(holiday.default_months);
  const [stop, setStop] = useState<string>(holiday.default_stop);
  const start = useStartHoliday(saveId);
  const valid = Number.isInteger(months) && months >= 1 && months <= holiday.max_months;
  // Executives' pitches (27.1, M13b): under the limit they go ahead while you are away.
  const scaleup = useScaleup(saveId);
  const policy = scaleup.data?.pitch_policy;
  const setPolicy = useScaleupAction(saveId);
  const [useDefault, setUseDefault] = useState<boolean | null>(null);
  const [dollars, setDollars] = useState<number | null>(null);
  const [stopBig, setStopBig] = useState<boolean | null>(null);
  const isDefault = useDefault ?? policy?.auto_approve_cents === null;
  const limitDollars = dollars ?? Math.round((policy?.limit_cents ?? 0) / 100);
  const stopForBig = stopBig ?? policy?.stop_for_big ?? false;
  const go = () => {
    const begin = () =>
      start.mutate(
        { months, stop: stop as 'minor' | 'major' | 'critical' },
        { onSuccess: onClose },
      );
    if (!policy) return begin();
    const cents = isDefault ? null : Math.max(0, Math.round(limitDollars * 100));
    if (cents === policy.auto_approve_cents && stopForBig === policy.stop_for_big) return begin();
    setPolicy.mutate(
      { action: 'pitch_policy', auto_approve_cents: cents, stop_for_big: stopForBig },
      { onSuccess: begin },
    );
  };
  return (
    <Modal opened onClose={onClose} title="Go on holiday" centered>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          Months pass one Continue at a time. Your delegates keep acting; you take no actions, and
          minor or major events below your stop level resolve to their first choice.
        </p>
        <NumberInput
          label={`Months (1–${holiday.max_months})`}
          min={1}
          max={holiday.max_months}
          value={months}
          onChange={(v) => setMonths(typeof v === 'number' ? v : Number(v))}
          data-testid="holiday-months"
        />
        <div>
          <div style={{ fontSize: 13, marginBottom: 6 }}>Stop after</div>
          <SegmentedControl
            fullWidth
            value={stop}
            onChange={setStop}
            data={Object.entries(STOP_LABELS).map(([value, label]) => ({ value, label }))}
            data-testid="holiday-stop"
          />
        </div>
        <div style={{ fontSize: 13 }}>
          <span className="tst-muted">It always stops when </span>
          {alwaysStops(holiday).join('; ')}.
        </div>
        {policy && (
          <div
            data-testid="holiday-pitches"
            style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
          >
            <div style={{ fontSize: 13 }}>
              <Term term="exec.auto_approve">Executives&apos; pitches</Term> costing less than this
              over 12 months go ahead while you are away; bigger ones wait.
            </div>
            <Checkbox
              label={`5% of cash (now ${formatMoneyWhole(policy.default_cents)})`}
              checked={isDefault}
              onChange={(e) => setUseDefault(e.currentTarget.checked)}
              data-testid="pitch-limit-default"
            />
            {!isDefault && (
              <NumberInput
                label="Auto-approve limit, $ (0: always ask)"
                min={0}
                value={limitDollars}
                onChange={(v) => setDollars(typeof v === 'number' ? v : Number(v) || 0)}
                data-testid="pitch-limit"
              />
            )}
            <Checkbox
              label="Stop the holiday for a pitch above the limit"
              checked={stopForBig}
              onChange={(e) => setStopBig(e.currentTarget.checked)}
              data-testid="pitch-stop-big"
            />
          </div>
        )}
        {setPolicy.error && <Alert color="red">{setPolicy.error.message}</Alert>}
        {start.error && (
          <Alert color="red" title="Holiday did not start">
            {start.error.message}
          </Alert>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="default" h={44} onClick={onClose}>
            Cancel
          </Button>
          <Button
            h={44}
            disabled={!valid || start.isPending || setPolicy.isPending}
            onClick={go}
            data-testid="holiday-start"
          >
            Start holiday
          </Button>
        </div>
      </div>
    </Modal>
  );
}

const STRIP = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: 16,
  padding: '8px 20px',
  background: 'var(--tst-panel-active)',
  borderBottom: '1px solid var(--tst-border)',
  fontSize: 13,
} as const;

/** Under the top bar: progress while a holiday runs, then why it stopped. */
export function HolidayStrip({ saveId }: { saveId: string }) {
  const holiday = useHoliday(saveId);
  const stop = useStopHoliday(saveId);
  const [dismissed, setDismissed] = useState<number | null>(null);
  const h = holiday.data;
  if (!h || h.status === 'idle') return null;
  if (h.status === 'running') {
    const pct = h.months > 0 ? Math.round((h.months_done / h.months) * 100) : 0;
    return (
      <div style={STRIP} role="status" data-testid="holiday-strip">
        <strong>On holiday</strong>
        <span className="tst-num" data-testid="holiday-progress">
          Month {Math.min(h.months_done + 1, h.months)} of {h.months} · {h.date_label}
        </span>
        <div
          role="progressbar"
          aria-label="Holiday progress"
          aria-valuemin={0}
          aria-valuemax={h.months}
          aria-valuenow={h.months_done}
          style={{ width: 160, height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: 6,
              background: 'var(--tst-accent)',
              borderRadius: 3,
            }}
          />
        </div>
        <span className="tst-muted">
          Stops after: {STOP_LABELS[h.stop ?? 'major']?.toLowerCase()}, short runway or an offer
        </span>
        <Button
          variant="default"
          size="xs"
          h={32}
          style={{ marginLeft: 'auto' }}
          disabled={h.stop_requested || stop.isPending}
          onClick={() => stop.mutate()}
          data-testid="holiday-stop-button"
        >
          {h.stop_requested ? 'Stopping after this month…' : 'Stop after this month'}
        </Button>
      </div>
    );
  }
  const key = h.summary_item_id ?? -1;
  if (dismissed === key) return null;
  return (
    <div style={STRIP} role="status" data-testid="holiday-done">
      {h.status === 'failed' ? (
        <span style={{ color: 'var(--tst-warn)' }}>
          Holiday stopped after {h.months_done} month{h.months_done === 1 ? '' : 's'}: {h.error}
        </span>
      ) : (
        <span>
          Back from holiday after {h.months_done} month{h.months_done === 1 ? '' : 's'}: stopped
          because {h.reason_text}.
        </span>
      )}
      {h.summary_item_id != null && (
        <Link to={`/game/${saveId}/inbox/${h.summary_item_id}`} data-testid="holiday-summary-link">
          While you were away
        </Link>
      )}
      <Button
        variant="subtle"
        size="xs"
        style={{ marginLeft: 'auto' }}
        onClick={() => setDismissed(key)}
      >
        Dismiss
      </Button>
    </div>
  );
}
