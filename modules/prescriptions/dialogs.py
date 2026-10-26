"""Prescription editor dialog and per-customer prescription history."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from modules.prescriptions.models import SOURCES, Prescription
from modules.prescriptions.repository import PrescriptionRepository
from modules.prescriptions.widgets import PrescriptionEditor
from ui.components.calendar import make_date_edit
from ui.components.ui_kit import make_button, notice


def _title_bar(title: str, subtitle: str) -> QFrame:
    bar = QFrame()
    bar.setObjectName("windowTitleBar")
    layout = QVBoxLayout(bar)
    layout.setContentsMargins(18, 13, 18, 13)
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setObjectName("windowTitle")
    caption = QLabel(subtitle)
    caption.setObjectName("windowSubtitle")
    caption.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(caption)
    return bar


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    return date(value.year + month // 12, month % 12 + 1, min(value.day, 28))


class PrescriptionDialog(QDialog):
    """Create, renew or edit a structured prescription."""

    def __init__(self, customer_name: str, prescription: Prescription | None = None,
                 validity_months: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._original = prescription
        self._validity_months = validity_months
        self._expiry_touched = bool(prescription and prescription.expires_at)
        editing = bool(prescription and prescription.id)
        self.setWindowTitle("Editar receita" if editing else "Nova receita")
        self.resize(1080, 720)
        self.setMinimumSize(920, 620)
        self.result_prescription: Prescription | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(_title_bar(
            "Receita oftálmica",
            f"{customer_name} — registre os valores exatamente como na receita; o sistema confere passos e faixas.",
        ))

        info = QFrame()
        info.setObjectName("surfaceCard")
        info_grid = QGridLayout(info)
        info_grid.setContentsMargins(18, 14, 18, 14)
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(10)
        self.prescribed_at = make_date_edit(QDate.currentDate())
        self.expires_at = make_date_edit()
        self.source = QComboBox()
        for code, label in SOURCES.items():
            self.source.addItem(label, code)
        self.prescriber_name = QLineEdit()
        self.prescriber_name.setPlaceholderText("Nome do oftalmologista / optometrista")
        self.prescriber_registry = QLineEdit()
        self.prescriber_registry.setPlaceholderText("CRM / registro profissional")
        for column, (label_text, widget) in enumerate([
            ("Data da receita", self.prescribed_at), ("Validade", self.expires_at), ("Origem", self.source),
        ]):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            info_grid.addWidget(label, 0, column * 2)
            info_grid.addWidget(widget, 0, column * 2 + 1)
        professional_label = QLabel("Profissional")
        professional_label.setObjectName("fieldLabel")
        registry_label = QLabel("Registro")
        registry_label.setObjectName("fieldLabel")
        info_grid.addWidget(professional_label, 1, 0)
        info_grid.addWidget(self.prescriber_name, 1, 1, 1, 3)
        info_grid.addWidget(registry_label, 1, 4)
        info_grid.addWidget(self.prescriber_registry, 1, 5)
        root.addWidget(info)

        editor_card = QFrame()
        editor_card.setObjectName("surfaceCard")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(18, 14, 18, 14)
        heading = QLabel("Refração e medidas")
        heading.setObjectName("cardHeading")
        editor_layout.addWidget(heading)
        self.editor = PrescriptionEditor(validity_months)
        editor_layout.addWidget(self.editor)
        root.addWidget(editor_card)

        extra = QHBoxLayout()
        extra.setSpacing(12)
        self.lens_recommendation = QLineEdit()
        self.lens_recommendation.setPlaceholderText("Recomendação de lente (ex.: multifocal 1.67 antirreflexo)")
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Observações clínicas ou do atendimento")
        self.notes.setMaximumHeight(70)
        left = QVBoxLayout()
        label = QLabel("Recomendação")
        label.setObjectName("fieldLabel")
        left.addWidget(label)
        left.addWidget(self.lens_recommendation)
        left.addStretch(1)
        right = QVBoxLayout()
        label = QLabel("Observações")
        label.setObjectName("fieldLabel")
        right.addWidget(label)
        right.addWidget(self.notes)
        extra.addLayout(left, 1)
        extra.addLayout(right, 1)
        root.addLayout(extra)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar receita")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.prescribed_at.dateChanged.connect(self._sync_expiry)
        self.expires_at.dateChanged.connect(self._mark_expiry_touched)
        if prescription:
            self.prescribed_at.setDate(QDate(prescription.prescribed_at.year, prescription.prescribed_at.month, prescription.prescribed_at.day))
            expiry = prescription.effective_expiry(validity_months)
            self.expires_at.blockSignals(True)
            self.expires_at.setDate(QDate(expiry.year, expiry.month, expiry.day))
            self.expires_at.blockSignals(False)
            self.source.setCurrentIndex(max(0, self.source.findData(prescription.source)))
            self.prescriber_name.setText(prescription.prescriber_name)
            self.prescriber_registry.setText(prescription.prescriber_registry)
            self.lens_recommendation.setText(prescription.lens_recommendation)
            self.notes.setPlainText(prescription.notes)
            self.editor.load(prescription)
        else:
            self._sync_expiry()
            self.editor.load(None)

    def _mark_expiry_touched(self, *_args: object) -> None:
        self._expiry_touched = True

    def _sync_expiry(self, *_args: object) -> None:
        if self._expiry_touched:
            return
        start = self.prescribed_at.date().toPython()
        expiry = _add_months(start, self._validity_months)
        self.expires_at.blockSignals(True)
        self.expires_at.setDate(QDate(expiry.year, expiry.month, expiry.day))
        self.expires_at.blockSignals(False)

    def build(self) -> Prescription:
        base = replace(self._original) if self._original else Prescription()
        base.prescribed_at = self.prescribed_at.date().toPython()
        base.expires_at = self.expires_at.date().toPython()
        base.source = str(self.source.currentData())
        base.prescriber_name = self.prescriber_name.text().strip()
        base.prescriber_registry = self.prescriber_registry.text().strip()
        base.lens_recommendation = self.lens_recommendation.text().strip()
        base.notes = self.notes.toPlainText().strip()
        self.editor.apply_to(base)
        base.normalize()
        return base

    def _accept(self) -> None:
        prescription = self.build()
        problems = prescription.errors()
        if problems:
            QMessageBox.warning(self, "Receita incompleta", "\n".join(f"• {item}" for item in problems))
            return
        notes = prescription.warnings(self._validity_months)
        if notes:
            answer = QMessageBox.question(
                self, "Confira a receita",
                "Encontramos pontos que merecem conferência:\n\n" + "\n".join(f"• {item}" for item in notes)
                + "\n\nOs valores estão corretos e deseja salvar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.result_prescription = prescription
        self.accept()


class PrescriptionHistoryDialog(QDialog):
    """Customer prescription history; optionally used as a picker by the POS."""

    def __init__(self, customer: dict, repository: PrescriptionRepository, validity_months: int = 12,
                 select_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._customer = customer
        self._repository = repository
        self._validity_months = validity_months
        self._items: list[Prescription] = []
        self.selected: Prescription | None = None
        name = str(customer.get("full_name") or "Cliente")
        self.setWindowTitle(f"Receitas — {name}")
        self.resize(1080, 620)
        self.setMinimumSize(900, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(_title_bar(
            f"Receitas de {name}",
            "Histórico de receitas oftálmicas. A mais recente e válida é sugerida automaticamente nas vendas.",
        ))
        if repository.is_preview:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • as receitas ficam apenas na memória até fechar o aplicativo."))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.new_button = make_button("Nova receita", "fa5s.plus", "primaryButton")
        self.new_button.clicked.connect(self._new)
        self.renew_button = make_button("Renovar a partir da selecionada", "fa5s.copy", "secondaryButton")
        self.renew_button.setToolTip("Cria uma nova receita copiando os valores da selecionada (ex.: após novo exame sem alteração).")
        self.renew_button.clicked.connect(self._renew)
        self.edit_button = make_button("Editar", "fa5s.pen", "secondaryButton")
        self.edit_button.clicked.connect(self._edit)
        self.toggle_button = make_button("Ativar / inativar", "fa5s.power-off", "dangerButton")
        self.toggle_button.clicked.connect(self._toggle_active)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.renew_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.toggle_button)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Data", "Validade", "OD", "OE", "DNP (OD/OE)", "Altura", "Origem", "Situação"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._choose() if select_mode else self._edit())
        root.addWidget(self.table, 1)

        self.empty = QLabel("Nenhuma receita cadastrada para este cliente. Use “Nova receita”.")
        self.empty.setObjectName("emptyState")
        root.addWidget(self.empty)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = make_button("Fechar", None, "secondaryButton")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        if select_mode:
            choose = make_button("Usar receita selecionada", "fa5s.check", "primaryButton")
            choose.clicked.connect(self._choose)
            footer.addWidget(choose)
        root.addLayout(footer)
        self._load()

    def _load(self) -> None:
        try:
            self._items = self._repository.list_for_customer(str(self._customer.get("id")))
        except Exception as exc:
            QMessageBox.critical(self, "Receitas indisponíveis",
                                 f"Não foi possível carregar as receitas.\n\n{exc}\n\nConfirme se a migration 202610250002 foi aplicada.")
            self._items = []
        today = date.today()
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            expiry = item.effective_expiry(self._validity_months)
            if not item.active:
                status, color = "Inativa", "#8A97AB"
            elif expiry < today:
                status, color = "Vencida", "#C03030"
            elif (expiry - today).days <= 30:
                status, color = "Vence em breve", "#9A6200"
            else:
                status, color = "Válida", "#0E8A5B"
            dnp = " / ".join(
                f"{value:.1f}".replace(".", ",") if value is not None else "—" for value in (item.od_dnp, item.oe_dnp)
            )
            height = " / ".join(
                f"{value:.1f}".replace(".", ",") if value is not None else "—" for value in (item.od_height, item.oe_height)
            )
            values = [
                item.prescribed_at.strftime("%d/%m/%Y"), expiry.strftime("%d/%m/%Y"),
                item.eye_summary("od"), item.eye_summary("oe"), dnp, height,
                SOURCES.get(item.source, item.source), status,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.id)
                if column == 7:
                    cell.setForeground(QColor(color))
                self.table.setItem(row, column, cell)
        self.empty.setVisible(not self._items)
        if self._items:
            self.table.selectRow(0)

    def _current(self) -> Prescription | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._items):
            QMessageBox.information(self, "Selecione uma receita", "Selecione uma receita na lista.")
            return None
        return self._items[row]

    def _open_editor(self, prescription: Prescription | None) -> None:
        dialog = PrescriptionDialog(str(self._customer.get("full_name") or "Cliente"), prescription, self._validity_months, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_prescription is None:
            return
        result = dialog.result_prescription
        result.customer_id = str(self._customer.get("id"))
        try:
            saved = self._repository.save(result)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar a receita", str(exc))
            return
        self._load()
        for row, item in enumerate(self._items):
            if item.id == saved.id:
                self.table.selectRow(row)
                break

    def _new(self) -> None:
        self._open_editor(None)

    def _renew(self) -> None:
        current = self._current()
        if current is None:
            return
        renewed = replace(current, id=None, prescribed_at=date.today(), expires_at=None, active=True, created_at="")
        self._open_editor(renewed)

    def _edit(self) -> None:
        current = self._current()
        if current is not None:
            self._open_editor(current)

    def _toggle_active(self) -> None:
        current = self._current()
        if current is None:
            return
        updated = replace(current, active=not current.active)
        try:
            self._repository.save(updated)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível atualizar a receita", str(exc))
            return
        self._load()

    def _choose(self) -> None:
        current = self._current()
        if current is None:
            return
        if not current.active:
            QMessageBox.information(self, "Receita inativa", "Ative a receita antes de usá-la em uma venda.")
            return
        self.selected = current
        self.accept()
