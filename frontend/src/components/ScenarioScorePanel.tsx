// The result screen's score breakdown (M51, formulas.md 63.3): the company score at the verdict
// in its five parts, the challenge rules' multipliers, the score they give, and the player's
// best in this scenario from other saves. Every number comes from the API.
import type { GameOver } from '../hooks/api';
import type { ScenarioResult } from '../hooks/scenarios';
import { formatRatio } from '../lib/format';
import { Term } from './Term';

const PARTS: [keyof NonNullable<ScenarioResult['parts']>, string][] = [
  ['value', 'Value'],
  ['growth', 'Growth'],
  ['profit', 'Profit'],
  ['leadership', 'Leadership'],
  ['reputation', 'Reputation'],
];

export function ScenarioScorePanel({ g }: { g: GameOver }) {
  const mine = g.scenario_score;
  if (!mine) return null;
  const best = g.scenario_best;
  return (
    <div className="tst-card" data-testid="scenario-score" style={{ display: 'grid', gap: 8 }}>
      <span style={{ fontWeight: 600 }}>
        <Term term="kpi.company_score">Company score</Term>: {mine.score}
        {mine.challenges.length > 0 && (
          <>
            {' '}
            × {formatRatio(mine.score_mult)} for {mine.challenges.length} challenge
            {mine.challenges.length === 1 ? '' : 's'} ={' '}
            <span data-testid="scenario-adjusted">{mine.adjusted}</span>
          </>
        )}
      </span>
      {mine.parts && (
        <div className="tst-muted" style={{ fontSize: 13 }} data-testid="scenario-parts">
          {PARTS.map(([key, label]) => `${label} ${Math.round(mine.parts?.[key] ?? 0)}`).join(
            ' · ',
          )}
        </div>
      )}
      <div style={{ fontSize: 13 }} data-testid="scenario-compare">
        {best
          ? `Your best before this: ${best.result === 'success' ? 'won' : 'lost'} with ${best.adjusted} (${best.company}, ${best.date_label}).`
          : 'Your first result in this scenario.'}
      </div>
    </div>
  );
}
