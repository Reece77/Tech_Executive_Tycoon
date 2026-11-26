# M55: Media and entertainment (v6, lane B)

**Goal:** the player can run a streaming service, a games studio and a social network. Content is a capital asset whose returns are drawn like trials, creative talent has egos, and an advertising market ties social networks, ad tiers and consumer apps to the platforms (§44).

**Formulas:** `docs/formulas.md` §65 (all), with §11, §20, §32, §44, §48, §55, §61 · **ADRs:** 0002, 0003, 0013 (stream `media` 76), 0020, 0021 · **Research:** `docs/v6-research/media-dossier.md` · **Depends on:** `m53-done` (on `main`) · **Lane:** B, alongside M54 (lane A) and M52 (lane C)

## Reece's decisions (2026-11-21, 2026-11-22)

- **Media and entertainment** in v6: streaming, a games studio and social networks; content as an asset (hits drawn like trials); talent with egos; platforms and advertising tying back to M31.
- Defaults for everything else, including the order (telecom, then financial services, then media). M55 runs beside M54 because neither needs the other.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m55-media` from `main`.
- **Must not edit** M54's or M52's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M55 owns:**
  - new `backend/tst/sim/media/` (advertising market, titles and content assets, streaming, games, social networks, creative leads);
  - `media.yaml` (new);
  - the streaming, games, social and advertising categories (new keys);
  - the `creative` and `vision` attributes and the `ego` and `loyalty` hidden traits (added to the people model's data without changing any existing person's draws: new people only, or a separate draw keyed by person id);
  - the Studio, Streaming, Games and Social screens;
  - `tst/balance/m55.py` (new).
- **`consumer_apps`:** M55 may add ad pricing (§65.1) to it **only from 2026**, so its history and every earlier guard are unchanged.
- **Shared files** (keep both sides on a merge): `categories.yaml`, `incumbents.yaml` (append; ids follow merge order), `balance.yaml`, `regulation.yaml`, `roles.yaml`, `skills.yaml`, `personality.yaml`, `accounts.yaml`, glossary, inbox templates, formulas §65, the data dictionary, ADR-0013, CHANGELOG.
- **No fixed merge order** with M54 and M52: the first ready merges first; the others then merge `main`, re-parent their migrations on the new head, and re-run every guard.
- §65.8 target 1 is the guard.

## Out of scope

Theme parks and merchandise; linear TV channels and cable bundles; a record label (a follow-up); news publishing; esports leagues; console hardware beyond the existing `devices` category (a console is a device the player can already make).

## Sub-tasks (commit after each)

1. **Research and data:** `media.yaml` from the dossier, every value tagged S/D/R/A with its source; `media.*` keys and stream `media`; migration and data dictionary.
2. **Advertising** (§65.1): the market by region, impressions, targeting quality, privacy events. **Test:** `consumer_apps` before 2026 is identical to `main` (state hash, seeds 1–3).
3. **Titles and content assets** (§65.2): projects, capitalisation and amortisation, hit draws, franchises, the catalogue. **Property test:** books balance through capitalisation, amortisation and write-offs; a title's audience is drawn only at release. **Hidden-value test:** no audience draw or ego trait reaches the API or a prompt.
4. **Streaming** (§65.3) and **games** (§65.4), including licensing, tiers, console generations, free-to-play and live service.
5. **Social networks** (§65.5): network effects, format eras, moderation, divest-or-ban.
6. **Talent with egos** (§65.6): creative leads, overall deals, overrules and walks, strikes; creative leads in §61's one-to-ones.
7. **Rivals** (§65.7), pinned to history before 2026 as M53's operators were; YouTube and Prime Video as lines of the existing Alphabet and Amazon records.
8. **Screens:**
   - **Studio** (slate of titles in development with budget, lead and stage; released titles' audience against cost; the catalogue's value);
   - **Streaming** (subscribers by region and tier, churn, engagement, content spend);
   - **Games** (titles by platform, players and decay, in-app revenue);
   - **Social** (users by region, network-effect strength, format, moderation, ad revenue);
   - M29 unlocks; glossary entries (content asset, amortisation, overall deal, ARPU, ad load, format era, live service); Explain on a title's result and a lead's walk.
9. **API, e2e, balance and close-out:**
   - **Playwright:** (a) green-light a series with a creative lead and see its audience at release, (b) overrule a lead and see the morale warning, (c) launch an ad tier and see ad revenue on the Streaming screen;
   - a practice save `pt-media`: a consumer-apps group in 2016 with cash for a studio;
   - **§65.8 targets** printed, tuning only `media.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `media.yaml` cites a source for every value; history to 2025 follows it.
