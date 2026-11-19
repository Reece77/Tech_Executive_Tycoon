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
  family: {
    title: 'Family',
    path: 'people/family',
    what: 'Your partner and children: family time, the relationship, education, ratings as ranges and how ready each heir is to succeed you.',
    start: [
      'Give your family time each month: under 8 the relationship and closeness slip.',
      "Plan succession and the estate on your founder profile's Family tab.",
    ],
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
  automation: {
    title: 'Automation',
    path: 'automation',
    what: 'Hand any area of the business to a person: they act under a money limit, one-offs come to you, and a monthly digest says what they did.',
    start: [
      'Give an area to someone with a strong fit and enough energy; a weak owner makes visibly worse calls.',
    ],
  },
  equipment: {
    title: 'Equipment',
    path: 'products/equipment',
    what: "Lithography tools: ASML's generations, prices and order queue, your orders and their place as a range of months, the controls on who may receive them, and your own lithography programme.",
    start: [
      "A new buyer waits behind a year or more of rivals' orders; prepaying moves an order up, and a history of deliveries moves you up for good.",
      "Your own scanners are a decade-long bet: expensive, uncertain, and worse than ASML's at first.",
    ],
  },
  platforms: {
    title: 'Platforms',
    path: 'competitors/platforms',
    what: 'App stores and operating systems: who has the users and the developers, what each store charges, and the rules a store sets for your apps. Your own OS and store, when you build one, are run from here.',
    start: [
      'Your devices run Android unless you build an operating system: a thin catalogue costs them features.',
      "Apps sold through stores pay the stores' fees; from 2026 a store can remove an app, and you answer it as a critical event.",
    ],
  },
  power: {
    title: 'Power',
    path: 'products/power',
    what: 'Electricity for your data centres, fabs, mines and refineries: grid prices, carbon and outages by region, power contracts (PPAs) with generators, and from stage 4 plants of your own.',
    start: [
      'From 2026 a large data centre or fab waits in its grid queue for years in congested regions; a plant behind its meter that covers the whole load skips the queue.',
      'A PPA fixes the price of a volume for 5-20 years; energy you do not use still pays 70%.',
    ],
  },
  vehicles: {
    title: 'Vehicles',
    path: 'products/vehicles',
    what: 'Electric cars: EV markets by region, battery prices, subsidies, tariffs and approvals, the rival car makers, and your own cars, vehicle plants, battery cell plants and charging networks.',
    start: [
      'A car line is a product (Electric vehicles); set its pack, chemistry, charging, autonomy, platform and cells on its page here.',
      "Cells are the biggest cost a car's maker controls: from stage 4 a cell plant fed by your own lithium makes them at cost.",
    ],
  },
  medical: {
    title: 'Medical',
    path: 'products/medical',
    what: "Medical devices: wearables and diagnostics, imaging, surgical robots, implants and diagnostic software. Each needs clearance by region before it sells (510(k), De Novo or PMA in the US, CE marking in the EU), and payers' coverage and clinicians' trust before it sells widely.",
    start: [
      "Choose the device's intended use: its class and route follow. A 510(k) needs a predicate on the market and takes months; a PMA needs a pivotal study first and takes years.",
      'Evidence from studies shortens coverage decisions and speeds adoption; a better quality system means fewer recalls.',
    ],
  },
  robotics: {
    title: 'Robotics',
    path: 'products/robotics',
    what: 'Industrial robots and humanoids: installations, labour costs and makers by region, the humanoid era and its announcements, your robot lines, and robots in your own assembly and vehicle plants.',
    start: [
      'Robots in your own plants cut the line labour a unit: worth it where labour is dear (North America, Europe), barely in South and Southeast Asia.',
      'Humanoids sell only once their era arrives; your own AI model and accelerators lift their capability.',
    ],
  },
  pharma: {
    title: 'Pharma',
    path: 'products/pharma',
    what: 'Drug discovery to the generics cliff: programmes through preclinical work and Phase I-III trials at historical odds, filings with the FDA, EMA, PMDA and NMPA, prices by region and the IRA, plants and contract manufacturers, biotech licences and twelve big-pharma rivals.',
    start: [
      "About 8% of programmes entering Phase I reach approval, and it takes about a decade: run several, and stop the ones whose estimates disappoint. A molecule's true efficacy is never shown; each readout narrows its range.",
      'AI discovery (with a strong AI model) gives more candidates, a shorter preclinical stage and a modest lift in the early phases. When exclusivity ends, generics take most of a small molecule’s sales within a year.',
    ],
  },
  mobility: {
    title: 'Mobility',
    path: 'products/mobility',
    what: 'Robotaxis: cities where driverless service is approved, rival operators, and your own zones, fleets, depots, rides and incidents.',
    start: [
      'A robotaxi service is a product (Robotaxi services). Launch it, apply for a zone in an approved city, add L4 cars and a depot.',
      'Utilisation decides the economics: above the break-even rides a car a day a fleet earns; a serious incident suspends the zone.',
    ],
  },
  space: {
    title: 'Space',
    path: 'products/space',
    what: "Launch vehicles and reusability, launches and failures, cost a kg, your constellations (shells, coverage, capacity, payback), broadband subscribers and licences by region, and rivals' public launches and constellations.",
    start: [
      'A launch vehicle is a product (Launch services): set its design here and fly it from a launch site. Reusability research cuts its cost a kg; full reuse takes years.',
      'A constellation serves a Satellite broadband line: a region opens once a shell is complete over it and you hold a licence there. It is capital-heavy: expect most of a decade to pay back.',
    ],
  },
  regulation: {
    title: 'Regulation',
    path: 'competitors/regulation',
    what: 'Regulators by region: who is a designated gatekeeper, the duties that brings, investigations and their stages, fines, and the warning signs of a break-up. Your own position against each designation test is here too.',
    start: [
      'A warning comes a year before a designation; duties follow a few months after it.',
      'Each stage of an investigation comes to Needs you: settling early is cheaper than losing, and breaking a duty makes everything worse.',
    ],
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
    case 'automation': // M27a (40.8)
      return `${base}/${item.link_kind}`;
    default:
      return `${base}/inbox`;
  }
}
