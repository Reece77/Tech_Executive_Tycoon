import { Link, useParams } from 'react-router';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { useUnlocks } from '../hooks/onboarding';
import { GUIDES } from '../lib/guides';

// A guide page per system (M29, 42.1): /game/<save>/guide/<key>, and /guide for them all.
export function GuideScreen() {
  const { saveId = '', guideKey } = useParams();
  const unlocks = useUnlocks(saveId);
  if (unlocks.isPending) return <Loading />;
  if (unlocks.error) return <LoadError title="Could not load the guide" error={unlocks.error} />;
  const systems = unlocks.data.systems;
  const guide = guideKey ? GUIDES[guideKey] : undefined;
  const system = systems.find((s) => s.key === guideKey);

  if (!guide || !system) {
    return (
      <>
        <ScreenTitle>Guide</ScreenTitle>
        <Panel title="Every system" label="Guides">
          {systems.map((s) => (
            <div key={s.key} className="tst-row">
              <Link to={`/game/${saveId}/guide/${s.key}`}>{s.label}</Link>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {s.unlocked ? 'Open' : 'Not yet'}
              </span>
            </div>
          ))}
        </Panel>
      </>
    );
  }
  return (
    <>
      <ScreenTitle>{guide.title}</ScreenTitle>
      <Panel title="What it is" label="What it is" testId="guide-page">
        <p style={{ marginTop: 0 }}>{guide.what}</p>
        <p className="tst-muted" style={{ fontSize: 13 }} data-testid="guide-status">
          {system.unlocked
            ? `Open${system.reason ? ` because ${system.reason}` : ''}${system.since_label ? ` (since ${system.since_label})` : ''}.`
            : 'Not open yet: it appears in the side bar when it becomes relevant.'}
        </p>
        <h3 className="tst-ptitle">Where to start</h3>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {guide.start.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p>
          <Link to={`/game/${saveId}/${guide.path}`} data-testid="guide-open">
            Open {guide.title}
          </Link>
          {' · '}
          <Link to={`/game/${saveId}/guide`}>Every guide</Link>
        </p>
      </Panel>
    </>
  );
}
