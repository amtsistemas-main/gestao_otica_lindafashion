"""Customer registry and first CRM foundation for Ótica Linda Fashion."""
from __future__ import annotations

from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
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

        title = QLabel("Cadastro do cliente")
        title.setStyleSheet("font-size:22pt;font-weight:800;color:#102957;")
        root.addWidget(title)
        subtitle = QLabel("Centralize os dados de contato e as preferências de comunicação do cliente.")
        subtitle.setStyleSheet("color:#64748b;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

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
        heading = QVBoxLayout()
        title = QLabel("Clientes")
        title.setStyleSheet("font-size:24pt;font-weight:800;color:#102957;")
        heading.addWidget(title)
        subtitle = QLabel("Cadastro, relacionamento e base para campanhas e follow-ups.")
        subtitle.setStyleSheet("color:#64748b;")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
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
        self.history_button = QPushButton("Ver histórico CRM")
        self.history_button.clicked.connect(self._view_interactions)
        crm_actions.addWidget(self.history_button)
        self.crm_button = QPushButton("Registrar interação / follow-up")
        self.crm_button.setObjectName("primaryButton")
        self.crm_button.clicked.connect(self._add_interaction)
        crm_actions.addWidget(self.crm_button)
        root.addLayout(crm_actions)
        self.setStyleSheet("""
            QDialog { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; font-size:10pt; }
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
        heading = QLabel(f"Histórico de relacionamento: {customer.get('full_name', 'Cliente')}")
        heading.setStyleSheet("font-size:16pt;font-weight:750;color:#102957;")
        layout.addWidget(heading)
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
