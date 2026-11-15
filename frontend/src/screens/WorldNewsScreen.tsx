// World news (M28, formulas.md 41.7): rivals' deals, capacity moves, mothballings, executive
// moves and regional cycles, filterable by company, region, good and kind, each linked to its
// companies. Filters live in the URL so a company page can link to its own news.
import { Button, Select } from '@mantine/core';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { CompanyLink } from '../components/CompanyLink';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  NEWS_PAGE,
  useWorldNews,
  type CompanyRef,
  type NewsFilters,
  type WorldNews,
} from '../hooks/world';

const FILTERS = ['company', 'region', 'good', 'kind'] as const;

export function WorldNewsScreen() {
  const { saveId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const company = params.get('company');
  const filters: NewsFilters = {
    company: company ? Number(company) : undefined,
    region: params.get('region') ?? undefined,
    good: params.get('good') ?? undefined,
    kind: params.get('kind') ?? undefined,
  };
  const [limit, setLimit] = useState(NEWS_PAGE);
  const news = useWorldNews(saveId, filters, limit);
  const set = (key: (typeof FILTERS)[number], value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
    setLimit(NEWS_PAGE);
  };
  if (news.error) return <LoadError title="Could not load World news" error={news.error} />;
  if (!news.data) return <Loading />;
  return (
    <WorldNewsBody
      saveId={saveId}
      n={news.data}
      params={params}
      onSet={set}
      onMore={() => setLimit(limit + NEWS_PAGE)}
    />
  );
}

export function WorldNewsBody({
  saveId,
  n,
  params,
  onSet,
  onMore,
}: {
  saveId: string;
  n: WorldNews;
  params: URLSearchParams;
  onSet: (key: (typeof FILTERS)[number], value: string | null) => void;
  onMore?: () => void;
}) {
  const options = {
    company: n.companies.map((c) => ({ value: String(c.company_id), label: c.name })),
    region: n.regions.map((r) => ({ value: r.key, label: r.label })),
    good: n.goods.map((g) => ({ value: g.key, label: g.label })),
    kind: n.kinds.map((k) => ({ value: k.key, label: k.label })),
  };
  return (
    <>
      <ScreenTitle
        aside={
          <Link
            to={`/game/${saveId}/competitors/world`}
            style={{ marginLeft: 'auto', fontSize: 13 }}
          >
            World
          </Link>
        }
      >
        World news
      </ScreenTitle>
      {!n.started && (
        <p className="tst-muted" style={{ fontSize: 13 }} data-testid="world-not-started">
          Miners, refiners and foundries run as companies from January 2026.
        </p>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {FILTERS.map((key) => (
          <Select
            key={key}
            label={key === 'kind' ? 'Kind' : key[0].toUpperCase() + key.slice(1)}
            placeholder="All"
            clearable
            searchable
            size="xs"
            w={200}
            data={options[key]}
            value={params.get(key)}
            onChange={(v) => onSet(key, v)}
            data-testid={`news-filter-${key}`}
          />
        ))}
      </div>
      <Panel title={`${n.total} items`} testId="world-news">
        {n.items.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12 }}>
            Nothing yet.
          </p>
        ) : (
          n.items.map((x) => (
            <div key={x.news_id} style={{ fontSize: 13, padding: '3px 0' }} data-testid="news-item">
              <span className="tst-muted">{x.date_label}</span>{' '}
              <strong style={{ fontWeight: 600 }}>{x.kind_label}</strong> {x.message}
              {(x.company || x.other || x.good || x.region) && (
                <span className="tst-muted" style={{ fontSize: 12 }}>
                  {' '}
                  ·{' '}
                  {[x.company, x.other]
                    .filter((c): c is CompanyRef => c !== null && c !== undefined)
                    .map((c) => (
                      <span key={c.company_id} style={{ marginRight: 6 }}>
                        <CompanyLink saveId={saveId} companyId={c.company_id} name={c.name} />
                      </span>
                    ))}
                  {x.good ? `${x.good.label} ` : ''}
                  {x.region ? x.region.label : ''}
                </span>
              )}
            </div>
          ))
        )}
        {n.items.length < n.total && onMore && (
          <Button size="xs" variant="subtle" mt={6} onClick={onMore} data-testid="news-more">
            Show more ({n.total - n.items.length} older)
          </Button>
        )}
      </Panel>
    </>
  );
}
