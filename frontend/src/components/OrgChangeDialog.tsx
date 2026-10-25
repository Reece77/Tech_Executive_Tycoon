import { TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useState } from 'react';
import { useOrgChange, useOrgPreview, type OrgChange } from '../hooks/api';
import { PreviewDialog } from './PreviewDialog';

/** What the preview dialog shows: the change plus its wording. */
export interface Pending {
  change: OrgChange;
  title: string;
  subtitle?: string;
  confirmLabel: string;
  note?: string;
  nameInput?: boolean; // create and rename ask for a name inside the dialog
}

/** The preview-then-confirm dialog for one org change (create and rename take a name). */
export function ChangeDialog({
  saveId,
  pending,
  onDone,
}: {
  saveId: string;
  pending: Pending;
  onDone: (selectKey?: string) => void;
}) {
  const initialName =
    pending.change.change === 'rename_unit' || pending.change.change === 'create_unit'
      ? pending.change.name
      : '';
  const [name, setName] = useState(initialName);
  const [debounced] = useDebouncedValue(name, 200);
  const change: OrgChange =
    pending.change.change === 'rename_unit' || pending.change.change === 'create_unit'
      ? { ...pending.change, name: debounced }
      : pending.change;
  const needsName = pending.nameInput && debounced.trim() === '';
  const preview = useOrgPreview(saveId, needsName ? null : change);
  const apply = useOrgChange(saveId);
  return (
    <PreviewDialog
      opened
      title={pending.title}
      subtitle={pending.subtitle}
      preview={needsName ? undefined : preview.data}
      error={apply.error}
      confirmLabel={pending.confirmLabel}
      confirming={apply.isPending}
      note={pending.note}
      onCancel={() => onDone()}
      onConfirm={() =>
        apply.mutate(change, {
          onSuccess: (out) => {
            if (change.change === 'create_unit') {
              const created = out.org.units.reduce(
                (max, u) => (u.unit_id !== null && u.unit_id > max ? u.unit_id : max),
                0,
              );
              onDone(String(created));
            } else {
              onDone();
            }
          },
        })
      }
    >
      {pending.nameInput && (
        <TextInput
          label="Name"
          value={name}
          maxLength={64}
          data-autofocus
          data-testid="unit-name-input"
          onChange={(event) => setName(event.currentTarget.value)}
        />
      )}
    </PreviewDialog>
  );
}
