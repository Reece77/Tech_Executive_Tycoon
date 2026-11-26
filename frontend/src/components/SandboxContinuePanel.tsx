// M52 (formulas.md 66.3): after December 2069, play on in sandbox with no end. The score is still
// shown, kept out of comparisons, as a Sandbox's.
import { Button } from '@mantine/core';
import { useNavigate } from 'react-router';
import { useContinueSandbox } from '../hooks/editor';

export function SandboxContinuePanel({ saveId }: { saveId: string }) {
  const navigate = useNavigate();
  const go = useContinueSandbox(saveId);
  return (
    <section className="tst-panel" aria-label="Continue in sandbox" data-testid="sandbox-continue">
      <h2 className="tst-ptitle">Play on</h2>
      <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--tst-text-2)' }}>
        Continue in sandbox with no end date: new eras, slowing chips and rivals that keep handing
        over. The company score is still shown but kept out of comparisons.
      </p>
      <Button
        disabled={go.isPending}
        onClick={() =>
          go.mutate(undefined, { onSuccess: () => void navigate(`/game/${saveId}/overview`) })
        }
        data-testid="continue-sandbox"
      >
        Continue in sandbox
      </Button>
      {go.error && (
        <p style={{ margin: '8px 0 0', color: 'var(--tst-warn)', fontSize: 13 }}>
          {go.error.message}
        </p>
      )}
    </section>
  );
}
