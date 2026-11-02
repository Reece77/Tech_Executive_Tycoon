import { Link } from 'react-router';
import type { Schemas } from '../api/client';
import { Panel } from './ScreenState';

type ActiveEffect = Schemas['ActiveEffectOut'];

/** Event modifiers still running (23.2, M10b): what each does, the event it came from, and
 * the months left. Nothing renders when none run. */
export function ActiveEffects({
  saveId,
  effects,
  title = 'Active effects',
}: {
  saveId: string;
  effects: ActiveEffect[];
  title?: string;
}) {
  if (effects.length === 0) return null;
  return (
    <Panel title={title} label="Active effects">
      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
        data-testid="active-effects"
      >
        {effects.map((e) => (
          <li
            key={e.modifier_id}
            className="tst-row"
            data-testid="active-effect"
            style={{ fontSize: 14 }}
          >
            <span>{e.text}</span>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              {e.event_id != null ? (
                <Link to={`/game/${saveId}/events/${e.event_id}`}>{e.source}</Link>
              ) : (
                e.source
              )}{' '}
              · {e.months_left} month{e.months_left === 1 ? '' : 's'} left
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
