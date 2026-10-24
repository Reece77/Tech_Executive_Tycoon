# ADR-0016: Offers need an interview; founder energy is switched off

- Status: Accepted. Amends ADR-0014 §5 (founder energy) and `docs/formulas.md` §6, §7.
- Date: 2026-10-24
- Spec sections: §4, §5.3, §5.4

## Context

Reece's M1 playtest answered the two questions left open at the end of M1c:

1. **Hiring was too easy.** A player could make an offer to any candidate the moment a batch appeared, without learning anything about them. Scouting and judgment of talent then mattered little.
2. **Founder energy did not matter.** At 100 points a month and 6 per interview, energy never limited what the player wanted to do. It added a meter and a rejection path without creating a choice.

Reece's call: require an interview before an offer, and switch founder energy off, keeping the option to bring it back later.

## Decision

1. **An offer requires an interview.** `make_offer` fails with the domain error `InterviewRequired` unless the offering company has interviewed that candidate (by anyone: the founder or a delegate of the same company). A network intro or reference check is not an interview. The check applies equally to player and delegate actions (ADR-0015 §2). The API maps the error to HTTP 409 and gives each candidate an `offer_blocked_reason` (`null` or `"interview_required"`) so the screens can disable the Offer button and say why.
2. **Founder energy is switched off by a setting, not removed.** A new key `founder.energy_enabled` (default `false`) controls it. When it is `false`, founder actions neither check nor spend energy, `person_state.energy` for the founder stays at `founder.energy_per_month`, and the API reports `founder_energy_enabled: false` so the screens hide the energy meter. The energy costs in `balance.yaml`, the code path and its tests stay; the tests run with the setting turned on through a balance override.
3. **Delegate energy stays.** A delegate's 100 energy a month is their work capacity: it limits how many candidates a recruiter interviews and scouts each month (`docs/formulas.md` §13.10). It is unaffected by `founder.energy_enabled`.
4. **The founder's limit is now money and time.** Each interview still takes a month to turn into a hire (offers resolve at Continue), and searches cost money. Delegation's value in M2 is throughput and better judgment of talent, not saved energy.

## Consequences

- Golden scripts that make offers without interviewing must interview first; snapshots are regenerated with a CHANGELOG note.
- M2's case for delegation is weaker until the founder has a real constraint. M3 (products) is the natural place to reintroduce one, as attention spent on products versus hiring. Turning energy back on is a balance change plus a review of the costs.

## Alternatives considered

- Delete founder energy entirely: simpler, but rebuilding it later would cost more than keeping a dormant, tested path.
- Raise energy costs until they bind: keeps a meter that the playtest found uninteresting, and pushes the real question (what limits the founder) to tuning.
- Require only a reference check or a scouting month: cheaper for the player, but the interview is the action that reveals interests and work style, which the offer hint depends on.
