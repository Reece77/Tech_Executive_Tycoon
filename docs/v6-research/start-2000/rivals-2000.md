## Rivals of the 2000 world (`incumbents.yaml`, history_only)

M50b, 2026-11-28 (the brief's "Defaults for 2000", item 3). Eight companies are appended at the end of
`incumbents.yaml`. They are appended because company and product ids follow file position, so nothing
existing moves. Each has `history_only: true`, so it exists only in a world begun before 2008, and a
2008 or 2010 game is unchanged. Their `share_bp` are shares of January 2000's market, with no
`early_scale`.

Tags as the other dossiers use them:
- **S**: read this session on en.wikipedia.org (Compaq, Sun Microsystems, Cisco, Yahoo, AOL, eBay, History of Google and Motorola pages, 2026-11-28).
- **R**: recalled from the named filing or report, not re-read.
- **A**: an assumption, with its basis.
- **D**: derived from the figures beside it.

Most 2000 revenue, staff and cash figures are R. The Wikipedia pages read this session give few of
them; Cisco's FY2000 revenue of $18.9B is S. Employees are recorded here and in the comments only.
The file has no staff field: rivals' pools are sized by `target_margin_bp` (formulas.md 15.1).

### Companies

| Company | Founded | Listed from | Exit | 2000 revenue, staff, cash | Personality, skill, margin, cash_months |
|---|---|---|---|---|---|
| Compaq | 16 Feb 1982 (S) | Dec 1983 (S year, R month) | 2002-05 into HPE (S: closed May 2002) | $42.4B (R; S "$40 billion"), about 70,000, cash about $2.6B (R) | fast_follower, 12, 500, 24 (A: as Dell and HPE) |
| Sun Microsystems | 24 Feb 1982 (S) | Mar 1986 (S year) | 2010-01 into Oracle (S: 27 Jan 2010) | $15.7B (FY Jun 2000), about 43,000, cash and investments about $7B (R) | premium, 15, 1500, 36 |
| Cisco | 10 Dec 1984 (S) | Feb 1990 (S) | none | $18.9B (FY Jul 2000, S), about 34,000, about $20B (R) | aggressive, 14, 2000, 60 |
| Motorola | 1928 (S) | 1953 (A: the month and year are not given) | none (S: split in January 2011; one record, A) | $37.6B (R), 150,000 at peak in 2000 (S), cash about $3.3B (R) | fast_follower, 13, 500, 36 |
| AOL | 1985 (Quantum, R; S: from Control Video, 1983) | Mar 1992 (S year 1992) | none (S: Time Warner merger completed January 2001; the AOL record carries on) | $7.7B (FY Jun 2000), about 15,000, about $3B (R) | aggressive, 11, 2500, 48 |
| Yahoo | Jan 1994 (S) | Apr 1996 (S) | none | $1.11B, about 3,300, about $1.7B (R) | fast_follower, 13, 3000, 60 |
| eBay | 3 Sep 1995 (S) | Sep 1998 (S) | none | $431M, about 2,500, about $0.9B (R) | premium, 12, 2000, 36 |
| Google | 4 Sep 1998 (S) | Aug 2004 (S) | none | about $19M, a net loss of about $15M, about 200 staff (R/A); $25M round on 7 Jun 1999 (S) | premium, 17, 0, 120 (A, see below) |

### Products and January 2000 shares

| Company | Product | Category: segments (share_bp, price) | Basis |
|---|---|---|---|
| Compaq | Compaq ProLiant | servers: enterprise 1600 ($5,200), hyperscalers 800 ($4,200) | R: the largest x86 server vendor by units in 2000 (about 27% of x86, IDC) |
| Sun Microsystems | Sun Enterprise | servers: enterprise 1300 ($7,500), hyperscalers 2000 ($6,000) | R: about 15-17% of world server revenue (the Unix leader); the web's large sites ran on Sun |
| Cisco | Cisco PIX Firewall | cybersecurity: mid_market 500, enterprise 500 | R/A: a firewall-appliance leader; kept small because the segments are already crowded (below) |
| Cisco | Cisco UCS | servers: enterprise 0; launched 2009-03 | R: announced 16 Mar 2009; it joins with no customers, as launches before 2010 do |
| Motorola | Motorola DragonBall | chips_mobile_soc: device_oems 1500 ($35) | R/A: a leading mobile chip maker with TI (Freescale from July 2004, one record, A) |
| Motorola | Motorola RAZR | devices: consumer 0, smb 0; launched 2007-06 | A: devices open with the smartphones era. S: 18.4% of world handsets in 2007 |
| AOL | AOL | consumer_apps: consumer 1900 ($1.00) | S: "over 20 million" subscribers; R: AIM and ICQ reach further. A: price is revenue per user |
| Yahoo | Yahoo! | consumer_apps: consumer 2600 ($0.50) | S: the most popular starting point; R: about 180M users. D: $1.11B / 180M / 12 |
| eBay | eBay | consumer_apps: consumer 600 ($1.50) | S: 22.5M registered users at end 2000. D: $431M / 22.5M / 12 |
| Google | Google Search | consumer_apps: consumer 300 ($0.10) | R: about 18M searches a day in early 2000, 100M by the end of the year. S: keyword ads from 2000 |

The default regions are north_america and europe.

**Shares against the existing incumbents in January 2000.** Each existing product's 2000 share is its
share_bp x its 2000 early_scale over the category's 2000 size (categories.yaml early_growth):
servers 0.889, cybersecurity 0.252 and consumer_apps 0.131 of 2010.

| Segment | Existing products on sale in January 2000 (effective) | Added | Total |
|---|---|---|---|
| servers enterprise | Dell 9.8%, HPE 12.6%, Supermicro 1.5% | 29% | about 53% |
| servers hyperscalers | Dell 7.9%, HPE 5.1%, Supermicro 3.7% | 28% | about 45% |
| cybersecurity mid_market | Norton 24%, McAfee 26%, Check Point 24% | 5% | about 79% |
| cybersecurity enterprise | Norton 28%, McAfee 29%, Check Point 29% | 5% | about 92% |
| consumer_apps consumer | none (Facebook from 2004; QQ is east_asia only) | 54% | 54% |
| chips_mobile_soc device_oems | none (Snapdragon from 2008-11) | 15% | 15% |

The loader also checks a static total. `GameData`'s cross-check sums every company's share_bp in a
(category, segment, region), whatever its dates, and rejects a total above 100%. The 2010 records
already hold 45% of consumer_apps consumer, so the 2000 companies' consumer shares are capped at 55%.
The table uses 54%.

### Checks made

- `IncumbentsFile` validates, and `load_all(data)` passes, including the era-opening and exit_into checks.
- I ran a 2000 world on seed 3 for 30 turns with the CLI. Compaq closed at the end of April 2002, and HPE's ProLiant took its customers.
- In the first runs, Google went bankrupt in March 2001 with `cash_months` 18. Its revenue is tiny (10 cents a user), and the floor on its staff costs outran it. At 120 it survives and grows (A).
- Motorola, with only a 2007 devices line, went bankrupt in 2003 on seed 1, having no revenue. The DragonBall chip line was added so it has something on sale from 2000.

### Left out, and why

- **Nortel and Lucent.** Their only fitting category is `network_equipment`. That category's rival lines are pinned to telecom.yaml's vendor rows (`tst.sim.telecom.history.lines`, `vendor_of`), and this lane may not edit those here. telecom.yaml's 2000 RAN shares already leave Lucent, Nortel, Motorola and Alcatel as the unmodelled rest (about 43%). A network_equipment line without a vendor row would sell unpinned outside the telecom rules. Their exits (Nortel 2009-01, Lucent 2006-12) therefore need no rows.
- **Cisco's routers and switches and Motorola's network gear.** These were left out for the same reason. Cisco instead sells the PIX firewall (cybersecurity) and, from March 2009, UCS servers.
- **eBay in fintech.** It is skipped because PayPal's record already covers it (eBay owned PayPal from October 2002).
- **IBM servers.** These are not added, because IBM is an existing record with only Watson and existing entries stay unchanged. IBM held about 20% of 2000 server revenue (R).

### For the caller (not changed: existing entries)

- HPE's ProLiant 2000 `early_scale` of 0.45 is based on Compaq's ProLiant units ("Compaq's ProLiant about 1.0M servers (2000)"). With Compaq now its own record in a 2000 world, that counts Compaq's servers twice. HP's own 2000 x86 servers (NetServer) were about a third of Compaq's (R/A). An `early_scale` 2000 for HPE of about 0.15 would remove the double count. Only HPE's 2000 key would change, so 2008 and 2010 games would be unaffected.
- Oracle's record has no servers product, so Sun's customers return to the market in January 2010 rather than moving to Oracle.
- **Oracle dies before 2004 in a 2000 world** (seeds 1 and 2, `tst.balance.m50.start(seed, 2000)`). Its only line, CRM On Demand, launches in 2003-10, so it has no revenue until then. Sun's January 2010 exit therefore finds no buyer and simply closes. Other records whose only line launches after 2000 have the same problem; Lenovo (ThinkPad 2007-06) is one to check. An early line, or a guard for records with nothing on sale, would fix it.
- Seeds 1 and 2 to 2008: Compaq merges into HPE in May 2002 (HPE ProLiant about 17k to 36k customers), and the rest survive. Google grows from 0.2M to about 4.4M users by 2006, the largest. Motorola's RAZR joins in June 2007.