- [ ] A company without media lines plays exactly as before, and `consumer_apps` before 2026 is unchanged; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No audience draw, ego or loyalty trait reaches the API or a prompt (hidden-value test).
- [ ] §65.8 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m55-done`.

## Decisions made

1. **Workspace, branch and docs (2026-11-26).** Docs PR #108 (`docs-v6-round4`) was already on `main` at `139979f` when this session started (rule 9 satisfied). This session's own worktree (`../tst-m55`), branch `m55-media` from that `main`. No M54 or M52 branch existed on the remote during the build; no file of theirs was edited. Shared files (categories, incumbents, balance, roles, glossary, inbox templates, accounts, formulas §65, the data dictionary, ADR-0013, CHANGELOG) keep both sides on a merge. Unlock ids 40-43 leave 36-39 to M54 and M52.
2. **Research.** The session fetched no new source: `media.yaml`'s figures are the dossier's (its two S rows, GroupM's 2024-2025 and Newzoo's 2024, stay S), R recalled from the named source, D derived (in the comment) and A assumptions with their basis. Follow-up: re-check the R and A rows against GroupM, Newzoo, Antenna, Ampere, DTVR and the companies' filings.
3. **Rival records** (the brief's "YouTube and Prime Video as lines of the existing Alphabet and Amazon records"). The game has no Alphabet record (Google appears only as a platform owner and the 2012 entrant Google Cloud), and adding media lines to an existing record (Amazon Web Services, Facebook, Tencent, Microsoft, Comcast) would move that record's books, and so its decisions and every earlier guard, before 2026. So YouTube, Amazon Prime Video, Meta Platforms (Facebook's network and Instagram), Tencent Media (games, WeChat, Tencent Video, QQ Music), Microsoft Gaming (Xbox; Activision Blizzard's revenue after October 2023) and NBCUniversal (Peacock) are held records of their own, as Amazon Kuiper, Google Cloud and Microsoft Azure already are. The existing Facebook record keeps its consumer app (so its social line here is named "Facebook Feed"). Warner Bros. Discovery is one record under its 2022 name through Time Warner and WarnerMedia.
4. **Universal Music is not seeded.** Its business is the record label, which the brief leaves to a follow-up; music services' payout goes to rights holders outside the game (5160).
5. **Categories.** `streaming`, `music_streaming`, `games` and `social` (family `media`). "Advertising" is the ad market (`media.ads` keys, the Social screen's table), not a product category: nobody sells "advertising" as a line; social lines, ad tiers and opted-in consumer apps sell impressions in it.
6. **Segments** `viewers` (4% base churn: the leader's 2-3% and others' 5-7%, Antenna, with engagement moving it), `players` (5%) and `users` (2%).
7. **The player's games are titles.** A player's game earns its own copies or in-app spending (65.4) and is not a line in the `games` market; that market holds the rivals' lines (revenue a player a month) for history, competitors and conglomerate figures. A games line of the player's competing for players is a follow-up.
8. **Social revenue.** A social line's price is its ad revenue a user (the ad market's, set before phase 5), so phase 5 books it to 4000 with every line; only ad tiers' impressions post to 4080. The player cannot price a social network (its lever is ad load; `set_price` on it is overwritten each month).
9. **The ad market's continuity.** Before 2026 the price a thousand is derived from Meta's ARPU (media.yaml) for a reference line (quality 68, load 1); at `media.start` each region's impressions, price and digital spend are recorded once (`AdRef`), and from then the price follows digital spend over impressions offered. Prices continue across January 2026 to within a few percent (seed 1).
10. **Hidden ego and loyalty.** `personality.yaml` already has visible `ego` and `loyalty` traits (shown as ranges). A lead's hidden ego and loyalty are the person's traits + N(0, `talent.trait_sd`) (3), so the shown traits hint at them; they and creative and vision are drawn after the person from stream media (4, year, n), keyed by the offer (the person id is not known until signing), so no existing person's draws change. Creative and vision are shown as ranges of half-width `reveal_hw` (1 after a title together) whose centre is offset by a drawn fraction, so a range never centres on the true value.
11. **Egos bite through production** (target 5). Quality reads the lead's average morale over production, less `talent.grievance_keep` (0.5) of the morale the title's overrules, cuts and moves cost them: without it a lead's morale recovered before release (two overrules cut quality 0.2% on seed 1).
12. **Appeal is cubed in the choice** (§11.7), so engagement's and network effects' multipliers were narrowed before tuning (video [0.7, 1.2]; social [0.7, 1.15]): the first ranges ([0.3, 1.6], [0.2, 1.5]) left a new line with about 0.5% of what an incumbent wins.
13. **Stream keys.** ADR-0013's `media` row named families 0-3; as built adds `(3, 1|2|3, ...)` sub-families (generations, growth, ad growth), `(4, year, n)` the leads on offer and `(5, product, year)` rivals' format moves (the row is updated).
14. **Target 3's measure.** "Takes at least 5 years to positive cash flow" is read as the months from launch to the first trailing twelve months of positive cash flow (revenue and ad revenue less its own titles' production, licences, hosting, royalties and marketing), as the brief says cash flow, not cumulative payback (M53's target 3 measured payback).
15. **Target 4's script.** A scripted line's brand is static (M53's helper), so a marketing push moves nothing; the network instead starts in January 2026 with 5% of North America's internet users (under the brief's 10%), and (a) keeps the format it launched with or (b) switches to each new era the month it arrives. The first seeded era arrives within months of 2026 (the 2018 era is past its window), rivals following in one to three years.
16. **Test fixtures and helpers.** `tests/helpers.rival_cash` adds the media rivals' opening capital as `new_game` posts it (Warner Bros. Discovery has no revenue before 2015, so without it a test's dormant game ran it short of cash and M15b's 2013-start test differed); the space-ranking test's revenue stub favours the space companies (with 22 more rivals after them, the 50 highest ids no longer include theirs).

## Readings (seeds 1-10, `uv run --project backend python tools/m55_targets.py`)

(filled in below)

## Follow-ups

- Re-check media.yaml's R and A rows (decision 2).
- A record label (Universal Music) and music rights as a business (decision 4; the brief's follow-up).
- The player's games competing in the games market for players (decision 7).
- Rival ad tiers (Netflix's from November 2022, Disney+'s from December 2022) as lines' settings: before 2026 their revenue is pinned anyway.
- Licensing the player's titles to rival services by name (licences are to the market; licences in are a package, not named titles).
- Theme parks, linear TV, news, esports (out of scope).
