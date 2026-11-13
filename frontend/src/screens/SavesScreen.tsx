import { Alert, Button, Modal, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Term } from '../components/Term';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useBackups,
  useDeleteSave,
  useDuplicateSave,
  useRenameSave,
  useRestoreBackup,
  useSaves,
  useScenarios,
  type Save,
} from '../hooks/api';
import { useBackUp } from '../hooks/onboarding';
import { formatBytes, formatWhen, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// The saves manager (M7b): open, rename, duplicate, delete, and restore a backup as a new save.
// Reached from the main menu and the left nav.

type Dialog =
  | { kind: 'rename'; save: Save }
  | { kind: 'duplicate'; save: Save }
  | { kind: 'delete'; save: Save }
  | { kind: 'backups'; save: Save };

const STATE_LABELS: Record<string, string> = {
  active: 'Active',
  bankrupt: 'Bankrupt',
  founder_removed: 'Founder removed',
  exit: 'Sold', // M14
  scenario_done: 'Scenario judged', // M15b
  retired: 'Retired',
};

const helper = createColumnHelper<GameTableFeatures, Save>();

function columns(scenarioName: (id: string) => string, open: (d: Dialog) => void) {
  return helper.columns([
    helper.accessor('display_name', {
      header: 'Save',
      cell: ({ row }) => (
        <span>
          <strong>{row.original.display_name}</strong>
          {row.original.display_name !== row.original.save_id && (
            <span className="tst-muted" style={{ marginLeft: 6, fontSize: 12 }}>
              {row.original.save_id}
            </span>
          )}
        </span>
      ),
    }),
    helper.accessor('company_name', { header: 'Company' }),
    helper.accessor('scenario_id', {
      header: 'Scenario',
      cell: ({ getValue }) => scenarioName(getValue()),
    }),
    helper.accessor('difficulty', {
      header: 'Difficulty',
      cell: ({ getValue }) => humanize(getValue()),
    }),
    helper.accessor('mode', {
      header: 'Mode', // M15b (30.2-30.3)
      meta: { term: 'game_mode' },
      cell: ({ getValue }) => humanize(getValue() ?? 'campaign'),
    }),
    helper.accessor((s) => s.mod_name ?? '', {
      id: 'mod',
      header: 'Mod', // M25: modded games are flagged and earn no achievements
      meta: { term: 'field.mod_name' },
      cell: ({ row }) =>
        row.original.mod_name ? (
          <span data-testid={`save-mod-${row.original.save_id}`}>⚙ {row.original.mod_name}</span>
        ) : (
          '—'
        ),
    }),
    helper.accessor('score', {
      header: 'Score', // M15b (30.1): none for Sandbox games
      meta: { term: 'kpi.company_score' },
      cell: ({ getValue }) => <span className="tst-num">{getValue() ?? '—'}</span>,
    }),
    helper.accessor('turn', {
      header: 'Date',
      cell: ({ row }) => <span className="tst-num">{row.original.date_label}</span>,
    }),
    helper.accessor('game_state', {
      header: 'State',
      cell: ({ getValue }) => STATE_LABELS[getValue()] ?? humanize(getValue()),
    }),
    helper.accessor('last_played', {
      header: 'Last played',
      cell: ({ getValue }) => <span className="tst-num">{formatWhen(getValue())}</span>,
    }),
    helper.accessor('size_bytes', {
      header: 'Size',
      cell: ({ getValue }) => <span className="tst-num">{formatBytes(getValue())}</span>,
    }),
    helper.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const save = row.original;
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
            <Button
              component={Link}
              to={`/game/${save.save_id}`}
              size="compact-sm"
              data-testid={`open-${save.save_id}`}
            >
              Open
            </Button>
            <Button
              size="compact-sm"
              variant="default"
              onClick={() => open({ kind: 'rename', save })}
              data-testid={`rename-${save.save_id}`}
            >
              Rename
            </Button>
            {!save.ironman && (
              <>
                <Button
                  size="compact-sm"
                  variant="default"
                  onClick={() => open({ kind: 'duplicate', save })}
                  data-testid={`duplicate-${save.save_id}`}
                >
                  Duplicate
                </Button>
                <Button
                  size="compact-sm"
                  variant="default"
                  onClick={() => open({ kind: 'backups', save })}
                  data-testid={`backups-${save.save_id}`}
                >
                  Backups
                </Button>
              </>
            )}
            <Button
              size="compact-sm"
              variant="default"
              color="warn"
              onClick={() => open({ kind: 'delete', save })}
              data-testid={`delete-${save.save_id}`}
            >
              Delete
            </Button>
            {save.ironman && (
              <span className="tst-muted" style={{ fontSize: 12 }}>
                Ironman: no duplicate or restore
              </span>
            )}
            {save.busy && <span style={{ fontSize: 12, color: 'var(--tst-warn)' }}>Busy</span>}
          </div>
        );
      },
    }),
  ]);
}

