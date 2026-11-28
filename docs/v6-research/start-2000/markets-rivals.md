## Markets and rivals: categories, platforms, tech frontier, incumbents (M50b, 2000-2007)

Files: `backend/data/categories.yaml`, `platforms.yaml`, `tech_frontier.yaml`, `incumbents.yaml`.
The changes only insert. Every 2008 and later value and comment is byte-identical. An inline map
line gains its 2000-2007 keys ahead of `2008:`, and a comment line above it gives the basis.

### categories.yaml `early_growth` (44 categories, 2000-2007)

The 2000 size is the share of D0 given by D0 / prod(1 + g) over 2000-2009.

| Category | 2000-2007 growth | 2000 size | Basis (tag) |
|---|---|---|---|
| b2b_saas | .50 .25 .25 .35 .40 .40 .35 .30 | 6% | Salesforce revenue FY01-FY07, Gartner SaaS 2007 (R/D) |
| dev_tools | .15 -.10 -.08 .04 .08 .08 .10 .12 | 59% | software in the 2001-02 bust (R/A) |
| consumer_apps | .35 .10 .12 .18 .20 .22 .25 .28 | 13% | ITU internet users 0.4B to 1.3B (R/D) |
| cybersecurity | .25 .12 .10 .15 .16 .15 .14 .15 | 25% | Gartner/IDC security software (R/D) |
| fintech | .40 .15 .20 .30 .30 .30 .28 .27 | 10% | PayPal volume, damped (R/D) |
| ai_models | .15 .10 .10 .18 x5 | 22% | pre-deep-learning ML (A) |
| cloud_hosting | .30 .10 .10 .20 .25 .30 .60 .50 | 9% | hosting before S3/EC2 2006 (A); the era gates it |
| devices | .10 -.05 .02 .06 .08 .08 .07 .09 | 48% | PC and phone units, price-damped (R/D) |
| servers | .12 -.12 -.06 .06 .10 .08 .06 .06 | 89% | IDC server revenue (R) |
| chips_mobile_soc | .30 -.20 .05 .18 .25 .12 .12 .10 | 41% | WSTS (R) |
| chips_server_cpu | .15 -.20 -.05 .08 .12 .08 .06 .06 | 87% | WSTS, IDC (R) |
| chips_ai_accelerator | .25 .10 .10 0 .08 .12 .20 .25 | 33% | NVIDIA revenue, damped (R/A) |
| contract_manufacturing | .30 -.15 -.05 .12 .18 .15 .15 .12 | 52% | EMS boom, bust and outsourcing (R/A) |
| wearables_diagnostics | .10 .08 .08 .10 x5 | 39% | A |
| imaging | .06 .05 .05 .06 .06 .06 .05 .04 | 67% | CT/MRI growth, the DRA cut in 2007 (R/A) |
| surgical_robotics | .80 .60 .30 .20 .35 .40 .40 .40 | 4% | Intuitive revenue $27M (2000) to $601M (2007) (R) |
| implantables | .06 .06 .07 .10 .12 .08 .04 .03 | 55% | DES 2003, ICD recalls 2005 (R/A) |
| samd | .20 x8 | 16% | the 2010 entry (A) |
| launch | -.10 -.12 0 -.05 -.08 .05 .10 .03 | 114% | world orbital launches (R) |
| satellite_broadband | .05 .03 .03 .05 x5 | 66% | A |
| earth_observation | .08 .10 .08 .12 .08 .10 .08 .10 | 44% | IKONOS, QuickBird, NextView (R/A) |
| os, mobility, pharma_* (7), robots (2), vehicles, telecom (4), finance (3), media (4) | 0.0 | - | M50's convention: their own system's data sets demand each month |

Decision: vehicles, social and streaming keep 0.0, not a small positive growth. Their addressable
customers are set each month from vehicles.yaml and media.yaml, so the back-projection there is
those files' job. The eras gate their opening.

### platforms.yaml `user_shares` (7 regions x 2000-2007)

- PA source: the worldwide share table in https://en.wikipedia.org/wiki/Mobile_operating_system,
  read 2026-11-28. Its own sources are PhoneArena (2000-03), ZDNet (2004-05), E-ChannelNews
  (2006) and CNET (2007).
