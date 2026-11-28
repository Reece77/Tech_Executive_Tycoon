## Telecom (`backend/data/telecom.yaml`, M50b)

107 series extended from 2008 back to 2000 (gap lister: `GAPS 0`), plus the two 3G auctions of 2000. Every value from 2008 on is unchanged (only insertions; inline maps gained leading 2000-2006 keys). Tags follow the file: S sourced and read this session, D derived (method in the row's comment), R recalled from the named source (not re-read), A assumption.

Pages read on 2026-11-28:
- ITU, *Key ICT indicator aggregates* (Nov 2026 xlsx): <https://www.itu.int/en/ITU-D/Statistics/Documents/facts/ITU_regional_global_Key_ICT_indicator_aggregates_Nov_2026.xlsx>, 2005-2007 by ITU region. World mobile 2,205.3M / 2,744.6M / 3,367.8M; world fixed broadband 219.6M / 284.0M / 346.1M.
- FRED CPIAUCSL monthly values: <https://fred.stlouisfed.org/data/CPIAUCSL.txt>.
- Wikipedia: [Spectrum auction](https://en.wikipedia.org/wiki/Spectrum_auction) (UK £22.5B; Germany DEM 98.8B, i.e. EUR 50.8B, 12 blocks, ended 18 Aug 2000), [FOMA](https://en.wikipedia.org/wiki/FOMA) (launched October 2001; over 40M in September 2007), [Southern Cross Cable](https://en.wikipedia.org/wiki/Southern_Cross_Cable) (about $1.5B, 28,900 km, in service November 2000), [Template:Broadband subscriptions](https://en.wikipedia.org/wiki/Template:Broadband_subscriptions) (2007 per-100 figures only), [List of sovereign states by number of broadband Internet subscriptions](https://en.wikipedia.org/wiki/List_of_sovereign_states_by_number_of_broadband_Internet_subscriptions) (2007: 5% of 6.6B, which is about 330M).

| Series family | Years given | Method and sources | Tags |
|---|---|---|---|
| `cpi` | 2000-2007 annual | BLS CPI-U annual averages, checked against FRED's monthly values | R (FRED checked) |
| Regions `mobile`, `fixed` | every year | 2005-2007: the ITU regional aggregates mapped to the game's regions (Europe + CIS less Central Asia; Americas less the north_america country sum; Africa + North Africa). 2000-2004: country sums (CTIA, MIIT, TRAI, Anatel, ITU, OECD; recalled). Where the file's 2008 value differs from the real 2008 sum, the series is scaled by the ratio (given in the comment) so 2007 meets 2008 smoothly: north_america x1.022 (mobile) and x1.054 (fixed), Europe x0.982 / x1.08, south_southeast_asia x1.237 / x1.38, latin_america fixed x1.46, Africa x1.114 / x1.43 | D, R |
| `fibre_share` | 2000, 2004 | Near zero (FiOS from September 2005; Japan's and Korea's FTTH/LAN; Fastweb) | R, A |
| `households` | 2000, 2004 | Censuses (US 2000, China 2000, India 2001, Brazil 2000), UN | R |
| `arpu_mobile_usd`, `arpu_fixed_usd` | 2000, 2004 | CTIA US ARPU, China Mobile RMB 201 to 102, TRAI, operators; East Asia weighted by subscriptions | R, D, A |
| `traffic_gb` | 2000, 2004, 2006 | WAP/i-mode era, no smartphones before 2007 | A |
| `generations.radio_usd` (g3, g4) | 2000 (+2004 g3) | 3G early WCDMA prices; 4G's 2008 value held back (4G from December 2009) | A |
| Operators (29 lines, `mobile`/`fixed`/`wholesale`) | 2000, 2002, 2004, 2006 (+2007 where history bends) | Predecessors where the line's company did not yet exist: Verizon Wireless (from April 2000), Cingular to AT&T Mobility, VoiceStream to T-Mobile USA, Sprint PCS + Nextel, Hutchison Essar to Vodafone India, Celtel/Zain to Airtel Africa, China Netcom to Unicom's fixed. China Telecom mobile 0 until the CDMA purchase (October 2008). Orange Europe (x0.78), Telefonica Europe (x1.44) and Telefonica Latin America (x1.3) are scaled to the file's 2008 basis. `wholesale` holds the 2008 A value | R, D, A |
| Vendors `share` | 2000, 2004 | Dell'Oro and Gartner (recalled). Nokia = Nokia Networks + Siemens (NSN from April 2007). Huawei and ZTE about 0.01 in 2000. Shares sum to about 0.57 in 2000 because Lucent, Nortel, Motorola and Alcatel are not in the file | R, D |
| `hyperscaler_share`, `site_civil_usd`, `fibre_home_usd`, `cable_km_usd` | 2000 (+2004 fibre) | 0 before Google's Unity (2010); tower about $120k; FiOS about $1,400 a home in 2004; Southern Cross $1.5B / 28,900 km | A, R, D |
| Auctions `uk_3g_2000`, `de_3g_2000` | April and August 2000 | Spectrum auction page (S) x FX (GBP 1.516, EUR 0.924, R); reserves, rounds, terms and obligations R | S, D, R |

The new auctions do not change a 2008 or 2010 game: `announce_month` adds a dated auction only within `notice_months` before its month.

### Could not check
- ITU's 2000-2004 aggregates (the xlsx starts at 2005; DataHub returned 403), TRAI, MIIT, CTIA, FCC, OECD, Anatel. Every 2000-2004 subscriber count is R.
- Every operator's 2000-2006 subscribers (annual reports were not reached). Low confidence: Orange Africa, Telefonica Latin America, America Movil Latin America, Celtel, MTN 2000-2002.
- ARPU, fibre share, traffic, radio and civil costs (R or A, as for 2008).
- The UK auction's reserves and rounds, and Germany's DEM 100M-a-block minimum (R).

### Looked wrong (not changed)
Several 2008 values in the file sit 20-45% above the real 2008 sums: south_southeast_asia mobile 1,090 against about 881; latin_america fixed 27 against about 18.5; Telefonica Europe 95 against about 66. The D rows scale history to the file's 2008 value so the series stays continuous. A later balance pass may want to revisit the 2008 values themselves; that is not M50b's to change.
