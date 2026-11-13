// Guide pages (M29, 42.1): what each system is for and where to start. Words only: what is
// open and why comes from the API.
import type { WhatNextItem } from '../hooks/onboarding';

export interface Guide {
  title: string;
  path: string; // the screen under /game/<save>/
  what: string;
  start: string[];
}

export const GUIDES: Record<string, Guide> = {
  inbox: {
    title: 'Inbox',
    path: 'inbox',
    what: 'Everything that happens to the company arrives here. Needs you holds what waits for your answer; the rest is for reading.',
    start: [
      'Answer what is under Needs you first: major and critical events stop Continue.',
      'Archive what you have read; bookmarked messages are never archived for you.',
    ],
  },
  overview: {
    title: 'Overview',
    path: 'overview',
    what: 'The company at a glance: cash, burn, runway, revenue and people, with What next.',
    start: ['Read What next each month.', 'Open Explain on a tile to see what moves it.'],
  },
  history: {
    title: 'History',
    path: 'history',
    what: 'Every month that has closed: the timeline, charts, storylines and your records.',
    start: ['Charts compare any two numbers over the years.'],
  },
  people: {
    title: 'People',
    path: 'people',
    what: 'Your staff: what you know of their skills (as ranges), morale, pay and tenure.',
    start: ['Open a person to see their profile and what you have learned about them.'],
  },
  recruitment: {
    title: 'Recruitment',
    path: 'recruitment',
    what: 'Searches, candidates, interviews and offers, and hiring plans that hire for you.',
    start: [
      'Open a search for the role you need, interview, then make an offer.',
      'A hiring plan lets a recruiter do this each month.',
    ],
  },
  org: {
    title: 'Org',
    path: 'org',
    what: 'Teams and departments, who leads them, what they work on, and executive seats.',
    start: ['Point a team at a product so it improves.', 'Give a seat authority to delegate.'],
  },
  offices: {
    title: 'Offices',
    path: 'org/offices',
    what: 'Where your people sit: offices in cities and regions, their seats and costs.',
    start: ['Open an office in a new region before selling there in earnest.'],
  },
  products: {
    title: 'Products',
    path: 'products',
    what: 'What you build and sell: quality, features, prices, customers and revenue.',
    start: ['Reach the launch bars, then launch.', 'Keep a team on every live product.'],
  },
  research: {
    title: 'Research',
    path: 'products/research',
    what: 'Research projects that move your products ahead of the market, and licences.',
    start: ['Start a project in the domain your products depend on most.'],
  },
  infrastructure: {
    title: 'Infrastructure',
    path: 'products/infrastructure',
    what: 'Data centres you own instead of renting compute, and the capacity you sell.',
    start: ['Compare a build with what you pay for cloud compute now.'],
  },
  hardware: {
    title: 'Hardware',
    path: 'products/hardware',
    what: 'Devices and servers: manufacturing contracts, assembly plants and their supply.',
    start: ['A hardware product needs a manufacturing source before it can launch.'],
  },
  markets: {
    title: 'Markets',
    path: 'products/markets',
    what: 'Each category and segment: demand, growth, prices and who sells there.',
    start: ['Find a segment that is growing and under-served.'],
  },
  competitors: {
    title: 'Competitors',
    path: 'competitors',
    what: 'Rival companies: their products, moves, leaders and what they might do next.',
    start: ['Open a rival to see its products and recent moves.'],
  },
  rankings: {
    title: 'Rankings',
    path: 'competitors/rankings',
    what: "Every January's league tables: where you stand among the industry.",
    start: ['Check where you rank after each January.'],
  },
  exploration: {
    title: 'Exploration',
    path: 'products/exploration',
    what: 'Finding minerals: desk studies, licences, surveys, drilling and feasibility studies.',
    start: [
      'A desk study tells you where to look; a licence lets you explore a block.',
      'Geologists run the work; each stage narrows what is really in the ground.',
    ],
  },
  mines: {
    title: 'Mines',
    path: 'products/mines',
    what: 'Building and running mines on feasible deposits, and selling or using their output.',
    start: ['Build where the feasibility study shows a margin at today’s prices.'],
  },
  refineries: {
    title: 'Refineries',
    path: 'products/refineries',
    what: 'Turning ore and feedstock into refined materials and wafers for chips.',
    start: ['A refinery near your mine cuts freight and secures supply.'],
  },
  fabs: {
    title: 'Fabs',
    path: 'products/fabs',
    what: 'Chip fabrication: process nodes, capacity, tools and foundry contracts.',
    start: ['Until you own a fab, a foundry contract makes your chips.'],
  },
  finance: {
    title: 'Finance',
    path: 'finance',
    what: 'Statements, the cap table, fundraising, debt, the board and deals.',
    start: ['Raise before runway is short: rounds take months.'],
  },
  group: {
    title: 'Group',
    path: 'finance/group',
    what: 'Your holding company and subsidiaries: mandates, stakes, transfers and listings.',
    start: ['Give each subsidiary a mandate; its CEO runs it within it.'],
  },
  world: {
    title: 'World',
    path: 'competitors/world',
    what: 'Countries, blocs and export controls: where you may sell and buy, and what it costs.',
    start: ['Check which rules bite your products and inputs before you expand.'],
  },
};

/** Where a What next item links (the same kinds as the COO's briefing, 17.3, plus guides). */
export function whatNextHref(saveId: string, item: WhatNextItem): string {
  const base = `/game/${saveId}`;
  switch (item.link_kind) {
    case 'event':
      return item.link_id ? `${base}/events/${item.link_id}` : `${base}/inbox`;
    case 'product':
      return item.link_id ? `${base}/products/${item.link_id}` : `${base}/products`;
    case 'person':
      return item.link_id ? `${base}/people/${item.link_id}` : `${base}/people`;
    case 'rival':
      return item.link_id ? `${base}/competitors/${item.link_id}` : `${base}/competitors`;
    case 'board':
      return `${base}/finance/board`;
    case 'guide':
      return `${base}/guide/${item.link_key ?? ''}`;
    case 'recruitment':
    case 'org':
    case 'finance':
      return `${base}/${item.link_kind}`;
    default:
      return `${base}/inbox`;
  }
}