- Worldwide shares 2000 to 2007:

  | OS | 2000 | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 |
  |---|---|---|---|---|---|---|---|---|
  | Symbian | 2% | 3% | 12% | 35% | 56% | 51% | 73% | 70% |
  | Windows | 26% | 31% | 27% | 19% | 13% | 17% | 8% | 10% |
  | BlackBerry | 2% | 3% | 5% | 6% | 5% | 3% | 7% | 8% |
  | Palm OS | 61% | 52% | 44% | 29% | 14% | 5% | 10% | 6% |
  | iPhone | - | - | - | - | - | - | - | 2% |

- Palm OS, Linux, Psion and feature phones go to `other`.
- Regional rows tilt the world shares as GN's 2008 rows do. This is A: North America has more
  RIM and Palm, and Europe, Asia and Africa have more Symbian.
- iOS and Android are 0.0 before launch. iOS is above 0 only in 2007, in North America and Europe.
- Every row sums to 1 (checked).

### tech_frontier.yaml `per_year` (10 domains)

A 2000 key at each domain's 2008 and 2010 rate (A). The node cadence held from 180 nm to 45 nm.

Note: `accrued()` clamps the run-back at 0. AI (start 10 at 1.5 a year) reaches 0 around mid-2003.
Reusability and lithography are 0 throughout.

### incumbents.yaml

**(a) A 2000 `early_scale` entry for 16 products that were on sale in January 2000.** Each is
year-2000 revenue (or users) over 2010's, as M50 did. Tags are mostly R or R/A:

| Product | 2000 scale |
|---|---|
| Sales Cloud (prototype from November 1999) | 0.003 |
| Norton | 0.25 |
| McAfee | 0.33 |
| Check Point | 0.39 |
| PayPal | 0.005 |
| Fiserv | 0.40 |
| Dragon | 0.07 |
| Kaspersky | 0.01 |
| QQ | 0.003 |
| Finacle (A) | 0.08 |
| Xeon | 0.45 |
| PowerEdge | 0.35 |
| ProLiant | 0.45 |
| SuperServer | 0.13 |
| Foxconn | 0.03 |
| Pegatron, as Asus's OEM arm (A) | 0.05 |

**(b) `launched` for 29 products first sold from February 2000 to December 2007:**

| Product | Launched | Product | Launched |
|---|---|---|---|
| CRM On Demand | 2003-10 | Mako | 2006-06 |
| Zoho CRM | 2005-11 | FreeStyle | 2000-06 (S) |
| JIRA | 2002-06 | Dexcom | 2006-03 |
| TFS | 2006-03 | Atlas V | 2002-08 |
| Facebook | 2004-02 | Fios | 2005-09 |
| QuickBooks Online | 2000-10 | UnionPay | 2002-03 |
| ByDesign | 2007-09 | Adyen | 2006-06 |
| Alipay (x2) | 2003-10 | Xbox | 2001-11 |
| AWS EC2 | 2006-03 | Tencent Games | 2003-08 |
| NVIDIA Tesla | 2007-06 | NetEase Games | 2001-12 |
| Opteron | 2003-04 | Roblox | 2006-09 |
| FireStream | 2006-11 | Twitter | 2006-07 |
| iPhone | 2007-06 | YouTube | 2005-05 |
| | | Netflix streaming | 2007-01 |

**(c) Era-gated categories.** The lead's instruction: a product on sale in a 2008 world launches at
its category's era, or at its real date if that is later. It is capped at January 2008, so a 2008
game is unchanged.

- Rackspace Cloud and SoftLayer: 2006-03.
- ThinkPad: 2007-06.
- Hulu: 2008-01 (public launch March 2008).
- Social products from 2010 on (WeChat, Instagram, Snapchat, TikTok, Douyin): 2004-02.
- Streaming products from 2010 on (Disney+, HBO Max, Peacock, Paramount+, Crunchyroll, Tencent
  Video, Prime Video): 2007-01.
- Spotify, QQ Music and YouTube Premium: 2008-01.
- All 13 vehicle lines: 2008-01.
- These are all A.

### Could not check (recalled, not re-read)

- Gartner, IDC, WSTS, NVR and ITU growth rates.
- The revenue figures behind each 2000 `early_scale`. PayPal's, QQ's, Kaspersky's, Finacle's,
  Supermicro's and Asus OEM's are the least certain.
- The launch months of JIRA, Adyen, NetEase and QuickBooks Online (only the year was confirmed).
- The regional tilts of the platform shares.
- WorldView has no `launched`: its line runs back to IKONOS imagery, sold from late 1999.
- IBM Watson and Baidu Brain (2011 and 2016) are on sale in a 2008 world with no `launched`. They
  were left alone because they fall outside 2000-2007.
