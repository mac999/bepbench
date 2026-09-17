# The scoring model

A BEP score answers one question: *if this plan were submitted today, would an appointing
party accept it?*

## Three numbers

| Metric | Question | Behaviour |
| --- | --- | --- |
| **Coverage** | How much of the template has been touched? | Rises fast. Flatters a draft. |
| **Required coverage** | Are the mandatory commitments answered *fully*? | Only counts fields scoring 1.0. |
| **Score** | Is what is written actually usable? | Weighted by depth. Rises slowly. |

Keeping them apart is what stops the tool from rewarding box-ticking.

## Field scoring

Each field returns 0.0–1.0.

```
empty                                    → 0.00
placeholder ("TBD", "N/A", "???", "-")   → 0.10   and raises an issue
answered but shallow                     → 0.35 + 0.65 × (actual / expected)
answered to the expected depth           → 1.00
```

The 0.35 presence floor is credit for answering at all; the ramp is the depth the framework
declares:

- **prose** — `min_words`, counted after whitespace normalisation
- **tables** — `min_rows`, multiplied by the proportion of *required cells* actually filled
- **lists** — `min_items`

So a five-row table with the owner column blank scores well below a five-row table that is
complete, and both score above a one-row table.

## Section and overall score

```
section_score  = Σ(field_score × field_weight) / Σ(field_weight) × 100
overall_score  = Σ(section_score × section_weight) / Σ(section_weight)
```

Weights are declared in the framework YAML. In `iso19650`, BIM Objectives and Uses carries
1.3 and Appendices 0.5 — a plan with beautiful appendices and no agreed uses should not
score well.

## Cross-field checks

Field scores cannot see relationships. Checks can, and they are declared in the framework:

| Rule | Catches |
| --- | --- |
| `table_column_filled` | A BIM use with no owner; a milestone with no date |
| `min_rows` | A LOIN table too thin to drive production |
| `field_not_value` | Security triage still marked "not yet performed" |
| `values_subset_of` | A use assigned to a team that is not in the delivery team table |
| `values_cover` | A task team with no TIDP row |

Severities: `blocker`, `major`, `minor`, `info`. Unanswered required fields become blockers
automatically.

## The issue gate

```
ready_to_issue = no blocking issues
               and score ≥ 65
               and required coverage ≥ 90%
```

Both thresholds are configurable (`scoring.ready_score`, `scoring.ready_required_coverage`).
A plan can score 80 and still not be issuable — that is the intent. One unowned BIM use is a
contractual hole regardless of how well the rest reads.

## Maturity bands

Bands are per framework. For `iso19650`:

| Score | Band | Meaning |
| --- | --- | --- |
| 0–24 | Initial | Little more than a project header |
| 25–44 | Drafted | Structure in place, substance missing |
| 45–64 | Defined | Core commitments written |
| 65–84 | Managed | Auditable; suitable for pre-appointment submission |
| 85–100 | Optimised | Complete, evidenced, mobilisation ready |

## Recommendations

Every incomplete field is ranked by the overall points it would recover:

```
points = (1 − field_score) × field_weight/Σ(section field weights)
                           × section_weight/Σ(section weights) × 100
```

The list answers "where do the next points come from", which is the question a team with one
hour before a submission actually has.

## Deliberate limits

The engine measures **whether commitments are stated, specific and internally consistent**.
It cannot tell you whether a commitment is *right* for the project — whether a 25 mm
services tolerance is sensible, or whether the milestone dates are achievable. That is a
reviewer's job, and the tool is built to make that reviewer's time go further, not to
replace them.
