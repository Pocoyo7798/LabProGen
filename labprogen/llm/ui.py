"""UI for LLM-powered article text generation."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .client import AieduClient, AieduConfig, load_aiedu_config, save_aiedu_config
from .article import generate_article_text

_PRIMARY_BUTTON_STYLE = (
    "QPushButton {"
    "  background-color: #6b4cff; color: white; border-radius: 8px;"
    "  padding: 8px 18px; font-weight: 600; font-size: 13px;"
    "  border: none; min-height: 34px;"
    "}"
    "QPushButton:hover { background-color: #5a3de6; }"
    "QPushButton:pressed { background-color: #4b33bf; }"
    "QPushButton:disabled { background-color: #cbd5e1; color: #64748b; }"
)

_SECONDARY_BUTTON_STYLE = (
    "QPushButton {"
    "  background-color: #ffffff; color: #334155; border-radius: 8px;"
    "  padding: 8px 18px; font-weight: 600; font-size: 13px;"
    "  border: 1px solid #d0d4db; min-height: 34px;"
    "}"
    "QPushButton:hover { background-color: #f8fafc; border-color: #94a3b8; }"
    "QPushButton:pressed { background-color: #f1f5f9; }"
    "QPushButton:disabled { background-color: #f8fafc; color: #94a3b8; }"
)

_DIALOG_STYLE = (
    "QDialog { background-color: #f5f7fa; }"
    "QGroupBox {"
    "  font-size: 13px; font-weight: 700; color: #334155;"
    "  border: 1px solid #e2e8f0; border-radius: 10px;"
    "  margin-top: 12px; padding-top: 14px; background: #ffffff;"
    "}"
    "QGroupBox::title {"
    "  subcontrol-origin: margin; left: 14px; padding: 0 6px;"
    "}"
    "QLabel { color: #334155; font-size: 13px; }"
    "QLineEdit {"
    "  background-color: #ffffff; color: #1e293b;"
    "  border: 1px solid #d0d4db; border-radius: 6px;"
    "  padding: 8px 12px; font-size: 13px;"
    "}"
    "QLineEdit:focus { border: 2px solid #6b4cff; padding: 7px 11px; }"
    "QCheckBox { color: #334155; font-size: 13px; spacing: 8px; }"
    "QCheckBox::indicator { width: 16px; height: 16px; }"
)

_OUTPUT_STYLE = (
    "QTextEdit {"
    "  background-color: #ffffff; color: #1e293b;"
    "  border: 1px solid #d0d4db; border-radius: 8px;"
    "  padding: 14px; font-size: 13px;"
    "  selection-background-color: #ddd6fe; selection-color: #1e293b;"
    "}"
)

_STATUS_OK_STYLE = (
    "color: #0f766e; background-color: #ecfdf5; border: 1px solid #99f6e4;"
    "border-radius: 8px; padding: 10px 12px; font-size: 12px;"
)

_STATUS_WARN_STYLE = (
    "color: #b45309; background-color: #fffbeb; border: 1px solid #fde68a;"
    "border-radius: 8px; padding: 10px 12px; font-size: 12px;"
)

_TITLE_STYLE = "font-size: 16px; font-weight: 700; color: #1e293b;"
_SUBTITLE_STYLE = "font-size: 13px; color: #64748b;"


class _ArticleGenerationWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        protocol_data: dict,
        procedure_guide_text: str,
        config: AieduConfig,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._protocol_data = protocol_data
        self._procedure_guide_text = procedure_guide_text
        self._config = config

    def run(self) -> None:
        try:
            text = generate_article_text(
                self._protocol_data,
                procedure_guide_text=self._procedure_guide_text,
                client=AieduClient(self._config),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(text)


class AieduConfigDialog(QDialog):
    """Collect and persist AIedu API credentials."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AIedu API Configuration")
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_STYLE)
        self.config: AieduConfig | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Connect to AIedu")
        title.setStyleSheet(_TITLE_STYLE)
        root.addWidget(title)

        intro = QLabel(
            "Paste the endpoint URL, API key and channel ID from the AIedu agent settings. "
            "Credentials are stored locally in the config folder next to the application."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(_SUBTITLE_STYLE)
        root.addWidget(intro)

        group = QGroupBox("API credentials")
        form_host = QFormLayout(group)
        form_host.setSpacing(12)
        form_host.setContentsMargins(16, 20, 16, 16)
        existing = load_aiedu_config() or AieduConfig("", "", "")

        self._endpoint_edit = QLineEdit(existing.endpoint_url)
        self._endpoint_edit.setPlaceholderText(
            "https://api.iaedu.pt/agent-chat/api/v1/agent/.../stream"
        )
        form_host.addRow("Endpoint URL:", self._endpoint_edit)

        self._api_key_edit = QLineEdit(existing.api_key)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_host.addRow("API key:", self._api_key_edit)

        self._channel_edit = QLineEdit(existing.channel_id)
        form_host.addRow("Channel ID:", self._channel_edit)
        root.addWidget(group)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save configuration")
        save_btn.setStyleSheet(_PRIMARY_BUTTON_STYLE)
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        root.addLayout(button_row)

    def _save(self) -> None:
        config = AieduConfig(
            endpoint_url=self._endpoint_edit.text().strip(),
            api_key=self._api_key_edit.text().strip(),
            channel_id=self._channel_edit.text().strip(),
        )
        try:
            config.validate()
            save_aiedu_config(config)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid configuration", str(exc))
            return
        self.config = config
        self.accept()


class GenerateArticleDialog(QDialog):
    """Generate article-style Methods text from the current protocol."""

    def __init__(
        self,
        *,
        protocol_data: dict,
        procedure_guide_text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Article Text")
        self.setMinimumSize(820, 620)
        self.setStyleSheet(_DIALOG_STYLE)
        self._protocol_data = protocol_data
        self._procedure_guide_text = procedure_guide_text
        self._worker: _ArticleGenerationWorker | None = None
        self.generated_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        title = QLabel("Generate article Methods text")
        title.setStyleSheet(_TITLE_STYLE)
        header_layout.addWidget(title)
        subtitle = QLabel(
            "Uses your exported protocol JSON and the procedure guide to draft "
            "publication-ready Methods prose through AIedu."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(_SUBTITLE_STYLE)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        options_group = QGroupBox("Generation options")
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(16, 20, 16, 16)
        self._include_guide = QCheckBox("Include current procedure guide as LLM context")
        self._include_guide.setChecked(True)
        options_layout.addWidget(self._include_guide)
        root.addWidget(options_group)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        output_group = QGroupBox("Generated text")
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(16, 20, 16, 16)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(_OUTPUT_STYLE)
        self._output.setPlaceholderText(
            "Generated article text will appear here after you click Generate."
        )
        output_layout.addWidget(self._output)
        root.addWidget(output_group, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #e2e8f0;")
        root.addWidget(separator)

        button_row = QHBoxLayout()
        self._configure_btn = QPushButton("Configure AIedu")
        self._configure_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        self._configure_btn.clicked.connect(self._configure_aiedu)
        button_row.addWidget(self._configure_btn)

        button_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)

        self._copy_btn = QPushButton("Copy text")
        self._copy_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        self._copy_btn.clicked.connect(self._copy_output)
        self._copy_btn.setEnabled(False)
        button_row.addWidget(self._copy_btn)

        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setStyleSheet(_PRIMARY_BUTTON_STYLE)
        self._generate_btn.clicked.connect(self._generate)
        button_row.addWidget(self._generate_btn)

        root.addLayout(button_row)
        self._refresh_status()

    def _refresh_status(self) -> None:
        config = load_aiedu_config()
        if config is None:
            self._status_label.setText(
                "AIedu is not configured yet. Open “Configure AIedu” and paste your credentials."
            )
            self._status_label.setStyleSheet(_STATUS_WARN_STYLE)
            return
        endpoint = config.endpoint_url
        if len(endpoint) > 72:
            endpoint = endpoint[:69] + "..."
        self._status_label.setText(f"AIedu connected · {endpoint}")
        self._status_label.setStyleSheet(_STATUS_OK_STYLE)

    def _configure_aiedu(self) -> None:
        dialog = AieduConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_status()

    def _guide_text_for_generation(self) -> str:
        if self._include_guide.isChecked():
            return self._procedure_guide_text
        return ""

    def _set_busy(self, busy: bool) -> None:
        self._generate_btn.setEnabled(not busy)
        self._configure_btn.setEnabled(not busy)
        self._include_guide.setEnabled(not busy)
        self._copy_btn.setEnabled(not busy and bool(self.generated_text.strip()))

    def _generate(self) -> None:
        config = load_aiedu_config()
        if config is None:
            self._configure_aiedu()
            config = load_aiedu_config()
        if config is None:
            return

        self._set_busy(True)
        self._output.setPlainText("Generating article text…")
        self._copy_btn.setEnabled(False)

        self._worker = _ArticleGenerationWorker(
            protocol_data=self._protocol_data,
            procedure_guide_text=self._guide_text_for_generation(),
            config=config,
            parent=self,
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_finished(self, text: str) -> None:
        self._worker = None
        self._set_busy(False)
        self.generated_text = text
        self._output.setPlainText(text)
        self._copy_btn.setEnabled(bool(text.strip()))

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False)
        self._output.setPlainText("")
        self._copy_btn.setEnabled(False)
        QMessageBox.critical(self, "Generation failed", message)

    def _copy_output(self) -> None:
        text = self._output.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
