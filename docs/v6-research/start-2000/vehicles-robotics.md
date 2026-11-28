# Vehicles and robotics (M50b): `backend/data/vehicles.yaml`, `backend/data/robotics.yaml`, `balance.yaml vehicles.bom.drive_cents`, 2000-2007

101 series filled (gap lister: 52 in vehicles.yaml, 48 in robotics.yaml, 1 in balance.yaml before; 0 after). Inserted
entries only: every 2008+ value is byte-identical (checked line by line: each changed line is the old line plus one
contiguous insertion). Tags as the files' own: S read this session, R recalled from the named source (not re-read),
D derived, A assumption. Before 2008 there was no EV industry: shares sit at or near 0, prices and divisors stay
positive.

## Vehicles

| Series | 2000-2007 values | Tags | Source / basis |
| --- | --- | --- | --- |
| `cpi` | 172.200, 177.067, 179.875, 183.958, 188.883, 195.292, 201.592, 207.342 | S | FRED CPIAUCNS annual, https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS |
| `car_sales` north_america (M) | 19.8, 19.6, 19.5, 19.2, 19.5, 19.7, 19.3, 18.9 | D | US FRED ALTSALES (S: 17.350 ... 16.089) + Canada 1.55-1.70 and Mexico 0.85-1.14 (R) |
| `car_sales` europe | 15.7, 15.6, 15.3, 15.2, 15.4, 15.5, 15.8, 16.0 | R | ACEA EU + EFTA (with the 2004 entrants) |
| `car_sales` east_asia | 8.7, 8.8, 9.4, 10.1, 10.4, 11.5, 12.5, 13.2 | D | CAAM China (2005-2007 R; 2000-2004 A on the later passenger-vehicle definition), JADA, KAMA, Taiwan (R) |
| `car_sales` SSEA / LatAm / Africa / Oceania | 2.1-3.8 / 2.4-4.0 (2002-2003 dip) / 0.9-1.5 / 0.87-1.15 | A, A, A, D | SIAM, ASEAN AF, Fenabrave/ADEFA, NAAMSA, FCAI (R) plus small A for other countries |
| `ev_share` | NA 0.0001 (2000) falling to 0.000005; Europe 0.00016 to 0.00003-0.00005; East Asia 0.00002 (2000-2001) then 0; rest 0 | A | EV1 (no sales after 1999, leases ended 2003), RAV4 EV, Ranger EV, PSA 106/Saxo électrique (to 2005), Think, G-Wiz, Hypermini (Wikipedia pages, R) |
| `chargers` (k) | NA 1.5 (2000) to 0.5 (2007); Europe 0.4; East Asia 0.1; rest 0 | A | California's 1990s points removed with the EV1s |
| `battery.pack_usd` (2023 $) | 2800, 2600, 2400, 2250, 2100, 1950, 1800, 1700 | A | Nykvist and Nilsson 2015's 2007-2009 estimates run back about 7% a year real; Wikipedia Lithium-ion battery (S): consumer cells about 3 Wh/$ in 2005 |
| `cell_share`, `lfp_share` | 0.70; 0.0 (2000, 2005) | A | held; LFP commercial from A123 (2006) |
| `world_cells_gwh` | 0.003, 0.001 x5, 0.002, 0.005 | A | Nissan Altra (Li-ion, about 200 cars), conversions, Tesla prototypes; other EVs lead-acid or NiMH |
| `km_per_kwh`, `range_expected_km` | 4.9, 100 (2000) | A | held at 2008's |
| `charge_expected_kw` | 7 (2000, 2006), 10 (2007) | A | 6.6 kW Magne Charge / Avcon AC; positive (the feature score divides by it) |
| `software_attach` | 0.0 | A | no paid car software |
| cell makers' `share` | CATL, BYD, SK, Samsung SDI 0; LG 0 to 2005, 0.02, 0.05; Panasonic/Sanyo 0.20 -> 0.35 | A | founding dates (R) |
| rivals' `shares` | Tesla, BYD, VW, GM 0; Toyota East Asia 0.10 to 2003; Stellantis (PSA) Europe 0.60 (2000) -> 0 (2005) | A | EV00 facts in the file |
| `subsidies` us_30d | $4,000 (2000), 3,000 (2002), 2,000 (2003), 4,000 (2004), 1,000 (2006), 0 (2007) | R | IRC 30 (EPAct 1992, phase-down, Working Families Tax Relief Act 2004) |
| `subsidies` fr_bonus | 0 from 2000-01 | A | the bonus began in 2008 |
| `tariffs` (7) | 2000-01 at the MFN rates (US 2.5%, EU 10%, Canada 6.1%) | R/V | as M50's 2008 rows |
| `balance.yaml vehicles.bom.drive_cents` | 450,000 (2000), 390,000 (2004) | A | the 2008-2015 fall run back, flattening |

