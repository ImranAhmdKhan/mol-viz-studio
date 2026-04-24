"""Qt WebChannel bridge between Python and the 3Dmol.js viewer."""

from __future__ import annotations

import json
from typing import Callable, Any

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal


class ViewerBridge(QObject):
    """Exposed to JavaScript as ``bridge``; relays events to Python callbacks."""

    # Emitted whenever the JS viewer fires an event
    viewerEvent = pyqtSignal(str, str)  # (event_name, json_payload)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._callbacks: dict[str, list[Callable]] = {}

    # ------------------------------------------------------------------
    # Called from JavaScript
    # ------------------------------------------------------------------

    @pyqtSlot(str, str)
    def onViewerEvent(self, event: str, payload: str) -> None:
        """Receive an event from the JS viewer and dispatch to registered callbacks."""
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"raw": payload}

        self.viewerEvent.emit(event, payload)

        for cb in self._callbacks.get(event, []):
            cb(data)
        for cb in self._callbacks.get("*", []):
            cb(event, data)

    # ------------------------------------------------------------------
    # Python-side subscription API
    # ------------------------------------------------------------------

    def on(self, event: str, callback: Callable) -> None:
        """Register *callback* for *event*.  Use ``'*'`` for all events."""
        self._callbacks.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable | None = None) -> None:
        if callback is None:
            self._callbacks.pop(event, None)
        else:
            self._callbacks.get(event, []).remove(callback)
