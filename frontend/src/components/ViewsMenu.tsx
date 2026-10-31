import { Button, Checkbox, Menu, Modal, TextInput } from '@mantine/core';
import type { ReactTable, RowData } from '@tanstack/react-table';
import { useState } from 'react';
import { DEFAULT_VIEW, sortSummary, type TableViewsApi } from '../hooks/useTableViews';
import type { GameTableFeatures } from '../lib/table';

// The "Views for <table>" menu (M7b, wireframe: Tooltips, views and the COO): the built-in
// Default and saved views with their sort, "Save current as…", and Columns (show, hide, move).

function headerText(column: { id: string; columnDef: { header?: unknown } }): string {
  const h = column.columnDef.header;
  return typeof h === 'string' && h ? h : column.id;
}

export function ViewsMenu<T extends RowData>({
  table,
  views,
  label,
}: {
  table: ReactTable<GameTableFeatures, T>;
  views: TableViewsApi;
  label: string;
}) {
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const columns = table.getAllLeafColumns();
  const labelOf = (id: string) => {
    const col = columns.find((c) => c.id === id);
    return col ? headerText(col) : id;
  };
  const order = views.state.columnOrder;
  const ordered = order.length
    ? [...columns].sort((a, b) => {
        const ia = order.indexOf(a.id);
        const ib = order.indexOf(b.id);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
      })
    : columns;
  const move = (id: string, by: -1 | 1) => {
    const ids = ordered.map((c) => c.id);
    const i = ids.indexOf(id);
    const j = i + by;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    table.setColumnOrder(ids);
  };
  const hideable = ordered.filter((c) => c.getCanHide() && headerText(c) !== c.id);
  return (
    <>
      <Menu closeOnItemClick={false} position="bottom-start" width={300}>
        <Menu.Target>
          <Button variant="default" size="sm" h={36} data-testid={`views-${views.tableId}`}>
            View: {views.current}
            {views.modified ? ' (changed)' : ''} ▾
          </Button>
        </Menu.Target>
        <Menu.Dropdown mah={460} style={{ overflowY: 'auto' }} aria-label={`Views for ${label}`}>
          <Menu.Label>Views for {label}</Menu.Label>
          <Menu.Item
            onClick={() => views.select(DEFAULT_VIEW)}
            rightSection={<span className="tst-muted">built in</span>}
            data-testid="view-option"
            aria-current={views.current === DEFAULT_VIEW}
          >
            {views.current === DEFAULT_VIEW ? '✓ ' : ''}
            {DEFAULT_VIEW}
          </Menu.Item>
          {views.views.map((v) => (
            <Menu.Item
              key={v.name}
              onClick={() => views.select(v.name)}
              data-testid="view-option"
              aria-current={views.current === v.name}
              rightSection={
                <span
                  role="button"
                  tabIndex={0}
                  aria-label={`Delete view ${v.name}`}
                  className="tst-muted"
                  onClick={(e) => {
                    e.stopPropagation();
                    views.remove(v.name);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.stopPropagation();
                      views.remove(v.name);
                    }
                  }}
                >
                  ✕
                </span>
              }
            >
              <div>
                {views.current === v.name ? '✓ ' : ''}
                {v.name}
              </div>
              <div className="tst-muted" style={{ fontSize: 11 }}>
                {sortSummary(v, labelOf)}
              </div>
            </Menu.Item>
          ))}
          <Menu.Divider />
          <Menu.Item
            onClick={() => {
              setName('');
              setNaming(true);
            }}
            data-testid="view-save-as"
          >
            Save current as…
          </Menu.Item>
          <Menu.Divider />
          <Menu.Label>Columns</Menu.Label>
          {hideable.map((c) => (
            <div
              key={c.id}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 12px' }}
            >
              <Checkbox
                size="xs"
                checked={c.getIsVisible()}
                onChange={() => c.toggleVisibility()}
                label={headerText(c)}
                style={{ flex: 1 }}
                data-testid={`column-${c.id}`}
              />
              <Button
                size="compact-xs"
                variant="subtle"
                onClick={() => move(c.id, -1)}
                aria-label={`Move ${headerText(c)} left`}
              >
                ↑
              </Button>
              <Button
                size="compact-xs"
                variant="subtle"
                onClick={() => move(c.id, 1)}
                aria-label={`Move ${headerText(c)} right`}
              >
                ↓
              </Button>
            </div>
          ))}
        </Menu.Dropdown>
      </Menu>
      {naming && (
        <Modal opened onClose={() => setNaming(false)} title="Save view as" centered>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              views.saveAs(name);
              setNaming(false);
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <TextInput
              label="View name"
              maxLength={40}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              error={name.trim() === DEFAULT_VIEW ? 'Default is built in' : undefined}
              data-testid="view-name"
              data-autofocus
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button variant="default" h={44} onClick={() => setNaming(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                h={44}
                disabled={!name.trim() || name.trim() === DEFAULT_VIEW}
                data-testid="view-save"
              >
                Save view
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
