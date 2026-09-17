"""Persistence layer.

Answers are stored one row per field rather than as a single JSON blob: it keeps
per-field timestamps and authorship cheap, and lets a framework gain or lose
fields without migrating stored plans.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import UniqueConstraint

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(240), nullable=False)
    framework_id = db.Column(db.String(60), nullable=False)
    client = db.Column(db.String(240), default="")
    reference = db.Column(db.String(120), default="")
    status = db.Column(db.String(40), default="draft")
    # Which ISO 19650-2 appointment stage this plan is written for.
    stage = db.Column(db.String(40), default="delivery")
    owner = db.Column(db.String(240), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    answers = db.relationship(
        "Answer", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    snapshots = db.relationship(
        "Snapshot", back_populates="project", cascade="all, delete-orphan",
        lazy="selectin", order_by="Snapshot.created_at.desc()",
    )
    models = db.relationship(
        "IfcModel", back_populates="project", cascade="all, delete-orphan",
        lazy="selectin", order_by="IfcModel.uploaded_at.desc()",
    )

    def values(self) -> dict[str, dict[str, Any]]:
        """Nested ``{section_id: {field_id: value}}`` view of the answers."""
        out: dict[str, dict[str, Any]] = {}
        for answer in self.answers:
            out.setdefault(answer.section_id, {})[answer.field_id] = answer.value
        return out

    def answer(self, section_id: str, field_id: str) -> "Answer | None":
        for a in self.answers:
            if a.section_id == section_id and a.field_id == field_id:
                return a
        return None

    def to_dict(self, include_values: bool = False) -> dict[str, Any]:
        data = {
            "slug": self.slug,
            "name": self.name,
            "framework": self.framework_id,
            "client": self.client,
            "reference": self.reference,
            "status": self.status,
            "stage": self.stage,
            "owner": self.owner,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_values:
            data["values"] = self.values()
        return data


class Answer(db.Model):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("project_id", "section_id", "field_id", name="uq_answer_path"),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = db.Column(db.String(80), nullable=False)
    field_id = db.Column(db.String(80), nullable=False)
    payload = db.Column(db.Text, default="null")
    updated_by = db.Column(db.String(240), default="")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="answers")

    @property
    def value(self) -> Any:
        try:
            return json.loads(self.payload or "null")
        except json.JSONDecodeError:
            return self.payload

    @value.setter
    def value(self, new_value: Any) -> None:
        self.payload = json.dumps(new_value, ensure_ascii=False)

    @property
    def path(self) -> str:
        return f"{self.section_id}.{self.field_id}"


class Snapshot(db.Model):
    """An immutable point-in-time capture of answers plus the score at that moment."""

    __tablename__ = "snapshots"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(160), default="")
    score = db.Column(db.Float, default=0.0)
    maturity_label = db.Column(db.String(60), default="")
    payload = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="snapshots")

    @property
    def data(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload or "{}")
        except json.JSONDecodeError:
            return {}

    @data.setter
    def data(self, value: dict[str, Any]) -> None:
        self.payload = json.dumps(value, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "score": round(self.score or 0.0, 1),
            "maturity": self.maturity_label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IfcModel(db.Model):
    """An uploaded IFC file and its derived viewer payload.

    The IFC itself is kept so the payload can be regenerated when the
    tessellation settings change; only the derived files are served to the
    browser.
    """

    __tablename__ = "ifc_models"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    directory = db.Column(db.String(1024), nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    schema = db.Column(db.String(40), default="")
    element_count = db.Column(db.Integer, default=0)
    discipline = db.Column(db.String(80), default="")
    status = db.Column(db.String(40), default="ready")
    error = db.Column(db.Text, default="")
    payload = db.Column(db.Text, default="{}")
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="models")

    @property
    def meta(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload or "{}")
        except json.JSONDecodeError:
            return {}

    @meta.setter
    def meta(self, value: dict[str, Any]) -> None:
        self.payload = json.dumps(value, ensure_ascii=False)

    @property
    def source_path(self) -> str:
        return str(Path(self.directory) / "source.ifc")

    @property
    def index_path(self) -> str:
        return str(Path(self.directory) / "model.json")

    @property
    def buffer_path(self) -> str:
        return str(Path(self.directory) / "model.bin")

    def to_dict(self) -> dict[str, Any]:
        meta = self.meta
        return {
            "id": self.id,
            "filename": self.filename,
            "discipline": self.discipline,
            "schema": self.schema,
            "size_bytes": self.size_bytes,
            "element_count": self.element_count,
            "status": self.status,
            "error": self.error,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "classes": meta.get("classes", {}),
            "storeys": meta.get("storeys", []),
            "bbox": meta.get("bbox", []),
            "truncated": meta.get("truncated", False),
            "total_elements": meta.get("total_elements", self.element_count),
        }
