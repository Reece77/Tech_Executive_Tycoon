// TanStack Query hooks for the living world (M28, formulas.md 41.7): World news with its
// filters and the chain companies by good. Kept beside hooks/api.ts so the lanes' hooks merge
// cleanly.
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap } from './api';

export type WorldNews = Schemas['WorldNewsOut'];
export type WorldNewsItem = Schemas['WorldNewsItemOut'];
export type WorldCompany = Schemas['WorldCompanyOut'];
export type WorldFacility = Schemas['WorldFacilityOut'];
export type Chain = Schemas['ChainOut'];
export type CompanyRef = Schemas['CompanyRefOut'];

export type NewsFilters = {
  company?: number;
  region?: string;
  good?: string;
  kind?: string;
};

export const NEWS_PAGE = 200; // items a page (M30: the server pages the feed)

export function useWorldNews(saveId: string, filters: NewsFilters, limit = NEWS_PAGE) {
  return useQuery({
    queryKey: ['saves', saveId, 'world-news', filters, limit],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/world-news', {
          params: { path: { save_id: saveId }, query: { ...filters, limit } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useChain(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'chain'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/saves/{save_id}/chain', { params: { path: { save_id: saveId } } }),
      ),
  });
}
