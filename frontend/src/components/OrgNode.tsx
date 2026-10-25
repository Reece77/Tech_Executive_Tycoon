import type { DragEvent, KeyboardEvent, ReactNode } from 'react';
import { Link } from 'react-router';
import { UNIT_KIND_LABELS, policyText, type UnitKind } from '../lib/org';
import { SpanBadge } from './SpanBadge';

const KIND_STYLES: Record<UnitKind, { color: string; background: string }> = {
  company: { color: 'var(--tst-text-2)', background: 'var(--tst-grey-bg)' },
  department: { color: 'var(--tst-purple)', background: 'var(--tst-purple-bg)' },
  team: { color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
};

export function UnitKindBadge({ kind }: { kind: UnitKind }) {
  return (
    <span
      data-kind={kind}
      style={{
        ...KIND_STYLES[kind],
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        borderRadius: 4,
        padding: '2px 7px',
      }}
    >
      {UNIT_KIND_LABELS[kind]}
    </span>
  );
}

export interface OrgNodeProps {
  kind: UnitKind;
  name: string;
  leaderName: string | null;
  leaderHref: string | null;
  isFounderLed?: boolean;
  policy: string | null; // own policy, null = inherited
  effectivePolicy: string;
  headcount: number;
  span: { reports: number; limit: number; over: boolean } | null;
  selected?: boolean;
  dropActive?: boolean;
  draggable?: boolean;
  onSelect?: () => void;
  onDragStart?: (event: DragEvent) => void;
  onDragOver?: (event: DragEvent) => void;
  onDragLeave?: () => void;
  onDrop?: (event: DragEvent) => void;
  testId?: string;
  children?: ReactNode;
}

/** One unit in the Org tree: kind, name, leader, work location, headcount and span. */
export function OrgNode(props: OrgNodeProps) {
  const {
    kind,
    name,
    leaderName,
    leaderHref,
    isFounderLed,
    policy,
    effectivePolicy,
    headcount,
    span,
    selected,
    dropActive,
  } = props;
  const onKey = (event: KeyboardEvent) => {
    if ((event.key === 'Enter' || event.key === ' ') && props.onSelect) {
      event.preventDefault();
      props.onSelect();
    }
  };
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected ? 'true' : 'false'}
      aria-label={`${UNIT_KIND_LABELS[kind]} ${name}`}
      data-testid={props.testId ?? 'org-node'}
      data-unit-name={name}
      draggable={props.draggable}
      onClick={props.onSelect}
      onKeyDown={onKey}
      onDragStart={props.onDragStart}
      onDragOver={props.onDragOver}
      onDragLeave={props.onDragLeave}
      onDrop={props.onDrop}
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        background: selected || dropActive ? 'var(--tst-accent-bg)' : 'var(--tst-panel)',
        border: `1px ${dropActive ? 'dashed' : 'solid'} ${
          selected || dropActive ? 'var(--tst-accent)' : 'var(--tst-border)'
        }`,
        borderRadius: 8,
        cursor: props.draggable ? 'grab' : 'pointer',
      }}
    >
      <UnitKindBadge kind={kind} />
      <span style={{ fontWeight: 600, fontSize: 15 }}>{name}</span>
      <span className="tst-muted" style={{ fontSize: 13 }}>
        {leaderName === null ? (
          'No leader'
        ) : (
          <>
            Led by{' '}
            {leaderHref ? (
              <Link to={leaderHref} onClick={(e) => e.stopPropagation()}>
                {leaderName}
              </Link>
            ) : (
              leaderName
            )}
            {isFounderLed ? ' (founder)' : ''}
          </>
        )}
      </span>
      <span
        style={{
          fontSize: 13,
          color:
            effectivePolicy === 'remote' && policy !== null
              ? 'var(--tst-link)'
              : 'var(--tst-muted)',
        }}
      >
        {policyText(policy, effectivePolicy)}
      </span>
      <span style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
        <span className="tst-num tst-muted" style={{ fontSize: 13 }}>
          {headcount} {headcount === 1 ? 'person' : 'people'}
        </span>
        {span && <SpanBadge {...span} />}
      </span>
      {props.children}
    </div>
  );
}

/** Marks a unit's leader in member lists and the People roster. */
export function LeadsChip() {
  return (
    <span
      data-testid="leads-chip"
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: 'var(--tst-link)',
        background: 'var(--tst-accent-bg)',
        borderRadius: 4,
        padding: '1px 6px',
      }}
    >
      Leads
    </span>
  );
}
