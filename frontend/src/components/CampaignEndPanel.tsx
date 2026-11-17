// M37 (52.1): at a standard campaign's end, December 2039: end it, or continue in dynasty
// mode to December 2069 as the same company and family.
import { Button } from '@mantine/core';
import { useNavigate } from 'react-router';
import type { GameOver } from '../hooks/api';
import { useContinueDynasty, useEndCampaign } from '../hooks/campaign';

export function CampaignEndPanel({ saveId, over }: { saveId: string; over: GameOver }) {
  const navigate = useNavigate();
  const go = useContinueDynasty(saveId);
  const end = useEndCampaign(saveId);
  const error = go.error ?? end.error;
  return (
    <section className="tst-panel" aria-label="The campaign's end" data-testid="campaign-end">
      <h2 className="tst-ptitle">Thirty years on</h2>
      <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--tst-text-2)' }}>
        The standard campaign ends here, in December 2039, and your legacy goes into the Hall of
        Fame. Or play on in dynasty mode to December 2069: new eras, slowing chips, rivals&apos;
        founders handing over, and your own succession.
      </p>
      {over.dynasty_score !== null && over.dynasty_score !== undefined && (
        <p
          className="tst-num"
          style={{ margin: '0 0 12px', fontSize: 14 }}
          data-testid="dynasty-score"
        >
          Dynasty score {over.dynasty_score}
        </p>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <Button
          disabled={go.isPending || end.isPending}
          onClick={() =>
            go.mutate(undefined, { onSuccess: () => void navigate(`/game/${saveId}/overview`) })
          }
          data-testid="continue-dynasty"
        >
          Continue in dynasty mode
        </Button>
        <Button
          variant="default"
          disabled={go.isPending || end.isPending}
          onClick={() => end.mutate()}
          data-testid="end-campaign"
        >
          End the campaign
        </Button>
      </div>
      {error && (
        <p style={{ margin: '8px 0 0', color: 'var(--tst-warn)', fontSize: 13 }}>{error.message}</p>
      )}
    </section>
  );
}
