"""Field-level completeness rules and declarative cross-field checks.

Two independent mechanisms feed the score:

* :func:`score_field` turns one answer into a 0..1 completeness ratio. It is
  deliberately more than a "filled in?" test — depth expectations declared on the
  field (``min_words``, ``min_rows``, ``min_items``) and placeholder detection
  mean a plan padded with "TBD" scores like the empty plan it really is.
* :data:`CHECK_RULES` holds cross-field consistency handlers referenced by name
  from the framework YAML. These do not change the numeric score directly; they
  raise issues, and blocking issues gate submission readiness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from ..schema.models import Field, Framework
from ..settings import get as setting

# Words that look like an answer but carry no commitment.
PLACEHOLDER_TOKENS = {
    "tbd", "tba", "tbc", "todo", "to be defined", "to be confirmed",
    "to be advised", "to be agreed", "n/a", "na", "none", "nil", "-", "--",
    "?", "??", "???", "xxx", "xx", "tbd.", "pending", "lorem ipsum", "placeholder",
}

# Credit for answering at all, before depth is taken into account (configurable).
PRESENCE_FLOOR = float(setting("scoring.presence_floor", 0.35))


def normalise(value: Any) -> str:
    """Lowercase, de-punctuate and collapse whitespace for fuzzy matching."""
    text = re.sub(r"[^\w\s/&-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text in PLACEHOLDER_TOKENS:
        return True
    return bool(re.fullmatch(r"[\s.\-_?xX*]+", text))


def word_count(value: Any) -> int:
    return len([w for w in re.split(r"\s+", str(value or "").strip()) if w])


def _ramp(actual: float, expected: float) -> float:
    """Presence floor plus a linear ramp to full credit at ``expected``."""
    if expected <= 0:
        return 1.0
    return min(1.0, PRESENCE_FLOOR + (1.0 - PRESENCE_FLOOR) * (actual / expected))


def is_empty(field: Field, value: Any) -> bool:
    if value is None:
        return True
    if field.type == "boolean":
        return False
    if field.type == "table":
        return len(table_rows(value)) == 0
    if field.type in ("multiselect", "list"):
        return len([v for v in _as_list(value) if str(v).strip()]) == 0
    return not str(value).strip()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [p.strip() for p in str(value).split(",") if p.strip()]


def table_rows(value: Any) -> list[dict[str, Any]]:
    """Return non-blank rows of a table value."""
    if not isinstance(value, list):
        return []
    rows = []
    for row in value:
        if not isinstance(row, dict):
            continue
        if any(str(cell).strip() for cell in row.values()):
            rows.append(row)
    return rows


@dataclass
class FieldScore:
    section_id: str
    field_id: str
    label: str
    type: str
    required: bool
    weight: float
    score: float
    state: str            # empty | partial | complete
    detail: str           # plain-language reason the field is not yet complete
    filled: bool

    @property
    def path(self) -> str:
        return f"{self.section_id}.{self.field_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "section": self.section_id,
            "field": self.field_id,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "weight": self.weight,
            "score": round(self.score, 4),
            "state": self.state,
            "detail": self.detail,
            "filled": self.filled,
        }


def score_field(section_id: str, field: Field, value: Any) -> FieldScore:
    """Grade a single answer against the field's declared depth expectations."""

    def build(score: float, state: str, detail: str, filled: bool) -> FieldScore:
        return FieldScore(
            section_id=section_id,
            field_id=field.id,
            label=field.label,
            type=field.type,
            required=field.required,
            weight=field.weight,
            score=max(0.0, min(1.0, score)),
            state=state,
            detail=detail,
            filled=filled,
        )

    if is_empty(field, value):
        return build(0.0, "empty", "Not answered.", False)

    if field.type not in ("table", "multiselect", "list") and is_placeholder(value):
        return build(0.1, "partial", "Placeholder text — no actual commitment recorded.", True)

    q = field.quality

    if field.type in ("markdown", "textarea"):
        words = word_count(value)
        if q.min_words and words < q.min_words:
            return build(
                _ramp(words, q.min_words),
                "partial",
                f"{words} words — expected around {q.min_words} to be auditable.",
                True,
            )
        return build(1.0, "complete", "", True)

    if field.type == "table":
        rows = table_rows(value)
        required_cols = [c for c in field.columns if c.required]
        depth = _ramp(len(rows), q.min_rows) if q.min_rows else 1.0
        if required_cols:
            total = len(rows) * len(required_cols)
            filled_cells = sum(
                1 for row in rows for c in required_cols
                if str(row.get(c.id, "")).strip() and not is_placeholder(row.get(c.id))
            )
            cells = filled_cells / total if total else 0.0
        else:
            cells = 1.0
        score = depth * (PRESENCE_FLOOR + (1 - PRESENCE_FLOOR) * cells if cells < 1 else 1.0)
        details = []
        if q.min_rows and len(rows) < q.min_rows:
            details.append(f"{len(rows)} of about {q.min_rows} expected rows")
        if cells < 1:
            details.append("required cells left blank")
        state = "complete" if score >= 0.999 else "partial"
        return build(score, state, "; ".join(details).capitalize() + ("." if details else ""), True)

    if field.type in ("multiselect", "list"):
        items = [v for v in _as_list(value) if str(v).strip()]
        if q.min_items and len(items) < q.min_items:
            return build(
                _ramp(len(items), q.min_items),
                "partial",
                f"{len(items)} of about {q.min_items} expected entries.",
                True,
            )
        return build(1.0, "complete", "", True)

    # text, number, date, select, link, boolean
    if q.min_words:
        words = word_count(value)
        if words < q.min_words:
            return build(_ramp(words, q.min_words), "partial", f"{words} words — expected around {q.min_words}.", True)
    return build(1.0, "complete", "", True)


