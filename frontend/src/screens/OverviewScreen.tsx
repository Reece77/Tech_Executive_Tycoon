import { Alert, Center, Loader, SimpleGrid, Stack, Title } from '@mantine/core';
import { useParams } from 'react-router';
import { CashChart } from '../components/CashChart';
import { KpiTile } from '../components/KpiTile';
import { useOverview } from '../hooks/api';
import { formatMoney, formatRunway } from '../lib/format';

export function OverviewScreen() {
  const { saveId = '' } = useParams();
  const { data, error, isPending } = useOverview(saveId);

  if (isPending) {
    return (
      <Center h={200}>
        <Loader />
      </Center>
    );
  }
  if (error) {
    return (
      <Alert color="red" title="Could not load the overview">
        {error.message}
      </Alert>
    );
  }

  return (
    <Stack gap="md">
      <Title order={3}>Overview</Title>
      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
        <KpiTile
          label="Cash"
          value={formatMoney(data.cash_cents)}
          hint="Balance of the cash account"
          testId="kpi-cash"
        />
        <KpiTile
          label="Monthly burn"
          value={formatMoney(data.monthly_burn_cents)}
          hint="Net cash spent in the last closed month"
          testId="kpi-burn"
        />
        <KpiTile
          label="Runway"
          value={formatRunway(data.runway_months)}
          hint="Whole months of cash left at the current burn"
          testId="kpi-runway"
        />
      </SimpleGrid>
      <CashChart history={data.history} />
    </Stack>
  );
}
