"""Customer registry and first CRM foundation for Ótica Linda Fashion."""
from __future__ import annotations

from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


CUSTOMER_FIELDS = (
    "full_name", "document", "email", "phone", "whatsapp", "birth_date",
    "postal_code", "street", "address_number", "address_complement",
    "neighborhood", "city", "state", "notes", "marketing_email_consent",
    "whatsapp_consent", "active",
)


class CustomerFormDialog(QDialog):
    def __init__(self, customer: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar cliente" if customer else "Novo cliente")
        self.setMinimumSize(760, 620)
        self.resize(900, 720)
        self._customer = customer or {}
        self.fields: dict[str, QWidget] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 13, 18, 13)
        title_layout.setSpacing(4)
        title = QLabel("Cadastro do cliente")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Centralize os dados de contato e as preferências de comunicação do cliente.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        groups = [
            ("Identificação", [
                ("full_name", "Nome completo *"), ("document", "CPF"),
                ("birth_date", "Data de nascimento"),
            ]),
            ("Contato", [
                ("email", "E-mail"), ("phone", "Telefone"), ("whatsapp", "WhatsApp"),
            ]),
            ("Endereço", [
                ("postal_code", "CEP"), ("street", "Logradouro"),
                ("address_number", "Número"), ("address_complement", "Complemento"),
                ("neighborhood", "Bairro"), ("city", "Cidade"), ("state", "UF"),
            ]),
        ]
        for tab_name, fields in groups:
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(18, 18, 18, 18)
            form.setSpacing(12)
            for key, label_text in fields:
                if key == "birth_date":
                    widget = QDateEdit()
                    widget.setCalendarPopup(True)
                    widget.setDisplayFormat("dd/MM/yyyy")
                    widget.setSpecialValueText("Não informado")
                    widget.setDate(widget.minimumDate())
                    raw = self._customer.get(key)
                    if raw:
                        widget.setDate(date.fromisoformat(str(raw)[:10]))
                    else:
                        widget.setDate(widget.minimumDate())
                else:
                    widget = QLineEdit()
                    widget.setClearButtonEnabled(True)
                    widget.setPlaceholderText(label_text)
                    widget.setText(str(self._customer.get(key) or ""))
                widget.setMinimumHeight(38)
                self.fields[key] = widget
                form.addRow(label_text, widget)
            tabs.addTab(page, tab_name)

        crm_page = QWidget()
        crm_form = QFormLayout(crm_page)
        crm_form.setContentsMargins(18, 18, 18, 18)
        crm_form.setSpacing(12)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Preferências, observações e histórico relevante...")
        self.notes.setPlainText(str(self._customer.get("notes") or ""))
        self.notes.setMaximumHeight(130)
        crm_form.addRow("Observações internas", self.notes)
        self.email_consent = QCheckBox("Autorizou receber e-mail marketing")
        self.email_consent.setChecked(bool(self._customer.get("marketing_email_consent", False)))
        self.whatsapp_consent = QCheckBox("Autorizou contato pelo WhatsApp")
        self.whatsapp_consent.setChecked(bool(self._customer.get("whatsapp_consent", False)))
        self.active = QCheckBox("Cliente ativo")
        self.active.setChecked(bool(self._customer.get("active", True)))
        crm_form.addRow(self.email_consent)
        crm_form.addRow(self.whatsapp_consent)
        crm_form.addRow(self.active)
        tabs.addTab(crm_page, "CRM e permissões")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar cliente")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
                        QLineEdit, QDateEdit, QTextEdit {
                background:#FFFFFF; color:#102957; border:1px solid #D9E3F1;
                border-radius:8px; padding:8px;
                selection-background-color:#2165F5; selection-color:#FFFFFF;
            }
            QLineEdit:focus, QDateEdit:focus, QTextEdit:focus { border:1px solid #2165F5; }
            QTabWidget::pane { border:1px solid #E4EAF5; border-radius:8px; }
            QTabBar::tab { background:#FFFFFF; color:#4B5675; padding:10px 16px; border:1px solid #E4EAF5; }
            QTabBar::tab:selected { color:#FFFFFF; background:#2165F5; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 14px; }
            QPushButton:hover { background:#F3F7FF; }
            QCheckBox { spacing:8px; padding:5px; }
        """)

    def _validate(self) -> None:
        name = self.fields["full_name"].text().strip()
        if not name:
            QMessageBox.warning(self, "Campo obrigatório", "Informe o nome completo do cliente.")
            self.fields["full_name"].setFocus()
            return
        email = self.fields["email"].text().strip()
        if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
            QMessageBox.warning(self, "E-mail inválido", "Confira o endereço de e-mail informado.")
            self.fields["email"].setFocus()
            return
        self.accept()

    def record(self) -> dict:
        record: dict = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QDateEdit):
                record[key] = widget.date().toString("yyyy-MM-dd") if widget.date() > widget.minimumDate() else None
            elif isinstance(widget, QLineEdit):
                record[key] = widget.text().strip()
        record["notes"] = self.notes.toPlainText().strip()
        record["marketing_email_consent"] = self.email_consent.isChecked()
        record["whatsapp_consent"] = self.whatsapp_consent.isChecked()
        record["active"] = self.active.isChecked()
        return record


class CustomersPage(QDialog):
    """Organization-scoped customer CRUD with an initial CRM interaction timeline."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Clientes e CRM — Ótica Linda Fashion")
        self.resize(1200, 780)
        self.setMinimumSize(960, 640)
        self._client = None
        self._organization_id: str | None = None
        self._user_id: str | None = None
        self._rows: list[dict] = []
        if not preview_mode:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O módulo Clientes exige login e configuração do Supabase.")
            self._client = get_supabase_client()
            session = session_manager.current
            self._user_id = session.user_id
            memberships = (
                self._client.table("organization_members")
                .select("organization_id").eq("user_id", session.user_id)
                .eq("active", True).limit(1).execute().data or []
            )
            if not memberships:
                raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
            self._organization_id = str(memberships[0]["organization_id"])

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        heading = QVBoxLayout(title_bar)
        heading.setContentsMargins(18, 13, 18, 13)
        heading.setSpacing(4)
        title = QLabel("Clientes")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Cadastro, relacionamento e base para campanhas e follow-ups.")
        subtitle.setObjectName("windowSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addWidget(title_bar, 1)
        self.new_button = QPushButton("+ Novo cliente")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new_customer)
        header.addWidget(self.new_button)
        root.addLayout(header)

        metrics = QHBoxLayout()
        self.total_label = QLabel("0 clientes")
        self.email_label = QLabel("0 com e-mail autorizado")
        self.whatsapp_label = QLabel("0 com WhatsApp autorizado")
        for item in (self.total_label, self.email_label, self.whatsapp_label):
            item.setStyleSheet("background:#FFFFFF;border:1px solid #E4EAF5;border-radius:9px;padding:12px;color:#102957;font-weight:650;")
            metrics.addWidget(item)
        root.addLayout(metrics)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nome, CPF, e-mail ou telefone...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render_rows)
        filters.addWidget(self.search, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Todos os clientes", "Ativos", "Inativos"])
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        filters.addWidget(self.status_filter)
        root.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Cliente", "Telefone / WhatsApp", "E-mail", "Consentimentos", "Situação", "Ações"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._edit_selected)
        root.addWidget(self.table, 1)

        crm_actions = QHBoxLayout()
        self.orders_button = QPushButton("Pedidos e status")
        self.orders_button.clicked.connect(self._manage_orders)
        crm_actions.addWidget(self.orders_button)
        self.history_button = QPushButton("Ver histórico CRM")
        self.history_button.clicked.connect(self._view_interactions)
        crm_actions.addWidget(self.history_button)
        self.whatsapp_templates_button = QPushButton("Mensagens automáticas WhatsApp")
        self.whatsapp_templates_button.clicked.connect(self._manage_whatsapp_templates)
        crm_actions.addWidget(self.whatsapp_templates_button)
        self.crm_button = QPushButton("Registrar interação / follow-up")
        self.crm_button.setObjectName("primaryButton")
        self.crm_button.clicked.connect(self._add_interaction)
        crm_actions.addWidget(self.crm_button)
        root.addLayout(crm_actions)
        self.setStyleSheet("""
            QDialog { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; font-size:10pt; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
                        QLineEdit, QComboBox { background:#FFFFFF; color:#102957; border:1px solid #D9E3F1; border-radius:8px; padding:9px; min-height:22px; }
            QLineEdit:focus, QComboBox:focus { border:1px solid #2165F5; }
            QTableWidget { background:#FFFFFF; alternate-background-color:#F7F9FD; border:1px solid #E0E8F4; gridline-color:#EDF1F7; selection-background-color:#E8F0FF; selection-color:#102957; }
            QHeaderView::section { background:#102957; color:#FFFFFF; border:none; padding:10px; font-weight:700; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 13px; font-weight:650; }
            QPushButton:hover { background:#F3F7FF; }
            QPushButton#primaryButton { background:#2165F5; color:#FFFFFF; border:1px solid #2165F5; }
        """)
        self._load_customers()

    def _load_customers(self) -> None:
        if self._preview_mode:
            self._rows = [
                {"id":"demo-1","full_name":"Mariana Costa","document":"","email":"mariana@example.com","phone":"(82) 99999-1234","whatsapp":"(82) 99999-1234","active":True,"marketing_email_consent":True,"whatsapp_consent":False,"notes":""},
                {"id":"demo-2","full_name":"João Santos","document":"","email":"joao@example.com","phone":"(82) 98888-4321","whatsapp":"(82) 98888-4321","active":True,"marketing_email_consent":False,"whatsapp_consent":True,"notes":""},
            ]
        else:
            try:
                self._rows = (
                    self._client.table("customers").select("*")
                    .eq("organization_id", self._organization_id)
                    .order("full_name").execute().data or []
                )
            except Exception as exc:
                QMessageBox.critical(self, "Falha ao carregar clientes", f"Não foi possível carregar os clientes.\n\n{exc}")
                self._rows = []
        self._render_rows()

    def _render_rows(self) -> None:
        query = self.search.text().strip().casefold()
        status = self.status_filter.currentText() if hasattr(self, "status_filter") else "Todos os clientes"
        filtered = []
        for row in self._rows:
            haystack = " ".join(str(row.get(k) or "") for k in ("full_name","document","email","phone","whatsapp")).casefold()
            if query and query not in haystack:
                continue
            if status == "Ativos" and not row.get("active", True):
                continue
            if status == "Inativos" and row.get("active", True):
                continue
            filtered.append(row)
        self.table.setRowCount(len(filtered))
        for row_index, record in enumerate(filtered):
            values = [
                record.get("full_name", ""),
                " / ".join(filter(None, [record.get("phone", ""), record.get("whatsapp", "")])),
                record.get("email", ""),
                "E-mail ✓" if record.get("marketing_email_consent") else "E-mail —",
                "Ativo" if record.get("active", True) else "Inativo",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
                self.table.setItem(row_index, col, item)
            action = QPushButton("Editar")
            action.clicked.connect(lambda checked=False, item=record: self._edit_customer(item))
            self.table.setCellWidget(row_index, 5, action)
        total = len(self._rows)
        email_count = sum(bool(row.get("marketing_email_consent") and row.get("email")) for row in self._rows)
        whatsapp_count = sum(bool(row.get("whatsapp_consent") and row.get("whatsapp")) for row in self._rows)
        self.total_label.setText(f"{total} clientes cadastrados")
        self.email_label.setText(f"{email_count} com e-mail autorizado")
        self.whatsapp_label.setText(f"{whatsapp_count} com WhatsApp autorizado")

    def _selected_customer(self) -> dict | None:
        row_index = self.table.currentRow()
        if row_index < 0:
            return None
        customer_id = self.table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
        return next((row for row in self._rows if row.get("id") == customer_id), None)

    def _new_customer(self) -> None:
        dialog = CustomerFormDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_customer(dialog.record())

    def _edit_selected(self) -> None:
        customer = self._selected_customer()
        if customer:
            self._edit_customer(customer)

    def _edit_customer(self, customer: dict) -> None:
        dialog = CustomerFormDialog(customer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_customer(dialog.record(), customer.get("id"))

    def _save_customer(self, record: dict, customer_id: str | None = None) -> None:
        if self._preview_mode:
            QMessageBox.information(self, "Modo de pré-visualização", "O modo de pré-visualização não persiste alterações. Entre no sistema para salvar clientes.")
            return
        payload = {**record, "organization_id": self._organization_id}
        try:
            if customer_id:
                self._client.table("customers").update(payload).eq("id", customer_id).eq("organization_id", self._organization_id).execute()
            else:
                self._client.table("customers").insert(payload).execute()
            self._load_customers()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar cliente", f"Não foi possível salvar o cadastro.\n\n{exc}")

    def _manage_orders(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente para consultar ou cadastrar pedidos.")
            return
        if self._preview_mode:
            QMessageBox.information(self, "Pedidos demonstrativos", "O acompanhamento de pedidos exige uma sessão autenticada para salvar dados.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Pedidos — {customer.get('full_name', 'Cliente')}")
        dialog.resize(900, 560)
        layout = QVBoxLayout(dialog)
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 12, 18, 12)
        title = QLabel(f"Pedidos de {customer.get('full_name', 'Cliente')}")
        title.setObjectName("windowTitle")
        title_layout.addWidget(title)
        layout.addWidget(title_bar)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Nº pedido", "Descrição", "Status", "Previsão", "Criado em"])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table, 1)
        form = QFormLayout()
        number = QLineEdit()
        number.setPlaceholderText("Ex.: OC-2026-001 (opcional)")
        description = QLineEdit()
        description.setPlaceholderText("Ex.: Armação + lentes multifocais")
        status = QComboBox()
        status.addItem("Em desenvolvimento", "em_desenvolvimento")
        status.addItem("Óculos pronto", "pronto")
        status.addItem("Entregue", "entregue")
        status.addItem("Cancelado", "cancelado")
        expected = QDateEdit()
        expected.setCalendarPopup(True)
        expected.setDisplayFormat("dd/MM/yyyy")
        expected.setDate(date.today())
        notes = QTextEdit()
        notes.setPlaceholderText("Observações do pedido...")
        notes.setMaximumHeight(70)
        form.addRow("Número", number)
        form.addRow("Descrição *", description)
        form.addRow("Status", status)
        form.addRow("Previsão", expected)
        form.addRow("Observações", notes)
        layout.addLayout(form)
        actions = QHBoxLayout()
        refresh_button = QPushButton("Atualizar lista")
        update_status_button = QPushButton("Alterar status selecionado")
        history_button = QPushButton("Histórico de status")
        save_button = QPushButton("Cadastrar pedido")
        save_button.setObjectName("primaryButton")
        actions.addWidget(refresh_button)
        actions.addWidget(update_status_button)
        actions.addWidget(history_button)
        actions.addStretch(1)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        status_labels = {"em_desenvolvimento":"Em desenvolvimento","pronto":"Óculos pronto","entregue":"Entregue","cancelado":"Cancelado"}

        def load_orders() -> None:
            try:
                rows = self._client.table("customer_orders").select(
                    "id,order_number,description,status,expected_at,created_at"
                ).eq("organization_id", self._organization_id).eq(
                    "customer_id", customer["id"]
                ).order("created_at", desc=True).execute().data or []
            except Exception as exc:
                QMessageBox.critical(dialog, "Erro ao carregar pedidos", f"Não foi possível carregar os pedidos.\\n\\n{exc}")
                return
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                values = [
                    row.get("order_number") or "—", row.get("description") or "",
                    status_labels.get(row.get("status", ""), row.get("status", "")),
                    row.get("expected_at") or "—", str(row.get("created_at") or "")[:10],
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if column == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                    table.setItem(index, column, cell)

        def update_order_status() -> None:
            row_index = table.currentRow()
            if row_index < 0 or table.item(row_index, 0) is None:
                QMessageBox.information(dialog, "Selecione um pedido", "Selecione um pedido na lista para alterar seu status.")
                return
            order_id = table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
            choices = ["Em desenvolvimento", "Óculos pronto", "Entregue", "Cancelado"]
            values = ["em_desenvolvimento", "pronto", "entregue", "cancelado"]
            selected, accepted = QInputDialog.getItem(dialog, "Atualizar status", "Novo status:", choices, 0, False)
            if not accepted:
                return
            new_status = values[choices.index(selected)]
            try:
                current_rows = self._client.table("customer_orders").select(
                    "status"
                ).eq("id", order_id).eq("organization_id", self._organization_id).eq(
                    "customer_id", customer["id"]
                ).limit(1).execute().data or []
                if not current_rows:
                    QMessageBox.warning(dialog, "Pedido não encontrado", "O pedido não foi localizado nesta organização.")
                    return
                previous_status = str(current_rows[0].get("status") or "")
                if previous_status == new_status:
                    QMessageBox.information(dialog, "Sem alteração", "O pedido já está com esse status.")
                    return
                now = __import__("datetime").datetime.now().astimezone().isoformat()
                payload = {"status": new_status, "updated_at": now}
                if new_status == "pronto":
                    payload["completed_at"] = now
                elif new_status == "entregue":
                    payload["delivered_at"] = now
                self._client.table("customer_orders").update(payload).eq("id", order_id).eq(
                    "organization_id", self._organization_id
                ).eq("customer_id", customer["id"]).execute()
                QMessageBox.information(
                    dialog, "Status atualizado",
                    "Status atualizado e registrado no histórico. Nenhuma mensagem externa foi enviada.",
                )
                load_orders()
            except Exception as exc:
                QMessageBox.critical(dialog, "Erro ao atualizar status", f"Não foi possível atualizar o status.\\n\\n{exc}")

        def view_order_history() -> None:
            row_index = table.currentRow()
            if row_index < 0 or table.item(row_index, 0) is None:
                QMessageBox.information(dialog, "Selecione um pedido", "Selecione um pedido para consultar o histórico.")
                return
            order_id = table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
            try:
                events = self._client.table("customer_order_events").select(
                    "previous_status,new_status,changed_at,note"
                ).eq("organization_id", self._organization_id).eq(
                    "customer_id", customer["id"]
                ).eq("order_id", order_id).order("changed_at", desc=True).limit(100).execute().data or []
            except Exception as exc:
                QMessageBox.critical(dialog, "Erro no histórico", f"Não foi possível carregar o histórico de status.\\n\\n{exc}")
                return
            history_dialog = QDialog(dialog)
            history_dialog.setWindowTitle("Histórico de status do pedido")
            history_dialog.resize(720, 420)
            history_layout = QVBoxLayout(history_dialog)
            history_title_bar = QFrame()
            history_title_bar.setObjectName("windowTitleBar")
            history_title_layout = QVBoxLayout(history_title_bar)
            history_title_layout.setContentsMargins(18, 12, 18, 12)
            history_title = QLabel(f"Histórico — {customer.get('full_name', 'Cliente')}")
            history_title.setObjectName("windowTitle")
            history_title_layout.addWidget(history_title)
            history_layout.addWidget(history_title_bar)
            history_table = QTableWidget(0, 4)
            history_table.setHorizontalHeaderLabels(["Data", "Status anterior", "Novo status", "Observação"])
            history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            history_table.verticalHeader().setVisible(False)
            history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            history_table.setRowCount(len(events))
            for index, event in enumerate(events):
                previous = status_labels.get(event.get("previous_status", ""), event.get("previous_status", "") or "—")
                current = status_labels.get(event.get("new_status", ""), event.get("new_status", ""))
                values = [
                    str(event.get("changed_at") or "")[:16].replace("T", " "),
                    previous, current, event.get("note", ""),
                ]
                for column, value in enumerate(values):
                    history_table.setItem(index, column, QTableWidgetItem(str(value)))
            history_layout.addWidget(history_table)
            if not events:
                empty = QLabel("Ainda não há alterações de status registradas para este pedido.")
                empty.setStyleSheet("color:#64748b;padding:8px;")
                history_layout.addWidget(empty)
            close_history = QPushButton("Fechar")
            close_history.clicked.connect(history_dialog.accept)
            history_layout.addWidget(close_history, alignment=Qt.AlignmentFlag.AlignRight)
            history_dialog.setStyleSheet(dialog.styleSheet())
            history_dialog.exec()

        def save_order() -> None:
            if not description.text().strip():
                QMessageBox.warning(dialog, "Descrição obrigatória", "Informe a descrição do pedido.")
                description.setFocus()
                return
            order_status = status.currentData()
            now = __import__("datetime").datetime.now().astimezone().isoformat()
            record = {
                "organization_id": self._organization_id,
                "customer_id": customer["id"],
                "order_number": number.text().strip(),
                "description": description.text().strip(),
                "status": order_status,
                "expected_at": expected.date().toString("yyyy-MM-dd"),
                "notes": notes.toPlainText().strip(),
                "created_by": self._user_id,
                "completed_at": now if order_status == "pronto" else None,
                "delivered_at": now if order_status == "entregue" else None,
            }
            try:
                self._client.table("customer_orders").insert(record).execute()
                QMessageBox.information(dialog, "Pedido cadastrado", "Pedido salvo. Nenhuma mensagem externa foi enviada.")
                number.clear()
                description.clear()
                notes.clear()
                load_orders()
            except Exception as exc:
                QMessageBox.critical(dialog, "Erro ao salvar pedido", f"Não foi possível salvar o pedido.\\n\\n{exc}")

        refresh_button.clicked.connect(load_orders)
        update_status_button.clicked.connect(update_order_status)
        history_button.clicked.connect(view_order_history)
        save_button.clicked.connect(save_order)
        load_orders()
        dialog.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; }
            QLineEdit, QComboBox, QDateEdit, QTextEdit { background:#FFFFFF; color:#102957; border:1px solid #D9E3F1; border-radius:8px; padding:8px; }
            QTableWidget { background:#FFFFFF; alternate-background-color:#F7F9FD; gridline-color:#EDF1F7; selection-background-color:#E8F0FF; selection-color:#102957; }
            QHeaderView::section { background:#102957; color:#FFFFFF; border:none; padding:9px; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 13px; }
            QPushButton#primaryButton { background:#2165F5; color:#FFFFFF; border:1px solid #2165F5; }
        """)
        dialog.exec()


    def _manage_whatsapp_templates(self) -> None:
        if self._preview_mode:
            QMessageBox.information(self, "Pré-visualização", "A configuração das mensagens WhatsApp exige uma sessão autenticada.")
            return
        templates = [
            ("order_em_desenvolvimento", "Em desenvolvimento", "Olá, {{cliente}}! Seu pedido {{pedido}} ({{descricao}}) está em desenvolvimento. Previsão: {{previsao}}. — Ótica Linda Fashion"),
            ("order_pronto", "Óculos pronto", "Olá, {{cliente}}! Boas notícias: seu pedido {{pedido}} ({{descricao}}) está pronto para retirada. — Ótica Linda Fashion"),
            ("order_entregue", "Entregue", "Olá, {{cliente}}! Registramos a entrega do pedido {{pedido}} ({{descricao}}). Obrigado por escolher a Ótica Linda Fashion!"),
            ("order_cancelado", "Cancelado", "Olá, {{cliente}}. O pedido {{pedido}} ({{descricao}}) foi cancelado. Entre em contato conosco se precisar de ajuda. — Ótica Linda Fashion"),
        ]
        try:
            existing = self._client.table("customer_whatsapp_templates").select(
                "event_type,message_body,enabled"
            ).eq("organization_id", self._organization_id).execute().data or []
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar mensagens", f"Não foi possível carregar os modelos de WhatsApp.\\n\\n{exc}")
            return
        existing_by_type = {str(row.get("event_type")): row for row in existing}
        dialog = QDialog(self)
        dialog.setWindowTitle("Modelos automáticos de WhatsApp")
        dialog.resize(820, 760)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 12, 18, 12)
        title = QLabel("Mensagens automáticas de pedidos")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Personalize o texto enviado quando o status do pedido mudar.")
        subtitle.setObjectName("windowSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)
        help_text = QLabel("Variáveis disponíveis: {{cliente}}, {{pedido}}, {{descricao}}, {{status}}, {{previsao}}. A mensagem entra na fila apenas se o cliente estiver ativo, tiver WhatsApp cadastrado e consentimento marcado.")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color:#475569;padding:4px;")
        root.addWidget(help_text)
        editors: dict[str, tuple[QTextEdit, QCheckBox]] = {}
        for event_type, label, default_body in templates:
            row = existing_by_type.get(event_type, {})
            section = QFrame()
            section.setStyleSheet("QFrame { background:#F7F9FD; border:1px solid #E0E8F4; border-radius:8px; }")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(12, 10, 12, 10)
            section_layout.setSpacing(6)
            heading = QHBoxLayout()
            heading_label = QLabel(label)
            heading_label.setStyleSheet("font-weight:700;color:#102957;background:transparent;border:none;")
            enabled = QCheckBox("Ativar")
            enabled.setChecked(bool(row.get("enabled", True)))
            heading.addWidget(heading_label)
            heading.addStretch(1)
            heading.addWidget(enabled)
            section_layout.addLayout(heading)
            editor = QTextEdit()
            editor.setMinimumHeight(86)
            editor.setPlainText(str(row.get("message_body") or default_body))
            section_layout.addWidget(editor)
            root.addWidget(section)
            editors[event_type] = (editor, enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar modelos")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)
        dialog.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
            QTextEdit { background:#FFFFFF; color:#102957; border:1px solid #D9E3F1; border-radius:7px; padding:8px; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 14px; }
            QPushButton:hover { background:#F3F7FF; }
        """)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = []
        for event_type, _label, _default_body in templates:
            editor, enabled = editors[event_type]
            body = editor.toPlainText().strip()
            if enabled.isChecked() and not body:
                QMessageBox.warning(dialog, "Mensagem vazia", "Preencha o texto de cada modelo ativado ou desative-o.")
                return
            payload.append({
                "organization_id": self._organization_id,
                "event_type": event_type,
                "message_body": body,
                "enabled": enabled.isChecked(),
                "updated_by": self._user_id,
            })
        try:
            self._client.table("customer_whatsapp_templates").upsert(
                payload, on_conflict="organization_id,event_type"
            ).execute()
            QMessageBox.information(self, "Modelos salvos", "Os modelos foram salvos. As mudanças de status passarão a gerar mensagens na fila quando houver consentimento e WhatsApp cadastrado. O envio externo depende da configuração do provedor WhatsApp.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar modelos", f"Não foi possível salvar os modelos.\\n\\n{exc}")

    def _view_interactions(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente para consultar o histórico CRM.")
            return
        if self._preview_mode:
            QMessageBox.information(self, "Histórico demonstrativo", "O histórico persistido estará disponível quando houver registros reais.")
            return
        try:
            rows = (
                self._client.table("customer_interactions").select(
                    "interaction_type,subject,body,order_status,follow_up_at,created_at"
                ).eq("organization_id", self._organization_id)
                .eq("customer_id", customer["id"]).order("created_at", desc=True)
                .limit(100).execute().data or []
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao consultar histórico", f"Não foi possível carregar o histórico CRM.\\n\\n{exc}")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Histórico CRM — {customer.get('full_name', 'Cliente')}")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        heading_bar = QFrame()
        heading_bar.setObjectName("windowTitleBar")
        heading_layout = QVBoxLayout(heading_bar)
        heading_layout.setContentsMargins(18, 12, 18, 12)
        heading = QLabel(f"Histórico de relacionamento: {customer.get('full_name', 'Cliente')}")
        heading.setObjectName("windowTitle")
        heading_layout.addWidget(heading)
        layout.addWidget(heading_bar)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Data", "Tipo", "Assunto", "Registro", "Status do pedido"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        type_labels = {"observacao":"Observação","ligacao":"Ligação","email":"E-mail","whatsapp":"WhatsApp","follow_up":"Follow-up","status_pedido":"Status do pedido"}
        status_labels = {"em_desenvolvimento":"Em desenvolvimento","pronto":"Óculos pronto","entregue":"Entregue","cancelado":"Cancelado","": "—"}
        table.setRowCount(len(rows))
        for index, item in enumerate(rows):
            values = [
                str(item.get("created_at") or "")[:16].replace("T", " "),
                type_labels.get(item.get("interaction_type", ""), item.get("interaction_type", "")),
                item.get("subject", ""),
                item.get("body", ""),
                status_labels.get(item.get("order_status", ""), "—"),
            ]
            for column, value in enumerate(values):
                table.setItem(index, column, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _add_interaction(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente na tabela antes de registrar uma interação.")
            return
        if self._preview_mode:
            QMessageBox.information(self, "Pré-visualização", "O histórico CRM será demonstrativo neste modo.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar interação / follow-up")
        dialog.resize(560, 420)
        form = QFormLayout(dialog)
        kind = QComboBox()
        kind.addItems(["Observação", "Ligação", "E-mail", "WhatsApp", "Follow-up", "Status do pedido"])
        subject = QLineEdit()
        subject.setPlaceholderText("Ex.: Atualização do pedido")
        body = QTextEdit()
        body.setPlaceholderText("Registre o contato, próximo passo ou atualização...")
        status = QComboBox()
        status.addItem("Sem alteração de status", "")
        status.addItem("Em desenvolvimento", "em_desenvolvimento")
        status.addItem("Óculos pronto", "pronto")
        status.addItem("Entregue", "entregue")
        status.addItem("Cancelado", "cancelado")
        follow_up = QDateEdit()
        follow_up.setCalendarPopup(True)
        follow_up.setDisplayFormat("dd/MM/yyyy")
        follow_up.setDate(date.today())
        form.addRow("Tipo", kind)
        form.addRow("Assunto", subject)
        form.addRow("Registro", body)
        form.addRow("Status do pedido", status)
        form.addRow("Data do follow-up", follow_up)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        form.addRow(buttons)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        type_map = {"Observação":"observacao","Ligação":"ligacao","E-mail":"email","WhatsApp":"whatsapp","Follow-up":"follow_up","Status do pedido":"status_pedido"}
        record = {
            "organization_id": self._organization_id,
            "customer_id": customer["id"],
            "interaction_type": type_map[kind.currentText()],
            "subject": subject.text().strip(),
            "body": body.toPlainText().strip(),
            "order_status": status.currentData(),
            "follow_up_at": follow_up.date().toString("yyyy-MM-dd") if kind.currentText() == "Follow-up" else None,
            "created_by": self._user_id,
        }
        try:
            self._client.table("customer_interactions").insert(record).execute()
            QMessageBox.information(self, "Interação registrada", "O registro foi adicionado ao histórico CRM. Nenhuma mensagem externa foi enviada.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro no CRM", f"Não foi possível registrar a interação.\n\n{exc}")
