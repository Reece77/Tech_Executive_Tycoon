# Research dossier: financial services and currencies (M54)

**Status:** placeholder figures for M54's `finance_services.yaml` and `fx_history.yaml` (2026-11-25, product manager). Tags: **S** fetched from the source named, **R** recalled from the named source and to be checked by the M54 session, **A** an assumption with its basis. As with M40 and M53, the session may reach only en.wikipedia.org: it re-checks every R row against Wikipedia's pages or the sources' filings where reachable, records corrections in the YAML header, and keeps the tag honest.

All money is real dollars here; the game applies the economy scale (§54, 0.085) as M53 did.

## 1. Banking

| Item | Value | Tag | Source |
| --- | --- | --- | --- |
| US banks' net interest margin | about 3.8% (2010), 3.3% (2015), 2.8% (2020), 2.5% (2021 low), 3.3% (2023), 3.2% (2024) | R | FDIC Quarterly Banking Profile, historical trends (https://fdic.gov/quarterly-banking-profile/fdic-historical-trends-december-2024-pdf); FRED QBPQYNTIY |
| Policy rate | already in `macro_history.yaml` (`base_rate`, the effective federal funds rate, 2008–2025) | S | FRED FEDFUNDS |
| Deposit beta (deposit rates follow the policy rate) | about 0.3 in 2016–2019's rises, about 0.4–0.5 in 2022–2023's | R | Federal Reserve and bank filings, commonly cited |
| Basel III minimums | CET1 4.5%, Tier 1 6%, total capital 8% of risk-weighted assets; capital conservation buffer 2.5% phased in 2016–2019; leverage ratio 3% (US large banks' enhanced 5%) | R | BIS, Basel III framework (2010, revised 2017) |
| G-SIB surcharges | 1.0%–3.5% of risk-weighted assets, from 2016 | R | FSB G-SIB list |
| Risk weights (standardised) | residential mortgages 35–50%, corporate loans 100%, consumer and cards 75–100%, sovereigns of rich countries 0% | R | Basel III standardised approach |
| US stress tests | CCAR from 2011, DFAST from 2013; yearly, results in June | R | Federal Reserve |
| Deposit insurance | US $250,000 (made permanent by Dodd-Frank, July 2010); EU €100,000 (Directive 2014/49/EU) | R | FDIC; EU DGSD |
| Loan losses (net charge-offs, US all loans) | about 2.5% (2010), 0.5% (2015–2019), 0.3% (2021 low), 0.6% (2024); cards about 3–5% | R | FDIC QBP; Federal Reserve charge-off series |
| Bank runs | Silicon Valley Bank failed 10 March 2023 after $42B of withdrawals in one day; Signature Bank 12 March; First Republic 1 May 2023 | R | FDIC; Wikipedia "Collapse of Silicon Valley Bank" |
| Fintechs with charters | Varo (national bank charter, July 2020); SoFi (bank holding company, January 2022, via Golden Pacific Bancorp); Square's Block (industrial bank, 2021) | R | OCC; company filings |
| Big banks 2010 → 2024 (total assets) | JPMorgan $2.1T → $4.0T; Bank of America $2.3T → $3.3T; Citigroup $1.9T → $2.4T; Wells Fargo $1.3T → $1.9T (asset cap February 2018 – June 2025); HSBC $2.5T → $3.0T; ICBC $2.0T → $6.7T; BNP Paribas $2.6T → $2.9T | R | the banks' annual reports |

## 2. Payments

| Item | Value | Tag | Source |
| --- | --- | --- | --- |
| Visa payments volume | about $3.2T (FY2010), $4.9T (FY2015), $8.8T (FY2020), $13.2T (FY2024) | R | Visa 10-K filings (https://www.sec.gov/Archives/edgar/data/0001403161/000140316115000013/v093015.htm) |
| Mastercard gross dollar volume | about $2.7T (2010), $4.8T (2015), $6.3T (2020), $9.8T (2024) | R | Mastercard 10-K filings |
| Network net revenue as a share of volume | about 0.2–0.3% (Visa net revenue / payments volume) | D | from the two rows above and Visa's revenue |
| Interchange (paid to the card issuer) | US credit about 1.8–2.2%; US regulated debit capped at 21¢ + 0.05% (+1¢ fraud) from October 2011 (Durbin amendment); EU 0.2% debit, 0.3% credit from December 2015 (IFR) | R | Federal Reserve Regulation II; EU Regulation 2015/751 |
| PayPal total payment volume | $92B (2010), $282B (2015), $936B (2020), $1.68T (2024) | R | PayPal annual reports |
| Stripe total payment volume | $1.4T (2024) | R | Stripe annual letter |
| Real-time rails | India's UPI from April 2016 (over 10 billion transactions a month by 2023); Brazil's Pix from November 2020; US FedNow from July 2023 | R | NPCI; Banco Central do Brasil; Federal Reserve |
| Apple Pay | US launch October 2014; Apple Card with Goldman Sachs August 2019 | R | Apple |
| Buy now, pay later | Klarna, Affirm (IPO January 2021); US CFPB rule on BNPL as credit cards, May 2024 (later withdrawn, 2025) | R | CFPB |
| Fraud losses | about 6–7¢ per $100 of card volume worldwide | R | Nilson Report |

## 3. Insurance

| Item | Value | Tag | Source |
| --- | --- | --- | --- |
| World premiums | about $4.3T (2010), $4.6T (2015), $6.3T (2020), about $7.2T (2024); real growth 5.2% in 2024 | R (2024 growth S) | Swiss Re sigma World insurance reports (https://www.swissre.com/institute/research/sigma-research/sigma-2025-02-world-insurance-risker-fragmented-world.html) |
| Split | life about 45%, non-life about 55% | R | Swiss Re sigma |
| Combined ratio (P&C) | about 95–105%, worse in catastrophe years (2011, 2017, 2022) | R | Swiss Re; AM Best |
| Investment income | the float earns about the policy rate, a large part of an insurer's profit | A | standard insurer economics |
| Solvency rules | EU Solvency II from 1 January 2016; US risk-based capital (NAIC) | R | EIOPA; NAIC |
| Catastrophe losses (insured) | about $130B (2011), $150B (2017), $125B (2022), $140B (2024) | R | Swiss Re sigma natural catastrophes |
| Insurtechs | Lemonade (founded 2015, IPO July 2020); Root (IPO October 2020) | R | company filings |
| Large insurers | Allianz, AXA, Ping An, Berkshire Hathaway, Prudential, Chubb, Generali, MetLife | R | annual reports |

## 4. Currencies (to 2025; yearly averages, local units a US dollar except EUR and GBP)

| Pair | 2010 | 2015 | 2020 | 2022 | 2024 | Tag | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EUR/USD (dollars a euro) | 1.33 | 1.11 | 1.14 | 1.05 | 1.08 | R | Federal Reserve H.10 |
| GBP/USD (dollars a pound) | 1.55 | 1.53 | 1.28 | 1.24 | 1.28 | R | Federal Reserve H.10 |
| USD/JPY | 87.8 | 121.0 | 106.8 | 131.5 | 151.4 | R | Federal Reserve H.10 |
| USD/CNY | 6.77 | 6.23 | 6.90 | 6.73 | 7.19 | R | Federal Reserve H.10 |
| USD/INR | 45.7 | 64.2 | 74.1 | 78.6 | 83.7 | R | Reserve Bank of India |
| USD/KRW | 1,156 | 1,131 | 1,180 | 1,292 | 1,364 | R | Bank of Korea |
| USD/BRL | 1.76 | 3.33 | 5.16 | 5.16 | 5.39 | R | Banco Central do Brasil |

Events: the Swiss franc's floor removed 15 January 2015 (CHF up about 20% in a day); the UK's referendum 23 June 2016 (GBP down about 8%); China's devaluation 11 August 2015; the yen's slide in 2022 and 2024.

**Hedging.** A forward's rate = spot × (1 + home rate) / (1 + foreign rate) for its term (covered interest parity); banks charge a spread of about 0.05–0.2% for majors and more for emerging currencies. Large tech groups hedge about 50–80% of a year's forecast foreign revenue (R: Apple, Microsoft and Alphabet 10-K hedging notes).

Monthly series for 2008–2025 come from the Federal Reserve H.10 (or Wikipedia's per-currency pages where only those are reachable); M54 builds `fx_history.yaml` with 12 values a year and the game's regions' currencies.

## 5. Regulation names

US: the Federal Reserve, the OCC, the FDIC, the CFPB (from July 2011), state insurance regulators. EU: the ECB's Single Supervisory Mechanism (from November 2014), the EBA, EIOPA. UK: the PRA and FCA (from April 2013). China: the PBoC and the NFRA (from 2023). India: the RBI. Notable actions: Wells Fargo's asset cap (2018–2025); Ant Group's IPO halted (November 2020); the CFPB's open-banking rule (October 2024).
