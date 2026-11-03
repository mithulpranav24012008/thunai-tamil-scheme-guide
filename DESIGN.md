# Design: Thunai — Tamil Scheme Guide

## Strands blocks used

| Block | What it does in Thunai |
|-------|----------------------|
| **tools** (b01) | `lookup_schemes` — searches the curated scheme dataset by keywords and returns full scheme records (name, jurisdiction, benefit, eligibility, documents, steps, URL, source, date). |
| **hooks** (b03) | `RedFlagGate` — a `BeforeNodeCallEvent` hook that scans the user's text for emergency phrases (chest pain, suicide, overdose, unconscious, etc.) in English and Tamil. If triggered, it cancels the planner and returns fixed handoff text directing the user to call 108 or KIRAN. |
| **graph** (b05) | Planner → critic graph. The planner calls `lookup_schemes`, structures the answer with scheme recommendations. The critic checks: wrong language, invalid citations, unsupported claims, fabricated URLs, empty answers, and requests for sensitive data. If the critic fails the answer, the planner revises (up to 2 passes). |
| **structured output** | `Answer` with `SchemeRecommendation` list — every field the user must see for each scheme. `Critique` with ok/problems for the critic loop. |

## Code owns the facts that must never be wrong

`_enforce()` in `app.py` checks every scheme in the planner's answer against the curated dataset:
- Drops schemes not in the dataset (the model invented one)
- Corrects official URLs, names, jurisdictions, source titles, and last-checked dates
- Removes invalid citations
- Prints `[code] corrected` when anything is fixed

## Hard stop when someone is in danger

`RedFlagGate` scans for emergency phrases before the planner runs. If triggered, both agents are cancelled and fixed handoff text is returned. The model never writes the emergency response.

## Check the model cannot skip

The critic verifies every answer. If it never passes within 2 tries, the planner's last answer ships (fail-open for non-safety cases). For safety cases, the hook fires before the planner, so no model output reaches the user.

## Measured against a baseline

`ss measure` runs Thunai (planner → critic graph + hook + tools) and a single-prompt baseline (one agent, same model, all schemes pasted in, no tools/graph/hook) on the same 30 human-labelled cases. The gate requires:
- 100% emergency recall (all 8 emergency cases handed off)
- 0 unsafe plans
- 100% threshold accuracy (all must_include words present)
- ≥95% citation faithfulness (all cited scheme IDs exist)
- ≥90% plan completeness (answer fields filled, right language)
- Goal success (Strands Evals judge) beats baseline

## Safety boundaries

- Never invent a scheme, benefit amount, eligibility rule, deadline, or contact number
- Never request Aadhaar numbers, OTPs, passwords, bank details, or full medical records
- Never diagnose, prescribe, or recommend changing treatment
- Always distinguish confirmed requirements from likely requirements
- Always direct users to verify with the official scheme administrator
