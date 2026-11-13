import { Fragment, useMemo } from 'react';
import { Link, useLocation } from 'react-router';
import { usePalette } from '../hooks/onboarding';
import { crumbs } from '../lib/nav';

// Breadcrumbs (M29, 42.4): where this screen sits, e.g. Products / Fabs or People / Ana Ruiz.
export function Breadcrumbs({ saveId }: { saveId: string }) {
  const { pathname } = useLocation();
  const palette = usePalette(saveId);
  const names = useMemo(
    () => new Map((palette.data?.entries ?? []).map((e) => [e.path, e.label] as const)),
    [palette.data],
  );
  const here = pathname.replace(`/game/${saveId}/`, '');
  const trail = crumbs(here, names);
  if (trail.length < 2) return null;
  return (
    <nav aria-label="Breadcrumbs" className="tst-crumbs" data-testid="breadcrumbs">
      {trail.map((c, i) => (
        <Fragment key={`${c.label}-${i}`}>
          {i > 0 && <span aria-hidden="true">/</span>}
          {c.path ? (
            <Link to={`/game/${saveId}/${c.path}`}>{c.label}</Link>
          ) : (
            <span aria-current="page">{c.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
