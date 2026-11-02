import type { Schemas } from '../api/client';

type Role = Schemas['RoleOut'];

/** What a role does and when to hire one (23.4, M10b), under a role picker or on a profile. */
export function RoleHelp({ role }: { role: Role | undefined }) {
  if (!role) return null;
  return (
    <div className="tst-muted" style={{ fontSize: 13, lineHeight: 1.45 }} data-testid="role-help">
      <div>{role.summary}</div>
      <div>
        <span style={{ color: 'var(--tst-text-2)' }}>Why hire one: </span>
        {role.why_hire}
      </div>
    </div>
  );
}
