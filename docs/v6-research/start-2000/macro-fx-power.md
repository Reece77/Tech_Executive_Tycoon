# Macro, currencies and power: 2000-2007 (M50b)

Files: `backend/data/macro_history.yaml`, `fx_history.yaml`, `power_history.yaml`, `power.yaml`
(`compute_index.yaml` had no gap). Every row from 2008 on is unchanged (checked by parsing the
files before and after and comparing every key from 2008). `first_year` moves from 2008 to 2000 in
`macro_history.yaml` and `fx_history.yaml`, because their validators and index offsets need it.
Inline maps (`gdp`, `fx`, `generation`, `grid_intensity`, `queue_months`) gained entries at the
front of the existing line. Europe's carbon map had its first key move to a new line.

## Macro (`macro_history.yaml`)

| Series | 2000-2007 | Source | Tag |
|---|---|---|---|
| base_rate | monthly, 96 values | FRED FEDFUNDS, https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS (fetched 2026-11-28; the 2008-2009 rows match the file) | V |
| confidence | monthly, 96 values | FRED UMCSENT, same URL with `?id=UMCSENT` | V |
| climate | monthly, 96 values | 0.90 x the quarter's US venture dollars / $5.45B (MoneyTree, later Thomson Reuters vintage, recalled, about +/-10%) | D (from R) |
| gdp (7 regions) | 2000 and 2004 anchors | IMF WEO, recalled and summed by country, as M50 did | R |

How the climate was derived:

- **Quarterly dollars, in $B:** 2000: 28.0, 27.6, 26.9, 22.2 (a total of $104.7B, the peak). 2001: 14.0, 11.0, 7.8, 7.8. 2002: 6.0, 5.6, 5.1, 5.2. 2003: 4.6, 4.9, 4.9, 5.3.
- **Annual dollars from 2004, in $B:** 2004 22.5, 2005 23.0, 2006 26.8, 2007 30.9. I could not recall these years' quarters.
- **Interpolation:** linear between mid-quarter points (mid-year points from 2004). Mid-2007's 1.28 eases down to M50's 1.05 in January 2008, so the two series join without a seam (A).
- **The cap:** the uncapped values are 4.62 to 3.21 through 2000 and 2.76 to 1.82 from January to May 2001. They are capped at 1.8, the upper bound of `balance.yaml` `macro.climate.bounds`. Without the cap, ARR multiples would be about 4.6x in 2000. `MacroHistory` itself only requires the climate to be positive. The uncapped derivation is recorded in the file's comment.
- **The resulting path:** 1.80 to May 2001, then 1.29 by August 2001 and a 2002-2003 trough of 0.76-0.99. It recovers to 0.89-1.01 in 2004-2005 and 1.03-1.28 in 2006-2007.

GDP totals: about $33.5T in 2000 (world about $34T) and $42.6T in 2004 (world about $44T). The
2004 anchor captures the dollar's 2002-2007 fall.

## Currencies and policy rates (`fx_history.yaml`)

All 11 currencies and all 12 policy rates are monthly, 2000-01 to 2007-12, tag S. They come from the
same FRED series as the existing rows (EXUSEU, EXUSUK, EXSZUS, EXCHUS, EXJPUS, EXKOUS, EXINUS,
EXBZUS, EXMXUS, EXUSAL, EXSFUS; FEDFUNDS, ECBDFR daily averaged by calendar month, and the
IRSTCI01*/IR3TIB01CN rates), fetched 2026-11-28. They are rounded the way the file's 2008-2009
rows are; that rounding reproduces those rows exactly. India's rate uses 2 decimals rather than
0, because 2000-2001 has 7.5. FRED's China 3-month rate has no value for January 2006. It is filled
with the mean of December 2005 and February 2006 (D, noted on the row). The EUR/USD annual means
are 0.923 (2000), 0.896, 0.945, 1.132, 1.244, 1.245, 1.256 and 1.371 (2007), matching the brief.

## Power

| Series | Added | Source | Tag |
|---|---|---|---|
| power_history (7 regions) | 2000-2007 at each region's 2008 level | as M50: sources no better than for 2008 | S (NA, by definition) / A |
| cpi | 2000-2007 annual | FRED CPIAUCNS annual means (172.2 to 207.342) | S |
| fx EUR / USD | 2000-2007 / 2000 | FRED EXUSEU annual means, inverted / by definition | S |
| gas: NA | 2000-2007 | FRED AHHNGSP (4.31 ... 6.97) | S |
| gas: Europe, East Asia | 2000-2007 | World Bank CMO Historical Data Annual (nominal; Natural gas Europe, Japan LNG), read this session: https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Annual.xlsx | S |
| gas: other 4 regions | 2000-2007 | the file's rules (LNG x 0.9; Henry Hub x 2) | A |
| generation (7) | 2000-2007 | OWID energy-data CSV (Ember/EI), the same countries and divisors as 2008, read this session | D |
| grid_intensity (7) | 2000, 2004 | OWID carbon_intensity_elec, the same weighting as 2008 | D |
| queue_months (7) | 2000 | North America 20 (QU24: under 2 years for projects built 2000-2007); the others hold 2008's value | S/D, A |
| Europe carbon | 2000-2004 0.0; 2005 18.0, 2006 17.0, 2007 0.7 EUR | the EU ETS started in 2005; phase I spot prices (EEA and Point Carbon, recalled) | A / R |
| capex: gas | 2000 $460 (1999$), 2004 $560 | AEO2001 and AEO2005 conventional combined cycle (recalled, +/-15%) | R |
| capex: solar_storage | 2000 $13,030 (2000$) | Tracking the Sun PV about $9/W x 1.448 (SL24's hybrid ratio) | D (from R) |
| capex: wind | 2000 and 2004 $1,300 (2008$) | LBLW08 2001-2004 trough (recalled) | R |
| capex: nuclear | 2000 $2,000 (2002$) | MIT, The Future of Nuclear Power (2003) (recalled) | R |

## Could not check

- MoneyTree quarterly venture dollars for 2000-2003 and the annual totals for 2004-2007. pwcmoneytree.com was not opened. Contemporaneous press releases (via search) give lower, unrevised figures: Q2 2000 $19.8B, 2001 $41B, 2002 $21.2B, 2003 $18.9B. The climate is capped, so only the 2001-2007 levels depend on these figures.
- IMF WEO regional GDP for 2000 and 2004 (imf.org not opened; recalled).
- Plant capex for 2000 and 2004 (AEO2001/2005, LBNL, MIT; recalled).
- EU ETS phase I annual prices for 2005-2007 (recalled).
- Regional power price ratios for 2000-2007 (held at 2008's, A, as M50 held 2008 at 2010's).
