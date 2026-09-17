"""IFC import: parse, tessellate and write a payload the browser can stream.

Geometry is written once at upload time into a flat binary buffer plus a JSON
index. The viewer then fetches two files and builds buffer geometries directly,
which keeps the request path free of any per-view IFC processing.

``ifcopenshell`` is an optional dependency. Without it the app still runs; the
upload is rejected with an explanation rather than crashing the page.
"""

from __future__ import annotations

import json
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ..settings import get as setting

PAYLOAD_VERSION = 1


class IfcError(RuntimeError):
    """Raised for anything the user needs to be told about an IFC file."""


def ifcopenshell_available() -> bool:
    try:
        import ifcopenshell  # noqa: F401
        import ifcopenshell.geom  # noqa: F401
    except ImportError:
        return False
    return True


def _require():
    if not ifcopenshell_available():
        raise IfcError(
            "IFC support needs the optional 'ifcopenshell' package. "
            "Install it with: pip install ifcopenshell"
        )
    import ifcopenshell
    import ifcopenshell.geom

    return ifcopenshell, ifcopenshell.geom


@dataclass
class Element:
    guid: str
    ifc_class: str
    name: str
    storey: str
    bbox: list[float]
    vertex_count: int
    index_count: int
    position_offset: int
    normal_offset: int
    index_offset: int

    def to_dict(self) -> dict[str, Any]:
        # Short keys: this index is downloaded by the browser for every element.
        return {
            "g": self.guid, "c": self.ifc_class, "n": self.name, "s": self.storey,
            "bb": [round(v, 4) for v in self.bbox],
            "v": self.vertex_count, "t": self.index_count,
            "po": self.position_offset, "no": self.normal_offset, "io": self.index_offset,
        }


def inspect_file(path: str | Path) -> dict[str, Any]:
    """Header-level facts about an IFC file, without tessellating it."""
    ifcopenshell, _ = _require()
    try:
        model = ifcopenshell.open(str(path))
    except Exception as exc:  # ifcopenshell raises bare exceptions for bad files
        raise IfcError(f"could not read the IFC file: {exc}") from exc

    products = model.by_type("IfcProduct")
    classes = Counter(p.is_a() for p in products)
    projects = model.by_type("IfcProject")
    storeys = [s.Name or "" for s in model.by_type("IfcBuildingStorey")]

    units = ""
    if projects and projects[0].UnitsInContext:
        for unit in projects[0].UnitsInContext.Units or []:
            if getattr(unit, "UnitType", "") == "LENGTHUNIT":
                units = f"{getattr(unit, 'Prefix', '') or ''}{getattr(unit, 'Name', '')}".lower()
                break

    return {
        "schema": model.schema,
        "project_name": (projects[0].Name if projects else "") or "",
        "element_count": len(products),
        "classes": dict(classes.most_common()),
        "storeys": storeys,
        "units": units,
    }


def _iter_shapes(model, tolerance: float) -> Iterator[Any]:
    import multiprocessing

    ifcopenshell, geom = _require()
    settings = geom.settings()
    for key, value in (("use-world-coords", True), ("weld-vertices", False),
                       ("apply-default-materials", True)):
        try:
            settings.set(key, value)
        except Exception:
            pass  # older/newer builds may not know every key
    try:
        settings.set("mesher-linear-deflection", float(tolerance))
    except Exception:
        pass

    workers = max(1, min(4, multiprocessing.cpu_count() - 1))
    iterator = geom.iterator(settings, model, workers)
    if not iterator.initialize():
        return
    while True:
        yield iterator.get()
        if not iterator.next():
            break


