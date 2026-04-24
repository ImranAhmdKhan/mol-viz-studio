"""Annotation data model and manager for MolViz Studio."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum


class AnnotationType(str, Enum):
    LABEL = "label"
    ARROW = "arrow"
    DISTANCE = "distance"
    ANGLE = "angle"
    SHAPE = "shape"


@dataclass
class Annotation:
    """A single annotation that can be serialised to/from JSON."""

    ann_type: AnnotationType
    label: str = ""
    # 3-D anchor point (Å)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # For arrow / distance annotations: second anchor
    x2: float = 0.0
    y2: float = 0.0
    z2: float = 0.0
    # Appearance
    color: str = "#FFD700"
    font_size: int = 14
    bold: bool = False
    visible: bool = True
    ann_id: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ann_type"] = self.ann_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        d = dict(d)
        d["ann_type"] = AnnotationType(d["ann_type"])
        return cls(**d)


class AnnotationManager:
    """Manages the collection of annotations for the current molecule."""

    def __init__(self) -> None:
        self._annotations: List[Annotation] = []
        self._next_id: int = 1

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add(self, ann: Annotation) -> Annotation:
        ann.ann_id = self._next_id
        self._next_id += 1
        self._annotations.append(ann)
        return ann

    def remove(self, ann_id: int) -> bool:
        original = len(self._annotations)
        self._annotations = [a for a in self._annotations if a.ann_id != ann_id]
        return len(self._annotations) < original

    def get(self, ann_id: int) -> Optional[Annotation]:
        for a in self._annotations:
            if a.ann_id == ann_id:
                return a
        return None

    def update(self, ann_id: int, **kwargs) -> bool:
        ann = self.get(ann_id)
        if ann is None:
            return False
        for k, v in kwargs.items():
            setattr(ann, k, v)
        return True

    def clear(self) -> None:
        self._annotations.clear()

    @property
    def all(self) -> List[Annotation]:
        return list(self._annotations)

    @property
    def visible(self) -> List[Annotation]:
        return [a for a in self._annotations if a.visible]

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #

    def to_json(self) -> str:
        return json.dumps([a.to_dict() for a in self._annotations], indent=2)

    def from_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        self._annotations = [Annotation.from_dict(d) for d in data]
        if self._annotations:
            self._next_id = max(a.ann_id for a in self._annotations) + 1

    # ------------------------------------------------------------------ #
    # JavaScript representation (for 3Dmol.js viewer)
    # ------------------------------------------------------------------ #

    def to_js_commands(self) -> str:
        """
        Generate JavaScript snippet to render all visible annotations
        in the 3Dmol.js viewer via the global *viewer* object.
        """
        cmds: list[str] = ["viewer.removeAllLabels();"]
        for ann in self.visible:
            if ann.ann_type == AnnotationType.LABEL:
                cmds.append(
                    f"viewer.addLabel({json.dumps(ann.label)}, {{"
                    f"position: {{x:{ann.x},y:{ann.y},z:{ann.z}}},"
                    f"fontColor:{json.dumps(ann.color)},"
                    f"fontSize:{ann.font_size},"
                    f"bold:{str(ann.bold).lower()},"
                    f"backgroundOpacity:0.7"
                    f"}});"
                )
            elif ann.ann_type in (AnnotationType.DISTANCE, AnnotationType.ARROW):
                # Draw a cylinder (arrow) between the two points
                cmds.append(
                    f"viewer.addCylinder({{"
                    f"start:{{x:{ann.x},y:{ann.y},z:{ann.z}}},"
                    f"end:{{x:{ann.x2},y:{ann.y2},z:{ann.z2}}},"
                    f"radius:0.05,"
                    f"color:{json.dumps(ann.color)},"
                    f"dashed:true"
                    f"}});"
                )
                if ann.label:
                    mx = (ann.x + ann.x2) / 2
                    my = (ann.y + ann.y2) / 2
                    mz = (ann.z + ann.z2) / 2
                    cmds.append(
                        f"viewer.addLabel({json.dumps(ann.label)}, {{"
                        f"position:{{x:{mx},y:{my},z:{mz}}},"
                        f"fontColor:{json.dumps(ann.color)},"
                        f"fontSize:{ann.font_size},"
                        f"backgroundOpacity:0.7"
                        f"}});"
                    )
        cmds.append("viewer.render();")
        return "\n".join(cmds)
