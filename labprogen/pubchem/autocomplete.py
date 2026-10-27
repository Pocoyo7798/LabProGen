"""Qt autocomplete for chemical names via PubChem compound dictionary."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QRunnable, QThreadPool, QTimer, Signal, Slot, QStringListModel
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QCompleter, QFrame, QLineEdit, QListView

from .api import PUBCHEM_AUTOCOMPLETE_MIN_LEN, fetch_compound_autocomplete

_DEBOUNCE_MS = 400
_AUTOCOMPLETE_LIMIT = 10
_MAX_VISIBLE_ITEMS = 8

# Matches LabProGen dialogs: light surface, purple accent, subtle borders.
PUBCHEM_COMPLETER_POPUP_STYLE = """
    QListView {
        background-color: #ffffff;
        color: #1f2937;
        border: 1px solid #c7d2fe;
        border-radius: 8px;
        padding: 4px;
        outline: 0;
        font-size: 12px;
    }
    QListView::item {
        padding: 7px 12px;
        border-radius: 6px;
        margin: 1px 2px;
    }
    QListView::item:hover {
        background-color: #eef2ff;
        color: #3730a3;
    }
    QListView::item:selected {
        background-color: #6b4cff;
        color: #ffffff;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 6px;
        margin: 4px 2px 4px 0;
    }
    QScrollBar::handle:vertical {
        background: #c7d2fe;
        border-radius: 3px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #a5b4fc;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        height: 0;
        background: none;
    }
    QScrollBar:horizontal {
        height: 0;
    }
"""


def _style_completer_popup(completer: QCompleter, line_edit: QLineEdit) -> None:
    popup = completer.popup()
    if not isinstance(popup, QListView):
        return
    popup.setObjectName("pubchemCompoundCompleterPopup")
    popup.setStyleSheet(PUBCHEM_COMPLETER_POPUP_STYLE)
    popup.setFrameShape(QFrame.Shape.NoFrame)
    popup.setAutoFillBackground(True)
    palette = popup.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#6b4cff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    popup.setPalette(palette)
    popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    popup.setUniformItemSizes(True)
    popup.setSpacing(0)
    popup.setMinimumWidth(max(line_edit.width(), 260))


def _append_pubchem_placeholder_hint(line_edit: QLineEdit) -> None:
    base = (line_edit.placeholderText() or "Name").strip()
    hint = "PubChem suggestions appear after 3 letters"
    if hint.lower() not in base.lower():
        line_edit.setPlaceholderText(f"{base} {hint}")


class _FetchSignals(QObject):
    finished = Signal(str, list)


class _FetchRunnable(QRunnable):
    def __init__(self, query: str, signals: _FetchSignals) -> None:
        super().__init__()
        self._query = query
        self._signals = signals

    def run(self) -> None:
        terms = fetch_compound_autocomplete(self._query, limit=_AUTOCOMPLETE_LIMIT)
        self._signals.finished.emit(self._query, terms)


class PubChemCompoundAutocomplete(QObject):
    """Debounced PubChem compound suggestions on a name QLineEdit."""

    compound_selected = Signal(str)

    def __init__(self, line_edit: QLineEdit, parent: QObject | None = None) -> None:
        super().__init__(parent or line_edit)
        self._edit = line_edit
        self._pool = QThreadPool.globalInstance()
        self._fetch_signals = _FetchSignals()
        self._fetch_signals.finished.connect(self._apply_results)

        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self._edit)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._completer.setMaxVisibleItems(_MAX_VISIBLE_ITEMS)
        self._edit.setCompleter(self._completer)
        _style_completer_popup(self._completer, self._edit)
        _append_pubchem_placeholder_hint(self._edit)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._schedule_fetch)

        self._last_selected = ""
        self._suppress_autocomplete = False

        line_edit.textChanged.connect(self._on_text_changed)
        self._completer.activated.connect(self._on_compound_activated)

    @Slot(str)
    def _on_compound_activated(self, text: str) -> None:
        selected = str(text).strip()
        if not selected:
            return
        self._last_selected = selected
        self._suppress_autocomplete = True
        self._debounce.stop()
        self._model.setStringList([])
        self._completer.popup().hide()
        self.compound_selected.emit(selected)

    @Slot(str)
    def _on_text_changed(self, text: str) -> None:
        if self._suppress_autocomplete:
            if text.strip() == self._last_selected:
                self._completer.popup().hide()
                return
            self._suppress_autocomplete = False

        if len(text.strip()) < PUBCHEM_AUTOCOMPLETE_MIN_LEN:
            self._model.setStringList([])
            self._completer.popup().hide()
            self._debounce.stop()
            return
        self._debounce.start()

    def _schedule_fetch(self) -> None:
        query = self._edit.text().strip()
        if len(query) < PUBCHEM_AUTOCOMPLETE_MIN_LEN:
            self._model.setStringList([])
            return
        self._pool.start(_FetchRunnable(query, self._fetch_signals))

    @Slot(str, list)
    def _apply_results(self, query: str, terms: list) -> None:
        if query != self._edit.text().strip():
            return
        _style_completer_popup(self._completer, self._edit)
        popup = self._completer.popup()
        popup.setMinimumWidth(max(self._edit.width(), 260))
        self._model.setStringList(terms)
        if terms and self._edit.hasFocus() and not self._suppress_autocomplete:
            self._completer.complete()


def attach_pubchem_compound_autocomplete(line_edit: QLineEdit) -> PubChemCompoundAutocomplete:
    """Enable PubChem compound autocomplete on a chemical name field."""
    return PubChemCompoundAutocomplete(line_edit)