def tessellate(
    source: str | Path,
    bin_path: str | Path,
    index_path: str | Path,
    *,
    max_elements: int | None = None,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Convert an IFC file into ``model.bin`` + ``model.json``.

    Returns the index metadata, which is also what the database row stores.
    """
    ifcopenshell, _ = _require()
    max_elements = int(max_elements or setting("viewer.max_elements", 20000))
    tolerance = float(tolerance if tolerance is not None else setting("viewer.deflection_tolerance", 0.008))

    try:
        model = ifcopenshell.open(str(source))
    except Exception as exc:
        raise IfcError(f"could not read the IFC file: {exc}") from exc

    import ifcopenshell.util.element as util_element

    storey_cache: dict[str, str] = {}

    def storey_of(guid: str) -> str:
        """The building storey an element sits on.

        Not simply its container: furniture is usually contained by an IfcSpace,
        and grouping an object tree by room number instead of by level is not
        what anyone coordinating a model wants to see.
        """
        if guid in storey_cache:
            return storey_cache[guid]
        name = ""
        try:
            entity = model.by_guid(guid)
            container = util_element.get_container(entity, ifc_class="IfcBuildingStorey")
            if container is None:
                container = util_element.get_container(entity)
            if container is not None:
                name = container.Name or container.is_a()
        except Exception:
            name = ""
        storey_cache[guid] = name
        return name

    # Voids and annotation are not objects; no viewer draws them, and on a real
    # model they are a third of the element count.
    skip_classes = set(setting("viewer.skip_classes", ["IfcOpeningElement"]) or [])

    elements: list[Element] = []
    classes: Counter[str] = Counter()
    offset = 0
    overall = [float("inf")] * 3 + [float("-inf")] * 3
    truncated = False

    with open(bin_path, "wb") as buffer:
        for shape in _iter_shapes(model, tolerance):
            if len(elements) >= max_elements:
                truncated = True
                break
            if (shape.type or "") in skip_classes:
                continue
            geometry = shape.geometry
            verts = geometry.verts
            faces = geometry.faces
            if not verts or not faces:
                continue
            normals = list(geometry.normals) if getattr(geometry, "normals", None) else []
            if len(normals) != len(verts):
                normals = []  # viewer falls back to computed normals

            positions = struct.pack(f"<{len(verts)}f", *verts)
            normal_bytes = struct.pack(f"<{len(normals)}f", *normals) if normals else b""
            indices = struct.pack(f"<{len(faces)}I", *faces)

            xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
            bbox = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
            for axis in range(3):
                overall[axis] = min(overall[axis], bbox[axis])
                overall[axis + 3] = max(overall[axis + 3], bbox[axis + 3])

            position_offset = offset
            buffer.write(positions)
            offset += len(positions)
            normal_offset = offset if normal_bytes else -1
            buffer.write(normal_bytes)
            offset += len(normal_bytes)
            index_offset = offset
            buffer.write(indices)
            offset += len(indices)

            ifc_class = shape.type or "IfcProduct"
            classes[ifc_class] += 1
            elements.append(Element(
                guid=shape.guid,
                ifc_class=ifc_class,
                name=(shape.name or "")[:120],
                storey=storey_of(shape.guid),
                bbox=bbox,
                vertex_count=len(verts) // 3,
                index_count=len(faces),
                position_offset=position_offset,
                normal_offset=normal_offset,
                index_offset=index_offset,
            ))

    if not elements:
        raise IfcError(
            "no renderable geometry was found in this file. It may contain only "
            "spatial structure or property data."
        )

    header = inspect_file(source)
    index = {
        "version": PAYLOAD_VERSION,
        "schema": header["schema"],
        "project_name": header["project_name"],
        "units": header["units"] or "metre",
        "bbox": [round(v, 4) for v in overall],
        "classes": dict(classes.most_common()),
        "storeys": sorted({e.storey for e in elements if e.storey}),
        "element_count": len(elements),
        "total_elements": header["element_count"],
        "truncated": truncated,
        "buffer_bytes": offset,
        "elements": [e.to_dict() for e in elements],
    }
    Path(index_path).write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def summary(index: dict[str, Any]) -> dict[str, Any]:
    """The part of the index worth storing on the database row."""
    return {key: index[key] for key in
            ("schema", "project_name", "units", "bbox", "classes", "storeys",
             "element_count", "total_elements", "truncated", "buffer_bytes")
            if key in index}


# ---------------------------------------------------------------------------
# Element properties, read on demand
# ---------------------------------------------------------------------------

_OPEN_FILES: dict[str, Any] = {}
_OPEN_ORDER: list[str] = []
_MAX_OPEN = 2


def _open_cached(path: str):
    """Keep a couple of parsed IFC files in memory.

    Property inspection is interactive — a click in the viewer should not pay
    for re-parsing a 200 MB file every time.
    """
    ifcopenshell, _ = _require()
    if path in _OPEN_FILES:
        return _OPEN_FILES[path]
    model = ifcopenshell.open(path)
    _OPEN_FILES[path] = model
    _OPEN_ORDER.append(path)
    while len(_OPEN_ORDER) > _MAX_OPEN:
        _OPEN_FILES.pop(_OPEN_ORDER.pop(0), None)
    return model


def forget(path: str) -> None:
    _OPEN_FILES.pop(path, None)
    if path in _OPEN_ORDER:
        _OPEN_ORDER.remove(path)


SKIP_ATTRS = {"GlobalId", "OwnerHistory", "ObjectPlacement", "Representation",
              "RepresentationMaps", "HasAssignments", "IsDecomposedBy", "Decomposes"}


def element_properties(ifc_path: str | Path, guid: str) -> dict[str, Any]:
    """Attributes, property sets and quantities for one element."""
    ifcopenshell, _ = _require()
    import ifcopenshell.util.element as util_element

    model = _open_cached(str(ifc_path))
    try:
        entity = model.by_guid(guid)
    except (RuntimeError, KeyError) as exc:
        raise IfcError(f"element {guid} is not in this model") from exc

    attributes: dict[str, Any] = {}
    info = entity.get_info()
    for key, value in info.items():
        if key in SKIP_ATTRS or key == "type" or value is None:
            continue
        if hasattr(value, "is_a"):
            value = getattr(value, "Name", None) or value.is_a()
        if isinstance(value, (list, tuple)):
            continue
        attributes[key] = value

    def flatten(sets: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, props in (sets or {}).items():
            cleaned = {}
            for key, value in (props or {}).items():
                if key == "id" or value is None or value == "":
                    continue
                cleaned[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
            if cleaned:
                out[name] = cleaned
        return out

    try:
        psets = flatten(util_element.get_psets(entity, psets_only=True))
    except TypeError:  # older signatures
        psets = flatten(util_element.get_psets(entity))
    try:
        quantities = flatten(util_element.get_psets(entity, qtos_only=True))
    except TypeError:
        quantities = {}

    container = None
    try:
        parent = util_element.get_container(entity)
        container = (parent.Name or parent.is_a()) if parent is not None else None
    except Exception:
        container = None

    materials: list[str] = []
    try:
        material = util_element.get_material(entity)
        if material is not None:
            if material.is_a("IfcMaterial"):
                materials = [material.Name or ""]
            elif hasattr(material, "MaterialLayers"):
                materials = [(layer.Material.Name if layer.Material else "")
                             for layer in material.MaterialLayers]
            elif hasattr(material, "Materials"):
                materials = [(m.Name or "") for m in material.Materials]
    except Exception:
        materials = []

    return {
        "guid": guid,
        "ifc_class": entity.is_a(),
        "name": getattr(entity, "Name", "") or "",
        "description": getattr(entity, "Description", "") or "",
        "predefined_type": str(getattr(entity, "PredefinedType", "") or ""),
        "container": container or "",
        "materials": [m for m in materials if m],
        "attributes": attributes,
        "property_sets": psets,
        "quantities": quantities,
    }
