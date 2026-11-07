// Rival profile (M5): style, tiles (staff and revenue in your markets, money, stance),
// products by segment with what is running, key people with your ranges and "Poach from",
// and recent moves (approaches to your people in orange). Every value comes from the API.
import { Alert, Button } from '@mantine/core';
import { Link, useNavigate, useParams } from 'react-router';
import { AttributeRange } from '../components/AttributeRange';
import { KpiTile } from '../components/KpiTile';
import { RivalDealPanel } from '../components/RivalDealPanel';
import { RivalLeaderPanel } from '../components/RivalLeaderPanel';
import { Term } from '../components/Term';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { useOpenSearch, useRival, type RivalProfile } from '../hooks/api';
import {
  formatMoneyShort,
  formatMoneyWhole,
  formatWhole,
  humanize,
  scoreNote,
} from '../lib/format';
import { MoveTag, ProductMarkets, StartupChip, StyleChip } from '../lib/rivals';

export function RivalScreen() {
  const { saveId = '', rivalId = '0' } = useParams();
  const rival = useRival(saveId, Number(rivalId));
  if (rival.error) return <LoadError title="Could not load the rival" error={rival.error} />;
  if (!rival.data) return <Loading />;
  return <RivalBody saveId={saveId} r={rival.data} />;
}

function RivalBody({ saveId, r }: { saveId: string; r: RivalProfile }) {
  const open = useOpenSearch(saveId);
  const navigate = useNavigate();
  const poach = (role: string) =>
    open.mutate(
      { role, channel: 'poach', rival_id: r.company_id },
      { onSuccess: (s) => navigate(`/game/${saveId}/recruitment?search=${s.search_id}`) },
    );
  return (
    <>
      <ScreenTitle
        aside={
          <Link to={`/game/${saveId}/competitors`} style={{ marginLeft: 'auto', fontSize: 13 }}>
            All competitors
          </Link>
        }
      >
        <span
          style={{ display: 'inline-flex', gap: 10, alignItems: 'center' }}
          data-testid="rival-name"
        >
          {r.name}
          {r.is_startup && <StartupChip />}
          <StyleChip personality={r.personality} label={r.personality_label} />
        </span>
      </ScreenTitle>
      <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
        {r.style_text} Founded {r.founded_label}.{r.failed ? ' Closed.' : ''}
      </p>
      <RivalLeaderPanel saveId={saveId} rivalId={r.company_id} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <KpiTile
          term="kpi.rival_staff"
          label="Staff in your markets"
          value={`~${formatWhole(r.staff_in_your_markets)}`}
          note={`~${formatWhole(r.staff_estimate)} in all`}
        />
        <KpiTile
          term="kpi.rival_revenue"
          label="Revenue in your markets"
          value={formatMoneyShort(r.revenue_in_your_markets_cents)}
          note="a month, from public prices"
        />
        <KpiTile term="kpi.rival_money" label="Money" value={r.money_label ?? '—'} small />
        {r.score && (
          <KpiTile
            term="kpi.company_score"
            label="Company score"
            value={String(r.score.score)}
            note={scoreNote(r.score)}
            testId="rival-score"
          />
        )}
        <KpiTile
          term="kpi.rival_stance"
          label="Stance"
          value={r.stance}
          note={r.stance_reason}
          small
          testId="rival-stance"
        />
      </div>
      <RivalDealPanel saveId={saveId} companyId={r.company_id} />
      <Panel title="Products">
        <ProductMarkets products={r.products} />
        <table className="tst-table" aria-label="Rival products">
          <thead>
            <tr>
              <th>
                <Term term="name">Product</Term>
              </th>
              <th>
                <Term term="segment">Segment</Term>
              </th>
              <th>
                <Term term="quality">Quality</Term>
              </th>
              <th>
                <Term term="feature_score">Features</Term>
              </th>
              <th>
                <Term term="brand">Brand</Term>
              </th>
              <th>
                <Term term="price">Price</Term>
              </th>
              <th>
                <Term term="customers">Customers</Term>
              </th>
              <th>
                <Term term="running_now">Running now</Term>
              </th>
            </tr>
          </thead>
          <tbody>
            {r.segments.map((s) => (
              <tr key={`${s.product_id}-${s.segment}`} data-testid="rival-segment">
                <td>{s.product_name}</td>
                <td>
                  {s.segment_label}
                  {s.shared_with_player && (
                    <span style={{ color: 'var(--tst-link)', fontSize: 12 }}> · you sell here</span>
                  )}
                </td>
                <td className="tst-num">{formatWhole(s.quality)}</td>
                <td className="tst-num">{formatWhole(s.feature_score)}</td>
                <td className="tst-num">{formatWhole(s.brand)}</td>
                <td className="tst-num">
                  {s.price_cents === null ? '—' : formatMoneyWhole(s.price_cents)}
                </td>
                <td className="tst-num">{formatWhole(s.customers)}</td>
                <td>
                  {s.running ? (
                    `${s.running} until ${s.running_until_label ?? ''}`
                  ) : (
                    <span className="tst-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
        <Panel
          title="Key people"
          style={{ flex: '2 1 480px', display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {r.key_people.length === 0 && <span className="tst-muted">Nobody left to poach.</span>}
          {r.key_people.map((k) => (
            <div key={k.person_id} className="tst-row" data-testid="key-person">
              <span style={{ display: 'flex', flexDirection: 'column' }}>
                <strong>{k.name}</strong>
                <span className="tst-muted" style={{ fontSize: 12 }}>
                  {humanize(k.level)} {k.role_label.toLowerCase()} · {k.potential_phrase}
                </span>
              </span>
              <span style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                {k.top_skills.map((a) => (
                  <span key={a.key} style={{ fontSize: 12 }}>
                    {a.short_label} <AttributeRange range={a.range} label={a.label} />
                  </span>
                ))}
              </span>
            </div>
          ))}
          {!r.failed && r.key_people.length > 0 && (
            <>
              <Button
                size="compact-sm"
                loading={open.isPending}
                onClick={() => poach(r.key_people[0]?.role ?? 'software_engineer')}
                data-testid="poach-rival"
              >
                Poach from {r.name} · {r.poach_energy} energy
              </Button>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                Their people arrive as candidates next month and ask 1.3× their salary; leaving an
                employer makes them harder to win. A builder who leaves costs {r.name} quality.
              </span>
            </>
          )}
          {open.error && <Alert color="red">{open.error.message}</Alert>}
        </Panel>
        <Panel
          title="Recent moves"
          style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          {r.recent_moves.length === 0 && (
            <span className="tst-muted">No moves in the last two years.</span>
          )}
          {r.recent_moves.map((m, i) => (
            <span
              key={i}
              style={{
                fontSize: 13,
                display: 'flex',
                gap: 8,
                color: m.approach ? 'var(--tst-warn)' : undefined,
              }}
              data-testid="rival-move"
            >
              <span className="tst-num tst-muted" style={{ flex: 'none' }}>
                {m.date_label}
              </span>
              <MoveTag tag={m.tag} />
              {m.detail}
            </span>
          ))}
        </Panel>
      </div>
    </>
  );
}
