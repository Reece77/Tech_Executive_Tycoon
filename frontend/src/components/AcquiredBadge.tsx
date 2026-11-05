// M14 (formulas.md 28.5): a unit made for an acquired product is flagged on Org for its first
// months after closing (mna.acquired_flag_months), naming the company it came from.
import { Badge } from '@mantine/core';
import { useParams } from 'react-router';
import { useMna } from '../hooks/api';

export function AcquiredBadge({ unitId }: { unitId: number }) {
  const { saveId = '' } = useParams();
  const mna = useMna(saveId);
  const from = mna.data?.acquisitions.find((a) => a.flagged && a.unit_ids.includes(unitId));
  if (!from) return null;
  return (
    <Badge variant="light" color="grape" data-testid="acquired-badge">
      Acquired from {from.name}
    </Badge>
  );
}
