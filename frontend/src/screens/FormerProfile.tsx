import { Link } from 'react-router';
import { AttributeRange } from '../components/AttributeRange';
import { Panel } from '../components/ScreenState';
import type { FormerProfile } from '../hooks/api';
import { formatMonths, humanize } from '../lib/format';

const GROUPS = [
  ['technical', 'Technical'],
  ['business', 'Business'],
  ['leadership', 'Leadership'],
] as const;

/** A person who has left (M7c): read-only, as the company knew them at departure. */
export function FormerProfileView({ saveId, p }: { saveId: string; p: FormerProfile }) {
  return (
    <>
      <Link to={`/game/${saveId}/people`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← People
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'baseline' }}>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }} data-testid="person-name">
          {p.name}
        </h1>
        <span
          data-testid="former-badge"
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: 'uppercase',
            background: 'var(--tst-grey-bg)',
            borderRadius: 4,
            padding: '2px 7px',
          }}
        >
          Former employee
        </span>
        <span style={{ color: 'var(--tst-text-2)' }}>
          {p.role_label} · {humanize(p.level)}
          {p.unit_name ? ` · ${p.unit_name}` : ''}
        </span>
      </div>
      <p className="tst-muted" style={{ margin: 0 }} data-testid="former-summary">
        Joined {p.start_date_label} · left {p.end_date_label} after {formatMonths(p.tenure_months)}{' '}
        · {p.reason_label}
        {p.rival_id !== null && (
          <>
            {' '}
            (<Link to={`/game/${saveId}/competitors/${p.rival_id}`}>{p.rival_name}</Link>)
          </>
        )}
      </p>
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        What you knew when they left. Read-only.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <Panel title="Skills" style={{ flex: '2 1 420px' }}>
          {GROUPS.map(([group, label]) => (
            <div key={group}>
              <div className="tst-muted" style={{ fontSize: 12, marginTop: 8 }}>
                {label}
              </div>
              {p.skills
                .filter((s) => s.group === group)
                .map((s) => (
                  <div className="tst-row" key={s.key}>
                    <span>{s.label}</span>
                    <AttributeRange range={s.range} label={s.label} />
                  </div>
                ))}
            </div>
          ))}
        </Panel>
        <Panel title="Personality and potential" style={{ flex: '1 1 300px' }}>
          <div className="tst-row">
            <span>Potential</span>
            <span>{p.potential_phrase}</span>
          </div>
          {p.personality.map((t) => (
            <div className="tst-row" key={t.key}>
              <span>{t.label}</span>
              <AttributeRange range={t.range} label={t.label} />
            </div>
          ))}
          {p.work_style && (
            <div className="tst-row">
              <span>Work style</span>
              <span>{humanize(p.work_style)}</span>
            </div>
          )}
          {p.interests && (
            <div className="tst-row">
              <span>Interests</span>
              <span>{p.interests.map(humanize).join(', ')}</span>
            </div>
          )}
          {p.noticed_tags.map((t) => (
            <div className="tst-row" key={t.key} data-testid="former-tag">
              <span>{t.label}</span>
              <span className="tst-muted">noticed {t.noticed_date_label}</span>
            </div>
          ))}
        </Panel>
      </div>
      <Panel title="History">
        {p.history.length === 0 && <p className="tst-muted">Nothing recorded.</p>}
        {p.history.map((h) => (
          <div className="tst-row" key={h.key} data-testid="former-history">
            <span className="tst-muted" style={{ width: 80 }}>
              {h.date_label}
            </span>
            <span style={{ flex: 1 }}>
              {h.title}
              {h.detail ? ` · ${h.detail}` : ''}
            </span>
          </div>
        ))}
      </Panel>
    </>
  );
}