# --------------------------------------------------------------------------
# Cross-field checks
# --------------------------------------------------------------------------

@dataclass
class Issue:
    id: str
    severity: str          # blocker | major | minor | info
    message: str
    section_id: str = ""
    section_title: str = ""
    field_id: str = ""
    detail: str = ""
    fix: str = ""
    source: str = "check"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "section": self.section_id,
            "section_title": self.section_title,
            "field": self.field_id,
            "detail": self.detail,
            "fix": self.fix,
            "source": self.source,
        }


CheckFn = Callable[[Any, dict[str, Any], Framework], tuple[bool, str]]
CHECK_RULES: dict[str, CheckFn] = {}


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    def deco(fn: CheckFn) -> CheckFn:
        CHECK_RULES[name] = fn
        return fn
    return deco


def _value(values: dict[str, Any], section_id: str, field_id: str) -> Any:
    return (values.get(section_id) or {}).get(field_id)


@register("table_column_filled")
def _table_column_filled(check, values, framework) -> tuple[bool, str]:
    """Pass when every row of a table has the named column filled in."""
    rows = table_rows(_value(values, check.section, check.params["field"]))
    if not rows:
        return True, ""  # emptiness is already penalised by the field score
    column = check.params["column"]
    missing = [i + 1 for i, row in enumerate(rows) if not str(row.get(column, "")).strip() or is_placeholder(row.get(column))]
    if missing:
        shown = ", ".join(str(m) for m in missing[:6])
        more = f" (+{len(missing) - 6} more)" if len(missing) > 6 else ""
        return False, f"{len(missing)} of {len(rows)} rows incomplete — row {shown}{more}."
    return True, ""


@register("min_rows")
def _min_rows(check, values, framework) -> tuple[bool, str]:
    rows = table_rows(_value(values, check.section, check.params["field"]))
    expected = int(check.params.get("min", 1))
    if len(rows) < expected:
        return False, f"{len(rows)} row(s) present, at least {expected} expected."
    return True, ""


@register("field_present")
def _field_present(check, values, framework) -> tuple[bool, str]:
    section = framework.section_by_id(check.section)
    field = section.field_by_id(check.params["field"]) if section else None
    if field is None:
        return True, ""
    value = _value(values, check.section, field.id)
    if is_empty(field, value) or is_placeholder(value):
        return False, "No value recorded."
    return True, ""


@register("field_not_value")
def _field_not_value(check, values, framework) -> tuple[bool, str]:
    value = _value(values, check.section, check.params["field"])
    if value is None or not str(value).strip():
        return True, ""
    if normalise(value) == normalise(check.params.get("value")):
        return False, f"Currently set to “{value}”."
    return True, ""


def _column_values(values, section_id, field_id, column) -> list[str]:
    return [
        str(row.get(column, "")).strip()
        for row in table_rows(_value(values, section_id, field_id))
        if str(row.get(column, "")).strip()
    ]


@register("values_subset_of")
def _values_subset_of(check, values, framework) -> tuple[bool, str]:
    """Every value used in this column must exist in the reference table."""
    p = check.params
    used = _column_values(values, check.section, p["field"], p["column"])
    reference = _column_values(values, p["against_section"], p["against_field"], p["against_column"])
    if not used or not reference:
        return True, ""
    known = {normalise(r) for r in reference}
    unknown = sorted({u for u in used if normalise(u) not in known})
    if unknown:
        return False, "Not recognised: " + ", ".join(unknown[:5]) + ("…" if len(unknown) > 5 else "")
    return True, ""


@register("values_cover")
def _values_cover(check, values, framework) -> tuple[bool, str]:
    """Every entry of the reference table must be represented in this column."""
    p = check.params
    used = _column_values(values, check.section, p["field"], p["column"])
    reference = _column_values(values, p["against_section"], p["against_field"], p["against_column"])
    if not reference:
        return True, ""
    present = {normalise(u) for u in used}
    missing = sorted({r for r in reference if normalise(r) not in present})
    if missing:
        return False, "Missing: " + ", ".join(missing[:5]) + ("…" if len(missing) > 5 else "")
    return True, ""


def run_checks(framework: Framework, values: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for check in framework.checks:
        handler = CHECK_RULES.get(check.rule)
        if handler is None:
            issues.append(Issue(
                id=check.id,
                severity="info",
                message=f"Check rule {check.rule!r} is not implemented and was skipped.",
                section_id=check.section,
            ))
            continue
        try:
            ok, detail = handler(check, values, framework)
        except (KeyError, TypeError, AttributeError) as exc:
            issues.append(Issue(
                id=check.id,
                severity="info",
                message=f"Check {check.id!r} could not run: {exc}",
                section_id=check.section,
            ))
            continue
        if not ok:
            section = framework.section_by_id(check.section)
            issues.append(Issue(
                id=check.id,
                severity=check.severity,
                message=check.message,
                section_id=check.section,
                section_title=section.title if section else "",
                field_id=check.params.get("field", ""),
                detail=detail,
                fix=check.fix,
            ))
    return issues
