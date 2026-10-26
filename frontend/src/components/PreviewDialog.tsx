import { Alert, Button, Modal } from '@mantine/core';
import type { ReactNode } from 'react';
import type { ChangePreview } from '../hooks/api';
import { signed } from '../lib/org';

/** The preview's facts: who it affects and how much, the energy, or why it is refused. */
export function PreviewBody({
  preview,
  note,
}: {
  preview: ChangePreview | undefined;
  note?: ReactNode;
}) {
  if (!preview) return <p className="tst-muted">Checking the change…</p>;
  if (!preview.allowed) {
    return (
      <Alert color="warn" title="This change is not allowed" data-testid="preview-problem">
        {preview.problem}
      </Alert>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span className="tst-muted" style={{ fontSize: 13 }} data-testid="preview-energy">
        Costs {preview.energy_cost} energy.
      </span>
      <div>
        <h3 className="tst-ptitle" style={{ margin: '0 0 6px' }}>
          One-off morale changes
        </h3>
        {preview.morale_changes.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0, fontSize: 13 }} data-testid="preview-none">
            Nobody&apos;s morale changes.
          </p>
        ) : (
          preview.morale_changes.map((c) => (
            <div key={c.person_id} className="tst-row" data-testid="preview-change">
              <span>{c.name}</span>
              <span
                className="tst-num"
                style={{ color: c.change < 0 ? 'var(--tst-warn)' : 'var(--tst-good)' }}
              >
                {signed(c.change)}
              </span>
            </div>
          ))
        )}
      </div>
      {note && (
        <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
          {note}
        </p>
      )}
    </div>
  );
}

/** Every reorganization opens this first: the API preview, then Confirm or Cancel. */
export function PreviewDialog({
  opened,
  title,
  subtitle,
  preview,
  error,
  confirmLabel,
  confirming,
  onConfirm,
  onCancel,
  note,
  children,
}: {
  opened: boolean;
  title: string;
  subtitle?: ReactNode;
  preview: ChangePreview | undefined;
  error?: Error | null;
  confirmLabel: string;
  confirming?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  note?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <Modal opened={opened} onClose={onCancel} title={title} centered size="lg">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="preview">
        {subtitle && (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {subtitle}
          </span>
        )}
        {children}
        <PreviewBody preview={preview} note={note} />
        {error && (
          <Alert color="red" title="Could not apply the change">
            {error.message}
          </Alert>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Button
            onClick={onConfirm}
            loading={confirming}
            disabled={!preview?.allowed}
            size="md"
            data-testid="preview-confirm"
          >
            {confirmLabel}
          </Button>
          <Button variant="default" size="md" onClick={onCancel} data-testid="preview-cancel">
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
