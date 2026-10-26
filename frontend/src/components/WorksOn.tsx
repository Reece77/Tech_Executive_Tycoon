import { Alert, Button, Menu } from '@mantine/core';
import { Link, useParams } from 'react-router';
import { useProductAction, useProducts, useProductsMeta, type OrgUnit } from '../hooks/api';

/** The Org unit panel's "Works on": the unit's product with Unassign, or Assign (M3b). */
export function WorksOn({ unit }: { unit: OrgUnit }) {
  const { saveId = '' } = useParams();
  const products = useProducts(saveId);
  const meta = useProductsMeta();
  const act = useProductAction(saveId);
  const costs = meta.data?.energy_costs;
  const choices = (products.data ?? []).filter(
    (p) => p.status !== 'retired' && p.product_id !== unit.product_id,
  );
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }} data-testid="works-on">
      <div className="tst-muted">Works on</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
        {unit.product_id == null ? (
          <span style={{ fontSize: 15 }}>No product</span>
        ) : (
          <>
            <Link
              to={`/game/${saveId}/products/${unit.product_id}`}
              style={{ fontSize: 15 }}
              data-testid="works-on-product"
            >
              {unit.product_name}
            </Link>
            <Button
              size="compact-sm"
              variant="default"
              loading={act.isPending}
              onClick={() =>
                act.mutate({
                  productId: unit.product_id as number,
                  action: { action: 'unassign', unit_id: unit.unit_id },
                })
              }
              data-testid="works-on-unassign"
            >
              Unassign · {costs?.unassign_unit ?? ''}
            </Button>
          </>
        )}
        {unit.product_id == null && (
          <Menu position="bottom-start">
            <Menu.Target>
              <Button
                size="compact-sm"
                variant="default"
                disabled={choices.length === 0}
                title={choices.length === 0 ? 'Create a product first' : undefined}
                data-testid="works-on-assign"
              >
                Assign to a product · {costs?.assign_unit ?? ''}
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              {choices.map((p) => (
                <Menu.Item
                  key={p.product_id}
                  onClick={() =>
                    act.mutate({
                      productId: p.product_id,
                      action: { action: 'assign', unit_id: unit.unit_id },
                    })
                  }
                  data-testid="works-on-option"
                >
                  {p.name} · {p.category_label}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
        )}
      </div>
      {act.error && (
        <Alert color="red" title="Could not change the assignment">
          {act.error.message}
        </Alert>
      )}
    </div>
  );
}
