import { Badge, NavLink as MantineNavLink, Stack } from '@mantine/core';
import { NavLink } from 'react-router';
import { NAV_ITEMS } from '../lib/nav';

export function LeftNav({ saveId }: { saveId: string }) {
  return (
    <Stack gap={2} p="xs" component="nav" aria-label="Game screens">
      {NAV_ITEMS.map((item) => (
        <NavLink key={item.path} to={`/game/${saveId}/${item.path}`} style={{ all: 'unset' }}>
          {({ isActive }) => (
            <MantineNavLink
              component="span"
              active={isActive}
              label={item.label}
              rightSection={
                item.arrivesIn ? (
                  <Badge size="xs" variant="outline" color="gray">
                    {item.arrivesIn}
                  </Badge>
                ) : undefined
              }
            />
          )}
        </NavLink>
      ))}
    </Stack>
  );
}