function NameDialog({
  title,
  initial,
  submit,
  onClose,
  pending,
  error,
  testId,
}: {
  title: string;
  initial: string;
  submit: (name: string) => void;
  onClose: () => void;
  pending: boolean;
  error: Error | null;
  testId: string;
}) {
  const [name, setName] = useState(initial);
  return (
    <Modal opened onClose={onClose} title={title} centered>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(name);
        }}
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <TextInput
          label="Save name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.currentTarget.value)}
          data-testid={`${testId}-name`}
          data-autofocus
        />
        {error && (
          <Alert color="red" title="Not done">
            {error.message}
          </Alert>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="default" h={44} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" h={44} disabled={!name.trim() || pending} data-testid={testId}>
            {title}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function DeleteDialog({
  save,
  onClose,
  onDeleted,
}: {
  save: Save;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [typed, setTyped] = useState('');
  const remove = useDeleteSave();
  return (
    <Modal opened onClose={onClose} title={`Delete ${save.display_name}?`} centered>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p style={{ margin: 0, fontSize: 14 }}>
          This deletes the save <strong>{save.display_name}</strong> ({save.company_name},{' '}
          {save.date_label}) and its backups. It cannot be undone. Type the save name to confirm.
        </p>
        <TextInput
          aria-label="Type the save name"
          value={typed}
          onChange={(e) => setTyped(e.currentTarget.value)}
          data-testid="delete-confirm-name"
        />
        {remove.error && (
          <Alert color="red" title="Not deleted">
            {remove.error.message}
          </Alert>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="default" h={44} onClick={onClose}>
            Cancel
          </Button>
          <Button
            color="warn"
            h={44}
            disabled={typed.trim() !== save.display_name || remove.isPending}
            onClick={() => remove.mutate(save.save_id, { onSuccess: onDeleted })}
            data-testid="delete-confirm"
          >
            Delete save
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function BackupsDialog({
  save,
  onClose,
  onRestored,
}: {
  save: Save;
  onClose: () => void;
  onRestored: (restored: Save) => void;
}) {
  const backups = useBackups(save.save_id);
  const restore = useRestoreBackup();
  const backUp = useBackUp(); // M29 (42.5)
  return (
    <Modal opened onClose={onClose} title={`Backups of ${save.display_name}`} centered size="lg">
      <p className="tst-muted" style={{ marginTop: 0, fontSize: 13 }}>
        A backup restores as a new save named after the company and the backup's date. The original
        save is never changed.
      </p>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <Button
          size="compact-sm"
          loading={backUp.isPending}
          onClick={() => backUp.mutate(save.save_id)}
          data-testid="back-up-now"
        >
          Back up now
        </Button>
        {backUp.data && (
          <span className="tst-muted" style={{ fontSize: 12 }} data-testid="backed-up">
            Backed up at {backUp.data.date_label}.
          </span>
        )}
        {backUp.error && (
          <span style={{ fontSize: 12, color: 'var(--tst-warn)' }}>{backUp.error.message}</span>
        )}
      </div>
      {backups.isPending ? (
        <Loading />
      ) : backups.error ? (
        <LoadError title="Could not list backups" error={backups.error} />
      ) : backups.data.length === 0 ? (
        <p className="tst-muted">No backups yet. One is taken every 12 months of play.</p>
      ) : (
        <table className="tst-table" aria-label="Backups" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>
                <Term term="turn">Game date</Term>
              </th>
              <th>
                <Term term="backup_kind">Kind</Term>
              </th>
              <th>
                <Term term="backup_taken">Taken</Term>
              </th>
              <th>
                <Term term="size_bytes">Size</Term>
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {backups.data.map((b) => (
              <tr key={b.backup_id} data-testid="backup-row">
                <td className="tst-num">{b.date_label}</td>
                <td>
                  {b.kind === 'periodic'
                    ? 'Periodic'
                    : b.kind === 'manual'
                      ? 'Backed up by you'
                      : 'Before an upgrade'}
                </td>
                <td className="tst-num">{formatWhen(b.created)}</td>
                <td className="tst-num">{formatBytes(b.size_bytes)}</td>
                <td>
                  <Button
                    size="compact-sm"
                    disabled={restore.isPending}
                    onClick={() =>
                      restore.mutate(
                        { saveId: save.save_id, backupId: b.backup_id },
                        { onSuccess: onRestored },
                      )
                    }
                    data-testid="restore-backup"
                  >
                    Restore as new save
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {restore.error && (
        <Alert color="red" title="Not restored" mt="sm">
          {restore.error.message}
        </Alert>
      )}
    </Modal>
  );
}

/** The saves table and its dialogs; `current` is the save open in the game, if any. */
export function SavesManager({ current }: { current?: string }) {
  const saves = useSaves();
  const scenarios = useScenarios();
  const rename = useRenameSave();
  const duplicate = useDuplicateSave();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [notice, setNotice] = useState<Save | null>(null);
  const names = useMemo(
    () => new Map((scenarios.data ?? []).map((s) => [s.id, s.name])),
    [scenarios.data],
  );
  const cols = useMemo(() => columns((id) => names.get(id) ?? humanize(id), setDialog), [names]);
  const table = useTable({
    features: gameTableFeatures,
    columns: cols,
    data: saves.data ?? [],
    getRowId: (s) => s.save_id,
  });
  const close = () => {
    rename.reset();
    duplicate.reset();
    setDialog(null);
  };
  if (saves.isPending) return <Loading />;
  if (saves.error) return <LoadError title="Could not load saves" error={saves.error} />;
  return (
    <>
      {notice && (
        <Alert
          color="green"
          title="Restored as a new save"
          withCloseButton
          onClose={() => setNotice(null)}
          data-testid="restored-notice"
        >
          {notice.display_name} is in the list. <Link to={`/game/${notice.save_id}`}>Open it</Link>
        </Alert>
      )}
      <DataTable
        table={table}
        label="Saves"
        rowTestId="save-row"
        selectedRowId={current}
        empty="No saves yet. Start a new game."
      />
      {dialog?.kind === 'rename' && (
        <NameDialog
          title="Rename"
          initial={dialog.save.display_name}
          pending={rename.isPending}
          error={rename.error}
          testId="rename-submit"
          onClose={close}
          submit={(name) =>
            rename.mutate({ saveId: dialog.save.save_id, name }, { onSuccess: close })
          }
        />
      )}
      {dialog?.kind === 'duplicate' && (
        <NameDialog
          title="Duplicate"
          initial={`${dialog.save.display_name} (copy)`}
          pending={duplicate.isPending}
          error={duplicate.error}
          testId="duplicate-submit"
          onClose={close}
          submit={(name) =>
            duplicate.mutate({ saveId: dialog.save.save_id, name }, { onSuccess: close })
          }
        />
      )}
      {dialog?.kind === 'delete' && (
        <DeleteDialog
          save={dialog.save}
          onClose={close}
          onDeleted={() => {
            close();
            if (dialog.save.save_id === current) void navigate('/');
          }}
        />
      )}
      {dialog?.kind === 'backups' && (
        <BackupsDialog
          save={dialog.save}
          onClose={close}
          onRestored={(restored) => {
            close();
            setNotice(restored);
          }}
        />
      )}
    </>
  );
}

/** The Saves screen inside a game (left nav). */
export function SavesScreen() {
  const { saveId = '' } = useParams();
  return (
    <>
      <ScreenTitle
        aside={
          <Button component={Link} to="/new" ml="auto" h={36} variant="default">
            New game
          </Button>
        }
      >
        Saves
      </ScreenTitle>
      <Panel>
        <SavesManager current={saveId} />
      </Panel>
    </>
  );
}
