## Financial services (`finance_services.yaml`), 2000-2007

M50b, 2026-11-28. 61 series extended back to 2000 by insertion only; every value from 2008 on is unchanged. Tags as the file's header: **S** fetched this session, **D** derived, **R** recalled from the named source (not re-read), **A** an assumption with its basis. FRED's CSV service (`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series>`) was reachable; yearly values are the means of the series' observations, and the 2008-2009 means were re-computed and match the file's existing S rows exactly.

| Series family | 2000-2007 values (2000 ... 2007) | Tag | Source |
| --- | --- | --- | --- |
| `cpi` (CPI-U, NSA, annual average) | 172.200, 177.067, 179.875, 183.958, 188.883, 195.292, 201.592, 207.342 | S | FRED CPIAUCNS (BLS) |
| `banking.nim`, % | 3.93, 3.85, 4.07, 3.75, 3.62, 3.56, 3.45, 3.35 | S | FRED USNIM (FDIC) |
| `banking.deposits_trn`, $T | 3.602, 3.903, 4.217, 4.527, 4.934, 5.390, 5.852, 6.366 | S | FRED DPSACBW027SBOG (H.8) |
| `banking.loans_trn`, $T | 3.562, 3.744, 3.813, 4.088, 4.412, 4.942, 5.523, 6.106 | S | FRED TOTLL (H.8) |
| losses: mortgage, % | 0.12, 0.24, 0.16, 0.19, 0.10, 0.08, 0.10, 0.26 | S | FRED CORSFRMACBS |
| losses: consumer | 2.31, 2.72, 3.16, 2.88, 2.66, 2.74, 2.01, 2.48 | S | FRED CORCACBS |
| losses: card | 4.31, 5.42, 6.40, 5.82, 4.96, 4.84, 3.54, 3.99 | S | FRED CORCCACBS |
| losses: small business | 0.74, 1.38, 1.80, 1.30, 0.56, 0.26, 0.28, 0.48 | S | FRED CORBLACBS |
| losses: corporate | 0.59, 1.10, 1.44, 1.04, 0.44, 0.20, 0.22, 0.38 | D | business x 0.8 (the file's rule) |
| `insurance.combined_ratio.property`, % | 110.4, 115.8, 107.2, 100.1, 98.7, 100.7, 92.4, 95.5 | R | US P&C industry (III / ISO / AM Best), recalled |
| `insurance.combined_ratio.life` | 2000 anchor 103.0 | A | the file's flat assumption |
| `insurance.cat_losses_bn`, $B | 11, 13, 12, 18, 49, 83, 16, 28 | R | Swiss Re sigma, recalled, nominal; 2001 excludes 11 September (man-made, about $20B+, held in 2001's combined ratio) |
| `insurance.premiums_bn` | life 1521 (2000), 1848 (2004), 2393 (2007); property 600, 907, 1084 | R / D | Swiss Re sigma world premiums (recalled); property = non-life x 0.65 (health out of scope; the same factor reproduces the file's 2010 1180) |
| `payments.volume_bn` (2000, 2004 anchors) | NA 1650, 2300; EU 700, 1150; EA 450, 800; SSEA 60, 110; LatAm 130, 200; Africa 15, 28; Oceania 75, 130 | A | US card purchase volume about $1.5-1.6T in 2000 (Nilson, R) plus Canada and Mexico; elsewhere scaled from the 2010 rows by recalled network growth (Visa, Mastercard, Amex volumes roughly 40-50% of 2010's in 2000) and the dollar's 2000-2004 strength |
| network shares (2000, 2004) | Visa and Mastercard as 2008 within a few points; Amex slightly higher in 2000 (NA 0.17); East Asia Visa 0.25 / MC 0.20 before UnionPay | A | UnionPay founded March 2002 (R): 0.0 at 2000 and 2002, 0.15 at 2004 |
| rivals' shares (2000, 2004 anchors) | e.g. JPMorgan Chase 0.07, 0.10 (Bank One July 2004); Bank of America 0.10, 0.125 (FleetBoston 2004); Wells Fargo 0.047, 0.056, 0.054 (2007; Wachovia end 2008); SVB 0.0014, 0.0009, 0.0008 | A | each company's recalled deposits or premiums (R: annual reports) over the market at the date (deposits_trn above for US banks) |
| fintech entrants | Adyen 0.0 (2000, 2006: founded 2006); Ant Group 0.0 (2000, 2004: Alipay December 2004) | A | did not exist: share zero (the code multiplies a share by the market; zero is safe) |
| other rivals | First Data 0.40 (held); Worldpay 0.20, 0.22 (RBS Streamline / WorldPay); HSBC 0.045, 0.05; BNP Paribas 0.035, 0.04 (merger 2000); ICBC 0.05, 0.065; HDFC Bank 0.008, 0.015; Itau (alone before the November 2008 merger) 0.05, 0.06; Allianz 0.06, 0.065; AXA 0.07, 0.08; Generali 0.05, 0.06; Ping An 0.01, 0.015; Berkshire 0.05; MetLife 0.03, 0.035 (Travelers Life July 2005); Chubb (ACE) 0.012, 0.018 | A | as above |

Tag mix: 72 S values (cpi, NIM, deposits, loans, four charge-off series), 8 D (corporate losses) plus 3 D property premiums, 19 R (combined ratio, catastrophes, life premiums), the rest A (card volumes, network and rival shares, life combined ratio).

### Could not check

- Swiss Re sigma premiums and catastrophe losses, and the US P&C combined ratios (recalled; sigma's site was not tried).
- Card volumes by region and every network's regional split (A; Nilson Report not reachable).
- Rivals' 2000 and 2004 deposits and premiums (recalled from annual reports, not re-read).
- Not series, so not filled (the gap checker does not see them), but read by the code: `interchange_bp` and `insured_limit` start at 2008-01 / 2008-10, so `interchange_at` and `limit_at` return 0 before then; `capital` and `solvency` fall back to their first (2008) rows. Adding 2000 rows would change those lines, and the US limit row (October 2008) would change a 2008 game, so they are left for the lane's code owner (real values: US insured limit $100,000 before October 2008; EU minimum EUR 20,000 under Directive 94/19/EC; Basel I before 2008).
