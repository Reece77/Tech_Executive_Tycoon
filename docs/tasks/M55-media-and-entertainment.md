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

(filled in by the session)

## Follow-ups

(filled in by the session)
