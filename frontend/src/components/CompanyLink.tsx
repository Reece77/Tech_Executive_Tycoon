// A company's name, linked to its company page (the Rival screen) when it has one: chain
// companies have pages from January 2026 (M28, formulas.md 41.7).
import { Link } from 'react-router';

export function CompanyLink({
  saveId,
  companyId,
  name,
}: {
  saveId: string;
  companyId: number | null | undefined;
  name: string;
}) {
  if (companyId === null || companyId === undefined) return <>{name}</>;
  return (
    <Link to={`/game/${saveId}/competitors/${companyId}`} data-testid="company-link">
      {name}
    </Link>
  );
}
