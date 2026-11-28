## Entrants founded 2000-2007 (`entrants.yaml`)

M50b, 2026-11-28 (the brief's "Defaults for 2000", item 3: entrants arrive at their founding dates). 17 entrants appended to the end of `entrants.yaml` (list index is the `entrants` stream key, so nothing existing moved). Each is founded only when a game reaches exactly its year and month (`founding_turn`, `found_entrants`), so a game begun in 2008 or 2010 never founds one and stays identical to `main`. Tags as the other dossiers: **S** fetched this session, **R** recalled from the named source (not re-read), **A** an assumption with its basis. Months and listing dates are from en.wikipedia.org pages read this session (S); first money and staff are A, on M50's scale (a founding team of 2-8, the cash of a first angel or venture round).

| Entrant | Founded | Tag | Category, segments | Personality | Cash, staff | Listed from | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fortinet | October 2000 | S year, A month | cybersecurity: smb, mid_market, enterprise | premium | $10M, 8 | November 2009 (S) | page gives "founded in 2000"; about $10M first funding A |
| LinkedIn | December 2002 | S | consumer_apps: consumer | fast_follower | $4.7M, 6 | May 2011 (S) | launched 5 May 2003; Sequoia's Series A about $4.7M (R) |
| MySpace | August 2003 | S | consumer_apps: consumer | aggressive | $1M, 5 | (private) | launched 1 August 2003 inside eUniverse (A cash); News Corp bought it July 2005 (R) |
| Skype | August 2003 | S | consumer_apps: consumer, region europe | cost_leader | $0.25M, 4 | (private) | first release 29 August 2003; eBay bought it 2005 (R) |
| Splunk | October 2003 | S | dev_tools: mid_market, enterprise | fast_follower | $5M, 5 | April 2012 (S, from the cited NYT date) | log and machine data search for IT teams |
| Yelp | October 2004 | S | consumer_apps: consumer | fast_follower | $1M, 3 | March 2012 (S) | $1M from Max Levchin (R) |
| Palo Alto Networks | March 2005 | S | cybersecurity: mid_market, enterprise | premium | $9M, 6 | July 2012 (S) | Series A about $9M (R) |
| Workday | March 2005 | S | b2b_saas: mid_market, enterprise | premium | $15M, 8 | October 2012 (S) | Duffield and Bhusri's own money and Greylock, about $15M (R) |
| Box | April 2005 | S year, A month | b2b_saas: smb, mid_market | aggressive | $0.35M, 2 | January 2015 (S) | Mark Cuban's early money about $0.35M (R) |
| Etsy | June 2005 | S | consumer_apps: consumer | cost_leader | $0.315M, 3 | April 2015 (S) | angel round about $0.3M (R) |
| Reddit | June 2005 | S | consumer_apps: consumer | cost_leader | $12K, 2 | March 2024 (S) | Y Combinator's first batch, $12K (R); Condé Nast bought it October 2006 (R) |
| Shopify | June 2006 | S | b2b_saas: smb | fast_follower | $0.2M, 3 | May 2015 (S) | the founders' Snowdevil store dates from 2004; Shopify launched June 2006 |
| Mint | September 2006 | S year, A month | fintech: consumer | aggressive | $0.75M, 3 | (private) | page gives 2006 only; launched at TechCrunch40, September 2007 (R); Intuit bought it 2009 (R) |
| Tumblr | February 2007 | S | consumer_apps: consumer | cost_leader | $0.75M, 2 | (private) | Yahoo bought it 2013 (R) |
| Dropbox | May 2007 | S | consumer_apps: consumer | aggressive | $15K, 2 | March 2018 (S) | Evenflow, Inc.; Y Combinator's seed (amount A, YC's then $15K) |
| Zendesk | October 2007 | S year, A month | b2b_saas: smb, mid_market, region europe | fast_follower | $0.5M, 3 | May 2014 (S year, A month) | founded in Copenhagen |
| Zuora | October 2007 | S year, A month | b2b_saas: mid_market, enterprise | fast_follower | $6.5M, 5 | April 2018 (S) | Benchmark's Series A about $6.5M (R) |

### Choices

- **Social networks are consumer apps.** `social` is a media-family category, which only scheduled rivals sell (`Category.media`: "a startup never enters them"), so MySpace, Reddit and Tumblr are `consumer_apps`, as M50 placed WhatsApp. Media, telecom and finance families were avoided for the same reason.
- **Skipped as already present:** Twitter, Spotify, YouTube and Netflix (incumbents), Hulu (a Disney product), Facebook, GitHub, Atlassian, Salesforce.
- **Skipped, Palantir (May 2003):** it is a `government.yaml` prime; `awards._company_by_name` would attach the prime's contract wins to a rival company of the same name in a 2000 game, an interaction this lane should not decide alone.
- **Skipped for scope:** 37signals/Basecamp (founded 1999), Hulu (2007, a media product), Twilio and other 2008-2009 founders (M50's range).
- `listed_from` follows the real listing, as M50's entries do; companies acquired before listing (MySpace, Skype, Mint, Tumblr) have none.

### Could not check

- Founding months for Fortinet, Box, Mint, Zendesk and Zuora (the pages give the year only): A, as above.
- First-round amounts (recalled, R or A; no S-1 re-read).
- Real exits (MySpace 2005, Skype 2005, Reddit 2006, Mint 2009, Tumblr 2013, LinkedIn 2016, Zendesk 2022, Splunk 2024): `EntrantDef` has no exit field, so entrants run on as independents. A follow-up if the lane wants history-following exits.
- The full loader cross-check (`load_all`) could not run while other data files were mid-edit by concurrent sessions (history-gap errors in other files); the entrants' own checks (names unique against incumbents, entrants and generated names; personalities; categories; segments; regions) were run by hand and pass, and `EntrantsFile` validates.
