# Pharma, medical devices and space: 2000-2007 (M50b)

Files: `backend/data/pharma.yaml`, `backend/data/medical.yaml`, `backend/data/space.yaml`. Every 2000-2007
entry was inserted before the existing 2008 one; 2008 on is byte-identical (checked structurally against
`HEAD`), and the code's `from_2010` read (ADR-0024, M50b) drops these years for 2008 and 2010 games.
Researched 2026-11-28.

## Pharma (`pharma.yaml`, 41 series)

| Series | 2000-2007 entries | Tags | Sources |
|---|---|---|---|
| `indications[*].market_b` (20) | anchors 2000 and 2004 (interpolated between, then to 2008) | A | Class sizes from the period's leading drugs (Lipitor, Zocor, Plavix, Gleevec, Rituxan, Enbrel, Remicade, the SSRIs before generics, insulins and glitazones), scaled to world pharma sales of about $390B (2000) and $560B (2004) (IMS Health, R) |
| `rivals[*].revenue` (16) | anchors 2000, 2004, 2006 | R, D (currency), A est. (Abbott pharma, Merck ex-Medco, Roche 2000, GSK 2000 pro forma, Sandoz 2000, Sun) | Annual reports for FY2000, FY2004 and FY2006, recalled (not opened). Each is the same business as 2008's entry. Sanofi is Sanofi-Synthelabo in 2000 and Sanofi-Aventis as reported from August 2004. Merck excludes Medco (spun off 2003) |
| `rivals[*].drugs[*].revenue` (5) | Lipitor, Remicade, Copaxone: 2000/2004/2006. Humira: 0 in 2000 and 2002, then 2003/2004/2006. Crestor: 0 in 2000, then 2003/2004/2006 | R; Copaxone est. | Company reports (R). Humira was approved December 2002 and Crestor in 2003. The zeros come before approval (`key_drug_b` returns 0 before `approved` anyway) |
| Currency rates | 2000, 2004, 2006 annual averages | S | FRED AEXSZUS, AEXDNUS, AEXUSEU, AEXUSUK, AEXINUS (https://fred.stlouisfed.org/graph/fredgraph.csv?id=AEXUSEU etc., fetched) |

## Medical devices (`medical.yaml`, 12 series)

| Series | Entry | Tag | Source |
|---|---|---|---|
| `subcategories[*].uses[*].us_class` (12) | `"2000-01"`, the class held in 2008 | R | FDA product classification (21 CFR 862-892), recalled: no class changed between 2000 and 2007. The first CGM (MiniMed CGMS, PMA P980022, June 1999) was class III, and da Vinci (510(k) K990144, July 2000) is already the file's `predicate_from` |

## Space (`space.yaml`, 13 series)

| Series | 2000-2007 values | Tags | Source |
|---|---|---|---|
| `cpi` | 172.200, 177.067, 179.875, 183.958, 188.883, 195.292, 201.592, 207.342 | S | FRED CPIAUCNS, annual average (fetched). Its 2008 value, 215.303, matches the file's |
| `launch.world` | 85, 59, 65, 63, 54, 55, 67, 68 | S | en.wikipedia.org "2000 in spaceflight" to "2007 in spaceflight", infobox totals |
| SpaceX | 0 in every year | D | Founded 2002. Falcon 1's 2006-2007 flights are not counted, by M50's rule |
| United Launch Alliance | 0 (2000-2005), 1 (2006), 13 (2007) | D, S, R | Wikipedia "United Launch Alliance": formed December 2006, first launch on 14 December 2006. 2007 comes from ULA's GPS IIR-18 release ("13th and final mission for ULA in 2007"), read through a search summary |
| Arianespace | 12, 8, 12, 4, 3, 5, 5, 6 | S (2000-2006), R (2007) | Year pages, by-country and by-family tables (Ariane 4 and 5) |
| CASC | 5, 1, 5, 7, 8, 5, 6, 10 | D | China's totals x 1, M50's rule. 2003 includes Kaituozhe-1. 2007's tables did not load, so its 10 is R |
| ISRO | 0, 2, 1, 2, 1, 1, 1, 3 | S, R (2007) | Year pages, by-country tables |
| Shuttle `price_usd` | 2000: $1.642B (2012 $) | D | The programme average, as M50 used |
| Falcon 9 v1 `price_usd` | 2000: $49.9M (2010 $) | A | The first list price, held back (the vehicle was announced in 2005) |
| Viasat (WildBlue) satellites | 0 (2000-2003), 1 (2004-2005), 2 (2006-2007) | A, R | Anik F2's Ka payload (July 2004) and WildBlue-1 (December 2006) |
| Viasat (WildBlue) subscribers (thousands) | 0 (2000, 2004), 25 (2005), 135 (2006), 300 (2007) | A, R | Service from June 2005. About 25,000 by January 2006 (Satellite Today, December 2005). About 140,000 in early 2007 and 300,000 at the end of 2007 (SpaceNews). Both were read through search summaries |
| Maxar satellites | 0 (2000), 1 (2001), 1 (2006), 2 (2007) | S | Wikipedia "DigitalGlobe": QuickBird-1 was lost at launch (2000). QuickBird launched 18 October 2001 and WorldView-1 on 18 September 2007 |
| `satellite_cost_usd` | 2000: $20,000 a kg (2000 $) | A | Held at 2008's value |

## Could not check

- **Pharma figures:** every rival and drug revenue figure for 2000-2006 is recalled (R). No filing could be opened. The least certain are Abbott's pharma segment, Merck without Medco in 2000, Roche and Novartis Pharma in 2000, GSK's 2000 pro forma, Sandoz in 2000 and Sun Pharma's fiscal years.
- **Pharma market sizes:** every 2000 and 2004 `market_b` anchor is an assumption (A), as M42's and M50's were.
- **Space:** the 2007 by-country tables (China, India, Ariane) did not load. The ULA 2007 count and the WildBlue counts were read through search summaries only.
- **Possible data error:** M50's Maxar 2008 count (3) is one more than DigitalGlobe's satellites (QuickBird and WorldView-1). The 2007 entry gives the real count (2), so the series steps up in 2008.
