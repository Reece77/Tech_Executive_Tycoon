# v5 research dossier: market sizes (for M43a)

**Status:** researched by M43a (2026-11-17; section below), starting list kept above. The M43a session finds a published 2025 size (and where possible 2010 and 2020) for every category in `categories.yaml`, cites it, and records the definition used. Use a consistent source family where possible (Gartner IT spending, IDC, Statista, company reports, IEA for vehicles), and note the range where sources disagree.

## Anchors

- **World GDP:** about $110 trillion nominal (2024–2025), IMF World Economic Outlook *(verify)*; regional GDP from the IMF for the game's regions *(verify)*.
- **Worldwide IT spending:** about $5.4–5.7 trillion (2025), Gartner *(verify)*, about 5% of world GDP. Gartner's segments: data centre systems, devices, software, IT services, communications services.
- **Generative AI and AI models:** model APIs and AI software revenue in 2024–2025 (OpenAI about $3.7B in 2024 and higher in 2025; Anthropic; Google, Microsoft and AWS AI services), and broader "AI software" estimates (IDC, Gartner) *(verify)*. The game's `ai_models` definition must be pinned: model APIs and AI applications, or also AI cloud infrastructure (which `cloud_hosting` and the chip categories may already count).

## Per category (find each)

- `b2b_saas`, `consumer_apps`, `dev_tools`, `cloud_hosting` (public cloud IaaS and PaaS: about $400–500B in 2025 *(verify)*), `fintech`, `ai_models`, `devices` (smartphones about $450–500B *(verify)*), the chip categories (`chips_mobile`, `server_cpu`, `ai_accelerator`: data-centre AI chips about $150–250B in 2025 *(verify)*), `vehicles` (M38's), the medical sub-categories (M41's), robotics (M39's).
- For each: 2010, 2020 and 2025 sizes; definition; source.

## Ceilings

- Long-run IT spending share of GDP (historically about 4–6%) *(verify)*; highest share any single segment has reached (software about 1.1–1.3% of world GDP) *(verify)*; long-run real GDP growth assumptions (IMF, OECD long-term scenarios) *(verify)*.

## M43a research (2026-11-17)

Compiled by the M43a session (about 40 web searches). Tags: [V] checked in the source this session; [D] derived from [V] figures; [M] from memory, not re-checked (imf.org, gartner.com and statisticstimes.com were blocked by the session's network).

### Anchors

| Anchor | 2010 | 2020 | 2024 | 2025 | Notes / source |
|---|---|---|---|---|---|
| World GDP (IMF WEO) | ~$66.5T [M] | ~$85.5T [M] | ~$111T [M] | ~$117T [M] (Oct-2025 WEO) | The IMF datamapper/WEO could not be reached (blocked). Secondary sites quote $113.8T (Apr-2025 WEO) to $118T for 2025 [V, secondary]. Real growth: 3.3% (2024), 3.2% (2025), 3.1% (2026) per IMF WEO Oct 2025 [V] https://www.imf.org/en/publications/weo/issues/2025/10/14/world-economic-outlook-october-2025 |
| Gartner worldwide IT spending | $3.39T [V] (Apr-2010 forecast) | $3.69T [V] (Jan-2021 actual, -3.2%) | $5.04T [D] | $5.44T [V] (Jul-2025 forecast, +7.9%) | 2010: Gartner Apr 2010 via eWeek https://www.eweek.com/fr/networking/global-it-spending-to-grow-5-3-percent-in-2010-gartner/ ; 2020: Gartner Jan 2021 via NextPlatform https://www.nextplatform.com/2021/02/05/the-most-volatile-it-spending-year-is-in-the-rear-view-mirror/ ; 2025: Gartner Jul 2025 https://www.gartner.com/en/newsroom/press-releases/2025-07-15-gartner-forecasts-worldwide-it-spending-to-grow-7-point-9-percent-in-2025 (table reproduced at cxotoday/it-online) |
| IT spending as % of world GDP | ~5.1% [D] | ~4.3% [D] | ~4.5% [D] | ~4.6% [D] | Gartner divided by IMF [M] GDP. The 2010 figure uses Gartner's older taxonomy, in which telecom includes equipment. |

**Gartner segments**

| Segment | 2010 (old taxonomy) | 2020 (Jan-2021 actual) | 2025 (Jul-2025 forecast) | 2025 as % of GDP |
|---|---|---|---|---|
| Data center systems | in "computing hardware" $353B | $215B [V] | $474.9B [V] (+42.4%) | 0.41% |
| Devices | in hardware/telecom | ~$650B [M]; Jul-2020 forecast was $597B [V] | $759.6B [V] (the Oct-2025 revision has $783B) | 0.65% |
| Software | $232B [V] (older, narrower scope) | $465B [V] (enterprise software) | $1,232B [V] | 1.05% |
| IT services | $821B [V] | ~$1.01T [M]; Jul-2020 forecast was $969B [V] | $1,686B [V] | 1.44% |
| Communications services | $1,988B [V] ("telecom", which includes equipment) | ~$1.35T [V] | $1,283B [V] | 1.10% |

**Long-run real growth:**
- OECD 2014 "Shifting Gear": world growth slows from 3.6% (2010-20) to 2.4% (2050-60) [V].
- OECD 2018 "The Long View": 3.5% down to about 2% by 2060 [V, secondary].
- Latest OECD "The long game" (2023): the OECD+G20 trend falls from ~3% to ~1.5% by 2060 [V].
- A reasonable game default is ~3% world real growth falling toward ~2%. https://search.oecd.org/eco/growth/scenarios-for-the-world-economy-to-2060.htm ; https://www.stat.berkeley.edu/~aldous/157/Papers/shifting_gear.pdf

**Highest share of world GDP reached by one tech segment:**
- Gartner's 2010 "telecom" line (services plus equipment) was ~3.0% of GDP.
- The largest segment today is IT services, at ~1.4%.
- Software is at its all-time high of ~1.05% (2025).
- Communications services is ~1.1% and falling.
- Data center systems is ~0.4% and rising fast.
- No published "all-time maximum" figure was found. These shares are my own arithmetic [D].

**Regional GDP, 2025 nominal. Every value here is [M]** (IMF WEO Oct-2025 order of magnitude; the WEO could not be reached to check).

| Region | 2025 GDP | Built from |
|---|---|---|
| North America (US+CA+MX) | ~$34.5T | US ~30.5, Canada ~2.3, Mexico ~1.8 |
| Europe | ~$29T including Russia and Türkiye, ~$25T without | EU ~19.4, UK ~4.0, CH ~0.95 |
| East Asia (CN+JP+KR+TW) | ~$26.4T | China ~19.4, Japan ~4.3, Korea ~1.8, Taiwan ~0.85 |
| South and Southeast Asia | ~$9.3T | India ~4.1, ASEAN ~4.0-4.2, rest of South Asia ~1.0 |
| Latin America (excluding Mexico) | ~$4.8T | Brazil ~2.3, Argentina ~0.7 |
| Africa | ~$2.9T | |
| Oceania | ~$2.1T | |
| Remainder (Middle East and Central Asia) | ~$7T | |

### Market categories

| # | Category | 2010 | 2020 | 2025 (or 2024) | Definition / source | Notes |
|---|---|---|---|---|---|---|
| 1 | b2b_saas | $9.2B [V] (Gartner, SaaS within enterprise application software) | ~$100B [M] (Gartner SaaS) | $299B [V] (2025 forecast); $250B+ in 2024 | Gartner public-cloud end-user spending, SaaS line (Nov 2024 release) https://www.gartner.com/en/newsroom/press-releases/2024-11-19-gartner-forecasts-worldwide-public-cloud-end-user-spending-to-total-723-billion-dollars-in-2025 ; 2010: https://itpro.com/629455/enterprise-saas-revenues-top-9-billion | Gartner's total software line is $1.23T (2025). Its "enterprise application software" figure was $149.9B in 2015 (forecast) [V]. I found no 2025 enterprise-app total. A separate Gartner series gives 2024 SaaS revenue as $218.5B [V], so the series differ. |
| 2 | dev_tools | not found | not found | ~$13-14B [V] (2024, "DevOps market") | Fallback market-research firms only (Roots, IMARC, Credence) https://www.imarcgroup.com/devops-market-statistics | I found no Gartner or IDC figure. Company anchors (all [M]): Atlassian FY25 ~$5.2B, GitHub ~$2B+ ARR, GitLab ~$0.76B, JetBrains ~$0.6B. Counting app-dev and ALM more broadly plausibly gives ~$20-30B (my judgement). |
| 3 | consumer_apps | ~$5B [M] (Gartner app-store revenue est.) | $143B [V] (App Annie; includes China third-party Android stores) | $167B [V] (2025); $150B (2024) | Sensor Tower, gross in-app purchases, subscriptions and paid apps on iOS and Google Play (including the store commission). Excludes advertising, so social ads are excluded. https://sensortower.com/blog/2025-state-of-mobile-consumers-usd150-billion-spent-on-mobile-highlights ; https://techcrunch.com/2021/01/13/app-stores-saw-record-218-billion-downloads-in-2020-consumer-spend-of-143-billion | Games were $82B of the 2024 total, so non-game apps were ~$68B. If consumer_apps means non-game apps, use about half the total. |
| 4 | cybersecurity | ~$16.5B [M] (Gartner security software) | ~$124B [M] (Gartner infosec) | $213B [V] total; security software $106B, services $84B, network security $23B (2025) | Gartner information security end-user spending (Jul 2025) https://www.gartner.com/en/newsroom/press-releases/2025-07-29-gartner-forecasts-worldwide-end-user-spending-on-information-security-to-total-213-billion-us-dollars-in-2025 | The 2024 total was $193B. Gartner forecasts $240B for 2026. |
| 5 | fintech | not found | not found | $378B [V] (2024) | BCG and QED, "Fintech's Next Chapter: Scaled Winners and Emerging Disruptors" (Jun 2025), fintech revenues https://www.bcg.com/publications/2025/fintechs-scaled-winners-emerging-disruptors | Grew +21% in 2024. Payments fintechs are $126B. Fintech is ~3% of the $12.7T banking and insurance revenue pool. For 2025, ~$430-450B if growth stays at 15-20% [D]. |
| 6 | ai_models | ~0 | ~0 | Narrow: ~$20-40B (2025). Broad: ~$300B (2025). | Narrow: Gartner "GenAI models" $14.2B (2025) [V]; Gartner GenAI software $37.2B [V]. OpenAI recognised revenue ~$13B in 2025 and ~$20-21B run-rate at year end; Anthropic ~$9B run-rate at year end [V, press]. Broad: Gartner AI application software $172B plus AI infrastructure software $126B (2025) [V]. https://gartner.com/en/newsroom/press-releases/2025-09-17-gartner-says-worldwide-ai-spending-will-total-1-point-5-trillion-in-2025 ; https://www.gartner.com/en/newsroom/press-releases/2025-03-31-gartner-forecasts-worldwide-genai-spending-to-reach-644-billion-in-2025 | Gartner's total AI spending is $1.48T (2025), but that includes GenAI phones ($298B), servers ($268B), chips ($209B) and services ($283B), so do not use it as a software figure. Run-rates exploded in 2026 (OpenAI ~$70B, Anthropic ~$65B) [V, press]. |
| 7 | cloud_hosting | ~$2B [D] (from Synergy's 52%/yr decade CAGR) | $129B [V] (Synergy) | $419B [V] (Synergy 2025); Gartner IaaS $211.9B + PaaS $208.6B = $420B (2025 forecast) | Synergy: IaaS, PaaS and hosted private cloud https://www.srgresearch.com/articles/genai-helps-drive-quarterly-cloud-revenues-to-119-billion-as-growth-rate-jumped-yet-again-in-q4 ; 2020: https://www.srgresearch.com/articles/cloud-market-ends-2020-high-while-microsoft-continues-gain-ground-amazon | GPU cloud ("neoclouds") was >$25B in 2025 per Synergy [V], up 223% YoY in Q4. ABI's GPUaaS figure is $42B, on a different scope. https://srgresearch.com/articles/neocloud-market-forecast-to-approach-400b-by-2031-driven-by-surging-ai-infrastructure-demand |
| 8 | devices | Smartphones ~305M units [M]; PCs ~350M units [M] | Smartphones ~1.29B units [M]; PCs ~303M [M] | Smartphones 1.25B units [V]; value ~$540-560B [D] (IDC forecasts a $578.9B value at a $465 ASP for 2026). PCs 284.7M units [V]. Tablets ~150M [M]. | IDC trackers https://www.idc.com/resource-center/press-releases/q425mobilephonetop5/ ; PCs: https://www.thurrott.com/?p=331635 | Gartner's total devices line (phones, PCs, tablets) is $760-783B (2025) [V]. PCs ≈ $200B at ~$700 ASP [D]; tablets ≈ $50-60B [D]. The 2025 smartphone value is derived (forecast ASP ~+5%, value +6%). |
| 9 | servers | $48.1B [V] | ~$91B [D] (IDC quarters: $18.7B [M] + $24.0B + $22.6B + $25.8B) | $444.1B [V] (+80.4%) | IDC Worldwide Quarterly Server Tracker https://www.idc.com/resource-center/press-releases/4q25servertracker/ ; 2010: https://www.businesswire.com/news/home/20110228007267/en/ | GPU-embedded servers are >50% of 2025 revenue. Non-x86 rose +146%. |
| 10 | chips_mobile_soc | not found | not found | ~$40-50B [D/M] (2024-25) | Counterpoint gives revenue shares only, with no published total: Q4-2024 Apple 40%, Qualcomm 34%, MediaTek 13% https://www.counterpointresearch.com/insight/infographic-q4-2024-semiconductors-foundry-share-and-smartphone-ap-share | The dollar total is my rough build from company revenues [M] (Qualcomm handset ~$28B including modem/RF, MediaTek mobile ~$10B, Apple A-series internal value). Low confidence. |
| 11 | chips_server_cpu | ~$10-12B [M] (Intel DCG era) | ~$20B [M] | ~$23B [D] (2024); ~$25-30B (2025) | TechInsights: datacenter processors $136.3B in 2024, of which CPUs were 17% https://www.edge-ai-vision.com/2025/07/generative-ai-at-the-core-of-a-372-billion-data-center-processor-revolution/ | Mercury Q4-2025 revenue share: AMD 41.3% [V]. Intel DCAI ~$13B in 2024 [M]. Arm was ~13% of server units in Q1-25 [V]. Smaller estimates of $13-17B exist [V]. |
| 12 | chips_ai_accelerator | ~0 | ~$10-15B [M] (NVIDIA DC FY21 $6.7B [M]) | $170-290B [V] (2025) | NVIDIA FY26 (to Jan-2026) data center revenue $193.7B, of which networking was ~$31B [V] https://servethehome.com/nvidia-reports-q4-fy2026-earnings-data-center-and-proviz-drive-revenue-records ; Omdia "AI data center chips" $286B (2025) https://www.businesswire.com/news/home/20250828272306/en ; MarketsandMarkets $171B | Build: NVIDIA compute ~$160B, plus custom ASICs (Broadcom/Marvell ~$25B [M]), plus AMD MI ~$6-7B [M]. That gives ~$190-200B for accelerators alone [D]. |
| 13 | contract_manufacturing | ~$360B [M] | ~$500B [M] | $638-658B [V] (2024, EMS including ODM) | New Venture Research / Global Electronics Association https://www.emsnow.com/new-venture-research-releases-worldwide-electronic-manufacturing-services-market-2024-report/ ; https://iconnect007.com/article/150184/global-electronics-association-acquires-new-venture-research-ems-program/150181/smt | The top 50 EMS firms had $477B (2024, +12.7%) [V]. Foxconn alone was ~$213B (2024) and ~$250B (2025) [M]. Other firms give $810-820B, on a broader scope. |
| 14 | os | not found | not found | Rough ~$30-45B [M/judgement] | No published market total found. Windows OEM+Devices grew +3% in FY25 but Microsoft no longer reports a dollar figure [V] https://www.microsoft.com/en-us/investor/earnings/FY-2025-Q4/more-personal-computing-performance | Windows OEM is ~$15-18B [M]; Windows commercial and server OS, RHEL (~$5B) and others make up the rest. Mobile operating systems earn no licence fee (they are monetised through app stores and search). Low confidence. |
| 15 | vehicles (BEV+PHEV) | ~0.01M units | ~3M units [M] | 17M+ units (2024) [V]; >20M (2025) [V]. Value ~$550-650B [D] (2024) | IEA Global EV Outlook 2025 https://www.iea.org/reports/global-ev-outlook-2025/executive-summary ; spending chart https://www.iea.org/data-and-statistics/charts/global-consumer-and-government-spending-on-electric-cars-2017-2024 | EVs were >20% of global car sales in 2024. Government spending was <7% of the total. I could not read the IEA's dollar total. The value is 17M × ~$35k average [D]. |
| 16a | wearables_diagnostics | not found | not found | ~612M wearable units (2025) [V, secondary]; CGM ~$11B (2024) [M: Abbott Libre ~$6.8B + Dexcom $4.0B] | IDC Wearable Tracker via aggregator https://voxbooster.com/blog/wearables-statistics-2026 | I found no market-value total for wearables. Consumer wearables are ~$80-100B [judgement]. The medical-grade diagnostics part (CGM, cardiac monitors) is ~$15-20B [judgement]. |
| 16b | imaging | not found | not found | $42-46B [V] (2024) | Fortune Business Insights $41.9B; The Business Research Company $45.8B; BCC $63.4B (broad scope) https://fortunebusinessinsights.com/amp/industry-reports/medical-imaging-equipment-market-100382 | Fallback sources only. GE HealthCare, Siemens Healthineers imaging and Philips together make up the majority [M]. |
| 16c | surgical_robotics | ~$1.4B [M] (Intuitive 2010) | ~$4.4B [M] (Intuitive 2020) | Intuitive alone $8.35B (2024) [V], ~$10B (2025) [M] | Market reports give $2.9-4.3B (2024), which is clearly systems only [V] https://www.medicaldevice-network.com/features/why-2025-is-a-key-year-for-the-surgical-robotics-market/ | Including instruments and service, the market is ~$10-13B (2025) [D]. Intuitive's share is 60-84%. |
| 16d | implantables | not found | not found | $97-132B [V] (2024, all implantable devices) | Precedence / GMI via BioSpace https://www.biospace.com/press-releases/implantable-medical-devices-market-size-to-surpass-usd-179-70-billion-by-2034 | Fallback sources only. Cardiovascular is ~42% (≈$41B) [D]. Orthopedic is the largest or second-largest segment, ~$45-55B [M]. |
| 16e | samd | ~0 | ~$0.4B [V-ish] (Signify AI imaging) | ~$1-1.5B (2024) [D] AI in medical imaging | Signify Research: $576M (2022); forecast >$1.7B by 2027 https://www.auntminnie.com/imaging-informatics/artificial-intelligence/article/15633869/medical-imaging-ai-market-expected-to-exceed-17b-by-2027 | I found no broad SaMD market total. Fallback firms quote $5.9B for AI imaging (2024) [V], which is far above Signify. |
| 17a | industrial_robots | ~121k installations [M] | ~390k installations [M] | 542,076 installations (2024) [V]; 575k forecast for 2025 [V]. Value ~$16.5B [M] (IFR installation value, 2022) | IFR World Robotics 2025 https://ifr.org/ifr-press-releases/news/global-robot-demand-in-factories-doubles-over-10-years | China takes 54% of installations. The IFR's dollar value excludes software and peripherals. Including systems, the value is ~3× higher [M]. |
| 17b | humanoid_robots | 0 | ~0 | ~$0.4-3B (2025) [V, secondary]; ~13-18k units [V, secondary] | TrendForce forecasts >$2B by 2027 https://www.trendforce.com/presscenter/news/20250826-12685.html ; Goldman forecasts $38B by 2035 | Unitree's 2025 revenue was CNY 1.7B [V, secondary]. Low confidence. |

### Main gaps

- **Not found at all:** a market total for dev tools, mobile SoC chips, operating systems or broad SaMD, and any 2010 figure for most categories.
- **Taken from memory:** the IMF GDP figures. imf.org was blocked, so I could not re-check them.
- **Calculated rather than published:** the dollar value of EVs.
- **Gartner taxonomy change:** the 2010 Gartner segments use an older taxonomy (telecom includes equipment, and software is narrower), so they are not directly comparable with 2020 and 2025.
