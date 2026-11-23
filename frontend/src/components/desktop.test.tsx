// M58: the installed game's dialogs and key field, rendered to static markup with a client.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MantineProvider } from '@mantine/core';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Desktop } from '../hooks/desktop';
import { ApiKey } from '../screens/SettingsScreen';
import { DesktopPrompts, UpdateDialog } from './DesktopPrompts';

const BASE: Desktop = {
  desktop: true,
  version: '6.0.0',
  saves_dir: 'C:\\Users\\r\\Documents\\Tech Startup Tycoon\\saves',
  key_saved: false,
  import_offer: null,
  update_state: 'available',
  update: {
    version: '6.1.0',
    notes: '- Faster turns',
    page_url: 'https://example.invalid',
    size_bytes: 1,
  },
  update_message: '',
  backup_folder: null,
};

function render(node: ReactNode, desktop?: Desktop): string {
  const client = new QueryClient();
  if (desktop) client.setQueryData(['desktop'], desktop);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>{node}</MantineProvider>
    </QueryClientProvider>,
  );
  return html.replace(/<style[^>]*>[\s\S]*?<\/style>/g, ''); // Mantine's own styles
}

describe('DesktopPrompts', () => {
  it('shows nothing outside the installed game', () => {
    expect(render(<DesktopPrompts />, { ...BASE, desktop: false })).toBe('');
    expect(render(<DesktopPrompts />)).toBe('');
  });

  it('shows nothing when no update is offered', () => {
    expect(render(<DesktopPrompts />, { ...BASE, update: null, update_state: 'none' })).toBe('');
  });
});

describe('UpdateDialog', () => {
  // Mantine's Modal renders through a portal, so its contents are checked through the
  // dialog's own markup with the portal off.
  it('renders the notes and both choices while the update is offered', () => {
    const html = render(<UpdateDialogInline d={BASE} />);
    expect(html).toContain('- Faster turns');
    expect(html).toContain('Update now');
    expect(html).toContain('Later');
  });

  it('shows the step under way and a failure', () => {
    expect(render(<UpdateDialogInline d={{ ...BASE, update_state: 'backing_up' }} />)).toContain(
      'Backing up your saves',
    );
    const failed = render(
      <UpdateDialogInline
        d={{ ...BASE, update_state: 'failed', update_message: 'checksum does not match' }}
      />,
    );
    expect(failed).toContain('checksum does not match');
    expect(failed).toContain('Try again');
  });
});

function UpdateDialogInline({ d }: { d: Desktop }) {
  return (
    <MantineProvider
      theme={{
        components: {
          Modal: { defaultProps: { withinPortal: false, transitionProps: { duration: 0 } } },
        },
      }}
    >
      <UpdateDialog d={d} />
    </MantineProvider>
  );
}

describe('ApiKey', () => {
  it('never shows the key, only whether one is saved', () => {
    expect(render(<ApiKey d={BASE} />)).toContain('No key saved');
    const saved = render(<ApiKey d={{ ...BASE, key_saved: true }} />);
    expect(saved).toContain('A key is saved on this computer');
    expect(saved).toContain('Remove key');
    expect(saved).not.toContain('sk-ant-api');
  });
});
