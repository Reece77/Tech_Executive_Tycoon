# Supply chain and chips, 2000-2007 (M50b)

Files: `backend/data/commodities_history.yaml`, `components_history.yaml`, `chain_companies.yaml`,
`nodes.yaml`, `equipment.yaml`. Tags are each file's own: V read this session from the named source,
D derived (method in the row's comment), R recalled from a named source (not re-read), A an assumption.
Every value from 2008 on is unchanged: a parse of each file with 2000-2007 keys removed equals `main`'s.

Sources read this session:

- USGS Mineral Commodity Summaries 2005, 2006, 2007, 2009, 2010 and 2012:
  `https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/<mineral>/<abbr>mcs05.pdf`
  (also `mcs06`, `mcs07`) and `.../<mineral>/mcs-2009-<abbr>.pdf` (also 2010, 2012). Tantalum is under
  `niobium/`, rare earths under `rare-earth/`.
- USGS Minerals Yearbook, lithium, 2000-2001 (`lithium/450401.pdf`), 2003, 2004, 2005 and 2006
  (`lithium/lithimyb03.pdf` to `lithimyb06.pdf`), 2007 (`lithium/myb1-2007-lithi.pdf`), at the same host.
- FRED, IMF monthly prices: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCOPPUSDM` (also
  `PTINUSDM` and `PNICKUSDM`), 2000-01 to 2007-12.
- Web search excerpts (tagged R, not primary): TSMC Form 6-K, 2Q04 and 4Q04 (installed capacity of
  4.8M 8-inch-equivalent wafers in 2004 and 5.95M planned for 2005); ASML's 2006 annual results release
  (23 immersion systems shipped in 2006, 36 to date) and its 2005 annual report (13 immersion tools to date).

## Commodity prices (`commodities_history.yaml`, annual years and the shocks' months)

| Good | 2000-2007 values | Source | Tags |
|---|---|---|---|
| quartz_hp | 8,250 held | the 2021 level held back (33.1), as M50 did | D |
| silicon_metal | 54.8, 50.5, 53.2, 61.3, 81.9, 76.2, 79.3, 113 ¢/lb | MCS 2005, 2009, 2010 (silicon metal, dealer import) | V |
| polysilicon | 35, 32, 28, 25, 32, 60, 150, 300 $/kg | Bernreuter, recalled: the 2001-2003 glut, solar demand from 2004, the spot squeeze from 2005 | R |
| gallium | 640, 640, 530, 411, 550, 538, 443, 530 $/kg | MCS 2005, 2009, 2010 (year-end, 7N) | V |
| germanium | 1250, 890, 620, 380, 600, 660, 950, 1240 $/kg | MCS 2005, 2007, 2010 (year-end, zone refined) | V |
| copper | 82.2, 71.6, 70.7, 80.7, 130.0, 166.8, 304.9, 322.8 ¢/lb | MCS 2005, 2009 (LME high grade) | V |
| tin | 5436, 4489, 4061, 4890, 8481, 7385, 8755, 14495 $/t | FRED PTINUSDM annual means | V |
| tantalum | 485, 82, 68, 62, 68, 76, 71, 82 $/kg Ta2O5 | MCS 2005, 2007, 2009, 2012 ($/lb, x 2.2046) | D |
| cobalt | 15.16, 10.55, 6.91, 10.60, 23.93, 15.96, 17.22, 30.55 $/lb | MCS 2005, 2009 (spot cathode) | V |
| lithium_carbonate | 1450, 1440, 1600, 1550, 1720, 2750, 4125, 6000 $/t | MYB: Chilean and import customs unit values 2000-2004; producers' prices 2005-2007 | V, D, R |
| ndpr_oxide | 7, 6.5, 6, 6.5, 8, 10, 15, 28 $/kg | Nd oxide FOB China (Metal-Pages and Lynas, recalled; Argus's 2002+ series is behind a paywall) | R |
| neon | 1.0 held | the pre-2022 index held back | A |
| nickel | 8631, 5970, 6783, 9630, 13821, 14778, 24126, 37136 $/t | FRED PNICKUSDM annual means (MCS 2005 to 2009 LME cash agree within 1%) | V |
| manganese | 2.08, 2.13, 2.00, 2.10, 2.52, 3.83, 2.81, 2.70 $/dmtu | MCS CIF US 46-48% x 8.0 / 9.18 (M50's ratio) | D |
| graphite | 1030, 870, 880, 1030, 810, 850, 880, 830 $/t | MCS flake import value x 1200 / 720 (M50's ratio) | D |
| battery_cells | 1402.6, 1302.5, 1202.3, 1127.1, 1052.0, 976.8, 901.7, 851.6 $/kWh | vehicles.yaml pack_usd x cell_share, 2010 dollars (the lead's values; the loader checks them) | D |

Shocks. The coverage check reads each shock's `points` as a series, so the five 2008 shocks (copper, tin,
nickel, cobalt, polysilicon) now start in January 2000. Their 2008-2009 points are unchanged, and the
2000-2007 months run on the shock path rather than the held annual value:

- copper, tin, nickel: FRED's IMF months each January, April, July and October, plus the peaks (copper
  May 2006, 365.6 ¢/lb; nickel May 2007, $51,783/t) (V).
- cobalt: the USGS annual means placed mid-year, with the Q1 2004 spike of about $28/lb (R).
- polysilicon: a mid-year path through the annual values above (R).
- new, tantalum: the 2000 coltan spike, about $35/lb in early 2000 to $220/lb at year-end (MCS 2005,
  V), back to $37/lb by the end of 2001 (V). The shape between those points is A.

## World supply (`chain_companies.yaml` world_supply, points interpolated linearly)

| Good | New points | Basis | Tags |
|---|---|---|---|
| quartz_hp, neon | 2000: 12,600 | 2010 less ten years of 4.7% growth | A |
| silicon_metal | 2000 1.25M, 2004 1.47M, 2007 1.68M t | USGS world silicon (MCS 2006, 2009; 2000 recalled) x 0.30, M50's 2008 ratio | D |
| polysilicon | 2000 14.8M, 2001 10.6M, 2004 15.6M, 2007 23.1M kg | SEMI wafer area (recalled) as ratios to 2010 | D (R inputs) |
| gallium | 2000 172k, 2002 103k, 2007 137k kg | USGS primary output x 182 / 106 (2007 from MCS 2009; 2000 and 2002 recalled) | D |
| germanium | 2000 80k, 2004 87k, 2007 100k kg | MCS 2006, 2009 world refinery; 2000 A (earlier editions use a narrower basis) | V, A |
| copper | 2000 14.8M, 2004 15.9M, 2007 18.0M t | ICSG refined copper | R |
| tin | 2000 270k, 2004 330k, 2007 350k t | ITRI refined tin | R |
| tantalum | 2000 1.59M, 2003 1.48M, 2006 1.57M kg Ta2O5 | MCS 2005, 2007 mine Ta x 1.22; 2000 A | V, A |
| cobalt | 2000 33k, 2003 48.4k, 2005 57.9k, 2007 65.5k t | MCS 2005, 2007, 2009 mine; 2000 R | V, R |
| lithium_carbonate | 2000 80k, 2004 107.5k, 2007 137.3k t LCE | MCS 2006, 2009 Li x 5.32; 2000 R | V, R |
| ndpr_oxide | 2000 15.7M, 2004 19.2M, 2006 23.1M kg | USGS REO (MCS 2006, 2007; 2000 R) x 25,000 / 133 | D |
| nickel | 2000 1.25M, 2003 1.40M, 2006 1.55M, 2007 1.66M t | MCS 2005, 2007, 2009 mine; 2000 R | V, R |
| manganese | 2000 7.0M, 2003 8.2M, 2006 11.0M, 2007 12.6M t | the same | V, R |
| graphite | 2000 900k, 2003 960k, 2005 1.06M t | MCS 2007; 2003 rebased for the 2004 revision; 2000 A | V, D, A |
| battery_cells | 2000: 1,000 kWh | no EV lithium-ion cells (hybrids used NiMH); a token value because the loader needs positive points | A |

## Components (`components_history.yaml`, index January 2010 = 1.0)

Each good has a 2000-01 anchor, its own trend held back ten years (D): server 2.3021, GPU 2.8680,
device_bom 1.5041, server_bom 1.6702, equipment 1.2239, foundry_wafer 0.7441, vehicle_bom 1.0782.
euv_tools is flat at 1.0 (A: EUV was research only). The bends (A, with R context): server components
15% under trend in October 2001 (the DRAM collapse) and back on trend by January 2003. Foundry wafers
10% over trend in September 2000 (the capacity crunch), 15% under in December 2001 (the slump) and back
by January 2003. Vehicle BOM about 3% over trend in September 2004 (steel roughly doubled in 2004).

## Foundries (`nodes.yaml` capacity, thousand 12-inch-equivalent wafers a month)

| Foundry | New points | Basis | Tags |
|---|---|---|---|
| TSMC | 2000 126, 2004 178 | 3.4M (2000, recalled) and 4.8M (2004, 6-K via search) 8-inch-eq a year / 12 / 2.25 | R/D |
| Samsung | 2000 40, 2005 70 | System LSI logic; foundry open to customers from 2005 | A |
| Intel | 2000 250 | an IDM's logic capacity, below 2008's 330 | A |
| GlobalFoundries | 2000 0 | AMD's own fabs until the March 2009 spin-off | A |
| UMC | 2000 95, 2004 130 | about 2.6M 8-inch-eq after the 2000 five-in-one merger (recalled); 2004 between | R/D, A |
| SMIC | 2000 0, 2001 2, 2004 45 | founded April 2000; first wafers September 2001; about 100k 8-inch a month by 2004 | R, A |

Process nodes are not extended: the node list starts at 65 nm (generation 0), and 180, 130 and 90 nm
(2000, 2001, 2004) would need code that renumbers generations. See the follow-ups in the report.

## Lithography (`equipment.yaml`)

- duv_immersion shipments: 0 in 2000-2003 (A), 3 in 2004 (A), 10 in 2005 (D: 13 to date at the end of
  2005, R), 23 in 2006 (R: ASML's 2006 release), 38 in 2007 (V: 20-F 2009 KPI table). Uptime 0.95 and
  price $40M held back to 2000 (A). Nikon's ArFi: 0 to 2005, 3 in 2006 and 8 in 2007 (A; its first
  immersion tool, the NSR-S609B, shipped in 2006, R).
- euv_low: 0 shipments 2000-2007 (A; 20-F 2009, V, has no NXE before 2010); uptime 0.30 held back to 2000
  (A: the loader needs uptime above 0).

## Could not check

- Polysilicon spot prices 2000-2007 (Bernreuter's series was not re-read) and SEMI wafer area by year.
- Nd oxide FOB China prices 2000-2007 (Argus's series is paywalled).
- World output in 2000 for silicon, gallium, germanium, cobalt, lithium, rare earths, nickel, manganese and
  graphite: the MCS 2001-2003 PDFs were not reachable (the old minerals.usgs.gov paths return HTML; UNT's
  archive returned 503), so these 2000 points are recalled or assumed.
- ICSG refined copper and ITRI refined tin by year.
- TSMC's 2000 and UMC's 2000-2004 capacity; Samsung's and Intel's logic capacity (no public series).
- ASML's 2004-2005 immersion units by year (only the cumulative 13 to date); Nikon's ArFi units.
- The cobalt Q1 2004 peak and the shapes of the polysilicon and tantalum paths between their anchors.