## Robotics

| Series | 2000-2007 values | Tags | Source / basis |
| --- | --- | --- | --- |
| `cpi` | as vehicles | S | FRED CPIAUCNS |
| world installations (check) | 99, 78, 69, 81, 97, 120, 112, 114 k | S | Wikipedia, Industrial robot (IFR), https://en.wikipedia.org/wiki/Industrial_robot |
| `installations` NA (k) | 13.0, 10.8, 9.2, 12.6, 14.7, 19.5, 17.5, 18.0 | R | IFR World Robotics 2001-2008 (Americas less Brazil) |
| `installations` Europe | 27.5, 28.0, 23.5, 23.0, 27.5, 26.0, 30.0, 31.0 | R | IFR (Germany 10-14k) |
| `installations` East Asia | 55.0, 35.4, 33.9, 41.5, 49.1, 69.6, 58.4, 58.5 | D | Japan 47k ... 36k, Korea 4-14k, China 0.4-6.6k, Taiwan 2-4.6k (IFR, R) |
| `installations` rest | SSEA 1.8-4.5, LatAm 0.4-1.1, Africa 0.2-0.4, Oceania 0.3-0.5 | A | regions sum to the world total within 1% |
| `labour_usd` (anchors 2000, 2002, 2004, 2006) | NA 22.6-26.9; Europe 19.6, 21.0, 29.0, 30.8; East Asia 2.2-3.0; SSEA 1.0-1.3; LatAm 4.6, 3.3, 3.8, 5.9; Africa 1.2-1.8; Oceania 14.5-25.0 | D, D, A, A, R, A, A | BLS ILC (R); euro via FRED EXUSEU (S: 0.9234 ... 1.3709) |
| `density` (2000, 2004) | US 85, 100; Germany 155, 200; Japan 280, 290; SSEA 10, 14 | A | rising to 2008's IFR values |
| makers' `shares` (2000, some 2004) | FANUC/Yaskawa higher in East Asia (0.22/0.18); ABB, KUKA Europe 0.21, 0.26; UR and Estun 0 | A | Japan about 85% of East Asia's 2000 installations; UR founded 2005; Estun robots from about 2005 |

Humanoid and robotaxi series start after 2010 and need no pre-2008 entries (they did not exist: A).

## Could not check

- IFR's regional and country tables for 2000-2007 (ifr.org not opened; figures recalled, world totals S).
- Car sales outside the US (ACEA, CAAM, JADA, KAMA, SIAM, Fenabrave, NAAMSA, FCAI: all recalled), and China's
  pre-2005 passenger-vehicle definition break.
- Pre-2008 EV counts (no IEA series before 2010), pack prices before 2007 (BNEF starts 2010; Ziegler and Trancik's
  supplementary data not opened), BLS hourly compensation 2000-2007 and IFR robot density.
- **For the commodities lane:** `commodities_history.yaml battery_cells` must match `pack_usd x cell_share` in 2010
  dollars (the loader checks to 6 cents): 2000 1402.6, 2001 1302.5, 2002 1202.3, 2003 1127.1, 2004 1052.0,
  2005 976.8, 2006 901.7, 2007 851.6.
