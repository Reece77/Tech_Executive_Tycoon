// A medical device's class, route and evidence on its product page (M41, formulas.md 50.2-50.3),
// from the Medical screen's data; nothing for other products. Values are formatted only.
import { Badge, Group } from '@mantine/core';
import { Link } from 'react-router';
import { useMedical } from '../hooks/medical';
import { formatShare } from '../hooks/platforms';
import { Panel } from './ScreenState';
import { Term } from './Term';

export function MedicalSection({ saveId, productId }: { saveId: string; productId: number }) {
  const q = useMedical(saveId);
  const d = q.data?.devices.find((x) => x.product_id === productId);
  if (!d) return null;
  const cleared = d.routes.filter((r) => r.status === 'cleared').map((r) => r.regulator_name);
  return (
    <Panel title="Medical device" testId="medical-section">
      <Group gap="xs">
        <Badge>{d.use_label ?? 'no intended use chosen'}</Badge>
        {d.us_class && <Badge color="teal">US class {d.us_class}</Badge>}
        {d.eu_class && <Badge color="teal">EU class {d.eu_class}</Badge>}
        <Badge color="grape">evidence {formatShare(d.evidence)}</Badge>
      </Group>
      <p style={{ margin: '6px 0 0', fontSize: 13 }}>
        {d.routes.map((r) => `${r.regulator_name}: ${r.label} (${r.review})`).join(' · ')}
      </p>
      <p className="tst-muted" style={{ fontSize: 13 }}>
        {cleared.length > 0 ? `Cleared by ${cleared.join(', ')}. ` : 'Not cleared anywhere yet. '}
        <Term term="medical.pivotal_study">Evidence</Term> comes from studies.{' '}
        <Link to={`/game/${saveId}/products/medical`}>Open the Medical screen</Link>
      </p>
    </Panel>
  );
}
