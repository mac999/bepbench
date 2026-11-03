"""An IDS check's failures as BCF issues, for the tools reviewers already use.

BCF 2.1 is what Revit, BIMcollab, Solibri and the rest exchange issues in. One
topic per failed specification carries every failing element in its viewpoint;
``ids.bcf_topic_per = element`` makes one topic per element instead.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..settings import get as setting
from .builder import IdsError, _author_email, _require, ids_model


def bcf_available() -> bool:
    try:
        import bcf.v2.bcfxml  # noqa: F401
    except ImportError:
        return False
    return True


def _failures(document: Any) -> list[dict[str, Any]]:
    """Each failed specification with its failing elements and their reasons."""
    found = []
    for index, spec in enumerate(document.specifications):
        if not spec.failed_entities:
            continue
        reasons: dict[int, list[str]] = {}
        for requirement in spec.requirements:
            for failure in getattr(requirement, "failures", []) or []:
                element = failure.get("element")
                if element is not None:
                    reasons.setdefault(element.id(), []).append(failure.get("reason") or "")
        elements = []
        for element in spec.failed_entities:
            own = [r for r in dict.fromkeys(reasons.get(element.id(), [])) if r]
            elements.append({"element": element, "reasons": own})
        found.append({"index": index, "spec": spec, "elements": elements})
    return found


def _position(elements: list[Any], scale: float) -> list[float]:
    """A camera point near the failing elements: their centroid, offset like ifctester."""
    import ifcopenshell.util.placement as placement

    points = []
    for element in elements:
        if getattr(element, "ObjectPlacement", None):
            matrix = placement.get_local_placement(element.ObjectPlacement)
            points.append([float(v) * scale for v in matrix[:, 3][:3]])
    if not points:
        return [5.0, 5.0, 5.0]
    centre = [sum(p[i] for p in points) / len(points) for i in range(3)]
    return [c + 5.0 for c in centre]


def build_bcf(xml: str, ifc_path: str, *, project: Any, model_name: str,
              milestone: str = "", identifiers: list[str] | None = None) -> tuple[bytes, dict[str, Any]]:
    """Validate ``ifc_path`` against the IDS ``xml`` and return the failures as a .bcf file."""
    _require()
    if not bcf_available():
        raise IdsError("BCF export needs the bcf-client package: pip install 'bepkit[ids]'")
    import ifcopenshell
    import ifcopenshell.util.unit as unit
    import numpy as np
    from bcf.v2.bcfxml import BcfXml

    identifiers = identifiers or []
    per_element = str(setting("ids.bcf_topic_per", "specification")).lower() == "element"
    limit = int(setting("ids.bcf_max_topics", 500))
    author = str(setting("ids.bcf_author", "") or "").strip() or _author_email(project)
    topic_type = str(setting("ids.bcf_topic_type", "Issue"))
    topic_status = str(setting("ids.bcf_topic_status", "Open"))
    title_format = setting("ids.bcf_title_format", "{identifier} {name}: {failures} of {applicable} fail")
    element_format = setting("ids.bcf_element_title_format", "{identifier} {ifc_class} {element}: {reason}")

    with tempfile.TemporaryDirectory() as tmp:
        ids_path = Path(tmp) / "plan.ids"
        ids_path.write_text(xml, encoding="utf-8")
        document = ids_model.open(str(ids_path))
        model = ifcopenshell.open(ifc_path)
        document.validate(model)
        scale = unit.calculate_unit_scale(model)

        bcfxml = BcfXml.create_new(f"{project.name} — IDS check")
        topics = 0
        failed_elements = 0
        failed_specs = 0
        for item in _failures(document):
            spec = item["spec"]
            failed_specs += 1
            failed_elements += len(item["elements"])
            identifier = spec.identifier or (identifiers[item["index"]]
                                             if item["index"] < len(identifiers) else str(item["index"] + 1))
            requirement_text = "\n".join(r.to_string("requirement") for r in spec.requirements)
            context = [f"Model: {model_name}"]
            if milestone:
                context.append(f"Milestone: {milestone}")
            if spec.description:
                context.append(spec.description)
            if spec.instructions:
                context.append(spec.instructions)
            groups = [item["elements"]]
            if per_element:
                groups = [[e] for e in item["elements"]]
            for group in groups:
                if topics >= limit:
                    break
                elements = [g["element"] for g in group]
                guids = [e.GlobalId for e in elements if getattr(e, "GlobalId", None)]
                if per_element:
                    element = elements[0]
                    title = element_format.format(
                        identifier=identifier, name=spec.name, ifc_class=element.is_a(),
                        element=getattr(element, "Name", "") or "Unnamed",
                        reason="; ".join(group[0]["reasons"]) or "requirement not met")
                    lines = context + [requirement_text]
                else:
                    title = title_format.format(identifier=identifier, name=spec.name,
                                                failures=len(elements),
                                                applicable=len(spec.applicable_entities))
                    counted: dict[str, int] = {}
                    for g in group:
                        for reason in g["reasons"] or ["requirement not met"]:
                            counted[reason] = counted.get(reason, 0) + 1
                    lines = context + [requirement_text, ""] + [
                        f"{count} × {reason}" for reason, count in counted.items()]
                topic = bcfxml.add_topic(title, "\n".join(l for l in lines if l is not None),
                                         author, topic_type, topic_status)
                topic.topic.labels = [l for l in (identifier, milestone) if l]
                if milestone:
                    topic.topic.stage = milestone
                if guids:
                    topic.add_viewpoint_from_point_and_guids(np.array(_position(elements, scale)), *guids)
                topics += 1
        out = Path(tmp) / "check.bcf"
        bcfxml.save_project(out)
        content = out.read_bytes()
    return content, {"topics": topics, "failed_specifications": failed_specs,
                     "failed_elements": failed_elements, "truncated": topics >= limit}
