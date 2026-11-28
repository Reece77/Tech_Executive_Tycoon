# Media (M50b): `backend/data/media.yaml`, 2000-2007

73 series filled (gap lister: 73 before, 0 after). Inserted entries only: every 2008+ value is unchanged (checked by
a parsed comparison against the pre-edit file). Tags as the file's own: S fetched, R recalled from the named source
(not re-read), D derived, A assumption. Money is `[value, dollar year, tag]`, converted with the extended `cpi`.

| Series | 2000-2007 values | Tags | Source / basis |
| --- | --- | --- | --- |
| `cpi` | 172.192 ... 207.342 (annual) | R | BLS CPI-U annual averages |
| `ads.spend_usd` ($B) | 450, 415, 418, 432, 455, 468, 486, 500 | 2000-2001 R, rest A | Zenith/GroupM: about $450B at the 2000 peak, about -8% in the 2001 ad recession; A recovery at 3-4% a year to 2008's $480B (which fell from 2007) |
| `ads.digital_share` | 0.03 (2000) to 0.10 (2007), annual | 2000, 2007 R; between A | GroupM, IAB: internet about 3% of ad spend in 2000, about 10% by 2007 |
| `ads.region_share` | 2000, 2004 rows (North America 0.44, 0.41) | A | GroupM/Zenith regional rows (R) |
| `internet_users` (M) | 2000 and 2004 anchors (world about 380M and 830M) | R | ITU country counts; Wikipedia "Global Internet usage" (read: 16% of the world online in 2005, Europe 46%, Americas 36%, Africa 2%) |
| `multi_home` | 0.05 (2000), 0.1 (2003), 0.2 (2004), 0.6 (2006), 0.8 (2007) | A | networks tiny before Friendster/MySpace (2003) and Facebook (2004); held above zero |
| `arpu_usd` | 2000 and 2004 anchors, under 2008's | A | portal and early social ad revenue a user |
| `streaming_market` (M) | North America 0.4 (2000) to 11 (2007); elsewhere tiny | NA D, others A | the file's 2008 values count subscription rental by mail (Netflix, Blockbuster Online, LoveFilm); D = subscribers (R) / 0.8 |
| `music_market` (M) | tiny in 2000; NA 1.8, EU 1.5, East Asia 7 by 2006-2007 | A | Rhapsody (Dec 2001), Napster subscription (2003), Japan/Korea mobile music subscriptions; downloads (iTunes 2003) not counted |
| `licence_availability` | 1.0 (2000) | A | no pull-back before 2019 |
| `games_market_usd` ($B) | 22, 25, 28, 28, 30, 32, 37, 47 | 2000, 2007 R; between A | DFC Intelligence, PwC (software about $20-25B around 2000, about $45B in 2007); PS2/Xbox/GameCube, WoW (Nov 2004), Wii/DS |
| `games_region_share` | 2000, 2004 rows | A | Japan's consoles, Korea's PC online |
| `box_office_usd` ($B) | 16.5, 17.5, 19.8, 20.3, 25.2, 23.1, 25.8, 26.7 | 2002-2007 R, 2000-2001 A | MPA THEME reports |

## Rival lines

| Line | 2000-2007 | Tags | Basis |
| --- | --- | --- | --- |
| Netflix | 0.29, 0.46, 0.86, 1.49, 2.61, 4.18, 6.32, 7.48 M (year end) | R | NFLX 10-K subscribers (by mail; streaming from 16 January 2007, Wikipedia "Netflix", read). Wikipedia's table (read) shows 2.5, 4.0, 7.3 for 2005-2007 "paid memberships"; the 10-K totals were kept for continuity with 2008's 9.4 |
| Hulu | 0 to 2007 | A | public launch March 2008 |
| Spotify | 0 to 2007 | A | launched October 2008 |
| QQ Music | 0 to 2004, 0.5, 1, 2 M (2005-2007) | A | QQ Music from about 2005 |
| Facebook | 0 to 2003, 1, 5.5, 12, 58 M (2004-2007) | 2004-2007 R | Meta S-1 and press; Wikipedia "Timeline of Facebook" (read: 1.5M by October 2004, 100M August 2008) |
| Twitter | 0 (2000, 2006), 1 M (2007) | A | founded 2006; the line opens 2008-01 |
| YouTube | 0 to 2004, 20, 120, 250 M (2005-2007) | A | launched 2005; Google bought it October 2006 |
| EA | 1.3 ... 3.7 ($B) | R | EA fiscal years to March (year Y = FY ending March Y+1, as 2008's 4.0) |
| Activision Blizzard | 0.62 ... 1.51, 2.90 (2007) | R | Activision alone (fiscal to March; 2007 calendar year); Blizzard joined in July 2008 |
| Xbox | 0.4 (Microsoft PC games) ... 2.3 | A | Xbox from November 2001; Halo 2 (2004), Halo 3 (2007) |
| Take-Two | 0.39 ... 1.20, 1.04, 0.98 | R | TTWO fiscal years to October |
| Ubisoft | 0.33 ... 1.35 | R | fiscal years to March in euros, at the year's EUR/USD |
| Nintendo | 2.1 ... 3.7 | D | 45% of NTDO revenue (fiscal to March, in dollars), as the 2008 row |
| PlayStation Studios | 1.9 ... 3.7 | D | 2008's 3.5 x SONY Game segment revenue that year over 2008's |
| Tencent Games | 0 to 2002, 0.01 ... 0.2 | 2006-2007 R, rest A | Tencent's online games from 2003 (QQ Game) |
| NetEase Games | 0, 0.005, 0.02 ... 0.30 | 2002-2007 R | NetEase online games (Westward Journey 2001, Fantasy Westward Journey 2004) |
| Roblox | 0 to 2005, 0.001, 0.002 | A | beta 2005, launch 2006 |
| Disney Interactive | 0.3 (2000, 2004), 0.6 (2007) | A | Buena Vista Games inside Consumer Products |

Splits: each line's 2000 split is its 2008 split (A) except Netflix, Hulu, Twitter and Facebook (North America 1.0;
Facebook 2006 mostly North America, A), Spotify (Europe), QQ Music, Tencent and NetEase (East Asia), YouTube (a 2006
mix, A).

## Could not check

- GroupM/Zenith 2000-2007 ad spend, digital and regional shares (R and A; hosts not reached).
- ITU regional internet users by year (only 2005 shares read on Wikipedia).
- Publishers' 2000-2007 revenue (EA, Activision, Take-Two, Ubisoft, Nintendo, Sony, Tencent, NetEase): recalled.
- MPA box office 2000-2001; DFC/PwC games totals; every A row above.
- Tencent Games' existing 2008 row ($1.0B) looks high against Tencent's reported online games revenue
  (about RMB 3.4B, about $0.5B); left unchanged (2008 values are fixed).
