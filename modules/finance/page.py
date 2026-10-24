"""Finance module: cash flow, payables, receivables and period-based sales."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


TYPES = {"Entrada": "entrada", "Saída": "saida"}
STATUSES = {"Pendente": "pendente", "Pago/Recebido": "pago", "Cancelado": "cancelado"}
METHODS = ["Não definido", "Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência", "Boleto", "Outro"]


def _money(value: Any) -> str:
    amount = Decimal(str(value or 0))
    return ("R$ {:,.2f}".format(amount)).replace(",", "X").replace(".", ",").replace("X", ".")


def _date(value: Any) -> str:
    return str(value or "")[:10]


class FinancialEntryDialog(QDialog):
    def __init__(self, entry: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry or {}
        self.setWindowTitle("Editar lançamento financeiro" if entry else "Novo lançamento financeiro")
        self.setMinimumSize(560, 560)
        self.resize(620, 640)
        root = QVBoxLayout(self)
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
        self.amount = QDoubleSpinBox()
        self.amount.setDecimals(2)
        self.amount.setMaximum(999999999.99)
        self.amount.setMinimum(0.01)
        self.amount.setPrefix("R$ ")
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("dd/MM/yyyy")
        self.due_date.setDate(QDate.currentDate())
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
            self.amount.setValue(float(entry.get("amount") or 0.01))
            due = QDate.fromString(_date(entry.get("due_date")), "yyyy-MM-dd")
            if due.isValid():
                self.due_date.setDate(due)
            self.status.setCurrentText({"pendente": "Pendente", "pago": "Pago/Recebido", "cancelado": "Cancelado"}.get(str(entry.get("status")), "Pendente"))
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
        direction_label = self.direction.currentText()
        status = {"Pendente": "pendente", "Pago/Recebido": "pago", "Cancelado": "cancelado"}[self.status.currentText()]
        return {
            "direction": TYPES[direction_label],
            "category": self.category.currentText().strip() or "Outros",
            "description": self.description.text().strip(),
            "amount": round(self.amount.value(), 2),
            "due_date": self.due_date.date().toString("yyyy-MM-dd"),
            "status": status,
            "paid_at": date.today().isoformat() if status == "pago" else None,
            "payment_method": "" if self.method.currentText() == "Não definido" else self.method.currentText(),
            "counterparty": self.counterparty.text().strip(),
            "reference": self.reference.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class FinancePage(QDialog):
    """Organization-scoped finance workspace backed by Supabase."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Financeiro — Ótica Linda Fashion")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet("""
            QDialog { background:#F3F5F8; color:#24334B; font-family:"Arial"; font-size:10pt; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
            QLabel#muted { color:#7184A1; }
            QLabel#metric { background:#FFFFFF; color:#17365D; border:1px solid #DFE7F3; border-radius:12px; padding:14px; font-size:10pt; font-weight:700; }
            QLabel#incomeMetric { background:#F0FBF5; color:#167447; border:1px solid #BFE8D1; border-left:5px solid #21A366; border-radius:12px; padding:14px; font-size:10pt; font-weight:700; }
            QLabel#expenseMetric { background:#FFF3F2; color:#B42318; border:1px solid #F5CBC7; border-left:5px solid #E5484D; border-radius:12px; padding:14px; font-size:10pt; font-weight:700; }
            QLabel#balanceMetric { background:#F0F5FF; color:#244BAA; border:1px solid #D5E2FF; border-left:5px solid #3973E6; border-radius:12px; padding:14px; font-size:10pt; font-weight:700; }
            QLabel#pendingMetric { background:#FFF9E9; color:#8A5A00; border:1px solid #F2E2B5; border-left:5px solid #E8AB28; border-radius:12px; padding:14px; font-size:10pt; font-weight:700; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit, QTimeEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
                background:#FFFFFF; color:#172B4D; border:1px solid #CFD9E8;
                border-radius:8px; padding:8px 10px; min-height:20px;
                selection-background-color:#315FE8; selection-color:#FFFFFF;
            }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 13px; font-weight:650; }
            QPushButton:hover { background:#F0F5FF; }
            QPushButton#primaryButton { background:#245DE0; color:#FFFFFF; border:1px solid #245DE0; font-weight:750; }
            QTableWidget { background:#FFFFFF; alternate-background-color:#F7F9FD; border:1px solid #E0E8F4; gridline-color:#EDF1F7; selection-background-color:#E8F0FF; selection-color:#102957; }
            QHeaderView::section { background:#102957; color:#FFFFFF; border:none; border-right:1px solid #28456F; padding:11px 8px; min-height:22px; font-weight:700; }
            QTabWidget::pane { border:1px solid #DFE7F3; background:#FFFFFF; border-radius:10px; }
            QTabBar { background:transparent; }
            QTabBar::tab { background:#EAF0F9; color:#526782; padding:10px 18px; margin-right:4px; border:1px solid #DCE5F5; border-top-left-radius:7px; border-top-right-radius:7px; }
            QTabBar::tab:hover { background:#DCE7F8; color:#244BAA; }
            QTabBar::tab:selected { background:#245DE0; color:#FFFFFF; border-color:#245DE0; font-weight:750; }
            QTabBar::tab:!selected { margin-top:2px; }
        """)
        self._client = None
        self._organization_id: str | None = None
        self._entries: list[dict[str, Any]] = []
        if not preview_mode:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O módulo Financeiro exige login e configuração do Supabase.")
            self._client = get_supabase_client()
            session = session_manager.current
            memberships = self._client.table("organization_members").select("organization_id").eq("user_id", session.user_id).eq("active", True).limit(1).execute().data or []
            if not memberships:
                raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
            self._organization_id = str(memberships[0]["organization_id"])

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
        subtitle = QLabel("Fluxo de caixa, contas a pagar e receber e vendas por período.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addWidget(title_bar, 1)
        self.new_button = QPushButton("+ Novo lançamento")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new_entry)
        header.addWidget(self.new_button)
        root.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.period = QComboBox()
        self.period.addItems(["Este mês", "Últimos 7 dias", "Últimos 30 dias", "Este ano", "Todo o período"])
        self.period.setMinimumWidth(165)
        self.period.setToolTip("Filtra indicadores e tabelas pelo período selecionado.")
        self.period.currentIndexChanged.connect(self._render)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar descrição, categoria, cliente ou referência…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render)
        filters.addWidget(QLabel("Período"))
        filters.addWidget(self.period)
        filters.addWidget(self.search, 1)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._load)
        filters.addWidget(self.refresh_button)
        root.addLayout(filters)

        dashboard_label = QLabel("Visão geral")
        dashboard_label.setStyleSheet("color:#17365D;font-size:12pt;font-weight:750;padding:2px 0;")
        root.addWidget(dashboard_label)
        metrics = QHBoxLayout()
        self.income_metric = QLabel("Entradas no período\nR$ 0,00")
        self.income_metric.setObjectName("incomeMetric")
        self.expense_metric = QLabel("Saídas no período\nR$ 0,00")
        self.expense_metric.setObjectName("expenseMetric")
        self.balance_metric = QLabel("Saldo do período\nR$ 0,00")
        self.balance_metric.setObjectName("balanceMetric")
        self.pending_metric = QLabel("Em aberto\nR$ 0,00")
        self.pending_metric.setObjectName("pendingMetric")
        for label in (self.income_metric, self.expense_metric, self.balance_metric, self.pending_metric):
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            label.setMinimumHeight(68)
            metrics.addWidget(label, 1)
        root.addLayout(metrics)

        self.tabs = QTabWidget()
        self.cash_table = self._table(["Vencimento", "Tipo", "Descrição", "Categoria", "Cliente / fornecedor", "Valor", "Situação", "Forma", "Referência"])
        self.payables_table = self._table(["Vencimento", "Descrição", "Fornecedor / favorecido", "Categoria", "Valor", "Situação"])
        self.receivables_table = self._table(["Vencimento", "Descrição", "Cliente", "Categoria", "Valor", "Situação"])
        self.sales_table = self._table(["Data", "Venda / descrição", "Cliente", "Forma de pagamento", "Valor", "Situação", "Referência"])
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
        self.edit_button = QPushButton("Editar lançamento")
        self.edit_button.clicked.connect(self._edit_selected)
        self.settle_button = QPushButton("Marcar como pago/recebido")
        self.settle_button.clicked.connect(self._settle_selected)
        self.cancel_button = QPushButton("Cancelar lançamento")
        self.cancel_button.clicked.connect(self._cancel_selected)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.settle_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        root.addLayout(actions)
        if preview_mode:
            note = QLabel("PRÉ-VISUALIZAÇÃO • lançamentos financeiros reais exigem Supabase configurado e usuário autenticado.")
            note.setWordWrap(True)
            note.setStyleSheet("background:#FFF7DF;color:#79550B;padding:10px;border-radius:8px;")
            root.addWidget(note)
            for button in (self.new_button, self.edit_button, self.settle_button, self.cancel_button):
                button.setEnabled(False)
            self._entries = self._preview_entries()
            self._render()
        else:
            self._load()

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.horizontalHeader().setStretchLastSection(True)
        table.setWordWrap(False)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        return table

    @staticmethod
    def _preview_entries() -> list[dict[str, Any]]:
        today = date.today()
        return [
            {"id": "demo-1", "direction": "entrada", "category": "Venda", "description": "Venda de armação premium", "amount": 489.90, "due_date": today.isoformat(), "status": "pago", "payment_method": "Pix", "counterparty": "Cliente demonstração", "reference": "VEN-0001", "notes": "", "paid_at": today.isoformat()},
            {"id": "demo-2", "direction": "saida", "category": "Fornecedor", "description": "Reposição de armações", "amount": 1250.00, "due_date": (today + timedelta(days=3)).isoformat(), "status": "pendente", "payment_method": "Boleto", "counterparty": "Fornecedor demonstração", "reference": "CP-0001", "notes": "", "paid_at": None},
            {"id": "demo-3", "direction": "entrada", "category": "Venda", "description": "Venda de lentes", "amount": 799.00, "due_date": (today - timedelta(days=5)).isoformat(), "status": "pago", "payment_method": "Cartão de crédito", "counterparty": "Cliente demonstração", "reference": "VEN-0002", "notes": "", "paid_at": today.isoformat()},
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

    def _period_bounds(self) -> tuple[date | None, date | None]:
        today = date.today()
        choice = self.period.currentText()
        if choice == "Este mês":
            return today.replace(day=1), today
        if choice == "Últimos 7 dias":
            return today - timedelta(days=6), today
        if choice == "Últimos 30 dias":
            return today - timedelta(days=29), today
        if choice == "Este ano":
            return today.replace(month=1, day=1), today
        return None, None

    def _filtered(self) -> list[dict[str, Any]]:
        start, end = self._period_bounds()
        term = self.search.text().strip().casefold()
        result = []
        for entry in self._entries:
            due = _date(entry.get("paid_at") if entry.get("status") == "pago" else entry.get("due_date"))
            if start and due:
                try:
                    parsed = date.fromisoformat(due)
                except ValueError:
                    continue
                if parsed < start or parsed > end:
                    continue
            if term and not any(term in str(entry.get(key) or "").casefold() for key in ("description", "category", "counterparty", "reference")):
                continue
            result.append(entry)
        return result

    def _render(self, *_args: object) -> None:
        entries = self._filtered()
        paid_income = sum(float(e.get("amount") or 0) for e in entries if e.get("direction") == "entrada" and e.get("status") == "pago")
        paid_expense = sum(float(e.get("amount") or 0) for e in entries if e.get("direction") == "saida" and e.get("status") == "pago")
        open_total = sum(float(e.get("amount") or 0) for e in entries if e.get("status") == "pendente")
        self.income_metric.setText(f"Entradas recebidas\n{_money(paid_income)}")
        self.expense_metric.setText(f"Saídas pagas\n{_money(paid_expense)}")
        self.balance_metric.setText(f"Saldo realizado\n{_money(paid_income - paid_expense)}")
        self.pending_metric.setText(f"Em aberto\n{_money(open_total)}")
        self._populate(self.cash_table, entries, ["due_date", "direction", "description", "category", "counterparty", "amount", "status", "payment_method", "reference"])
        self._populate(self.payables_table, [e for e in entries if e.get("direction") == "saida"], ["due_date", "description", "counterparty", "category", "amount", "status"])
        self._populate(self.receivables_table, [e for e in entries if e.get("direction") == "entrada" and e.get("status") != "pago"], ["due_date", "description", "counterparty", "category", "amount", "status"])
        self._populate(self.sales_table, [e for e in entries if e.get("direction") == "entrada" and str(e.get("category") or "").casefold() == "venda"], ["due_date", "description", "counterparty", "payment_method", "amount", "status", "reference"])

    @staticmethod
    def _bold_font():
        from PySide6.QtGui import QFont
        font = QFont()
        font.setBold(True)
        return font

    def _populate(self, table: QTableWidget, rows: list[dict[str, Any]], fields: list[str]) -> None:
        table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            for column, field in enumerate(fields):
                if field == "due_date":
                    value = _date(entry.get(field)) or "—"
                elif field == "direction":
                    value = "Entrada" if entry.get(field) == "entrada" else "Saída"
                elif field == "amount":
                    value = _money(entry.get(field))
                elif field == "status":
                    value = {"pendente": "Pendente", "pago": "Pago/Recebido", "cancelado": "Cancelado"}.get(str(entry.get(field)), str(entry.get(field) or "—"))
                    if entry.get("status") == "pendente" and _date(entry.get("due_date")) and _date(entry.get("due_date")) < date.today().isoformat():
                        value = "Atrasado"
                elif field == "payment_method":
                    value = entry.get(field) or "—"
                else:
                    value = str(entry.get(field) or "—")
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
                if field == "amount":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                # Apply restrained semantic colors to reinforce income and expense meaning.
                is_receivable = table is self.receivables_table
                is_payable = table is self.payables_table
                is_income = entry.get("direction") == "entrada"
                if field == "amount":
                    if is_receivable or (not is_payable and is_income):
                        item.setForeground(Qt.GlobalColor.darkGreen)
                        item.setFont(self._bold_font())
                    elif is_payable or (table is self.cash_table and not is_income):
                        item.setForeground(Qt.GlobalColor.red)
                        item.setFont(self._bold_font())
                if field == "status":
                    if entry.get("status") == "pago":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    elif value == "Atrasado":
                        item.setForeground(Qt.GlobalColor.red)
                    elif entry.get("status") == "pendente":
                        item.setForeground(Qt.GlobalColor.darkYellow)
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _selected_entry(self) -> dict[str, Any] | None:
        table = [self.cash_table, self.payables_table, self.receivables_table, self.sales_table][self.tabs.currentIndex()]
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Selecione um lançamento", "Selecione um registro na tabela.")
            return None
        entry_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for entry in self._filtered():
            if str(entry.get("id")) == str(entry_id):
                return entry
        return None

    def _edit_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if self._preview_mode:
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
            if not result.data:
                # PostgREST may omit representations depending on client configuration; reload confirms persistence.
                self._load()
                if any(e.get("description") == record["description"] and float(e.get("amount") or 0) == record["amount"] for e in self._entries):
                    QMessageBox.information(self, "Lançamento salvo", "O lançamento foi registrado.")
                    return
                raise RuntimeError("O Supabase não confirmou o novo lançamento.")
            self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar lançamento", str(exc))

    def _settle_selected(self) -> None:
        entry = self._selected_entry()
        if not entry or self._preview_mode:
            return
        if entry.get("status") == "pago":
            QMessageBox.information(self, "Já liquidado", "Este lançamento já está marcado como pago/recebido.")
            return
        try:
            result = self._client.table("financial_entries").update({"status": "pago", "paid_at": date.today().isoformat()}).eq("id", entry["id"]).eq("organization_id", self._organization_id).execute()
            if not result.data:
                self._load()
            else:
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
