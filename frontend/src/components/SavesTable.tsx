import { Button, Table, Text } from '@mantine/core';
import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table';
import { Link } from 'react-router';
import type { Save } from '../hooks/api';

const features = tableFeatures({});
const helper = createColumnHelper<typeof features, Save>();
const columns = helper.columns([
  helper.accessor('company_name', { header: 'Company' }),
  helper.accessor('save_id', { header: 'Save' }),
  helper.accessor('date_label', { header: 'Date' }),
  helper.accessor('scenario_id', { header: 'Scenario' }),
  helper.display({
    id: 'open',
    header: '',
    cell: ({ row }) => (
      <Button
        component={Link}
        to={`/game/${row.original.save_id}/overview`}
        size="compact-sm"
        variant="light"
        data-testid={`open-${row.original.save_id}`}
      >
        Open
      </Button>
    ),
  }),
]);

export function SavesTable({ saves }: { saves: Save[] }) {
  const table = useTable({ features, columns, data: saves });

  if (saves.length === 0) {
    return <Text c="dimmed">No saves yet. Create a new game below.</Text>;
  }
  return (
    <Table striped highlightOnHover verticalSpacing={4} className="tst-num">
      <Table.Thead>
        {table.getHeaderGroups().map((group) => (
          <Table.Tr key={group.id}>
            {group.headers.map((header) => (
              <Table.Th key={header.id}>
                {header.isPlaceholder ? null : <table.FlexRender header={header} />}
              </Table.Th>
            ))}
          </Table.Tr>
        ))}
      </Table.Thead>
      <Table.Tbody>
        {table.getRowModel().rows.map((row) => (
          <Table.Tr key={row.id}>
            {row.getAllCells().map((cell) => (
              <Table.Td key={cell.id}>
                <table.FlexRender cell={cell} />
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
