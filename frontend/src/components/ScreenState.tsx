import { Alert, Center, Loader } from '@mantine/core';
import type { CSSProperties, ReactNode } from 'react';

/** Loading and error states shared by every screen. */
export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <Center h={200} aria-busy="true" aria-label={label}>
      <Loader />
    </Center>
  );
}

export function LoadError({ title, error }: { title: string; error: Error | null }) {
  return (
    <Alert color="red" title={title} role="alert">
      {error?.message ?? 'Unknown error'}
    </Alert>
  );
}

/** Render children once every query has data; otherwise the first loading or error state. */
export function WhenLoaded({
  queries,
  title,
  children,
}: {
  queries: { isPending: boolean; error: Error | null }[];
  title: string;
  children: () => ReactNode;
}) {
  const failed = queries.find((q) => q.error);
  if (failed) return <LoadError title={title} error={failed.error} />;
  if (queries.some((q) => q.isPending)) return <Loading />;
  return <>{children()}</>;
}

export function Panel({
  title,
  children,
  label,
  style,
  action,
}: {
  title?: string;
  label?: string;
  children: ReactNode;
  style?: CSSProperties;
  action?: ReactNode;
}) {
  return (
    <section className="tst-panel" aria-label={label ?? title} style={style}>
      {(title || action) && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          {title && <h2 className="tst-ptitle">{title}</h2>}
          {action && <div style={{ marginLeft: 'auto' }}>{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function ScreenTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
      <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>{children}</h1>
      {aside}
    </div>
  );
}
