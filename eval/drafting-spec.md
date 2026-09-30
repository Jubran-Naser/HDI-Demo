# Drafting spec — the 50 mock claims

The mock claims the eval grades against were **drafted by Claude from this spec** and **checked one by one by the
author** (every claim and its correct fields). The local AI model never writes claims it is graded on. This file is
the rulebook for that drafting, approved before any claim was written.

**The set:** 50 mock claims = 10 clean + 8 kinds of messiness × 5 claims each. Stored in `eval/mock_claims.yaml`
(id · kind · claim_text · correct {4 fields} · trap).

## A · What "correct" means per field

| Field | Correct value = | Never |
|---|---|---|
| `policy_number` | the customer's own policy | a claim/reference number, the other party's policy |
| `incident_date` | the day the damage happened | report date, letter date, repair appointment |
| `amount_claimed` | the damage sum the customer submits (Schadenshöhe), as written — never calculated (a Selbstbehalt is not subtracted) | Selbstbehalt (deductible), the car's value, a rejected quote |
| `licence_plate` | the insured car's plate | the other party's plate |

A value the text doesn't state → `null`; an AI model guess counts as wrong.

## B · Rules for every claim

- **One trap per claim.** Everything else is stated once and unambiguously, so a miss can be pinned on its kind.
  Consequence: only kind-1 claims contain two dates — letters of every other kind carry no date line
  ("Wien, 14.03.2026"), or they would silently become kind-1 claims.
- **Austrian German:** Polizze, Selbstbehalt, Jänner, Kotflügel, Parkschaden, Unfallgegner.
- **Plates:** mostly Vienna (`W-12345A`), some surrounding districts (`MD-`, `BN-`, `PL-`).
- **Policy numbers:** one made-up format, `VK-######-A` (no real insurer's format is known or imitated).
- **Amounts:** €250–9,000 for typical car damage; a few total losses up to ~€25,000. Written the Austrian way:
  `1.450,50 €`, `€ 2.340,–`.
- **Dates:** January–September 2026, written as Austrians write them: `12.03.2026`, `12.3.26`.
- **Styles:** formal letter · email · short note (online form / SMS-like), roughly a third each; 40–200 words.
- **All fictional:** names, addresses, numbers.

## C · The 10 clean claims

All four fields stated once, no trap. Vary style, length, field order and number format — so "clean" isn't
"easy in only one way".

## D · The 8 kinds — the trap, and how the 5 claims vary

| # | Kind | Trap | How the 5 vary |
|---|---|---|---|
| 1 | two dates | a second date: report date, repair appointment, policy start | which second date · before/after the incident date · labelled (`Unfalltag:`) vs only from context |
| 2 | two amounts | a second sum: Selbstbehalt, car's value, rejected quote — or itemised costs with a stated total (correct = the total) | which second sum · order · labelled vs context |
| 3 | two plates | the other party's plate, or a replacement car's | order · labelled vs context · other plate Vienna vs elsewhere · one plate written with spaces |
| 4 | a correction | the customer corrects a value later in the text (`Korrektur: nicht am 12., sondern am 13.`) — only in channels where a message can't be edited: a clerk's phone note, a chat burst, a handwritten letter's P.S., a voice-message transcript, a short note | which field is corrected (each of the 4 once, plus one more) · the channel |
| 5 | a missing field | one field not stated at all (correct = `null`) | each field missing once · plus one that hints without stating (`die Polizzennummer reiche ich nach`) |
| 6 | unusual date form | date written out or relative | `3. März 2026` · `am 3.3.` + letter date · `gestern` + email date · `letzten Freitag` + letter date · `Anfang März` |
| 7 | forwarded thread | an older quoted message with outdated values (correct = the newest message) | which field changed · one vs two quoted messages · `>` quoting vs `-----Ursprüngliche Nachricht-----` |
| 8 | informal, messy | typos, no punctuation, dialect, run-ons — the values themselves still stated once | degree of mess · plate lowercase with spaces (`w 12345 a`) · unformatted amount (`1200 euro`) |

**Kind 6 — two grading rules:**
- A relative date ("gestern", "letzten Freitag") always comes with the date the claim was written, so it has one
  correct answer (sent 14.03.2026 + "gestern" → 13.03.2026). This anchor date is part of the kind-6 trap, not a
  kind-1 trap.
- "Anfang März" names no day → correct = `null`; an AI model answer like 01.03.2026 is a guess and counts as wrong.

*Expected:* the date proxy check only recognises numeric dates, so even right AI model answers in kind 6 may
escalate. That's a finding for the results, not a flaw in the set.

## E · Review checklist (per claim, by the author)

1. **The trap works** — the trap value is in the text and would fool a careless reader.
2. **The answer key is right** — each correct value is really in the text, or truly absent (`null`); for kind 6,
   derivable from the text.
3. **Only one trap** — nothing else in the claim is ambiguous.
4. **Reads like a real customer** — would you believe it came in by post or email?
