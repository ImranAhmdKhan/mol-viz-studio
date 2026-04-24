"""Tests for the annotation manager."""

from __future__ import annotations

import json
import pytest

from molviz.annotations.annotation_manager import Annotation, AnnotationManager, AnnotationType


class TestAnnotationManager:
    def setup_method(self) -> None:
        self.mgr = AnnotationManager()

    def _make_label(self) -> Annotation:
        return Annotation(
            ann_type=AnnotationType.LABEL,
            label="Test",
            x=1.0, y=2.0, z=3.0,
            color="#FF0000",
        )

    def test_add_assigns_id(self) -> None:
        ann = self.mgr.add(self._make_label())
        assert ann.ann_id == 1

    def test_ids_increment(self) -> None:
        a1 = self.mgr.add(self._make_label())
        a2 = self.mgr.add(self._make_label())
        assert a2.ann_id == a1.ann_id + 1

    def test_get(self) -> None:
        ann = self.mgr.add(self._make_label())
        retrieved = self.mgr.get(ann.ann_id)
        assert retrieved is not None
        assert retrieved.label == "Test"

    def test_get_missing_returns_none(self) -> None:
        assert self.mgr.get(999) is None

    def test_remove(self) -> None:
        ann = self.mgr.add(self._make_label())
        assert self.mgr.remove(ann.ann_id) is True
        assert self.mgr.get(ann.ann_id) is None

    def test_remove_missing_returns_false(self) -> None:
        assert self.mgr.remove(42) is False

    def test_update(self) -> None:
        ann = self.mgr.add(self._make_label())
        self.mgr.update(ann.ann_id, label="Updated", font_size=20)
        updated = self.mgr.get(ann.ann_id)
        assert updated.label == "Updated"
        assert updated.font_size == 20

    def test_clear(self) -> None:
        self.mgr.add(self._make_label())
        self.mgr.add(self._make_label())
        self.mgr.clear()
        assert self.mgr.all == []

    def test_visible_filter(self) -> None:
        a1 = self.mgr.add(self._make_label())
        a2 = self.mgr.add(self._make_label())
        self.mgr.update(a2.ann_id, visible=False)
        assert len(self.mgr.visible) == 1
        assert self.mgr.visible[0].ann_id == a1.ann_id

    def test_to_json_round_trip(self) -> None:
        self.mgr.add(self._make_label())
        self.mgr.add(Annotation(
            ann_type=AnnotationType.DISTANCE,
            label="3.2 Å", x=0, y=0, z=0, x2=3.2, y2=0, z2=0
        ))
        js = self.mgr.to_json()
        new_mgr = AnnotationManager()
        new_mgr.from_json(js)
        assert len(new_mgr.all) == 2
        assert new_mgr.all[0].ann_type == AnnotationType.LABEL
        assert new_mgr.all[1].ann_type == AnnotationType.DISTANCE

    def test_to_js_commands_label(self) -> None:
        self.mgr.add(Annotation(
            ann_type=AnnotationType.LABEL,
            label="Hello",
            x=1.0, y=2.0, z=3.0,
        ))
        js = self.mgr.to_js_commands()
        assert "viewer.addLabel" in js
        assert "Hello" in js

    def test_to_js_commands_distance(self) -> None:
        self.mgr.add(Annotation(
            ann_type=AnnotationType.DISTANCE,
            label="4.2 Å",
            x=0.0, y=0.0, z=0.0,
            x2=4.2, y2=0.0, z2=0.0,
        ))
        js = self.mgr.to_js_commands()
        assert "viewer.addCylinder" in js
