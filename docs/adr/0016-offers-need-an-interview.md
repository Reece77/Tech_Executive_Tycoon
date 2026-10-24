# ADR-0016: Offers need an interview

- Status: Accepted. Amends `docs/formulas.md` §7.
- Date: 2026-10-24
- Spec sections: §4, §5.4

## Context

Reece's M1 playtest answered the two questions left open at the end of M1c:

1. **Hiring was too easy.** A player could make an offer to any candidate the moment a batch appeared, without learning anything about them. Scouting and judgment of talent then mattered little.
2. **Founder energy rarely bound** at 100 points a month and 6 per interview. Switching it off was considered, but Reece kept it: it is what makes delegation worth having in M2, and the interview requirement below makes every hire cost energy.

## Decision

1. **An offer requires an interview.** `make_offer` fails with the domain error `InterviewRequired` unless the offering company has interviewed that candidate (by anyone: the founder or a delegate of the same company). A network intro or reference check is not an interview. The check applies equally to player and delegate actions (ADR-0015 §2).
2. The API maps the error to HTTP 409 and gives each candidate an `offer_blocked_reason` (`null` or `"interview_required"`), so the screens can disable the Offer button and say why.
3. **Founder energy stays on** with the costs in `docs/formulas.md` §6. Whether it binds is reviewed in the M2b playtest and the balance pass.

## Consequences

- Each founder hire now costs at least 6 energy plus a share of the search, so a founder can make at most about 15 hires' worth of interviews a month; delegates' interviews unlock offers too.
- Golden scripts that make offers without interviewing must interview first; snapshots are regenerated with a CHANGELOG note.

## Alternatives considered

- Switch founder energy off by a setting: removes M2's main reason to delegate.
- Require only a reference check or a scouting month: cheaper for the player, but the interview is the action that reveals interests and work style, which the offer hint depends on.
