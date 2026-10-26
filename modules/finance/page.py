"""Finance module: cash flow, payables, receivables, period-based sales and accountant reports."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QRadioButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from core.session_manager import session_manager
from modules.finance import reports
from modules.settings.service import load_store_settings, store_display_name
from ui.components.calendar import make_date_edit
from ui.components.money import MoneyEdit
from ui.components.ui_kit import MetricTile, make_button, notice
import qtawesome as qta


TYPES = {"Entrada": "entrada", "Saída": "saida"}
STATUSES = {"Pendente": "pendente", "Pago/Recebido": "pago", "Cancelado": "cancelado"}
METHODS = ["Não definido", "Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência", "Boleto", "Outro"]
SALES_CATEGORIES = ("venda", "vendas")


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _bold() -> QFont:
    font = QFont()
    font.setBold(True)
    return font


class FinancialEntryDialog(QDialog):
    def __init__(self, entry: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry or {}
        self.setWindowTitle("Editar lançamento financeiro" if entry else "Novo lançamento financeiro")
        self.setMinimumSize(560, 560)
        self.resize(620, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 12, 18, 12)
        title = QLabel("Lançamento financeiro")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Registre entradas, saídas, contas a pagar ou valores a receber.")
        subtitle.setObjectName("windowSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(4, 12, 4, 12)
        form.setSpacing(12)
        self.direction = QComboBox()
        self.direction.addItems(list(TYPES))
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(["Venda", "Produto", "Fornecedor", "Aluguel", "Energia", "Água", "Internet", "Salários", "Impostos", "Serviços", "Outros"])
        self.description = QLineEdit()
        self.description.setPlaceholderText("Ex.: venda de armação, pagamento fornecedor…")
        # Typed through the cents (1, 2, 5, 0 -> R$ 12,50): no default value left in front of the digits.
        self.amount = MoneyEdit()
        self.due_date = make_date_edit(QDate.currentDate())
        self.status = QComboBox()
        self.status.addItems(list(STATUSES))
        self.method = QComboBox()
        self.method.addItems(METHODS)
        self.counterparty = QLineEdit()
        self.counterparty.setPlaceholderText("Cliente, fornecedor ou beneficiário (opcional)")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Número de documento ou referência (opcional)")
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(90)
        for label, widget in [
            ("Tipo", self.direction), ("Categoria", self.category), ("Descrição *", self.description),
            ("Valor *", self.amount), ("Vencimento", self.due_date), ("Situação", self.status),
            ("Forma de pagamento", self.method), ("Cliente / fornecedor", self.counterparty),
            ("Referência", self.reference), ("Observações", self.notes),
        ]:
            form.addRow(label, widget)
        root.addWidget(form_host, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar lançamento")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        if entry:
            self.direction.setCurrentText("Entrada" if entry.get("direction") == "entrada" else "Saída")
            self.category.setCurrentText(str(entry.get("category") or "Outros"))
            self.description.setText(str(entry.get("description") or ""))
            self.amount.setValue(float(entry.get("amount") or 0))
            due = QDate.fromString(_date(entry.get("due_date")), "yyyy-MM-dd")
            if due.isValid():
                self.due_date.setDate(due)
            self.status.setCurrentText(reports.STATUS_LABELS.get(str(entry.get("status")), "Pendente"))
            self.method.setCurrentText(str(entry.get("payment_method") or "Não definido"))
            self.counterparty.setText(str(entry.get("counterparty") or ""))
            self.reference.setText(str(entry.get("reference") or ""))
            self.notes.setPlainText(str(entry.get("notes") or ""))

    def _validate(self) -> None:
        if not self.description.text().strip():
            QMessageBox.warning(self, "Descrição obrigatória", "Informe uma descrição para o lançamento.")
            self.description.setFocus()
            return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Valor inválido", "O valor deve ser maior que zero.")
            self.amount.setFocus()
            return
        self.accept()

    def record(self) -> dict[str, Any]:
        status = STATUSES[self.status.currentText()]
        return {
            "direction": TYPES[self.direction.currentText()],
            "category": self.category.currentText().strip() or "Outros",
            "description": self.description.text().strip(),
            "amount": round(self.amount.value(), 2),
            "due_date": self.due_date.date().toString("yyyy-MM-dd"),
            "status": status,
            # Keep the original settlement date when editing an entry that was already paid.
            "paid_at": (
                (_date(self._entry.get("paid_at")) or date.today().isoformat())
                if status == "pago" and self._entry.get("status") == "pago"
                else (date.today().isoformat() if status == "pago" else None)
            ),
            "payment_method": "" if self.method.currentText() == "Não definido" else self.method.currentText(),
            "counterparty": self.counterparty.text().strip(),
            "reference": self.reference.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class ReportExportDialog(QDialog):
    """Period and format for the accountant report."""

    def __init__(self, initial_period: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportar relatório financeiro")
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 12, 18, 12)
        title = QLabel("Relatório para a contabilidade")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Resumo, todos os lançamentos do período e o resultado por categoria.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)

        form = QFormLayout()
        form.setSpacing(12)
        self.period = QComboBox()
        self.period.addItems(list(reports.REPORT_PERIODS))
        self.period.setCurrentText(initial_period if initial_period in reports.REPORT_PERIODS else "Este mês")
        form.addRow("Período", self.period)
        range_row = QHBoxLayout()
        self.start = make_date_edit(QDate.currentDate().addDays(1 - QDate.currentDate().day()))
        self.end = make_date_edit(QDate.currentDate())
        range_row.addWidget(self.start, 1)
        range_row.addWidget(QLabel("até"))
        range_row.addWidget(self.end, 1)
        self.range_host = QWidget()
        self.range_host.setLayout(range_row)
        range_row.setContentsMargins(0, 0, 0, 0)
        form.addRow("De", self.range_host)
        self.range_hint = QLabel("")
        self.range_hint.setObjectName("muted")
        form.addRow("", self.range_hint)

        formats = QHBoxLayout()
        self.pdf = QRadioButton("PDF (para imprimir ou enviar)")
        self.xlsx = QRadioButton("Planilha Excel (.xlsx)")
        self.pdf.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.pdf)
        group.addButton(self.xlsx)
        formats.addWidget(self.pdf)
        formats.addWidget(self.xlsx)
        formats.addStretch(1)
        form.addRow("Formato", formats)
        self.include_cancelled = QCheckBox("Incluir lançamentos cancelados")
        form.addRow("", self.include_cancelled)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Gerar relatório")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.period.currentIndexChanged.connect(self._sync)
        self.start.dateChanged.connect(self._sync)
        self.end.dateChanged.connect(self._sync)
        self._sync()

    def bounds(self) -> tuple[date | None, date | None]:
        return reports.period_bounds(self.period.currentText(), custom_start=self.start.date().toPython(),
                                     custom_end=self.end.date().toPython())

    def _sync(self, *_args: object) -> None:
        custom = self.period.currentText() == "Personalizado"
        self.range_host.setEnabled(custom)
        start, end = self.bounds()
        if not custom and start and end:
            self.start.blockSignals(True)
            self.end.blockSignals(True)
            self.start.setDate(QDate(start.year, start.month, start.day))
            self.end.setDate(QDate(end.year, end.month, end.day))
            self.start.blockSignals(False)
            self.end.blockSignals(False)
        days = (end - start).days + 1 if start and end else 0
        self.range_hint.setText(f"{days} dia(s) no relatório." if days else "")

    def _validate(self) -> None:
        if self.start.date() > self.end.date():
            QMessageBox.warning(self, "Período inválido", "A data inicial deve ser anterior à data final.")
            return
        self.accept()

    def extension(self) -> str:
        return "xlsx" if self.xlsx.isChecked() else "pdf"


class FinancePage(QDialog):
    """Organization-scoped finance workspace backed by Supabase."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Financeiro — Ótica Linda Fashion")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("O módulo Financeiro")
        self._client = self._ctx.client if self._ctx else None
        self._organization_id: str | None = self._ctx.organization_id if self._ctx else None
        self._entries: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 13, 18, 13)
        title_layout.setSpacing(4)
        title = QLabel("Financeiro")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Fluxo de caixa, contas a pagar e receber, vendas por período e relatórios para a contabilidade.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addWidget(title_bar, 1)
        root.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        period_label = QLabel("Período")
        period_label.setObjectName("filterLabel")
        self.period = QComboBox()
        self.period.addItems(list(reports.PERIODS))
        self.period.setCurrentText("Este mês")
        self.period.setMinimumWidth(170)
        self.period.setToolTip("Filtra indicadores e tabelas. Pagos contam pela data do pagamento; em aberto, pelo vencimento.")
        self.period.currentIndexChanged.connect(self._period_changed)
        self.custom_start = make_date_edit(QDate.currentDate().addDays(1 - QDate.currentDate().day()))
        self.custom_end = make_date_edit(QDate.currentDate())
        self.custom_until = QLabel("até")
        for widget in (self.custom_start, self.custom_end):
            widget.dateChanged.connect(self._render)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar descrição, categoria, cliente ou referência…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(qta.icon("fa5s.search", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._render)
        filters.addWidget(period_label)
        filters.addWidget(self.period)
        filters.addWidget(self.custom_start)
        filters.addWidget(self.custom_until)
        filters.addWidget(self.custom_end)
        filters.addWidget(self.search, 1)
        self.refresh_button = make_button("Atualizar", "fa5s.sync-alt", "secondaryButton")
        self.refresh_button.clicked.connect(self._load)
        filters.addWidget(self.refresh_button)
        self.export_button = make_button("Exportar relatório", "fa5s.file-export", "secondaryButton")
        self.export_button.setToolTip("Relatório por período em PDF ou planilha Excel para a contabilidade")
        self.export_button.clicked.connect(self._export_report)
        filters.addWidget(self.export_button)
        self.new_button = make_button("Novo lançamento", "fa5s.plus", "primaryButton")
        self.new_button.clicked.connect(self._new_entry)
        filters.addWidget(self.new_button)
        root.addLayout(filters)

        metrics = QHBoxLayout()
        metrics.setSpacing(14)
        self.income_metric = MetricTile("Entradas recebidas", "R$ 0,00", "fa5s.arrow-down", "success")
        self.expense_metric = MetricTile("Saídas pagas", "R$ 0,00", "fa5s.arrow-up", "danger")
        self.balance_metric = MetricTile("Saldo realizado", "R$ 0,00", "fa5s.balance-scale", "primary")
        self.pending_metric = MetricTile("Em aberto", "R$ 0,00", "fa5s.hourglass-half", "warning")
        for tile in (self.income_metric, self.expense_metric, self.balance_metric, self.pending_metric):
            metrics.addWidget(tile, 1)
        root.addLayout(metrics)

        # Same pattern in every tab: text columns share the free width, short columns fit their content.
        self.tabs = QTabWidget()
        self.cash_table = self._table(
            ["Data", "Tipo", "Descrição", "Categoria", "Cliente / fornecedor", "Valor", "Situação", "Forma", "Referência"],
            stretch=(2, 3, 4, 8))
        self.payables_table = self._table(
            ["Vencimento", "Descrição", "Fornecedor / favorecido", "Categoria", "Forma", "Valor", "Situação"],
            stretch=(1, 2, 3))
        self.receivables_table = self._table(
            ["Vencimento", "Descrição", "Cliente", "Categoria", "Forma", "Valor", "Situação"],
            stretch=(1, 2, 3))
        self.sales_table = self._table(
            ["Data", "Venda / descrição", "Cliente", "Forma de pagamento", "Valor", "Situação", "Referência"],
            stretch=(1, 2, 6))
        for table, tab_name in [
            (self.cash_table, "Entradas e saídas"),
            (self.payables_table, "Contas a pagar"),
            (self.receivables_table, "Contas a receber"),
            (self.sales_table, "Vendas por período"),
        ]:
            table.doubleClicked.connect(self._edit_selected)
            self.tabs.addTab(table, tab_name)
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        self.edit_button = make_button("Editar lançamento", "fa5s.pen", "secondaryButton")
        self.edit_button.clicked.connect(self._edit_selected)
        self.settle_button = make_button("Marcar como pago/recebido", "fa5s.check-circle", "secondaryButton")
        self.settle_button.clicked.connect(self._settle_selected)
        self.cancel_button = make_button("Cancelar lançamento", "fa5s.ban", "dangerButton")
        self.cancel_button.clicked.connect(self._cancel_selected)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.settle_button)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        root.addLayout(actions)
        self._period_changed()
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • lançamentos financeiros reais exigem Supabase configurado e usuário autenticado."))
            for button in (self.new_button, self.edit_button, self.settle_button, self.cancel_button):
                button.setEnabled(False)
            self._entries = self._preview_entries()
            self._render()
        else:
            self._load()

    @staticmethod
    def _table(headers: list[str], stretch: tuple[int, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setWordWrap(False)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(70)
        for column in range(len(headers)):
            mode = QHeaderView.ResizeMode.Stretch if column in stretch else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)
        return table

    @staticmethod
    def _preview_entries() -> list[dict[str, Any]]:
        today = date.today()
        return [
            {"id": "demo-1", "direction": "entrada", "category": "Vendas", "description": "Venda V-0001", "amount": 489.90, "due_date": today.isoformat(), "status": "pago", "payment_method": "Pix", "counterparty": "Cliente demonstração", "reference": "VEN-0001", "notes": "", "paid_at": today.isoformat(), "sales_order_id": "s1"},
            {"id": "demo-2", "direction": "saida", "category": "Fornecedor", "description": "Reposição de armações", "amount": 1250.00, "due_date": (today + timedelta(days=3)).isoformat(), "status": "pendente", "payment_method": "Boleto", "counterparty": "Fornecedor demonstração", "reference": "CP-0001", "notes": "", "paid_at": None},
            {"id": "demo-3", "direction": "entrada", "category": "Vendas", "description": "Venda V-0002 — parcela 2/3", "amount": 266.33, "due_date": (today + timedelta(days=12)).isoformat(), "status": "pendente", "payment_method": "Crediário", "counterparty": "Cliente demonstração", "reference": "VEN-0002", "notes": "", "paid_at": None, "sales_order_id": "s2"},
            {"id": "demo-4", "direction": "saida", "category": "Aluguel", "description": "Aluguel da loja", "amount": 2800.00, "due_date": (today - timedelta(days=2)).isoformat(), "status": "pendente", "payment_method": "Transferência", "counterparty": "Imobiliária", "reference": "", "notes": "", "paid_at": None},
        ]

    def _load(self) -> None:
        if self._client is None:
            self._render()
            return
        try:
            self._entries = list(self._client.table("financial_entries").select("*").eq("organization_id", self._organization_id).order("due_date", desc=True).execute().data or [])
            self._render()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar financeiro", f"{exc}\n\nConfirme se a migration 202610240006_finance_module.sql foi aplicada no Supabase.")

    def _period_changed(self, *_args: object) -> None:
        custom = self.period.currentText() == "Personalizado"
        for widget in (self.custom_start, self.custom_until, self.custom_end):
            widget.setVisible(custom)
        self._render()

    def _period_bounds(self) -> tuple[date | None, date | None]:
        return reports.period_bounds(self.period.currentText(), custom_start=self.custom_start.date().toPython(),
                                     custom_end=self.custom_end.date().toPython())

    def _filtered(self) -> list[dict[str, Any]]:
        start, end = self._period_bounds()
        term = self.search.text().strip().casefold()
        return [
            entry for entry in self._entries
            if reports.in_period(entry, start, end)
            and (not term or any(term in str(entry.get(key) or "").casefold() for key in ("description", "category", "counterparty", "reference")))
        ]

    def _render(self, *_args: object) -> None:
        if not hasattr(self, "sales_table"):
            return
        entries = self._filtered()
        paid_income = sum(float(e.get("amount") or 0) for e in entries if e.get("direction") == "entrada" and e.get("status") == "pago")
        paid_expense = sum(float(e.get("amount") or 0) for e in entries if e.get("direction") == "saida" and e.get("status") == "pago")
        open_total = sum(float(e.get("amount") or 0) for e in entries if e.get("status") == "pendente")
        self.income_metric.set_value(reports.money(paid_income))
        self.expense_metric.set_value(reports.money(paid_expense))
        self.balance_metric.set_value(reports.money(paid_income - paid_expense))
        self.pending_metric.set_value(reports.money(open_total))
        pending = [e for e in entries if e.get("status") == "pendente"]
        self._populate(self.cash_table, entries, ["entry_day", "direction", "description", "category", "counterparty", "amount", "status", "payment_method", "reference"])
        self._populate(self.payables_table, [e for e in pending if e.get("direction") == "saida"], ["due_date", "description", "counterparty", "category", "payment_method", "amount", "status"])
        self._populate(self.receivables_table, [e for e in pending if e.get("direction") == "entrada"], ["due_date", "description", "counterparty", "category", "payment_method", "amount", "status"])
        sales = [e for e in entries if e.get("direction") == "entrada"
                 and (e.get("sales_order_id") or str(e.get("category") or "").casefold() in SALES_CATEGORIES)]
        self._populate(self.sales_table, sales, ["entry_day", "description", "counterparty", "payment_method", "amount", "status", "reference"])

    def _populate(self, table: QTableWidget, rows: list[dict[str, Any]], fields: list[str]) -> None:
        table.setRowCount(len(rows))
        is_receivable = table is self.receivables_table
        is_payable = table is self.payables_table
        for row_index, entry in enumerate(rows):
            is_income = entry.get("direction") == "entrada"
            for column, field in enumerate(fields):
                if field == "entry_day":
                    day = reports.entry_day(entry)
                    value = day.strftime("%d/%m/%Y") if day else "—"
                elif field == "due_date":
                    value = reports.br_date(entry.get(field))
                elif field == "direction":
                    value = "Entrada" if is_income else "Saída"
                elif field == "amount":
                    value = reports.money(entry.get(field))
                elif field == "status":
                    value = reports.status_label(entry)
                else:
                    value = str(entry.get(field) or "—")
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
                if field == "amount":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if is_receivable or (not is_payable and is_income):
                        item.setForeground(QColor("#0E8A5B"))
                        item.setFont(_bold())
                    elif is_payable or not is_income:
                        item.setForeground(QColor("#C03030"))
                        item.setFont(_bold())
                if field == "status":
                    if entry.get("status") == "pago":
                        item.setForeground(QColor("#0E8A5B"))
                    elif value == "Atrasado":
                        item.setForeground(QColor("#C03030"))
                        item.setFont(_bold())
                    elif entry.get("status") == "pendente":
                        item.setForeground(QColor("#9A6200"))
                    elif entry.get("status") == "cancelado":
                        item.setForeground(QColor("#8A97AB"))
                table.setItem(row_index, column, item)

    def _current_table(self) -> QTableWidget:
        return [self.cash_table, self.payables_table, self.receivables_table, self.sales_table][self.tabs.currentIndex()]

    def _selected_entry(self) -> dict[str, Any] | None:
        table = self._current_table()
        row = table.currentRow()
        if row < 0 or table.item(row, 0) is None:
            QMessageBox.information(self, "Selecione um lançamento", "Selecione um registro na tabela.")
            return None
        entry_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((entry for entry in self._entries if str(entry.get("id")) == str(entry_id)), None)

    def _edit_selected(self) -> None:
        entry = self._selected_entry()
        if not entry or self._preview_mode:
            return
        dialog = FinancialEntryDialog(entry, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = self._client.table("financial_entries").update(dialog.record()).eq("id", entry["id"]).eq("organization_id", self._organization_id).execute()
            if not result.data:
                raise RuntimeError("Nenhuma linha foi alterada. Confira as permissões do usuário no Supabase.")
            self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao editar lançamento", str(exc))

    def _new_entry(self) -> None:
        if self._preview_mode:
            return
        dialog = FinancialEntryDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            record = dialog.record()
            record["organization_id"] = self._organization_id
            record["created_by"] = session_manager.current.user_id if session_manager.current else None
            result = self._client.table("financial_entries").insert(record).execute()
            self._load()
            if not result.data and not any(
                    e.get("description") == record["description"] and float(e.get("amount") or 0) == record["amount"] for e in self._entries):
                raise RuntimeError("O Supabase não confirmou o novo lançamento.")
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar lançamento", str(exc))

    def _settle_selected(self) -> None:
        entry = self._selected_entry()
        if not entry or self._preview_mode:
            return
        if entry.get("status") != "pendente":
            QMessageBox.information(self, "Lançamento não está em aberto",
                                    "Só lançamentos pendentes podem ser marcados como pagos/recebidos.")
            return
        try:
            self._client.table("financial_entries").update({"status": "pago", "paid_at": date.today().isoformat()}).eq("id", entry["id"]).eq("organization_id", self._organization_id).execute()
            self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao liquidar lançamento", str(exc))

    def _cancel_selected(self) -> None:
        entry = self._selected_entry()
        if not entry or self._preview_mode:
            return
        if entry.get("status") == "cancelado":
            return
        answer = QMessageBox.question(self, "Cancelar lançamento", f"Confirma o cancelamento de “{entry.get('description')}”?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.table("financial_entries").update({"status": "cancelado"}).eq("id", entry["id"]).eq("organization_id", self._organization_id).execute()
            self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao cancelar lançamento", str(exc))

    # ------------------------------------------------------------------ reports
    def _export_report(self) -> None:
        dialog = ReportExportDialog(self.period.currentText(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        start, end = dialog.bounds()
        store = store_display_name(self._ctx, load_store_settings(self._ctx)) if self._ctx else "Ótica Linda Fashion"
        report = reports.build_report(self._entries, store, dialog.period.currentText(), start, end,
                                      include_cancelled=dialog.include_cancelled.isChecked())
        extension = dialog.extension()
        documents = Path.home() / "Documents"
        suggested = str((documents if documents.is_dir() else Path.home()) / reports.default_filename(report, extension))
        filter_text = "Planilha Excel (*.xlsx)" if extension == "xlsx" else "Documento PDF (*.pdf)"
        path, _selected = QFileDialog.getSaveFileName(self, "Salvar relatório financeiro", suggested, filter_text)
        if not path:
            return
        if not path.lower().endswith(f".{extension}"):
            path += f".{extension}"
        try:
            (reports.export_xlsx if extension == "xlsx" else reports.export_pdf)(report, path)
        except PermissionError:
            QMessageBox.critical(self, "Arquivo em uso", "Feche o arquivo no Excel ou no leitor de PDF e tente novamente.")
            return
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao gerar relatório", str(exc))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Relatório gerado")
        box.setText(f"Relatório salvo com {len(report.rows)} lançamento(s) de {report.range_text}.")
        box.setInformativeText(path)
        open_button = box.addButton("Abrir arquivo", QMessageBox.ButtonRole.AcceptRole)
        folder_button = box.addButton("Abrir pasta", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Fechar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif box.clickedButton() is folder_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))
