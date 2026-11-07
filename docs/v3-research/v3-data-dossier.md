# Tech Startup Tycoon v3: upstream chip supply-chain data dossier (2010–2025)

Compiled 2026-11-06 for the v3 YAML data files (commodities, mining, refining, wafers, fabs, geopolitics).

**Reliability tags used throughout**

- **V** = verified in this research against the cited source (figure quoted from the source).
- **D** = derived by simple arithmetic from verified figures (shares, unit conversions, midpoints).
- **R** = widely reported figure taken from published company or press reports and recalled here, *not* re-fetched in this research. Spot-check before locking it into balance data.
- **e** = the source itself marks the value as an estimate (usually the latest year in a USGS edition).
- `n/a` = no reliable public annual figure found.

Unit conversions: 1 US¢/lb × 22.046 = US$/metric ton. 1 kg = 2.2046 lb.

---

## 1. Commodity price history, annual averages 2010–2025

### 1.1 Main table

Column key and units (series sources in 1.2):

| Col | Commodity | Unit | Basis |
|---|---|---|---|
| SiM | Silicon metal | US¢/lb Si | USGS US average price |
| Poly | Polysilicon, solar grade | US$/kg | Bernreuter spot annual average to 2019; † = rough level read from reported key points, not a published average |
| Ga | Gallium, high-purity refined | US$/kg | USGS (see breaks) |
| Ge | Germanium metal | US$/kg | USGS (see breaks) |
| Cu | Copper, LME cash | US¢/lb | USGS |
| Sn | Tin | US$/t | IMF Global price of tin (via FRED) |
| Ta | Tantalite ore | US$/kg Ta2O5 | USGS (Ryan's Notes to 2013, CRU from 2014) |
| Co | Cobalt cathode, US spot | US$/lb | USGS |
| Li | Lithium carbonate, battery grade | US$/t | USGS contract price |
| REE | Nd oxide 2010–2020; **NdPr oxide 2021–2025** | US$/kg | USGS, China FOB |

| Year | SiM ¢/lb | Poly $/kg | Ga $/kg | Ge $/kg | Cu ¢/lb | Sn $/t | Ta $/kg | Co $/lb | Li $/t | REE $/kg |
|---|---|---|---|---|---|---|---|---|---|---|
| 2010 | 140 | 60 | 600 ᵃ | 1,200 ᵃ | 341.7 | 20,367 | 120 | 20.85 | 5,180 | 86–89 ᵃ |
| 2011 | 158 | 56 | 688 ᵃ | 1,450 ᵃ | 399.8 | 26,051 | 275 | 17.99 | 5,180 | 190–200 ᵃ |
| 2012 | 127 | 22 | 529 ᵃ | 1,640 ᵃ | 360.6 | 21,109 | 239 | 14.07 | 6,060 | 75–80 ᵃ |
| 2013 | 122 | 17 | 502 ᵃ | 1,900 ᵃ | 332.3 | 22,282 | 260 | 12.89 | 6,800 | 65–70 ᵃ |
| 2014 | 140 | 20.5 | 362 ᵃ | 1,900 ᵃ | 315 e | 21,899 | 221 | 14.40 e | 6,600 | 56–60 ᵃ |
| 2015 | 127 | 16 | 317 | 1,792 | 249.5 | 16,067 | 193 | 13.44 | 6,500 | 48 |
| 2016 | 91 | 15 | 690 | 1,087 | 220.6 | 17,934 | 193 | 12.01 | 8,650 | 40 |
| 2017 | 116.6 | 16 | 477 | 1,082 | 279.5 | 20,061 | 193 | 26.97 | 15,000 | 50 |
| 2018 | 134.2 | 13 | 508 | 1,543 | 296.0 | 20,145 | 214 | 37.43 | 17,000 | 50 |
| 2019 | 105.7 | 9 | 570 | 1,236 | 272.4 | 18,661 | 161 | 16.95 | 12,700 | 45 |
| 2020 | 96.8 | ~9 † | 596 | 1,046 | 279.8 | 17,125 | 158 | 16.00 e | 8,000 e ᵇ | 47 e |
| 2021 | 220.3 | ~25 † | 625 | 1,187 | 422.5 | 32,387 | 158 | 24.21 | 11,700 ᵇ | **92** |
| 2022 | 361.9 | ~32 † | 560 | 1,294 | 399.8 | 31,383 | 196 | 30.78 | 63,700 ᵇ | **124** |
| 2023 | 179.7 | ~12 † | 450 | 1,392 | 384.8 | 25,912 | 170 | 17.20 | 39,000 ᵇ | **75** |
| 2024 | 170.3 | ~7 † | 500 e | 1,991 | 414.7 | 30,059 | 167 | 16.77 | 11,800 ᵇ | **55** |
| 2025 | 130 e | ~7 † | ~580 ᶜ | 4,100 e | 440 e | 34,058 | 180 | 21 e | 9,000 e ᵇ | **69 e** |

Footnotes:

- **ᵃ Year-end price, not annual average.** These are USGS MCS 2015 rows: gallium "price, yearend", germanium "producer, yearend, zone refined", and rare-earth year-end ranges for Nd oxide (99% min, China FOB). From 2015 USGS gives annual averages. Treat 2010–2014 values in these columns as level markers.
- **ᵇ Lithium series break.** MCS 2015–2021 give nominal contract prices. MCS 2025 gives an "annual average-real" series: 2020 10,100; 2021 14,200; 2022 71,100; 2023 41,300; 2024 14,000. MCS 2026 revises the same label to 2021 11,700; 2022 63,700; 2023 39,000; 2024 11,800; 2025 9,000 e. The table uses MCS 2026 for 2021–2025. Chinese spot lithium carbonate peaked far higher than these contract averages in late 2022 (no verified figure gathered here).
- **ᶜ Gallium 2025.** MCS 2026 dropped the high-purity row. It reports only the average unit value of all gallium imports: 2021 277, 2022 432, 2023 365, 2024 439, 2025e 580 $/kg. Use 580 as a rough 2025 level. The 2015 high-purity value (317) is as printed in MCS 2020 and looks low against neighbouring years.
- **Germanium.** 2015–2025 are annual averages for 99.999% metal (European price). Germanium dioxide on the same basis: 2015 1,211; 2016 830; 2017 731; 2018 1,084; 2019 913; 2020 724; 2021 770; 2022 828; 2023 883; 2024 1,281; 2025e 2,500 $/kg.
- **Copper.** The 2014 value is the MCS 2015 estimate. The 2025 value is the MCS 2026 estimate. COMEX and US producer cathode rows run a few cents higher (US producer cathode 2025e: 490 ¢/lb).
- **Cobalt.** LME cash, where you need a second series: 2011 16.01; 2012 13.06; 2013 12.26; 2014 14.00e; 2015 12.90; 2016 11.57; 2017 25.28; 2018 32.94; 2019 14.88; 2020 14.00e; 2021 23.17; 2022 28.83; 2023 15.48; 2024 11.84; 2025e 15 $/lb.
- **Silicon.** USGS revised its 2014 value from 121 (MCS 2015) to 140 (MCS 2017 and 2018). The table uses the revised value. Ferrosilicon 75% Si for comparison: 2010 97.2; 2017 86.9; 2020 87.4; 2021 192.3; 2022 312.1; 2023 142.2; 2024 132.0; 2025e 140 ¢/lb.
- **Rare earths, other oxides (USGS, $/kg).** Dysprosium oxide year-end 2010 285–305; 2011 1,400–1,420; 2012 600–630; 2013 440–490; 2014 320–360. Annual averages 2015 279; 2016 198; 2017 187; 2018 179; 2019 239; 2020 258e. Terbium oxide 2015 564; 2016 415; 2017 501; 2018 455; 2019 507; 2020 628e. NdPr was not a USGS row before MCS 2026. Nd oxide (2010–2020) is the closest proxy, and it tracked NdPr closely in 2021–2025 (Nd oxide 98/134/78/56/73).
- **† Polysilicon 2020–2025.** No free published annual average was found. The values are rough levels set from these data points (V):
  - 2020: trough about $6.75 (late June), peak $12.45 (mid-September), $10.40 (mid-December), global spot (Bernreuter).
  - 2021: Chinese mono-dense poly averaged $41.65/kg on 13 Oct 2021 (China Silicon Industry, via PV Tech). Prices rose through 2021 from about $10.
  - 2022: peak $39 (August, Bernreuter).
  - 2023: global average $22.70 at start of January, $8.60 in the first week of July, $10.40 in mid-September, $7.72 in late December.
  - 2024: China peak RMB 72.1/kg (about US$9.9) in January–February, then RMB 33–40/kg (about US$4.6–5.6) by December (Silicon Industry Branch, via PV Tech). Non-China prices are higher.
  - 2025: global average $6.88 on 3 Dec 2025 (Bernreuter).
- **Semiconductor-grade (electronic-grade, 9N–11N) polysilicon premium.** No public price series was found. Bernreuter states that published electronic-grade data sets are unusable. Electronic-grade poly is sold on long-term contracts (Wacker, Hemlock, Tokuyama, Mitsubishi, and others) at prices well above solar spot. For game balance, treat it as a design assumption (for example 2–4× solar spot, with far less volatility) and label it **assumption, not data**.

### 1.2 Commodities without an annual price series

**Quartz / high-purity quartz (HPQ).** No public benchmark or annual price series exists. Sales are bilateral, dominated by Spruce Pine, NC.

- USGS gives ground HPQ ranges (US$/t): 2021 500–16,000; 2022 500–17,000; 2023 500–20,000; 2024 500–17,000; 2025e 500–12,000 (V).
- Cultured quartz crystal, as-grown: about $200/kg (2014), $100/kg (2021–2022), $200/kg (2023–2025). Lumbered: about $400/kg (2014), $300 (2021–2022), $400 (2023), $500 (2024–2025) (V).
- Spruce Pine HPQ is ">99.999%" pure. Initial tests of new Chinese deposits reached 99.995–99.998% (V). HPQ crucibles are needed for Czochralski pulling of mono silicon ingots.
- Hurricane Helene (late September 2024) shut Spruce Pine operations for several weeks (R). USGS does not mention it.
- Suggested game handling: one "HPQ" good with a high, sticky contract price (assumption: $5,000–15,000/t for crucible grade), mostly from a single US region.

**Neon (semiconductor-grade, for DUV excimer lasers).** No public annual price series exists. Available indicators:

| Year | Ukraine export unit value, rare gases (US$/m³) ᵈ | Event |
|---|---|---|
| 2013 | 52 | |
| 2014 | 51 | Crimea, Feb–Mar 2014: neon "reportedly spiked over 600 percent" |
| 2015 | 174 | Spike passes through |
| 2016 | 98 | |
| 2017 | 67 | |
| 2018 | 95 | |
| 2019 | 86 | |
| 2020 | 136 | |
| 2021 | 228 | Prices tripled into Q1 2022 when Chinese steel mills were curtailed (Winter Olympics) |
| 2022 | n/a | Russia invades Ukraine, 24 Feb 2022. Ingas (Mariupol) and Cryoin (Odesa) halted. China neon prices rose about 10× in March 2022. Korean import price of Chinese neon went from $350,000/t (Q1 2022) to $2.28M/t (Q2), $2.9M/t in June 2022, about 17.5× late-2021 levels |
| 2023–2025 | n/a | No verified figures. Qualitatively, prices normalised as China, Korea and the US added recovery capacity |

ᵈ Covers HS 2804.29, which may include krypton and xenon, so it overstates neon-only values (USITC).

Before 2022, Ukraine supplied about 50–70% of world neon (about 70% of chip-grade in 2014). In 2021 China supplied 60% of Korea's neon imports, Ukraine 23%, Russia 5.2% (V, see sources).

### 1.3 Major shocks for event scripting

| When | Shock | Magnitude (V unless tagged) |
|---|---|---|
| Jul 2010 | China cuts H2 2010 rare-earth export quota (≈40% cut for 2010, R) | Prices begin climbing |
| Sep 2010 | Senkaku boat collision; China accused of unofficial RE export halt to Japan (China denies) | |
| Jan–Aug 2011 | Rare-earth bubble | Dy oxide $343/kg (Jan 2011) to $2,377/kg (Aug 2011 peak). Nd oxide year-end 2011 $190–200 vs $86–89 year-end 2010 |
| 2011–2012 | Polysilicon crash (capacity glut) | Spot $79/kg (Mar 2011) to <$30 (late 2011) to a $15.35–15.90 record low (Dec 2012) |
| 2011 | Tantalum spike | $120/kg (2010) to $275/kg (2011) |
| 2011 | Copper record-high annual average of that era | 399.8 ¢/lb LME |
| 2015–2016 | China slowdown commodity slump | Copper 220.6 ¢/lb (2016), tin $16,067/t (2015) |
| 2017–Q1 2018 | Cobalt EV-hype spike | $12.01/lb (2016) to $37.43/lb (2018 average) |
| 2017–2018 | First lithium boom | $6,500/t (2015) to $17,000/t (2018) |
| Mid-2020 | COVID low | Polysilicon about $6.75 (June 2020) |
| 2021–2022 | Chinese "dual control" power curbs, energy crisis | Silicon metal 96.8 ¢/lb (2020) to 361.9 ¢/lb (2022); polysilicon to $39 (Aug 2022) |
| 2021–Nov 2022 | Lithium super-spike | Contract average 11,700 (2021) to 63,700 (2022), then 9,000 (2025e) |
| Feb–Jun 2022 | Neon spike (Ukraine war) | About 10× in China; Korean import price about 17.5× |
| 2022 | NdPr peak | $124/kg annual average (2022) |
| 3 Jul 2023 announced; 1 Aug 2023 effective | China gallium/germanium export licensing | Gallium 99.99% at 1,775 yuan/kg (about $245) on announcement day (ING) |
| Dec 2024 | China bans Ga/Ge/Sb exports to the US | Germanium metal $1,991/kg (2024) to $4,100/kg (2025e), about 2×. US germanium imports down about 67% in 2025 |
| Feb 2025 | DRC cobalt export ban | Cobalt cathode $16.77/lb (2024) to $21/lb (2025e) |
| Apr & Oct 2025 | China rare-earth controls (see §5) | NdPr 55 (2024) to 69 (2025e) |

---

## 2. Where each commodity is produced (c. 2020–2024)

Shares are **D** (computed from USGS tonnages, 2024 unless noted) or **V** (quoted share). "Refining" is listed separately where it differs from mining.

| Commodity | Mining / primary production (share of world) | Refining / processing (share of world) |
|---|---|---|
| **Copper** (world mine 23.0 Mt Cu, 2024) | Chile 24%, DR Congo 13%, Peru 12%, China 8%, US 5%, Russia 4%, Indonesia 4%, Zambia 4%, Kazakhstan 3% | Refined 27.6 Mt: **China 45%**, DRC 9%, Chile 7%, Japan 6%, US 3%, Russia 3%. 2025e China 14.0 of 29.0 Mt (48%) |
| **Cobalt** (world mine 302 kt, 2024) | **DRC 75%**, Indonesia 12% (nickel by-product, growing fast), Russia 3%, Australia 2%, Canada 1% | **China about 80% (2023) to about 88% (2024)** of refined cobalt (IISD); 46% in 2013. IEA c.2019: 65% |
| **Lithium** (world mine 240 kt Li, 2024, MCS 2025) | Australia 37% (spodumene), Chile 20% (brine), China 17%, Zimbabwe 9%, Argentina 8% (brine), Brazil 4% | **China about 58–65% of chemical conversion** (IEA c.2019: 58%; IEA 2024–25 says China leads 19 of 20 strategic minerals at about 70% average share). Chile is second |
| **Rare earths** (world mine 380 kt REO, 2024) | **China 71%** (270 kt quota), US 12% (Mountain Pass, 45.5 kt), Australia 8% (Mt Weld), Burma 7% (largely ionic clays shipped to China), Thailand, India, Russia, Nigeria, Madagascar about 1% each | **Separation and refining: China about 87–90%** (IEA c.2019: 87%). Lynas Malaysia is the main non-China separator. Magnets: China dominant (R, about 90%) |
| **Gallium** (world low-purity 848 t, 2024) | By-product of alumina refining: **China 99%** (839 t), Russia 6 t, Japan 3 t | China also leads high-purity refining. Japan, the US and Slovakia refine and recycle smaller volumes (R) |
| **Germanium** | By-product of zinc ores and coal fly ash. Global data limited (USGS) | **China 68% of refinery output (2021, via ING)**. Others include Russia, Canada (Teck Trail), Belgium (Umicore, recycling) (R) |
| **Silicon metal** (world 4.6 Mt Si, 2024, MCS 2025) | **China 85%** (3.9 Mt), Brazil 4%, Norway 3%, France 2%, Russia 1%, Germany 1%. China was about 80% of all silicon materials in 2025 | Quartz/quartzite feed is widely available. Metallurgical-grade silicon is made in submerged-arc furnaces where power is cheap |
| **Polysilicon** (world output 1.61 Mt, 2023) | n/a (made from silicon metal) | **China 91.5% of output, 93.6% of capacity (2023)**. The top 5 producers, all Chinese (Tongwei, GCL, Daqo, Xinte, East Hope), make about 70%. Semiconductor grade is concentrated in Germany (Wacker), the US (Hemlock), Japan (Tokuyama, Mitsubishi Materials) and Korea (OCI) (R) |
| **High-purity quartz** | **US (Spruce Pine, NC) dominant** for crucible-grade; two US producers (USGS), namely Sibelco and The Quartz Corp (R). Others: Norway, Russia, India, China (lower grade) | Processing partly offshore (USGS: at least one US HPQ company ships product abroad for processing) |
| **Tin** (world mine 294 kt, 2024) | China 24%, Indonesia 19%, Peru 11%, Brazil 9%, DRC 9%, Bolivia 7%, Burma 7% (Wa State), Australia 4%, Vietnam 4% | Refined tin: China, Indonesia, Malaysia, Peru, Thailand lead (R) |
| **Tantalum** (world mine 2,500 t Ta, 2024) | **DRC 51%**, Nigeria 16%, Rwanda 15%, Brazil 4%, China 3%, Australia 2% (conflict mineral; 3TG rules) | Processing: China, Kazakhstan (Ulba), US, Germany, Japan, Thailand (R) |
| **Neon** | Pre-2022: **Ukraine 50–70%** (purification of crude neon from Soviet-era steel air-separation units), with Russia also significant. China rising fast since 2022 | Purification and blending is the chokepoint: Ingas and Cryoin (Ukraine), Linde, Air Liquide, Air Products, Chinese gas firms (R) |

---

## 3. Real companies for the rival roster, at c.2010 scale

The Rev 2010 column is in native currency where reported that way, with an approximate USD conversion. FY = fiscal year if not calendar. Tags: V/D verified, R recalled (verify).

### 3.1 Mining and primary producers

| Company | HQ | What it does | Listed? (2010) | Rev 2010 | Tag | Notes for game |
|---|---|---|---|---|---|---|
| Freeport-McMoRan | US | Copper, gold, moly; Grasberg (Indonesia), Morenci; in 2010 owned Tenke Fungurume (DRC copper-cobalt) | NYSE | ≈ $19.0B | R | Sold Tenke to CMOC in 2016. Grasberg divested to 51% Indonesian state ownership in 2018 (R) |
| BHP Billiton | AU/UK | Diversified: iron ore, copper (Escondida), coal, petroleum, nickel | ASX/LSE/NYSE | FY Jun-2010 ≈ $52.8B | R | Largest miner by market cap |
| Rio Tinto | UK/AU | Iron ore, aluminium, copper (Oyu Tolgoi, Kennecott), borates; later lithium (Rincon, Arcadium 2025) | LSE/ASX/NYSE | ≈ $60B gross sales | R | Bought Arcadium Lithium in 2025 (R) |
| Glencore | CH | Commodity trader and miner: copper, cobalt (Katanga, Mutanda), zinc, coal | **Private until May 2011 IPO** | ≈ $145B (2011 $186B was +28%) | D | Merged with Xstrata 2013. Largest non-Chinese cobalt producer |
| Codelco | CL | World's largest copper miner | **State-owned** | ≈ $16B | R | Partner in Chile's state lithium plan (SQM deal, 2023–24) (R) |
| Albemarle | US | Specialty chemicals; lithium only after buying Rockwood (Chemetall) in Jan 2015 | NYSE | ≈ $2.4B | R | Good "chemicals firm pivots to lithium" arc |
| SQM | CL | Lithium (Atacama brine), iodine, potash, fertilisers | NYSE/Santiago | ≈ $1.8B | R | Subject to Chile's 2023 national lithium strategy |
| Lynas | AU | Rare earths: Mt Weld mine (WA), LAMP separation plant (Kuantan, Malaysia) | ASX | ≈ pre-revenue | R | First LAMP feed in 2012 (R). Kalgoorlie cracking plant capex rose from A$500M to A$800M (V) |
| Molycorp → MP Materials | US | Mountain Pass rare-earth mine (CA) | Molycorp NYSE IPO Jul 2010 | ≈ $0.04B (small) | R | Molycorp Chapter 11 in 2015. MP Materials bought the mine in 2017 and listed **Nov 2020 via SPAC** (Fortress Value Acquisition Corp.) (R) |
| Umicore | BE | Refining and recycling of cobalt, germanium and precious metals; battery cathodes; catalysts | Euronext Brussels | ≈ $12.9B (incl. metal value) | V | Revenue excluding metal is far smaller (≈ €2B, R) |
| China Northern Rare Earth (Baotou) | CN | Bayan Obo light rare earths; holds the largest share of China's quota | Shanghai | n/a | – | State champion; useful as a Chinese state-backed rival |

### 3.2 Silicon, polysilicon and wafers

| Company | HQ | What it does | Listed? (2010) | Rev 2010 | Tag | Notes |
|---|---|---|---|---|---|---|
| Wacker Chemie | DE | Silicones, polymers, **polysilicon** (€1,177.5M external sales 2010); parent of Siltronic | Frankfurt | €4.75B (≈ $6.3B) | V | Leading semiconductor-grade poly supplier |
| Siltronic | DE | 300mm and 200mm silicon wafers | **Wacker subsidiary; IPO Jun 2015** (R) | €1,018.7M (≈ $1.35B) | V | GlobalWafers' takeover bid failed in 2022 (German approval not given in time) (R) |
| Hemlock Semiconductor | US (Michigan) | Polysilicon, semiconductor and solar grade | **Private JV**: Dow Corning majority, Shin-Etsu, Mitsubishi Materials (R) | not disclosed | – | Hit by Chinese anti-dumping duties on US poly (2014) (R) |
| GCL-Poly Energy | HK/CN | Solar polysilicon (17,853 t in 2010) and wafers (about 1.4 GW) | HKEX | HK$18.47B (≈ $2.4B) | V | Later GCL Technology; FBR granular silicon |
| OCI | KR | Polysilicon (solar) | KRX | n/a | – | Exited Korean poly 2020, kept Malaysia (R) |
| Shin-Etsu Chemical | JP | PVC, silicones; **world #1 silicon wafers** (Shin-Etsu Handotai); photoresists | TSE | ≈ $9.9B (FY Mar-2011) | V | Also a Hemlock JV partner |
| SUMCO | JP | Silicon wafers (#2 globally) | TSE | ≈ $3.2B | V | Pure-play wafer maker |
| MEMC Electronic Materials (SunEdison) | US | Silicon wafers plus solar | NYSE | ≈ $2.2B | R | Renamed SunEdison 2013. Its wafer arm, SunEdison Semiconductor, was bought by GlobalWafers in Dec 2016 (R) |
| GlobalWafers | TW | Silicon wafers | Spun out of Sino-American Silicon Products 2011; listed TPEx 2015 (R) | part of SAS in 2010 | R | Rises to #3 via acquisitions (Covalent 2012, SunEdison Semi 2016) (R) |

### 3.3 Foundries and integrated chip makers

| Company | HQ | What it does | Listed? (2010) | Rev 2010 | Tag | Notes |
|---|---|---|---|---|---|---|
| TSMC | TW | Pure-play foundry #1 | TWSE/NYSE | NT$419.5B (≈ $13.3B) | R (a 2010 analyst note said "likely to exceed $10B", V) | Leading edge from 7nm onward |
| Samsung Electronics (foundry inside System LSI) | KR | Memory, phones, logic foundry | KRX | Group ≈ ₩154.6T (≈ $134B). Foundry was a small fraction | R | Samsung Foundry became a separate business unit in May 2017 (R). First GAA (3nm, Jun 2022) |
| Intel | US | IDM: x86 CPUs, own fabs | Nasdaq | ≈ $43.6B | R | Leading edge until 14nm; 10nm delays 2015–2019; Intel Foundry Services from 2021 |
| GlobalFoundries | US (owned by Abu Dhabi's ATIC/Mubadala) | Foundry: AMD's former fabs (Dresden), plus Chartered (Singapore) from Jan 2010 | **Private; founded Mar 2009; IPO Oct 2021** (R) | ≈ $3.5B (company expectation) | V | Abandoned 7nm in Aug 2018 (R) |
| UMC | TW | Foundry #2 in 2010 | TWSE/NYSE | ≈ $3.9–4.3B (analyst est. $3.92B; Macrotrends $4.34B) | V | Mature nodes (28nm and above) |
| SMIC | CN | China's leading foundry (#4 globally in 2010) | HKEX (and NYSE ADR until 2019) | $1.55B | V | Entity List Dec 2020; 7nm-class (N+2) via DUV multipatterning (R) |

### 3.4 Semiconductor equipment

The 2011 column is VLSIresearch system sales, which confirms relative scale.

| Company | HQ | What it does | Listed? | Rev 2010 | Tag | 2011 sales (VLSI, V) |
|---|---|---|---|---|---|---|
| ASML | NL | Lithography: DUV, and **sole EUV supplier** (EUV in HVM from 2019) | Euronext/Nasdaq | €4.51B | R | $7.88B (#1) |
| Applied Materials | US | Deposition, etch, CMP, implant, inspection | Nasdaq | FY Oct-2010 ≈ $9.55B | R | $7.44B (#2) |
| Tokyo Electron | JP | Coater/developer, etch, deposition | TSE | FY Mar-2011 ≈ ¥669B (≈ $8B) | R | $6.20B (#3) |
| KLA-Tencor (KLA) | US | Process control and inspection | Nasdaq | FY Jun-2010 ≈ $1.82B | R | $3.11B (#4) |
| Lam Research | US | Etch, deposition (bought Novellus 2012) | Nasdaq | FY Jun-2010 ≈ $2.13B | R | $2.80B (#5) |

Others in the VLSI 2011 top 10: Dainippon Screen $2.10B, Nikon $1.65B, Advantest $1.45B, ASM International $1.44B, Novellus $1.32B (V). An EUV tool costs about $120M each (c.2020, Tom's Hardware, V).

---

## 4. Process node timeline

"First volume" means high-volume production or the first shipping product, with risk production noted where it matters. Intel naming caveat: in July 2021 Intel renamed its nodes. "10nm Enhanced SuperFin" became **Intel 7**, the former "7nm" became **Intel 4**, and Intel 3 and 20A/18A followed. Intel's names were chosen to line up with foundry density classes: Intel 10nm ≈ TSMC N7, Intel 4 ≈ TSMC N5-class. 20A was cancelled in Sept 2024 (R).

| Node (class) | TSMC first volume | Samsung first volume | Intel first volume (its own name) | EUV? | Leading fab cost (public examples) | Wafer price, 300mm (public estimates) |
|---|---|---|---|---|---|---|
| 65nm | 2006 (R) | 2006–07 (R) | 65nm: production Q4 2005, products Jan 2006 (R) | No | ≈ $3B-class 300mm fab (R, rule of thumb) | n/a (no reliable public figure found) |
| 45/40nm | 40nm: 2009 ramp (yield problems in 2009) (R) | 45nm: 2009 (R) | 45nm HKMG: Nov 2007, Penryn (R) | No | ≈ $3–4B (R) | ≈ $2,000 today for 40/45nm at UMC (2026 roundup; mature-node price, not launch price) (V) |
| 32/28nm | 28nm: Q4 2011 (R) | 28nm: 2011–12 (R) | 32nm: Jan 2010, Westmere (R) | No | ≈ $5–6B (R) | ≈ $3,000 for TSMC 28nm (2024 roundup; range $2,550–3,450) (V) |
| 22/20nm | 20SoC: 2014, Apple A8 Sep 2014 (R) | 20nm: 2014 (R) | **22nm, first FinFET**: Apr 2012, Ivy Bridge (R) | No (double patterning) | ≈ $6–7B (R) | n/a |
| 16/14nm | 16FF+: mass production Q3 2015 (CSET, V); 16FF started 2013–14 (V/R) | 14LPE: about Q4 2014 / early 2015, Exynos 7420 in Galaxy S6 Apr 2015 (V/R) | 14nm: 2014, Core M launched 5 Sep 2014 (V) | No | Capital per wafer-per-year ≈ $11,220 (CSET, V) | **$3,984** (CSET, 2020 price, V); ≈ $5,500 TSMC N16/N12 (2025 roundup, V) |
| 10nm | 10nm: mass production Q2 2017 (CSET, V) | 10LPE: Oct 2016 (R) | 10nm: Cannon Lake limited 2018; Ice Lake volume 2019 (R). Renamed Intel 7 (10ESF) Jul 2021, Alder Lake Nov 2021 (V/R) | No | ≈ $13,169 per wafer-per-year (CSET, V) | **$5,992** (CSET, V) |
| 7nm | **N7: volume Apr 2018** (DUV SAQP, no EUV) (V). **N7+: first EUV, HVM Oct 2019** (V) | 7LPP (EUV): risk production 28 Oct 2018; first product Exynos 9825, Aug 2019 (V) | **Intel 4 (first Intel EUV)**: Meteor Lake 2023 (V; launched Dec 2023, R) | N7 no; N7+, 7LPP, Intel 4 yes | ≈ $14,267 per wafer-per-year (CSET, V) | **$9,346** (CSET, V); ≈ $9,500 (2024, V) |
| 5nm | N5: risk Apr 2019, volume 2020 (Apple A14, R); EUV on up to 14 layers (V) | 5LPE: 2020 (V) | Intel 3: 2024, Xeon 6 (R) | **Yes** | Fab 18 (Tainan, 5nm, 3 phases, over 1M wafers/yr): **> NT$500B (≈ $17B)** (V; USD is D). TSMC Arizona Fab 1 (5nm, 20k wafers/month): **$12B** (2020 plan) (V) | **$16,988** (CSET 2020, V); ≈ $18,500, range $16–21.3k (2024, V) |
| 3nm | **N3: volume 29 Dec 2022** (FinFET) (V); N3E 2H 2023 (V) | **3nm GAA (MBCFET), world's first GAA: Jun 2022**; first shipment 25 Jul 2022 (V) | (Intel 3 is a 5nm-class FinFET; see row above) | **Yes** | Planned TSMC 3nm fab ≈ **$25.7B** (V, guru3d) | ≈ $20,000, range $18–27k (V); $25,000–27,000 average (TechNode/Icsmart 2025, V) |
| 2nm | **N2 (GAA nanosheet): volume Q4 2025** (V) | SF2: 2025 (Exynos 2600) (R) | **Intel 18A** (RibbonFET GAA plus PowerVia backside power): Fab 52 Arizona HVM late 2025; first Panther Lake SKU ships before end-2025; broad availability Jan 2026 (V) | **Yes** | Big-fab announcements: Samsung Taylor TX $17B (2021, R); Intel Ohio $20B for 2 fabs (2022, R); TSMC Arizona commitment raised to $165B (Mar 2025, R) | **≈ $30,000** (TSMC N2, 2025 reports; 10–20% above N3) (V). 1.6nm (A16) rumoured up to $45,000 (Tom's Hardware, rumour) |

Game-design reading of the table (D):

- Wafer price roughly doubled at each step from 10nm to 7nm to 5nm, then rose about 20–50% per step after that.
- Capital per wafer-per-year rose more slowly (+8–17% per node). Margins at the leading edge therefore widened, which is why TSMC dominated.
- EUV is a hard gate at 5nm and below. 7nm can be reached without EUV (TSMC N7; SMIC N+2 via DUV multipatterning), but at higher cost and lower yield.

---

## 5. Export controls and geopolitics timeline, 2010–2025

V = confirmed in a fetched source. R = widely reported and recalled, not re-fetched; verify the exact day before using it in game text.

| Date | Actor | Action | Goods / companies | Tag |
|---|---|---|---|---|
| Jul 2010 | China | Cuts H2 2010 rare-earth export quota sharply (≈40% lower for 2010 overall) | Rare earths | R |
| Sep 2010 | China → Japan | Alleged unofficial halt of RE shipments after the Senkaku boat collision (China denies) | Rare earths | V |
| Mar 2012 | US, EU, Japan | WTO case against China's RE, tungsten and molybdenum export restrictions | Rare earths, W, Mo | V (filing year) / R (month) |
| Jan 2014 | Indonesia | Raw mineral ore export ban (nickel, bauxite), relaxed Jan 2017 | Nickel ore, bauxite | R |
| Mar 2014 / Aug 2014 | WTO | Panel rules against China (Mar); Appellate Body upholds (Aug) | Rare earths | V (2014) / R (months) |
| 2014 | China | RE export quota 31,000 t (27,383 light, 3,617 heavy) | Rare earths | V |
| Jan 2015 | China | Drops RE export quotas (export tax removed May 2015, R) | Rare earths | V |
| Apr 2018 | US Commerce | Denial order on ZTE (lifted Jul 2018 after settlement) | US components to ZTE | R |
| Jun 2018 | DRC | New Mining Code: cobalt declared "strategic substance", 10% royalty | Cobalt | R |
| Jul–Sep 2018 | US (USTR, Section 301) | Tariffs on $34B (6 Jul), $16B (23 Aug, incl. many semiconductors), $200B (24 Sep) of Chinese goods; China retaliates | Broad, incl. chips | R |
| Oct 2018 | US Commerce | Fujian Jinhua (DRAM) added to Entity List | Chip equipment | R |
| May 2019 | US Commerce | **Huawei** and affiliates added to Entity List (16 May 2019); Section 301 tariff on $200B raised to 25% | Huawei; US-origin items | V (Huawei listed) / R (day) |
| Jan 2020 | Indonesia | **Nickel ore export ban** (brought forward from 2022) to force domestic smelting | Nickel ore | V (2020) / R (month) |
| May & Aug 2020 | US Commerce | **Foreign Direct Product Rule** extended to Huawei: foreign-made chips made with US tools/EDA need a licence (May); broadened (Aug) | Foundries worldwide, incl. TSMC | R |
| Dec 2020 | US Commerce | **SMIC** added to Entity List (presumption of denial for tools for ≤10nm) | SMIC | R |
| Apr 2022 | Mexico | Lithium nationalised (LitioMx state company) | Lithium | V |
| 7 Oct 2022 | US BIS | **Advanced computing and semiconductor rules**: advanced chips added to CCL; supercomputer and fab end-use controls; licence needed for PRC fabs making ≤16/14nm non-planar logic, ≤18nm half-pitch DRAM, ≥128-layer NAND; US-person restrictions; 28 entities | AI chips (NVIDIA A100/H100), chip equipment, US engineers | V |
| Dec 2022 | Zimbabwe | Ban on export of unprocessed lithium ore | Lithium | V |
| Jan 2023 | US, Netherlands, Japan | Reported trilateral deal (27 Jan) to align chip-tool controls | Lithography and other tools | V (deal) / R (day) |
| Jan 2023 | Bolivia | YLB picks CATL-led consortium for DLE lithium projects (later Russian Uranium One and Chinese CBC deals) | Lithium | R |
| Mar → Jul 2023 | Japan | Announces controls on 23 types of chipmaking equipment (Mar); enforced Jul 2023 | Tokyo Electron and others | V |
| Mar → Sep 2023 | Netherlands | Announces controls (Mar); enforced Sep 2023 (advanced DUV immersion, NXT:2000i and above) | ASML | V |
| Apr 2023 | Chile | **National Lithium Strategy**: state control and majority participation in strategic salars; Codelco–SQM partnership | Lithium | V |
| Jun 2023 | Indonesia | Bauxite export ban takes effect | Bauxite | V |
| Jun 2023 | Namibia | Ban on export of unprocessed lithium, cobalt, manganese, graphite, rare earths | Battery minerals | V (2023) / R (month) |
| 3 Jul 2023 → 1 Aug 2023 | China (MOFCOM) | **Gallium and germanium export licensing**; exporters must report end users | Ga, Ge and compounds (GaAs, GaN, etc.) | V |
| 17 Oct 2023 | US BIS | **Update to the Oct 2022 rules**: closes loopholes (A800/H800), adds performance-density thresholds, more tools, extends to 40+ countries' parent companies | AI chips, tools | V (Oct 2023) / R (details) |
| 20 Oct 2023 → 1 Dec 2023 | China | **Graphite** export permits for "highly sensitive" graphite products | Battery anode graphite | V |
| 21 Dec 2023 | China | Bans export of RE extraction, separation and magnet-making technology (adds to existing refining-tech ban) | RE technology | V |
| Aug → 15 Sep 2024 | China | Antimony export controls | Antimony | R |
| 2 Dec 2024 | US BIS | Two rules: **140 entities** added; **HBM** controls; FDPR expanded; more SME | Chinese toolmakers, fabs, HBM | V |
| 3 Dec 2024 | China | **Bans exports of gallium, germanium, antimony and superhard materials to the US**; tighter graphite end-use checks | Ga, Ge, Sb | V |
| 13–15 Jan 2025 | US Commerce | **AI Diffusion Framework** (country tiers for AI chips) and **Foundry Due Diligence Rule** (effective Jan 2025). AI Diffusion rule rescinded May 2025 before taking effect (R) | AI chips, foundries | V (issued) / R (rescission) |
| 4 Feb 2025 | China | Export licences for tungsten, tellurium, bismuth, molybdenum, indium products | W, Te, Bi, Mo, In | V |
| 22 Feb 2025 | DRC | **Temporary cobalt export ban** (4 months, then extended) to tackle oversupply | Cobalt | V (Feb 2025) / R (day) |
| 4 Apr 2025 | China | Export controls on 7 medium/heavy REEs (Sm, Gd, Tb, Dy, Lu, Sc, Y) incl. alloys and magnets | Rare earths, magnets | V |
| Apr 2025 | US | Licence requirement on NVIDIA H20 / AMD MI308 to China (later reversed for a revenue-share arrangement, R) | AI chips | R |
| Jul 2025 | China | Controls on battery-cathode and lithium/gallium processing technology | Tech exports | V |
| 29 Sep 2025 | US BIS | "Affiliates rule": Entity List restrictions extend to companies ≥50% owned by listed entities (suspended for 1 year in Nov 2025, R) | Subsidiaries | R |
| 9 Oct 2025 (effective 8 Nov) | China | Adds 5 more REEs (Ho, Er, Tm, Eu, Yb), RE mining and refining equipment, synthetic graphite, Li-ion battery items and equipment; extraterritorial rules | RE, graphite, batteries | V |
| 16 Oct 2025 | DRC | Replaces cobalt ban with **quotas**: 18,125 t for rest of 2025; up to 96,600 t/yr in 2026–27 (incl. 9,600 t strategic reserve) | Cobalt | V |
| 30 Oct–Nov 2025 | US–China (Busan Trump–Xi meeting) | China **suspends Oct 2025 RE controls for 1 year** (April controls remain; general licences issued) and **lifts its Ga/Ge US export ban for 1 year** | RE, Ga, Ge | V |
| 7 Nov 2025 | US (USGS/DOI) | Silicon added to the 2025 Final List of Critical Minerals | Silicon | V |

Other resource-nationalism items for flavour: the DRC banned raw copper and cobalt concentrate exports at various times (2014, 2016, 2018–19 moratoria, per IISD; 2022 per China Global South) (V). In May 2025 Tanzania required local value-addition plans for 40 critical minerals (V). Burma's Wa State tin mine suspension (Aug 2023) is a non-state supply shock (V). Myanmar's Kachin conflict affects heavy-REE clays (R).

---

## 6. Mining project economics: rules of thumb

| Topic | Rule of thumb | Source / tag |
|---|---|---|
| Discovery → production, all mines | IEA: **average 16.5 years** from discovery to first production. S&P Global: **15.7 years** (127 mines, 2023 study); **17.8 years** for mines started 2020–2024, vs about 6 years in the 1990s; US 19.1 years vs global 15.5 years. Projects still in feasibility average 28 years | V |
| Extreme cases | Resolution Copper (AZ) about 35 years if online 2030; Donlin Gold about 37 years; Tampakan about 36 years | V |
| Hard-rock lithium (spodumene) | **3–5 years** to production for conventional open-pit plus flotation once permitted; lowest capital intensity (up to 4× less than integrated carbonate) | V (Wood Mackenzie) |
| Lithium brine | **6–10-year development cycles** (pond evaporation takes 12–24 months per batch, R). Lower operating cost; climate-dependent; DLE has higher capex and better recovery | V (WoodMac); pond time R |
| Exploration success | "Only around **1 in 1,000 prospects becomes a mine**." Western-world exploration 1975–2012: $211B (2012 US$) for 1,896 "significant" discoveries, **≈ $111M per significant discovery** (D). Discovery rates are declining and cost per discovery is rising | V (McIntosh / Australian Academy of Science) |
| Copper project capex | Capital intensity, weighted average of 26 projects due by 2030: **$22,359 per tonne of annual paid copper**; Latin America $19,049; US/Canada $28,910; range $10,177 (Kamoa-Kakula) to $40,137 (Copper World). Hence a **mid-size 100 kt/yr copper mine ≈ $2–3B** (D). Project capex in the pipeline: $172M to $9.14B (Reko Diq) | V (S&P Global, Dec 2025) |
| Copper AISC | Industry average **$2.12/lb in 2021** (+16.2% year on year), about $2.19/lb expected 2022. New-project AISC: S&P study average $5,565/t (≈ $2.52/lb, D), range $2,936/t (≈ $1.33/lb) to $6,014/t (≈ $2.73/lb). Typical 2020s range **$1.5–3.0/lb**; top-quartile mines under $1.5/lb | V / D |
| Lithium brine capex | Rio Tinto Rincon (Argentina, DLE): **$2.5B for 60 kt/yr battery-grade carbonate** (3 kt starter + 57 kt expansion) ≈ **$42,000 per t/yr** (D). Construction from mid-2025, first output 2028, then a 3-year ramp | V |
| Rare-earth processing capex | Lynas Kalgoorlie cracking and leaching plant: budget rose **A$500M → A$730M (Aug 2023) → A$800M (Apr 2024)**, a +60% overrun. Lynas Malaysia heavy-RE expansion: RM497M (≈ A$180M) announced Oct 2025. A full mine plus separation chain is plausibly $1–2B for about 10 kt/yr NdPr (assumption, D-ish; treat as design estimate) | V / assumption |
| Overrun norm | Cost overruns of 20–60% on processing plants are common in this data (Lynas +60%); copper capital intensity rising | D |
| Tailings and accidents | No comprehensive global failure database exists (Wikipedia, citing the literature). Notable events: **Mount Polley, BC, 4 Aug 2014** (≈ 10 Mm³ water + 4.5 Mm³ tailings, no deaths); **Mariana / Fundão, Brazil, 5 Nov 2015** (19 deaths, ≈ 43–60 Mm³); **Brumadinho, Brazil, 25 Jan 2019** (≈ 270 deaths, R; ≈ 12 Mm³). Led to the Global Industry Standard on Tailings Management (Aug 2020, R). Commonly cited rate: about **2–5 significant tailings failures per year** worldwide (R; no V source found) | V / R |

Suggested game parameters (assumptions derived from the above, label them as such in `balance.yaml`):

- Exploration: 1 in 1,000 targets yields an economic deposit. Per-target exploration cost is small, but cost per discovery is about $100M.
- Stage durations, hard rock: exploration 4–8 years, studies 3–5 years, permitting 2–7 years (country modifier: US and Canada slowest), construction 2–4 years. Brine: +2–4 years ramp-up.
- Capex: copper ≈ $20–30k per t/yr; lithium carbonate ≈ $30–45k per t/yr (brine/DLE, outside China); spodumene concentrate much lower.
- Tailings incident: about 0.1–0.5% per mine-year chance of a reportable incident (pure design assumption), scaled by a management-quality attribute.

---

## 7. Sources

USGS Mineral Commodity Summaries (price and production tables)

- [USGS MCS 2026 — Gallium](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-gallium.pdf)
- [USGS MCS 2026 — Germanium](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-germanium.pdf)
- [USGS MCS 2026 — Silicon](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-silicon.pdf)
- [USGS MCS 2026 — Copper](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-copper.pdf)
- [USGS MCS 2026 — Cobalt](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-cobalt.pdf)
- [USGS MCS 2026 — Lithium](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-lithium.pdf)
- [USGS MCS 2026 — Tin](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-tin.pdf)
- [USGS MCS 2026 — Tantalum](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-tantalum.pdf)
- [USGS MCS 2026 — Rare Earths](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-rare-earths.pdf)
- [USGS MCS 2026 — Quartz (high-purity, cultured)](https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-quartz.pdf)
- [USGS MCS 2025 — Gallium](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-gallium.pdf)
- [USGS MCS 2025 — Germanium](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-germanium.pdf)
- [USGS MCS 2025 — Copper](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-copper.pdf)
- [USGS MCS 2025 — Lithium](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-lithium.pdf)
- [USGS MCS 2025 — Silicon](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-silicon.pdf)
- [USGS MCS 2025 — Tin](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-tin.pdf)
- [USGS MCS 2025 — Tantalum](https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-tantalum.pdf?v=050706)
- [USGS MCS 2022 — Silicon](https://pubs.usgs.gov/periodicals/mcs2022/mcs2022-silicon.pdf)
- [USGS Mineral Commodity Summaries 2021 (full volume)](https://pubs.usgs.gov/periodicals/mcs2021/mcs2021.pdf)
- [USGS Mineral Commodity Summaries 2020 (full volume, UNT web archive)](https://webarchive.library.unt.edu/web/20201219071832/https://pubs.usgs.gov/periodicals/mcs2020/mcs2020.pdf)
- [USGS MCS 2018 — Silicon](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/silicon/mcs-2018-simet.pdf)
- [USGS MCS 2017 — Silicon](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/silicon/mcs-2017-simet.pdf)
- [USGS Mineral Commodity Summaries 2015 (full volume)](https://apps.usgs.gov/minerals-information-archives/mcs/mcs2015.pdf)
- [USGS Minerals Yearbook 2019 — Tin](https://pubs.usgs.gov/myb/vol1/2019/myb1-2019-tin.pdf)
- [USGS Minerals Yearbook 2018 — Tantalum](https://pubs.usgs.gov/myb/vol1/2018/myb1-2018-tanta.pdf)
- [USGS Minerals Yearbook 2020 — Tantalum](https://pubs.usgs.gov/myb/vol1/2020/myb1-2020-tantalum.pdf)
- [IndexMundi — USGS tantalum price table (Ryan's Notes 2009–2013)](https://www.indexmundi.com/en/commodities/minerals/columbium_(niobium)_and_tantalum/columbium_(niobium)_and_tantalum_t2.html)
- [IndexMundi — USGS tin table](https://www.indexmundi.com/en/commodities/minerals/tin/tin_t1.html)
- [FRED — Global price of Tin (IMF), annual](https://fred.stlouisfed.org/data/PTINUSDA.txt)

Polysilicon, neon, quartz

- [Bernreuter Research — Polysilicon price trend](https://www.bernreuter.com/polysilicon/price-trend/)
- [Bernreuter — Polysilicon price decline in 2023 vs. 2011](https://www.bernreuter.com/newsroom/polysilicon-news/article/polysilicon-price-decline-in-2023-vs-2011-an-amazing-parallel/)
- [PV Tech — Polysilicon prices remained depressed throughout 2024](https://www.pv-tech.org/polysilicon-prices-remained-depressed-throughout-2024-when-will-they-rebound/)
- [PV Tech — Polysilicon prices jump a further 13% (Oct 2021)](https://www.pv-tech.org/pv-price-watch-polysilicon-prices-jump-a-further-13-as-double-control-energy-measures-exacerbate-supply-issues)
- [EnergyTrend — Global polysilicon industry in 2023](https://www.energytrend.com/print/47706)
- [USITC Executive Briefing — Ukraine, Neon, and Semiconductors](https://www.usitc.gov/publications/332/executive_briefings/ebot_decarlo_goodman_ukraine_neon_and_semiconductors.pdf)
- [ETNews — Neon import prices from China (Aug 2022)](https://english.etnews.com/20220809200008)
- [TechNode — A brief look at China's rare gas market](https://technode.com/2022/03/25/a-brief-look-at-chinas-rare-gas-market/)
- [SPIE Photonics Focus — Supplying noble gases for photonics in war time](https://lux.spie.org/news/photonics-focus/mayjune-2023/supplying-noble-gases-for-photonics-in-war-time)
- [Sibelco — High purity quartz](https://sibelco.com/materials/high-purity-quartz)

Production shares and refining

- [Visual Capitalist — China's dominance in clean energy metals (IEA data)](https://www.visualcapitalist.com/chinas-dominance-in-clean-energy-metals)
- [MINING.COM — IEA: critical minerals still dominated by few](https://www.mining.com/?p=1179474)
- [PBS — World's supply of clean energy minerals concentrated (IEA 2025)](https://www.pbs.org/newshour/world/worlds-supply-of-clean-energy-minerals-is-concentrated-in-fewer-countries-report-says)
- [IISD — Commodity profile: Cobalt (2026)](https://www.iisd.org/system/files/2026-05/commodity-profile-cobalt.pdf)
- [ING Think — China restricts exports of gallium and germanium](https://think.ing.com/articles/china-strikes-back-in-the-tech-war-restricting-exports-of-gallium-and-germanium/)

Companies

- [Wacker Chemie Annual Report 2010 — Earnings](https://reports.wacker.com/2010/ar/managementreport/earnings.html)
- [GCL-Poly 2010 annual results (HKEX)](https://www1.hkexnews.hk/listedco/listconews/sehk/2011/0317/ltn20110317592_c.pdf)
- [CompaniesMarketCap — SUMCO revenue](https://companiesmarketcap.com/sumco-corporation/revenue/)
- [CompaniesMarketCap — SMIC revenue](https://companiesmarketcap.com/smic/revenue/)
- [CompaniesMarketCap — Umicore revenue](https://companiesmarketcap.com/umicore/revenue/)
- [Macrotrends — UMC revenue](https://macrotrends.net/stocks/charts/UMC/united-microelectronics/revenue)
- [Macrotrends — Shin-Etsu revenue](https://macrotrends.net/stocks/charts/SHECY/shin-etsu-chemical/revenue)
- [SWI swissinfo — Glencore boosted by prices and demand](https://www.swissinfo.ch/eng/business/glencore-boosted-by-prices-and-demand/32232512)
- [APH Networks — GlobalFoundries expects $3.5 billion revenues in 2010](https://aphnetworks.com/index.php/news/2010/10/20/globalfoundries-expects-35-billion-revenues-2010)
- [DigiTimes — 2010 foundry rankings](https://www.digitimes.com/news/a20110124RS400.html?chid=2)
- [Wikipedia — Semiconductor equipment sales leaders by year](https://en.wikipedia.org/wiki/Semiconductor_equipment_sales_leaders_by_year)
- [Mining Weekly — Lynas ups Kalgoorlie capital costs to A$800m](https://www.Miningweekly.Com/article/lynas-ups-kalgoorlie-capital-costs-budget-to-a800m-2024-04-24)

Process nodes and wafer economics

- [CSET — Analysts believe a single TSMC 5nm wafer costs $17,000](https://cset.georgetown.edu/?p=3547)
- [TechSpot — TSMC 5nm wafer costs $17,000](https://www.techspot.com/news/86813-analysts-believe-single-tsmc-5nm-wafer-costs-17000.html)
- [Tom's Hardware — TSMC estimated wafer prices revealed](https://www.tomshardware.com/news/tsmcs-wafer-prices-revealed-300mm-wafer-at-5nm-is-nearly-dollar17000)
- [Silicon Analysts — Semiconductor wafer pricing by process node](https://siliconanalysts.com/data/wafer-pricing)
- [TechNode — TSMC sets 2nm wafer price at $30,000](https://technode.com/2025/10/09/tsmc-sets-2nm-wafer-price-at-30000-far-below-earlier-50-increase-speculation/)
- [Tom's Hardware — TSMC could charge up to $45,000 for 1.6nm wafers (rumour)](https://www.tomshardware.com/tech-industry/semiconductors/tsmc-could-charge-up-to-usd45-000-for-1-6nm-wafers-rumors-allege-a-50-percent-increase-in-pricing-over-prior-gen-wafers)
- [Focus Taiwan — TSMC began 2nm volume production in Q4 2025](https://focustaiwan.tw/sci-tech/202512300026)
- [Guru3D — TSMC breaks ground on Fab 18](https://guru3d.com/story/tsmc-breaks-ground-on-fab-18-in-southern-taiwan-science-park)
- [eeNews Europe — TSMC picks Arizona for 5nm wafer fab](https://www.eenewseurope.com/en/tsmc-picks-arizona-for-5nm-wafer-fab/)
- [Wikipedia — 7 nm process](https://en.wikipedia.org/wiki/7_nm_process)
- [Wikipedia — 14 nm process](https://en.wikipedia.org/wiki/14_nm_process)
- [Surf Wiki — 5 nm process](https://www.doc.surf/wiki/5-nm-process)
- [Wikiwand — 3 nm process](https://www.wikiwand.com/en/articles/3_nm)
- [Intel Newsroom — Panther Lake, first platform on 18A](https://www.intel.com/content/www/us/en/newsroom/news/client-computing/intel-unveils-panther-lake-architecture-first-ai-pc-platform-built-on-18a.html)

Export controls and geopolitics

- [Wikipedia — Rare earths trade dispute](https://en.wikipedia.org/wiki/Rare_earths_trade_dispute)
- [Wikipedia — US New Export Controls on Advanced Computing and Semiconductors to China](https://en.wikipedia.org/wiki/United_States_New_Export_Controls_on_Advanced_Computing_and_Semiconductors_to_China)
- [CSIS (Allen, Mar 2025) — AI export controls report](https://csis-website-prod.s3.amazonaws.com/s3fs-public/2025-03/250314_Allen_AI_Controls.pdf)
- [Reuters via TradingView — What critical minerals are on China's export control list now?](https://de.tradingview.com/news/reuters.com%2C2025%3Anewsml_L2N3VQ0C8%3A0-what-critical-minerals-are-on-china-s-export-control-list-now)
- [Reuters via Investing.com — Factbox: Chile lithium move latest in resource nationalism trend](https://ca.investing.com/news/commodities-news/factboxchile-lithium-move-latest-in-global-resource-nationalism-trend-2968785)
- [China Global South Project — Critical mineral resource nationalism](https://chinaglobalsouth.com/analysis/critical-minerals-resource-nationalism-china/)

Mining economics

- [S&P Global — From 6 years to 18 years: the increasing trend of mine lead times](https://www.spglobal.com/market-intelligence/en/news-insights/research/from-6years-to-18years-the-increasing-trend-of-mine-lead-times)
- [S&P Global — Discovery to production averages 15.7 years for 127 mines](https://www.spglobal.com/marketintelligence/en/news-insights/research/discovery-to-production-averages-15-7-years-for-127-mines)
- [S&P Global — Capital demands soar for new copper supply (Dec 2025)](https://www.spglobal.com/market-intelligence/en/news-insights/research/2025/12/capital-demands-soar-for-new-copper-supply)
- [S&P Global — Copper all-in sustaining cost jumps 16.2% YOY in 2021](https://www.spglobal.com/marketintelligence/en/news-insights/research/copper-all-in-sustaining-cost-jumps-162-yoy-in-2021-margins-double)
- [Mining News — IEA: government action to prevent critical mineral shortage (16.5-year lead time)](https://miningnews.net/esg/news/1409607/government-action-prevent-critical-mineral-shortage-iea)
- [Wood Mackenzie — Trade-offs in lithium: brine vs hard rock](https://www.woodmac.com/news/opinion/trade-offs-lithium-brine-hard-rock-extraction)
- [McIntosh — UNCOVER summit: exploration discovery statistics (Australian Academy of Science)](https://www.science.org.au/files/userfiles/support/reports-and-plans/2012/uncover/summit/session-1/3-5_mcintosh.pdf)
- [Mining Weekly — Rio Tinto to invest $2.5bn in Rincon lithium](https://www.miningweekly.com/article/rio-tinto-to-invest-25bn-in-rincon-lithium-project-capacity-expansion-2024-12-12)
- [Wikipedia — Tailings dam failure](https://en.wikipedia.org/wiki/Tailings_dam_failure)
