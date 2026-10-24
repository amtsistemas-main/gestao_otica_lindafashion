"""Structured AI results panel for the Ótica Linda Fashion desktop app.

This component intentionally contains no chat transcript or token-by-token renderer.
The AI/service layer should call set_loading(True) before a request and set_result(...)
with the complete response after the request finishes.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AIResultsPanel(QWidget):
    """Form-driven AI analysis view with structured results and contextual actions."""

    generate_requested = Signal(dict)
    regenerate_requested = Signal(dict)
    result_edited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: dict[str, Any] = {}
        self._last_request: dict[str, str] = {}
        self._editing = False
        self.setObjectName("aiResultsPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        heading = QVBoxLayout()
        eyebrow = QLabel("INTELIGÊNCIA DE NEGÓCIO")
        eyebrow.setObjectName("aiEyebrow")
        title = QLabel("Análises inteligentes")
        title.setObjectName("aiPageTitle")
        description = QLabel(
            "Gere análises objetivas da operação e visualize os resultados em indicadores, "
            "tabelas e recomendações."
        )
        description.setObjectName("aiDescription")
        description.setWordWrap(True)
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        heading.addWidget(description)
        root.addLayout(heading)

        form_card = QFrame()
        form_card.setObjectName("aiFormCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(10)
        form_layout.addWidget(self._label("O que você deseja analisar?", "aiFieldLabel"))

        fields = QHBoxLayout()
        fields.setSpacing(10)
        self.analysis_combo = QComboBox()
        self.analysis_combo.setObjectName("aiSelect")
        self.analysis_combo.addItem("Desempenho de vendas", "sales")
        self.analysis_combo.addItem("Situação do estoque", "inventory")
        self.analysis_combo.addItem("Produtos e categorias", "products")
        self.analysis_combo.addItem("Resumo financeiro", "finance")
        self.period_combo = QComboBox()
        self.period_combo.setObjectName("aiSelect")
        self.period_combo.addItem("Últimos 7 dias", "7d")
        self.period_combo.addItem("Últimos 30 dias", "30d")
        self.period_combo.addItem("Últimos 90 dias", "90d")
        self.period_combo.addItem("Este ano", "year")
        fields.addWidget(self.analysis_combo, 2)
        fields.addWidget(self.period_combo, 1)
        form_layout.addLayout(fields)

        self.context_input = QLineEdit()
        self.context_input.setObjectName("aiContextInput")
        self.context_input.setPlaceholderText("Contexto opcional (ex.: priorizar armações)")
        self.context_input.setClearButtonEnabled(True)
        form_layout.addWidget(self.context_input)

        form_actions = QHBoxLayout()
        form_actions.addStretch()
        self.generate_button = QPushButton("Gerar análise")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_button.clicked.connect(self._submit_request)
        form_actions.addWidget(self.generate_button)
        form_layout.addLayout(form_actions)
        root.addWidget(form_card)

        self.loading_card = QFrame()
        self.loading_card.setObjectName("aiLoadingCard")
        loading_layout = QVBoxLayout(self.loading_card)
        loading_layout.setContentsMargins(18, 18, 18, 18)
        loading_layout.setSpacing(14)
        loading_title = QLabel("Preparando análise…")
        loading_title.setObjectName("aiCardTitle")
        loading_layout.addWidget(loading_title)
        self._skeleton_metrics = QGridLayout()
        self._skeleton_metrics.setSpacing(12)
        for index in range(3):
            skeleton = QFrame()
            skeleton.setObjectName("aiSkeleton")
            skeleton.setMinimumHeight(82)
            self._skeleton_metrics.addWidget(skeleton, 0, index)
        loading_layout.addLayout(self._skeleton_metrics)
        for width in (0, 1, 2):
            line = QFrame()
            line.setObjectName("aiSkeletonLine")
            line.setFixedHeight(12 if width != 1 else 20)
            line.setMaximumWidth((560, 420, 500)[width])
            loading_layout.addWidget(line)
        self.loading_card.hide()
        root.addWidget(self.loading_card)

        self.results_card = QFrame()
        self.results_card.setObjectName("aiResultsCard")
        results_layout = QVBoxLayout(self.results_card)
        results_layout.setContentsMargins(18, 18, 18, 18)
        results_layout.setSpacing(14)

        result_header = QHBoxLayout()
        self.result_title = QLabel("Resultado da análise")
        self.result_title.setObjectName("aiCardTitle")
        result_header.addWidget(self.result_title, 1)
        self.status_badge = QLabel("Concluída")
        self.status_badge.setObjectName("aiStatusBadge")
        result_header.addWidget(self.status_badge)
        results_layout.addLayout(result_header)

        self.summary = QLabel("")
        self.summary.setObjectName("aiSummary")
        self.summary.setWordWrap(True)
        results_layout.addWidget(self.summary)

        self.metrics_host = QWidget()
        self.metrics_grid = QGridLayout(self.metrics_host)
        self.metrics_grid.setContentsMargins(0, 0, 0, 0)
        self.metrics_grid.setSpacing(12)
        results_layout.addWidget(self.metrics_host)

        self.table = QTableWidget()
        self.table.setObjectName("aiResultTable")
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.table.setMinimumHeight(150)
        results_layout.addWidget(self.table)

        self.text_editor = QPlainTextEdit()
        self.text_editor.setObjectName("aiEditableText")
        self.text_editor.setPlaceholderText("Recomendações e observações da análise…")
        self.text_editor.setMinimumHeight(110)
        self.text_editor.setReadOnly(True)
        self.text_editor.hide()
        results_layout.addWidget(self.text_editor)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_button = QPushButton("Copiar")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.clicked.connect(self.copy_result)
        self.edit_button = QPushButton("Editar texto")
        self.edit_button.setObjectName("secondaryButton")
        self.edit_button.clicked.connect(self.toggle_edit)
        self.csv_button = QPushButton("Exportar CSV")
        self.csv_button.setObjectName("secondaryButton")
        self.csv_button.clicked.connect(self.export_csv)
        self.pdf_button = QPushButton("Exportar PDF")
        self.pdf_button.setObjectName("secondaryButton")
        self.pdf_button.clicked.connect(self.export_pdf)
        self.regenerate_button = QPushButton("Gerar novamente")
        self.regenerate_button.setObjectName("primaryButton")
        self.regenerate_button.clicked.connect(self.regenerate)
        for button in (
            self.copy_button, self.edit_button, self.csv_button,
            self.pdf_button, self.regenerate_button,
        ):
            actions.addWidget(button)
        results_layout.addLayout(actions)
        self.results_card.hide()
        root.addWidget(self.results_card)
        root.addStretch(1)

        self.setStyleSheet("""
            #aiResultsPanel { color: #172C52; }
            #aiEyebrow { color: #2165F5; font-size: 9pt; font-weight: 800; letter-spacing: 1px; }
            #aiPageTitle { color: #172C52; font-size: 23pt; font-weight: 800; }
            #aiDescription { color: #657795; font-size: 10pt; }
            #aiFormCard, #aiLoadingCard, #aiResultsCard {
                background: #FFFFFF; border: 1px solid #E4EAF3; border-radius: 14px;
            }
            #aiFieldLabel { color: #263B5E; font-size: 10pt; font-weight: 700; }
            #aiSelect, #aiContextInput {
                min-height: 38px; padding: 0 10px; color: #172C52;
                background: #F9FBFE; border: 1px solid #DCE4F0; border-radius: 8px;
            }
            #primaryButton {
                color: #FFFFFF; background: #2165F5; border: 0; border-radius: 8px;
                padding: 10px 16px; font-weight: 700; min-height: 18px;
            }
            #primaryButton:hover { background: #174FD0; }
            #secondaryButton {
                color: #294265; background: #FFFFFF; border: 1px solid #DCE4F0;
                border-radius: 8px; padding: 8px 11px; font-weight: 600;
            }
            #secondaryButton:hover { background: #F3F7FD; }
            #aiCardTitle { color: #172C52; font-size: 14pt; font-weight: 750; }
            #aiSummary { color: #4E6281; font-size: 10pt; }
            #aiStatusBadge { color: #167553; background: #E4F7EF; border-radius: 10px; padding: 6px 10px; font-weight: 700; }
            #aiSkeleton, #aiSkeletonLine { background: #EDF2F8; border: 0; border-radius: 8px; }
            #aiMetricCard { background: #F8FAFE; border: 1px solid #E6ECF5; border-radius: 10px; }
            #aiMetricLabel { color: #71819A; font-size: 9pt; }
            #aiMetricValue { color: #172C52; font-size: 17pt; font-weight: 800; }
            #aiEditableText { color: #172C52; background: #FFFFFF; border: 1px solid #DCE4F0; border-radius: 8px; padding: 8px; }
            #aiResultTable { color: #263B5E; gridline-color: #E8EDF5; border: 1px solid #E4EAF3; }
        """)

    @staticmethod
    def _label(text: str, object_name: str) -> QLabel:
        item = QLabel(text)
        item.setObjectName(object_name)
        return item

    def _submit_request(self) -> None:
        request = {
            "analysis": str(self.analysis_combo.currentData()),
            "analysis_label": self.analysis_combo.currentText(),
            "period": str(self.period_combo.currentData()),
            "period_label": self.period_combo.currentText(),
            "context": self.context_input.text().strip(),
        }
        self._last_request = request
        self.set_loading(True)
        self.generate_requested.emit(request)

    def set_loading(self, loading: bool) -> None:
        """Show a stable skeleton while the service works; never render partial tokens."""
        self.generate_button.setEnabled(not loading)
        self.regenerate_button.setEnabled(not loading)
        self.loading_card.setVisible(loading)
        if loading:
            self.results_card.hide()
        elif not self._result:
            self.results_card.hide()

    def set_result(self, result: dict[str, Any]) -> None:
        """Render a complete response.

        Expected keys: title, summary, status, metrics[], columns[], rows[], recommendations.
        Metric items use label/value and optional change/status. Rows may be dicts or sequences.
        """
        self._result = dict(result)
        self.set_loading(False)
        self.result_title.setText(str(result.get("title") or "Resultado da análise"))
        self.summary.setText(str(result.get("summary") or ""))
        self.status_badge.setText(str(result.get("status") or "Concluída"))
        self._clear_layout(self.metrics_grid)

        metrics = result.get("metrics") or []
        for index, metric in enumerate(metrics):
            card = QFrame()
            card.setObjectName("aiMetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(5)
            card_layout.addWidget(self._label(str(metric.get("label", "Indicador")), "aiMetricLabel"))
            card_layout.addWidget(self._label(str(metric.get("value", "—")), "aiMetricValue"))
            change = metric.get("change")
            if change:
                change_label = self._label(str(change), "aiMetricLabel")
                card_layout.addWidget(change_label)
            self.metrics_grid.addWidget(card, index // 3, index % 3)

        columns = [str(column) for column in (result.get("columns") or [])]
        rows = result.get("rows") or []
        if rows and not columns and isinstance(rows[0], dict):
            columns = [str(key) for key in rows[0].keys()]
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row.get(column, "") for column in columns] if isinstance(row, dict) else list(row)
            for column_index, value in enumerate(values[:len(columns)]):
                item = QTableWidgetItem(str(value if value is not None else ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column_index, item)
        self.table.setVisible(bool(columns))
        self.table.resizeColumnsToContents()
        recommendations = result.get("recommendations", "")
        if isinstance(recommendations, (list, tuple)):
            recommendations = "\n".join(f"• {item}" for item in recommendations)
        self.text_editor.setPlainText(str(recommendations or ""))
        self.text_editor.setReadOnly(True)
        self.text_editor.setVisible(bool(recommendations))
        self._editing = False
        self.edit_button.setText("Editar texto")
        self.results_card.show()

    @staticmethod
    def _clear_layout(layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _plain_result(self) -> str:
        lines = [self.result_title.text(), self.summary.text()]
        for index in range(self.metrics_grid.count()):
            widget = self.metrics_grid.itemAt(index).widget()
            if widget is not None:
                labels = widget.findChildren(QLabel)
                lines.append(" — ".join(label.text() for label in labels))
        if self.table.columnCount():
            lines.append("\t".join(
                self.table.horizontalHeaderItem(column).text()
                for column in range(self.table.columnCount())
            ))
            for row in range(self.table.rowCount()):
                lines.append("\t".join(
                    self.table.item(row, column).text() if self.table.item(row, column) else ""
                    for column in range(self.table.columnCount())
                ))
        recommendations = self.text_editor.toPlainText() if self._editing else str(
            self._result.get("recommendations") or ""
        )
        if isinstance(self._result.get("recommendations"), (list, tuple)) and not self._editing:
            recommendations = "\n".join(f"• {item}" for item in self._result["recommendations"])
        if recommendations:
            lines.extend(["", "Recomendações", recommendations])
        return "\n".join(line for line in lines if line is not None)

    def copy_result(self) -> None:
        QApplication.clipboard().setText(self._plain_result())

    def toggle_edit(self) -> None:
        self._editing = not self._editing
        self.text_editor.setReadOnly(not self._editing)
        self.text_editor.setVisible(self._editing or bool(self.text_editor.toPlainText().strip()))
        if self._editing:
            recommendations = self.text_editor.toPlainText()
            if not recommendations:
                original = self._result.get("recommendations") or ""
                if isinstance(original, (list, tuple)):
                    original = "\n".join(f"• {item}" for item in original)
                self.text_editor.setPlainText(str(original))
            self.edit_button.setText("Salvar texto")
            return
        edited = self.text_editor.toPlainText()
        self._result["recommendations"] = edited
        self.result_edited.emit(edited)
        self.edit_button.setText("Editar texto")

    def regenerate(self) -> None:
        if self._last_request:
            self.set_loading(True)
            self.regenerate_requested.emit(dict(self._last_request))

    def export_csv(self) -> None:
        if not self.table.columnCount():
            QMessageBox.information(self, "Exportar CSV", "Esta análise não contém uma tabela para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar análise", "analise_ia.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with Path(path).open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow([
                    self.table.horizontalHeaderItem(column).text()
                    for column in range(self.table.columnCount())
                ])
                for row in range(self.table.rowCount()):
                    writer.writerow([
                        self.table.item(row, column).text() if self.table.item(row, column) else ""
                        for column in range(self.table.columnCount())
                    ])
        except OSError as exc:
            QMessageBox.critical(self, "Falha ao exportar CSV", str(exc))

    def export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar análise", "analise_ia.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
            from xml.sax.saxutils import escape

            document = SimpleDocTemplate(path, pagesize=A4, title=self.result_title.text())
            styles = getSampleStyleSheet()
            story = [
                Paragraph(escape(self.result_title.text()), styles["Title"]),
                Spacer(1, 10),
                Paragraph(escape(self.summary.text()), styles["BodyText"]),
                Spacer(1, 12),
            ]
            for index in range(self.metrics_grid.count()):
                widget = self.metrics_grid.itemAt(index).widget()
                if widget is not None:
                    parts = [item.text() for item in widget.findChildren(QLabel)]
                    story.append(Paragraph(escape(" — ".join(parts)), styles["BodyText"]))
                    story.append(Spacer(1, 5))
            if self.table.columnCount():
                data = [[
                    self.table.horizontalHeaderItem(column).text()
                    for column in range(self.table.columnCount())
                ]]
                for row in range(self.table.rowCount()):
                    data.append([
                        self.table.item(row, column).text() if self.table.item(row, column) else ""
                        for column in range(self.table.columnCount())
                    ])
                table = Table(data, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1FC")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172C52")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4F0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.extend([Spacer(1, 10), table])
            recommendations = self.text_editor.toPlainText() if self._editing else str(
                self._result.get("recommendations") or ""
            )
            if isinstance(self._result.get("recommendations"), (list, tuple)) and not self._editing:
                recommendations = "\n".join(f"• {item}" for item in self._result["recommendations"])
            if recommendations:
                story.extend([Spacer(1, 14), Paragraph("Recomendações", styles["Heading2"])])
                for line in recommendations.splitlines():
                    if line.strip():
                        story.append(Paragraph(escape(line), styles["BodyText"]))
                        story.append(Spacer(1, 4))
            document.build(story)
        except (OSError, ImportError, ValueError) as exc:
            QMessageBox.critical(self, "Falha ao exportar PDF", str(exc))
