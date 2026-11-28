## Policy: regulation, government and geopolitics (M50b, 2000-2007)

Files: `backend/data/regulation.yaml`, `backend/data/government.yaml`, `backend/data/countries.yaml`.
Only inserted entries; every value from 2008 on is unchanged (word diff shows no removals). Gap lister: `GAPS 0`.

### government.yaml

| Series | 2000-2007 values | Tag | Source |
|---|---|---|---|
| `cpi` (8 years) | 172.200, 177.067, 179.875, 183.958, 188.883, 195.292, 201.592, 207.342 | S | FRED CPIAUCNS monthly 2000-2007, averaged in this session: https://fred.stlouisfed.org/series/CPIAUCNS |
| `defence_usd_bn` (12 governments, every year) | e.g. US 320.1 (2000), 331.8, 378.5, 440.5, 493.0, 533.2, 558.3, 589.6 (2007); China 22.2 to 62.1; UK 39.3 to 73.4 | S (rest_of_eu D) | SIPRI-Milex-data-1949-2024_2.xlsx, sheet Current US$, downloaded and read this session (its 2008 column matches M50's values): https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2024_2.xlsx. rest_of_eu = EU-27 sum less France and Germany (65.1 in 2000, 120.7 in 2007) |
| `civil_it_usd_bn` (US) | 41.2, 44.4, 44.8, 53.0, 59.0, 60.5, 62.1, 64.0 | S 2000-2002 and 2007; R 2003-2005; D 2006 | OMB Analytical Perspectives FY2002 ch. 11 (total all IT, read): https://www.govinfo.gov/content/pkg/BUDGET-2002-PER/html/BUDGET-2002-PER-11-1.htm; FY2007 ch. 5-7 ("about $64 billion", "nearly 3 percent" over FY2006, read): https://www.govinfo.gov/content/pkg/BUDGET-2007-PER/html/BUDGET-2007-PER-5-7.htm; FY2004 and FY2006 figures from search extracts. 2006 = 64 / 1.03 |
| `clearances` p90_days | Secret 240 (2000), 240 (2004), 180 (2006); Top Secret 450, 480, 400 | A | the 2000-2005 DSS backlog (GAO-01-465, GAO-05-207 high-risk listing; OPM took over Feb 2005; IRTPA 2004 timeliness goals), not re-read |
| `protests` (FY2000-FY2007) | filed 1220, 1146, 1204, 1352, 1485, 1356, 1327, 1411; sustain 21/21/16/17/21/23/29/27%; effectiveness 33 (2000 A), 33, 33, 33, 34, 37, 39, 38% | S | WIFCON's table of GAO's annual reports (read): https://wifcon.com/protestsgaostat_1.htm; cross-checked with CRS R40227 and GAO-08-247R. FY2000 effectiveness not reported: FY2001's held (A) |
| `primes` revenue_usd_bn (7) | 2000 anchors plus 2002/2004/2006/2007 (Northrop also 2001, 2003; BAE 2000/2004/2007) | R | recalled from 10-Ks and SIPRI Top 100, not re-checked |

### regulation.yaml (strictness, 35 paths; all A, basis on a `# M50b:` line above each)

| Regulator | 2000-2007 | Basis |
|---|---|---|
| us_doj_ftc | 2000 0.8, 2001 0.6, 2002 0.4 | Jackson's break-up order 7 Jun 2000; reversed 28 Jun 2001; settled 2 Nov 2001; weak Section 2 enforcement to 2008 |
| eu_commission | 2000 0.6, 2004 0.7 | GE/Honeywell blocked 2001; Microsoft decision 24 Mar 2004 (EUR 497M) |
| uk_cma (OFT) | 2000 0.5, 2003 0.6 | Enterprise Act 2002 in force June 2003 |
| jftc | 2000 0.3, 2006 0.4 | AMA amendment (surcharges, leniency) from Jan 2006 |
| kftc | 2000 0.4, 2005 0.5 | Microsoft tying decision Dec 2005 |
| samr | 2000 0.3 | as 2008: no Anti-Monopoly Law before Aug 2008 |
| nmpa / nmpa_drugs | 0.6 / 0.5 in 2000, 0.7 / 0.6 from 2007 | SDA/SFDA before the 2007 reforms |
| fcc | 2000 1.0, 2001-2007 0.85 | WorldCom-Sprint abandoned Jul 2000; Powell-era deregulation |
| us_bank | 2000 0.95 | after Gramm-Leach-Bliley (Nov 1999) |
| all others | 2000 = the 2008 value | predecessor bodies noted (EMEA, MII, ACA, CIRC, CBRC, CEIOPS) |

Sarbanes-Oxley (July 2002) is not modelled: regulation.yaml has no listing-cost rule. GDPR does not exist yet; the file has no privacy regime to date.

### countries.yaml tension_history (US-China, 0-100; dates R, levels A)

2000-01 22 (after the 1999 Belgrade embassy bombing), 2000-10 19 (PNTR), 2001-04 28 (Hainan EP-3 collision, Taiwan arms package), 2001-08 22, 2001-10 17 (post-9/11 co-operation), 2001-12 15 (WTO entry), 2005-08 18 (CNOOC-Unocal), 2007-01 19 (ASAT test), then M50's 2008-01 18. The series is bloc tension only: 9/11, Afghanistan and Iraq lower US-China tension rather than raise it.

### Could not check

- Primes' 2000-2007 revenues (recalled, not re-read).
- OMB IT totals for 2003-2005 (search extracts only) and 2006 (derived).
- Clearance processing times before 2008 (assumptions from GAO's backlog reports, not re-read).
- All strictness levels are gameplay assumptions; dates recalled.
