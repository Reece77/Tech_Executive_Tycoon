import { Alert, Button, Group, Modal, Stack } from '@mantine/core';
import {
  useAnswerImport,
  useDesktop,
  useStartUpdate,
  useUpdateLater,
  type Desktop,
  type ImportOffer,
} from '../hooks/desktop';

const STEP: Partial<Record<string, string>> = {
  downloading: 'Downloading the new version and checking its checksum…',
  backing_up: 'Backing up your saves…',
  installing: 'Installing. The game will close and start again in a moment.',
};

/** The installed game's start-up dialogs (M58): the first-run import of the repository's
 * saves, then "What's new" when a newer release is out. Nothing outside the installed game. */
export function DesktopPrompts() {
  const desktop = useDesktop().data;
  if (!desktop?.desktop) return null;
  if (desktop.import_offer) return <ImportDialog d={desktop} offer={desktop.import_offer} />;
  const state = desktop.update_state ?? 'none';
  if (desktop.update && state !== 'none' && state !== 'checking')
    return <UpdateDialog d={desktop} />;
  return null;
}

function ImportDialog({ d, offer }: { d: Desktop; offer: ImportOffer }) {
  const answer = useAnswerImport();
  const n = offer.saves.length;
  return (
    <Modal
      opened
      onClose={() => answer.mutate(false)}
      title="Bring your saves across?"
      size="lg"
      data-testid="import-dialog"
    >
      <Stack gap="sm">
        <p style={{ margin: 0 }}>
          Found {n} {n === 1 ? 'save' : 'saves'} from the version you played before, in{' '}
          <code>{offer.folder}</code>: {offer.saves.join(', ')}.
        </p>
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          They are copied to <code>{d.saves_dir}</code>; the originals stay where they are. Saves
          with a name already here are kept as they are.
        </p>
        {answer.error && <Alert color="warn">{answer.error.message}</Alert>}
        <Group justify="flex-end">
          <Button
            variant="default"
            h={44}
            onClick={() => answer.mutate(false)}
            disabled={answer.isPending}
            data-testid="import-skip"
          >
            Not now
          </Button>
          <Button
            h={44}
            loading={answer.isPending}
            onClick={() => answer.mutate(true)}
            data-testid="import-accept"
          >
            Import {n === 1 ? 'it' : `all ${n}`}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function UpdateDialog({ d }: { d: Desktop }) {
  const start = useStartUpdate();
  const later = useUpdateLater();
  const state = d.update_state ?? 'none';
  const step = STEP[state];
  const working = step !== undefined;
  const failed = state === 'failed';
  if (!d.update) return null;
  const update = d.update;
  const error = start.error?.message ?? (failed ? d.update_message : null);
  return (
    <Modal
      opened
      onClose={() => !working && later.mutate()}
      withCloseButton={!working}
      closeOnClickOutside={!working}
      title={`What's new in ${update.version}`}
      size="xl"
      data-testid="update-dialog"
    >
      <Stack gap="sm">
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          You have {d.version}. Updating backs up every save first, then installs the new version
          and restarts the game. Your saves and settings are kept.
        </p>
        <div
          className="tst-panel"
          style={{
            whiteSpace: 'pre-wrap',
            maxHeight: 360,
            overflowY: 'auto',
            padding: '12px 16px',
            fontSize: 13,
          }}
          data-testid="update-notes"
        >
          {update.notes || 'Fixes and improvements.'}
        </div>
        {working && (
          <Alert color="blue" data-testid="update-progress">
            {step}
          </Alert>
        )}
        {error && (
          <Alert color="warn" title="The update did not run" data-testid="update-error">
            {error}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button
            variant="default"
            h={44}
            disabled={working || later.isPending}
            onClick={() => later.mutate()}
            data-testid="update-later"
          >
            Later
          </Button>
          <Button
            h={44}
            loading={working || start.isPending}
            onClick={() => start.mutate()}
            data-testid="update-now"
          >
            {failed ? 'Try again' : 'Update now'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
