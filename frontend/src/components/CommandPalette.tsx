import { Modal, TextInput } from '@mantine/core';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { usePalette, useUnlockedKeys, type PaletteEntry } from '../hooks/onboarding';
import { isOpen, SCREENS } from '../lib/nav';
import { matchOptions, type Option } from '../lib/palette';
import { pushRecent, readRecent } from '../lib/recent';

// The command palette (M29, 42.4): Ctrl+K (or Cmd+K) jumps to any open screen, person,
// product, facility or rival by name. With nothing typed it lists recent items.

const MAX_SHOWN = 12;
const KIND_LABELS: Record<string, string> = {
  screen: 'Screen',
  person: 'Person',
  product: 'Product',
  facility: 'Facility',
  rival: 'Rival',
};

function toOption(e: PaletteEntry): Option {
  return { key: `${e.kind}-${e.id}`, label: e.label, detail: e.detail, kind: e.kind, path: e.path };
}

export function CommandPalette({
  saveId,
  opened,
  onClose,
}: {
  saveId: string;
  opened: boolean;
  onClose: () => void;
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Go to"
      size="lg"
      data-testid="command-palette"
      transitionProps={{ duration: 0 }}
    >
      {opened && <PaletteBody saveId={saveId} onClose={onClose} />}
    </Modal>
  );
}

function PaletteBody({ saveId, onClose }: { saveId: string; onClose: () => void }) {
  const navigate = useNavigate();
  const unlocked = useUnlockedKeys(saveId);
  const palette = usePalette(saveId);
  const [query, setQuery] = useState('');
  const [index, setIndex] = useState(0);
  const [recent] = useState(() => readRecent(saveId));

  const options = useMemo<Option[]>(() => {
    const screens = SCREENS.filter((s) => isOpen(s, unlocked)).map((s) => ({
      key: `screen-${s.path}`,
      label: s.label,
      detail: 'Screen',
      kind: 'screen',
      path: s.path,
    }));
    return [...screens, ...(palette.data?.entries ?? []).map(toOption)];
  }, [palette.data, unlocked]);

  const shown: Option[] = query.trim()
    ? matchOptions(options, query).slice(0, MAX_SHOWN)
    : recent.map((r) => ({ key: `recent-${r.path}`, ...r, detail: KIND_LABELS[r.kind] ?? '' }));

  const go = (o: Option) => {
    pushRecent(saveId, { label: o.label, path: o.path, kind: o.kind });
    onClose();
    void navigate(`/game/${saveId}/${o.path}`);
  };

  return (
    <>
      <TextInput
        data-autofocus
        placeholder="A screen, person, product, facility or rival"
        value={query}
        aria-label="Search screens, people, products, facilities and rivals"
        data-testid="palette-input"
        onChange={(e) => {
          setQuery(e.currentTarget.value);
          setIndex(0);
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setIndex((i) => Math.min(i + 1, Math.max(shown.length - 1, 0)));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setIndex((i) => Math.max(i - 1, 0));
          } else if (e.key === 'Enter' && shown[index]) {
            e.preventDefault();
            go(shown[index]);
          }
        }}
      />
      <div role="listbox" aria-label="Results" style={{ marginTop: 10 }}>
        {!query.trim() && shown.length > 0 && (
          <div className="tst-muted" style={{ fontSize: 12, padding: '4px 8px' }}>
            Recent
          </div>
        )}
        {shown.map((o, i) => (
          <button
            key={o.key}
            type="button"
            role="option"
            aria-selected={i === index}
            className="tst-row"
            data-testid="palette-option"
            onMouseEnter={() => setIndex(i)}
            onClick={() => go(o)}
            style={{
              width: '100%',
              border: 0,
              cursor: 'pointer',
              textAlign: 'left',
              background: i === index ? 'var(--tst-panel-active)' : 'transparent',
              color: 'var(--tst-text)',
              borderRadius: 6,
              padding: '6px 8px',
            }}
          >
            <span>{o.label}</span>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {o.kind === 'screen' ? 'Screen' : `${KIND_LABELS[o.kind] ?? o.kind} · ${o.detail}`}
            </span>
          </button>
        ))}
        {query.trim() && shown.length === 0 && (
          <p className="tst-muted" style={{ margin: '8px', fontSize: 13 }}>
            {palette.isPending ? 'Loading…' : 'Nothing matches.'}
          </p>
        )}
      </div>
    </>
  );
}
