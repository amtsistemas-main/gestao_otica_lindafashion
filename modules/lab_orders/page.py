"""Order and laboratory workflow board: from sale to delivery."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

from core.organization import OrganizationContext, current_organization
from modules.lab_orders import statuses
from modules.lab_orders.repository import LabOrderRepository
from modules.prescriptions.repository import PrescriptionRepository
from ui.components.ui_kit import make_button, notice

FRAME_FIELDS = [("ponte", "Ponte"), ("horiz", "Horizontal"), ("vert", "Vertical"), ("diag_maior", "Diag. maior"), ("diametro", "Diâmetro")]


def _money(value: object) -> str:
    amount = float(value or 0)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _fmt_date(value: object) -> str:
    parsed = _parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


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


def order_alert(order: dict, today: date | None = None) -> tuple[str, str] | None:
    """(text, color) when the order is late for the customer or at the laboratory."""
    today = today or date.today()
    status = order.get("status", "")
    if status in statuses.CLOSED:
        return None
    promised = _parse_date(order.get("expected_at"))
    if promised and promised < today and status != "pronto_retirada":
        return f"Prazo do cliente vencido há {(today - promised).days} dia(s)", "#C03030"
    lab_due = _parse_date(order.get("lab_expected_at"))
    if lab_due and lab_due < today and status in ("enviado_laboratorio", "em_producao"):
        return f"Laboratório atrasado {(today - lab_due).days} dia(s)", "#B7791F"
    if promised and status != "pronto_retirada" and 0 <= (promised - today).days <= 1:
        return "Prazo do cliente vence hoje/amanhã", "#B7791F"
    return None


class StageChip(QPushButton):
    """Pipeline stage filter showing the number of orders in that stage."""

    def __init__(self, code: str, title: str, color: str, icon: str) -> None:
        super().__init__()
        self.code = code
        self.setObjectName("stageChip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Room for a two-line caption ("Enviado ao laboratório") on narrow windows.
        self.setMinimumHeight(84)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        top = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon, color=color).pixmap(15, 15))
        self.count = QLabel("0")
        self.count.setObjectName("stageCount")
        self.count.setStyleSheet(f"color:{color};")
        top.addWidget(icon_label)
        top.addStretch(1)
        top.addWidget(self.count)
        layout.addLayout(top)
        caption = QLabel(title)
        caption.setObjectName("stageLabel")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        for child in (icon_label, self.count, caption):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class LabOrderDialog(QDialog):
    """Create or edit an order with laboratory, deadlines, cost and frame measurements."""

    def __init__(self, repository: LabOrderRepository, prescriptions: PrescriptionRepository,
                 customers: list[dict], laboratories: list[dict], order: dict | None = None,
                 fixed_customer: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prescriptions = prescriptions
        self.setWindowTitle("Editar pedido" if order else "Novo pedido")
        self.resize(820, 720)
        self.record: dict | None = None
        order = order or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(_title_bar("Pedido / laboratório", "Dados do pedido, laboratório, prazos, custo e medidas da armação."))

        form = QFormLayout()
        form.setSpacing(10)
        self.customer = QComboBox()
        for customer in customers:
            self.customer.addItem(str(customer.get("full_name") or "Cliente"), customer.get("id"))
        selected_customer = (fixed_customer or {}).get("id") or order.get("customer_id")
        if selected_customer:
            self.customer.setCurrentIndex(max(0, self.customer.findData(selected_customer)))
        self.customer.setEnabled(not (fixed_customer or order))
        self.customer.currentIndexChanged.connect(self._load_prescriptions)
        self.number = QLineEdit(str(order.get("order_number") or ""))
        self.number.setPlaceholderText("Ex.: OS-2026-001 (opcional)")
        self.description = QLineEdit(str(order.get("description") or ""))
        self.description.setPlaceholderText("Ex.: Armação acetato + lentes multifocais 1.67")
        self.lens_description = QLineEdit(str(order.get("lens_description") or ""))
        self.lens_description.setPlaceholderText("Especificação das lentes para o laboratório")
        self.laboratory = QComboBox()
        self.laboratory.addItem("Sem laboratório definido", None)
        for lab in laboratories:
            self.laboratory.addItem(str(lab.get("trade_name") or lab.get("name") or "Laboratório"), lab.get("id"))
        self.laboratory.setCurrentIndex(max(0, self.laboratory.findData(order.get("laboratory_id"))))
        self.lab_number = QLineEdit(str(order.get("lab_order_number") or ""))
        self.lab_number.setPlaceholderText("Número do pedido no laboratório")
        self.lab_cost = QDoubleSpinBox()
        self.lab_cost.setRange(0, 999_999.99)
        self.lab_cost.setDecimals(2)
        self.lab_cost.setPrefix("R$ ")
        self.lab_cost.setValue(float(order.get("lab_cost") or 0))
        self.lab_expected = self._date_field(order.get("lab_expected_at"), 5)
        self.expected = self._date_field(order.get("expected_at"), 7)
        self.prescription = QComboBox()
        self._initial_prescription = order.get("prescription_id")
        self.notes = QTextEdit(str(order.get("notes") or ""))
        self.notes.setMaximumHeight(70)
        form.addRow("Cliente *", self.customer)
        form.addRow("Número", self.number)
        form.addRow("Descrição *", self.description)
        form.addRow("Lentes", self.lens_description)
        form.addRow("Receita", self.prescription)
        form.addRow("Laboratório", self.laboratory)
        form.addRow("Nº no laboratório", self.lab_number)
        form.addRow("Custo do laboratório", self.lab_cost)
        form.addRow("Previsão do laboratório", self.lab_expected)
        form.addRow("Prazo para o cliente", self.expected)
        form.addRow("Observações", self.notes)
        root.addLayout(form)

        frame_card = QFrame()
        frame_card.setObjectName("surfaceCard")
        frame_layout = QGridLayout(frame_card)
        frame_layout.setContentsMargins(14, 10, 14, 10)
        frame_layout.setHorizontalSpacing(6)
        title = QLabel("Medidas da armação (mm)")
        title.setObjectName("cardHeading")
        frame_layout.addWidget(title, 0, 0, 1, len(FRAME_FIELDS))
        measurements = order.get("frame_measurements") or {}
        self._frame: dict[str, QLineEdit] = {}
        for column, (key, caption) in enumerate(FRAME_FIELDS):
            header = QLabel(caption)
            header.setObjectName("measureHeader")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field = QLineEdit(str(measurements.get(key) or ""))
            field.setObjectName("measureInput")
            field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field.setPlaceholderText("—")
            frame_layout.addWidget(header, 1, column)
            frame_layout.addWidget(field, 2, column)
            self._frame[key] = field
        root.addWidget(frame_card)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar pedido")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_prescriptions()

    @staticmethod
    def _date_field(value: object, default_days: int) -> QDateEdit:
        field = QDateEdit()
        field.setCalendarPopup(True)
        field.setDisplayFormat("dd/MM/yyyy")
        parsed = _parse_date(value)
        field.setDate(QDate(parsed.year, parsed.month, parsed.day) if parsed else QDate.currentDate().addDays(default_days))
        return field

    def _load_prescriptions(self, *_args: object) -> None:
        self.prescription.clear()
        self.prescription.addItem("Sem receita vinculada", None)
        customer_id = self.customer.currentData()
        if not customer_id:
            return
        try:
            items = self._prescriptions.list_for_customer(str(customer_id))
        except Exception:
            items = []
        for item in items:
            label = f"{item.prescribed_at.strftime('%d/%m/%Y')} — OD {item.eye_summary('od')} | OE {item.eye_summary('oe')}"
            self.prescription.addItem(label + ("" if item.active else " (inativa)"), item.id)
        position = self.prescription.findData(self._initial_prescription)
        if position >= 0:
            self.prescription.setCurrentIndex(position)
        elif self.prescription.count() > 1:
            self.prescription.setCurrentIndex(1)

    def _accept(self) -> None:
        if not self.customer.currentData():
            QMessageBox.warning(self, "Cliente obrigatório", "Selecione o cliente do pedido.")
            return
        if not self.description.text().strip():
            QMessageBox.warning(self, "Descrição obrigatória", "Descreva o pedido (armação, lentes, serviço).")
            self.description.setFocus()
            return
        lab_due = self.lab_expected.date().toPython()
        promised = self.expected.date().toPython()
        if lab_due > promised:
            answer = QMessageBox.question(
                self, "Prazo apertado",
                "A previsão do laboratório é posterior ao prazo prometido ao cliente. Deseja salvar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.record = {
            "customer_id": self.customer.currentData(),
            "order_number": self.number.text().strip(),
            "description": self.description.text().strip(),
            "lens_description": self.lens_description.text().strip(),
            "prescription_id": self.prescription.currentData(),
            "laboratory_id": self.laboratory.currentData(),
            "lab_order_number": self.lab_number.text().strip(),
            "lab_cost": round(self.lab_cost.value(), 2),
            "lab_expected_at": lab_due.isoformat(),
            "expected_at": promised.isoformat(),
            "notes": self.notes.toPlainText().strip(),
            "frame_measurements": {key: field.text().strip() for key, field in self._frame.items() if field.text().strip()},
        }
        self.accept()


class OrderTimelineDialog(QDialog):
    """Status history and occurrences (delays, lab errors, rework, warranty) of one order."""

    def __init__(self, repository: LabOrderRepository, order: dict, customer_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._order = order
        self.setWindowTitle(f"Acompanhamento — {order.get('order_number') or 'pedido'}")
        self.resize(900, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(_title_bar(
            f"Pedido {order.get('order_number') or '—'} · {customer_name}",
            f"{order.get('description') or ''} — status atual: {statuses.label(order.get('status', ''))}",
        ))

        stamps = QHBoxLayout()
        stamps.setSpacing(8)
        for caption, key in (("Criado", "created_at"), ("Enviado", "sent_at"), ("Recebido", "received_at"),
                             ("Conferido", "checked_at"), ("Pronto", "completed_at"), ("Entregue", "delivered_at")):
            box = QLabel(f"{caption}\n{_fmt_date(order.get(key))}")
            box.setObjectName("infoNotice" if order.get(key) else "emptyState")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setMinimumWidth(box.sizeHint().width())
            stamps.addWidget(box, 1)
        root.addLayout(stamps)

        occurrences_title = QLabel("Ocorrências")
        occurrences_title.setObjectName("sectionTitle")
        root.addWidget(occurrences_title)
        self.occurrences = QTableWidget(0, 5)
        self.occurrences.setHorizontalHeaderLabels(["Data", "Tipo", "Descrição", "Custo", "Situação"])
        self.occurrences.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.occurrences.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.occurrences.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.occurrences, 1)
        occurrence_actions = QHBoxLayout()
        add = make_button("Registrar ocorrência", "fa5s.exclamation-circle", "primaryButton")
        add.clicked.connect(self._add_occurrence)
        resolve = make_button("Marcar como resolvida", "fa5s.check", "secondaryButton")
        resolve.clicked.connect(self._resolve)
        occurrence_actions.addWidget(add)
        occurrence_actions.addWidget(resolve)
        occurrence_actions.addStretch(1)
        root.addLayout(occurrence_actions)

        history_title = QLabel("Histórico de status")
        history_title.setObjectName("sectionTitle")
        root.addWidget(history_title)
        self.history = QTableWidget(0, 3)
        self.history.setHorizontalHeaderLabels(["Data", "De", "Para"])
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.history, 1)
        close = make_button("Fechar", None, "secondaryButton")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self._occurrence_rows: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            self._occurrence_rows = self._repository.occurrences(self._order["id"])
            events = self._repository.events(self._order["id"])
        except Exception as exc:
            QMessageBox.critical(self, "Acompanhamento indisponível", f"{exc}\n\nConfirme se a migration 202610250003 foi aplicada.")
            return
        self.occurrences.setRowCount(len(self._occurrence_rows))
        for row, item in enumerate(self._occurrence_rows):
            resolved = bool(item.get("resolved_at"))
            values = [
                str(item.get("created_at") or "")[:16].replace("T", " "),
                statuses.OCCURRENCE_TYPES.get(item.get("occurrence_type", ""), item.get("occurrence_type", "")),
                item.get("description", ""), _money(item.get("cost")),
                "Resolvida" if resolved else "Em aberto",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 4:
                    cell.setForeground(QColor("#0E8A5B" if resolved else "#C03030"))
                self.occurrences.setItem(row, column, cell)
        self.history.setRowCount(len(events))
        for row, event in enumerate(events):
            values = [
                str(event.get("changed_at") or "")[:16].replace("T", " "),
                statuses.label(event.get("previous_status", "")) if event.get("previous_status") else "Início",
                statuses.label(event.get("new_status", "")),
            ]
            for column, value in enumerate(values):
                self.history.setItem(row, column, QTableWidgetItem(value))

    def _add_occurrence(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar ocorrência")
        dialog.resize(520, 340)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        form = QFormLayout()
        kind = QComboBox()
        for code, caption in statuses.OCCURRENCE_TYPES.items():
            kind.addItem(caption, code)
        description = QTextEdit()
        description.setPlaceholderText("Descreva o que aconteceu e a providência tomada")
        cost = QDoubleSpinBox()
        cost.setRange(0, 99_999.99)
        cost.setDecimals(2)
        cost.setPrefix("R$ ")
        form.addRow("Tipo", kind)
        form.addRow("Descrição *", description)
        form.addRow("Custo adicional", cost)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not description.toPlainText().strip():
            QMessageBox.warning(self, "Descrição obrigatória", "Descreva a ocorrência.")
            return
        try:
            self._repository.add_occurrence(self._order["id"], str(kind.currentData()), description.toPlainText().strip(), cost.value())
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível registrar", str(exc))
            return
        self._load()

    def _resolve(self) -> None:
        row = self.occurrences.currentRow()
        if row < 0 or row >= len(self._occurrence_rows):
            QMessageBox.information(self, "Selecione uma ocorrência", "Selecione a ocorrência resolvida.")
            return
        try:
            self._repository.resolve_occurrence(self._order["id"], self._occurrence_rows[row]["id"])
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível atualizar", str(exc))
            return
        self._load()


class LabOrdersPage(QDialog):
    """Board that follows every order from the sale to the delivery."""

    def __init__(self, preview_mode: bool = False, customer: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._customer = customer
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("O módulo Pedidos")
        self._repository = LabOrderRepository(self._ctx)
        self._prescriptions = PrescriptionRepository(self._ctx)
        self._orders: list[dict] = []
        self._visible: list[dict] = []
        self._customers: dict[str, dict] = {}
        self._labs: dict[str, dict] = {}
        self._stage_filter = ""
        title = f"Pedidos — {customer.get('full_name')}" if customer else "Pedidos e laboratório"
        self.setWindowTitle(f"{title} — Ótica Linda Fashion")
        self.resize(1320, 820)
        self.setMinimumSize(1060, 660)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        root.addWidget(_title_bar(
            title,
            "Acompanhe cada pedido da venda à entrega: envio, produção no laboratório, conferência, retirada e ocorrências.",
        ))
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • pedidos demonstrativos; alterações não são gravadas."))

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self._chips: list[StageChip] = []
        all_chip = StageChip("", "Em andamento", "#2165F5", "fa5s.stream")
        late_chip = StageChip("__late__", "Com alerta de prazo", "#C03030", "fa5s.exclamation-triangle")
        for chip in [all_chip] + [StageChip(s.code, s.label, s.color, s.icon) for s in statuses.FLOW] + [late_chip]:
            chip.clicked.connect(lambda checked=False, code=chip.code: self._set_stage(code))
            chips.addWidget(chip, 1)
            self._chips.append(chip)
        root.addLayout(chips)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por pedido, cliente, descrição ou nº do laboratório…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(qta.icon("fa5s.search", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._render)
        toolbar.addWidget(self.search, 1)
        self.lab_filter = QComboBox()
        self.lab_filter.setMinimumWidth(200)
        self.lab_filter.currentIndexChanged.connect(self._render)
        toolbar.addWidget(self.lab_filter)
        self.show_closed = QComboBox()
        self.show_closed.addItems(["Somente em aberto", "Incluir entregues e cancelados"])
        self.show_closed.currentIndexChanged.connect(self._render)
        toolbar.addWidget(self.show_closed)
        refresh = make_button("Atualizar", "fa5s.sync-alt", "secondaryButton")
        refresh.clicked.connect(self._load)
        toolbar.addWidget(refresh)
        new = make_button("Novo pedido", "fa5s.plus", "primaryButton")
        new.clicked.connect(self._new)
        toolbar.addWidget(new)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Pedido", "Cliente", "Descrição", "Laboratório", "Status", "Prev. laboratório", "Prazo cliente", "Custo lab.", "Alerta",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        for column in range(9):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._timeline())
        self.table.itemSelectionChanged.connect(self._sync_actions)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.advance_button = make_button("Avançar etapa", "fa5s.arrow-right", "primaryButton")
        self.advance_button.clicked.connect(self._advance)
        self.status_button = make_button("Alterar status", "fa5s.exchange-alt", "secondaryButton")
        self.status_button.clicked.connect(self._change_status)
        self.edit_button = make_button("Editar pedido", "fa5s.pen", "secondaryButton")
        self.edit_button.clicked.connect(self._edit)
        self.timeline_button = make_button("Ocorrências e histórico", "fa5s.history", "secondaryButton")
        self.timeline_button.clicked.connect(self._timeline)
        self.cancel_button = make_button("Cancelar pedido", "fa5s.ban", "dangerButton")
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.advance_button)
        actions.addWidget(self.status_button)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.timeline_button)
        actions.addStretch(1)
        actions.addWidget(self.cancel_button)
        root.addLayout(actions)
        self._load()

    # Data -----------------------------------------------------------------
    def _load(self) -> None:
        try:
            self._customers = {str(row["id"]): row for row in self._repository.customers()}
            self._labs = {str(row["id"]): row for row in self._repository.laboratories()}
            self._orders = self._repository.list_orders((self._customer or {}).get("id"))
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar pedidos", f"{exc}\n\nConfirme se a migration 202610250003 foi aplicada.")
            self._orders = []
        current_lab = self.lab_filter.currentData()
        self.lab_filter.blockSignals(True)
        self.lab_filter.clear()
        self.lab_filter.addItem("Todos os laboratórios", "")
        for lab_id, lab in self._labs.items():
            self.lab_filter.addItem(str(lab.get("trade_name") or lab.get("name")), lab_id)
        self.lab_filter.setCurrentIndex(max(0, self.lab_filter.findData(current_lab)))
        self.lab_filter.blockSignals(False)
        self._render()

    def _set_stage(self, code: str) -> None:
        self._stage_filter = code
        self._render()

    def _render(self, *_args: object) -> None:
        include_closed = self.show_closed.currentIndex() == 1
        term = self.search.text().strip().casefold()
        lab_id = self.lab_filter.currentData() or ""
        open_orders = [order for order in self._orders if order.get("status") not in statuses.CLOSED]
        counts = {status.code: 0 for status in statuses.FLOW}
        for order in self._orders:
            if order.get("status") in counts and (order.get("status") != "entregue"):
                counts[order["status"]] += 1
        late = [order for order in open_orders if order_alert(order)]
        for chip in self._chips:
            chip.setChecked(chip.code == self._stage_filter)
            if chip.code == "":
                chip.count.setText(str(len(open_orders)))
            elif chip.code == "__late__":
                chip.count.setText(str(len(late)))
            elif chip.code == "entregue":
                chip.count.setText(str(sum(1 for order in self._orders if order.get("status") == "entregue")))
            else:
                chip.count.setText(str(counts.get(chip.code, 0)))

        rows = []
        for order in self._orders:
            status = order.get("status", "")
            if self._stage_filter == "__late__":
                if not order_alert(order):
                    continue
            elif self._stage_filter:
                if status != self._stage_filter:
                    continue
            elif not include_closed and status in statuses.CLOSED:
                continue
            if lab_id and str(order.get("laboratory_id") or "") != lab_id:
                continue
            customer = self._customers.get(str(order.get("customer_id")), {})
            lab = self._labs.get(str(order.get("laboratory_id")), {})
            haystack = " ".join(str(value or "") for value in (
                order.get("order_number"), customer.get("full_name"), order.get("description"), order.get("lab_order_number"),
            )).casefold()
            if term and term not in haystack:
                continue
            rows.append((order, customer, lab))
        self._visible = [order for order, _customer, _lab in rows]

        self.table.setRowCount(len(rows))
        for row_index, (order, customer, lab) in enumerate(rows):
            alert = order_alert(order)
            values = [
                order.get("order_number") or "—", customer.get("full_name") or "—", order.get("description") or "",
                lab.get("trade_name") or lab.get("name") or "—", statuses.label(order.get("status", "")),
                _fmt_date(order.get("lab_expected_at")), _fmt_date(order.get("expected_at")),
                _money(order.get("lab_cost")), alert[0] if alert else "",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, order.get("id"))
                if column == 4:
                    cell.setForeground(QColor(statuses.color(order.get("status", ""))))
                if column == 8 and alert:
                    cell.setForeground(QColor(alert[1]))
                if column == 7:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, cell)
        self._sync_actions()

    def _selected(self, warn: bool = True) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._visible):
            if warn:
                QMessageBox.information(self, "Selecione um pedido", "Selecione um pedido na lista.")
            return None
        return self._visible[row]

    def _sync_actions(self) -> None:
        order = self._selected(warn=False)
        target = statuses.next_status(order.get("status", "")) if order else None
        self.advance_button.setEnabled(target is not None)
        self.advance_button.setText(f"Avançar para “{target.label}”" if target else "Avançar etapa")
        closed = bool(order) and order.get("status") in statuses.CLOSED
        self.cancel_button.setEnabled(bool(order) and not closed)

    # Actions --------------------------------------------------------------
    def _apply_status(self, order: dict, target: str) -> None:
        if statuses.skips_quality_check(order.get("status", ""), target):
            answer = QMessageBox.question(
                self, "Pedido sem conferência",
                "Este pedido ainda não passou pela etapa “Em conferência”. Conferir grau, centragem e acabamento "
                "evita retrabalho e devoluções.\n\nDeseja liberar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self._repository.set_status(order, target)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível alterar o status", str(exc))
            return
        self._load()

    def _advance(self) -> None:
        order = self._selected()
        if order is None:
            return
        target = statuses.next_status(order.get("status", ""))
        if target is not None:
            self._apply_status(order, target.code)

    def _change_status(self) -> None:
        order = self._selected()
        if order is None:
            return
        labels = [status.label for status in statuses.ALL_STATUSES]
        current = labels.index(statuses.label(order.get("status", ""))) if statuses.label(order.get("status", "")) in labels else 0
        choice, accepted = QInputDialog.getItem(self, "Alterar status", "Novo status:", labels, current, False)
        if not accepted:
            return
        target = statuses.ALL_STATUSES[labels.index(choice)].code
        if target == order.get("status"):
            return
        self._apply_status(order, target)

    def _open_editor(self, order: dict | None) -> None:
        dialog = LabOrderDialog(
            self._repository, self._prescriptions, list(self._customers.values()), list(self._labs.values()),
            order, self._customer, self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.record is None:
            return
        try:
            self._repository.save(dialog.record, (order or {}).get("id"))
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar o pedido", str(exc))
            return
        self._load()

    def _new(self) -> None:
        if not self._customers:
            QMessageBox.information(self, "Sem clientes", "Cadastre o cliente antes de criar o pedido.")
            return
        self._open_editor(None)

    def _edit(self) -> None:
        order = self._selected()
        if order is not None:
            self._open_editor(order)

    def _timeline(self) -> None:
        order = self._selected()
        if order is None:
            return
        customer = self._customers.get(str(order.get("customer_id")), {})
        OrderTimelineDialog(self._repository, order, str(customer.get("full_name") or "Cliente"), self).exec()
        self._load()

    def _cancel(self) -> None:
        order = self._selected()
        if order is None:
            return
        answer = QMessageBox.question(
            self, "Cancelar pedido",
            f"Cancelar o pedido {order.get('order_number') or ''}? O histórico será mantido.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._apply_status(order, "cancelado")
