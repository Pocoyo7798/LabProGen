"""PubChem compound search: auto-fill form and paginate results in batches."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from .api import (
    PUBCHEM_SEARCH_BATCH_SIZE,
    PubChemCompoundRecord,
    fetch_compound_search_batch,
    map_pubchem_to_form_fields,
)

_NAV_BUTTON_STYLE = (
    "QPushButton {"
    "  background-color: #f8fafc; color: #475569; border: 1px solid #e2e8f0;"
    "  border-radius: 6px; min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px;"
    "  padding: 0; font-size: 10px; font-weight: 600;"
    "}"
    "QPushButton:hover:enabled { background-color: #eef2ff; border-color: #c7d2fe; color: #3730a3; }"
    "QPushButton:pressed:enabled { background-color: #e0e7ff; }"
    "QPushButton:disabled { color: #cbd5e1; background-color: #f8fafc; border-color: #f1f5f9; }"
)

_BAR_STYLE = (
    "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;"
)


def apply_values_to_field_trackers(
    values: dict[str, str],
    field_trackers: dict[str, object],
) -> None:
    """Write mapped values into dialog widgets (only keys present in trackers)."""
    for key, value in values.items():
        if key not in field_trackers or not value:
            continue
        tracker = field_trackers[key]
        if isinstance(tracker, QLineEdit):
            tracker.blockSignals(True)
            tracker.setText(value)
            tracker.blockSignals(False)
        elif isinstance(tracker, QComboBox):
            idx = tracker.findText(value)
            if idx >= 0:
                tracker.setCurrentIndex(idx)
            elif tracker.isEditable():
                tracker.setEditText(value)
        elif isinstance(tracker, tuple) and tracker:
            if isinstance(tracker[0], QLineEdit):
                tracker[0].setText(value)


class _BatchSignals(QObject):
    finished = Signal(str, object, object, int)  # selected_name, page, records, start_index
    failed = Signal(str)


class _BatchRunnable(QRunnable):
    def __init__(
        self,
        selected_name: str,
        *,
        start: int,
        signals: _BatchSignals,
    ) -> None:
        super().__init__()
        self._selected_name = selected_name
        self._start = start
        self._signals = signals

    def run(self) -> None:
        try:
            page, records = fetch_compound_search_batch(
                self._selected_name,
                start=self._start,
                batch_size=PUBCHEM_SEARCH_BATCH_SIZE,
            )
            self._signals.finished.emit(
                self._selected_name,
                page,
                records,
                self._start,
            )
        except Exception:
            self._signals.failed.emit(self._selected_name)


class PubChemResultNavigator(QWidget):
    """◀ / ▶ controls and position label for PubChem search results."""

    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_BAR_STYLE)
        self.setMaximumHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(22, 22)
        self._prev_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._prev_btn.setToolTip("Previous PubChem result")
        self._prev_btn.clicked.connect(self.prev_clicked.emit)

        self._status = QLabel("PubChem")
        self._status.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(22, 22)
        self._next_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._next_btn.setToolTip("Next PubChem result")
        self._next_btn.clicked.connect(self.next_clicked.emit)

        layout.addWidget(self._prev_btn)
        layout.addWidget(self._status, 1)
        layout.addWidget(self._next_btn)

        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        self._prev_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)

    def set_nav_enabled(self, *, prev: bool, next: bool) -> None:
        self._prev_btn.setEnabled(prev)
        self._next_btn.setEnabled(next)

    def set_status_text(self, text: str) -> None:
        self._status.setText(text)


class PubChemChemicalSearchController(QObject):
    """Loads compound results in batches of 5 and applies them to the chemical form."""

    def __init__(
        self,
        *,
        field_trackers: dict[str, object],
        visible_field_keys: set[str],
        chemical_type: str,
        navigator: PubChemResultNavigator,
        on_fields_applied: Callable[[dict[str, str]], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._trackers = field_trackers
        self._visible_keys = set(visible_field_keys)
        self._chemical_type = chemical_type
        self._navigator = navigator
        self._on_fields_applied = on_fields_applied
        self._pool = QThreadPool.globalInstance()
        self._batch_signals = _BatchSignals()
        self._batch_signals.finished.connect(self._on_batch_finished)
        self._batch_signals.failed.connect(self._on_batch_failed)

        self._selected_name = ""
        self._search_total = 0
        self._records: list[PubChemCompoundRecord | None] = []
        self._index = 0
        self._loading = False
        self._index_after_load: int | None = None

        navigator.prev_clicked.connect(self.show_previous)
        navigator.next_clicked.connect(self.show_next)

    @property
    def is_active(self) -> bool:
        return self._search_total > 0

    def start_search(self, selected_name: str) -> None:
        selected_name = selected_name.strip()
        if len(selected_name) < 3:
            return
        self._selected_name = selected_name
        self._search_total = 0
        self._records = []
        self._index = 0
        self._index_after_load = 0
        self._navigator.show()
        self._navigator.set_status_text("Searching PubChem…")
        self._navigator.set_enabled(False)
        self._load_batch(start=0)

    def show_previous(self) -> None:
        if self._loading or self._index <= 0:
            return
        self._index -= 1
        self._apply_current()
        self._update_navigator()

    def show_next(self) -> None:
        if self._loading:
            return
        if self._index < len(self._records) - 1:
            self._index += 1
            self._apply_current()
            self._update_navigator()
            return
        if self._has_more_to_load():
            self._index_after_load = self._index + 1
            self._load_batch(start=len(self._records))
            return
        self._update_navigator()

    def _has_more_to_load(self) -> bool:
        return len(self._records) < self._search_total

    def _load_batch(self, start: int) -> None:
        self._loading = True
        self._navigator.set_status_text("Loading PubChem…")
        self._navigator.set_enabled(False)

        self._pool.start(
            _BatchRunnable(
                self._selected_name,
                start=start,
                signals=self._batch_signals,
            )
        )

    @Slot(str, object, object, int)
    def _on_batch_finished(
        self, selected_name: str, page, records: list, start: int
    ) -> None:
        if selected_name != self._selected_name:
            return
        self._loading = False
        self._search_total = page.total

        if start == 0:
            self._records = list(records)
        else:
            self._records.extend(records)

        if self._search_total <= 0 or not self._records:
            self._navigator.set_status_text("No PubChem compounds found")
            self._navigator.set_enabled(False)
            return

        if self._index_after_load is not None:
            self._index = min(self._index_after_load, len(self._records) - 1)
            self._index_after_load = None
        elif self._index >= len(self._records):
            self._index = max(len(self._records) - 1, 0)
        self._apply_current()
        self._update_navigator()

    @Slot(str)
    def _on_batch_failed(self, query: str) -> None:
        if query != self._selected_name:
            return
        self._loading = False
        self._navigator.set_status_text("PubChem search failed")
        self._navigator.set_enabled(False)

    def _apply_current(self) -> None:
        if not self._records:
            return
        record = self._records[self._index] if self._index < len(self._records) else None
        mapped = map_pubchem_to_form_fields(
            record,
            self._selected_name,
            visible_keys=self._visible_keys,
            chemical_type=self._chemical_type,
        )
        apply_values_to_field_trackers(mapped, self._trackers)
        if self._on_fields_applied and mapped:
            self._on_fields_applied(mapped)

    def _update_navigator(self) -> None:
        total = self._search_total
        position = self._index + 1
        suffix = "+" if self._has_more_to_load() and position >= len(self._records) else ""
        self._navigator.set_status_text(
            f"PubChem result {position} of {total}{suffix}"
        )
        self._navigator.set_nav_enabled(
            prev=self._index > 0,
            next=self._index < len(self._records) - 1 or self._has_more_to_load(),
        )


