import { Modal } from '@mantine/core';

const SHORTCUTS: readonly [string, string][] = [
  ['Space or Enter', 'Continue to the next month'],
  ['H', 'Go on holiday'],
  ['1–9', 'Jump to a screen in the left nav'],
  ['/', 'Search the table on this screen'],
  ['?', 'Show these shortcuts'],
  ['Esc', 'Close a dialog'],
];

/** Every keyboard shortcut (M7b: `?`). */
export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <Modal opened onClose={onClose} title="Keyboard shortcuts" centered>
      <table className="tst-table" style={{ width: '100%' }} data-testid="shortcut-list">
        <tbody>
          {SHORTCUTS.map(([key, what]) => (
            <tr key={key}>
              <td className="tst-num" style={{ whiteSpace: 'nowrap', paddingRight: 16 }}>
                <kbd>{key}</kbd>
              </td>
              <td>{what}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="tst-muted" style={{ fontSize: 12, marginBottom: 0 }}>
        Shortcuts are off while you type in a box.
      </p>
    </Modal>
  );
}
