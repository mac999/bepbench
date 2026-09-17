"""IFC model attachments: store the upload, derive the viewer payload, clean up."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from ..config import _data_dir
from ..extensions import db
from ..ifcio import IfcError, ifcopenshell_available, summary, tessellate
from ..models import IfcModel, Project
from ..settings import get as setting
from .projects import ServiceError


def models_root() -> Path:
    root = _data_dir() / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_models(project: Project) -> list[IfcModel]:
    return list(project.models)


def get_model(project: Project, model_id: int) -> IfcModel:
    for model in project.models:
        if model.id == model_id:
            return model
    raise ServiceError(f"project '{project.slug}' has no model {model_id}")


def attach_model(
    project: Project,
    stream: BinaryIO,
    filename: str,
    *,
    discipline: str = "",
) -> IfcModel:
    """Save an uploaded IFC and tessellate it for the viewer."""
    if not ifcopenshell_available():
        raise ServiceError(
            "IFC support needs the optional 'ifcopenshell' package on the server "
            "(pip install ifcopenshell)."
        )
    if not filename.lower().endswith((".ifc", ".ifczip")):
        raise ServiceError("only .ifc files can be attached")

    directory = models_root() / project.slug / uuid.uuid4().hex[:12]
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source.ifc"

    limit = int(setting("viewer.max_upload_mb", 200)) * 1024 * 1024
    written = 0
    try:
        with open(source, "wb") as target:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise ServiceError(f"file is larger than the {limit // (1024 * 1024)} MB limit")
                target.write(chunk)
    except ServiceError:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    model = IfcModel(
        project=project, filename=filename, directory=str(directory),
        size_bytes=written, discipline=discipline, status="processing",
    )
    db.session.add(model)
    db.session.commit()

    try:
        index = tessellate(source, directory / "model.bin", directory / "model.json")
    except IfcError as exc:
        model.status = "failed"
        model.error = str(exc)
        db.session.commit()
        raise ServiceError(str(exc)) from exc

    model.status = "ready"
    model.schema = index.get("schema", "")
    model.element_count = index.get("element_count", 0)
    model.meta = summary(index)
    db.session.commit()
    return model


def delete_model(project: Project, model: IfcModel) -> None:
    directory = Path(model.directory)
    db.session.delete(model)
    db.session.commit()
    if directory.is_dir() and models_root() in directory.parents:
        shutil.rmtree(directory, ignore_errors=True)


def rebuild_model(model: IfcModel) -> dict[str, Any]:
    """Re-tessellate after a settings change (tolerance, element cap)."""
    directory = Path(model.directory)
    index = tessellate(model.source_path, directory / "model.bin", directory / "model.json")
    model.element_count = index.get("element_count", 0)
    model.meta = summary(index)
    model.status = "ready"
    model.error = ""
    db.session.commit()
    return index
