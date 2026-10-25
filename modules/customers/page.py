"""Customer registry and first CRM foundation for Ótica Linda Fashion."""
from __future__ import annotations

from datetime import date
import json
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QCalendarWidget, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client
from core.organization import OrganizationContext
from modules.lab_orders import statuses as order_statuses
from modules.lab_orders.page import LabOrdersPage
from modules.prescriptions.dialogs import PrescriptionHistoryDialog
from modules.prescriptions.repository import PrescriptionRepository
from modules.settings.service import load_store_settings
from ui.components.ui_kit import MetricTile, make_button
import qtawesome as qta


CUSTOMER_FIELDS = (
    "full_name", "document", "email", "phone", "whatsapp", "birth_date",
    "postal_code", "street", "address_number", "address_complement",
    "neighborhood", "city", "state", "notes", "marketing_email_consent",
    "whatsapp_consent", "active",
)

def _action_icon(action: str) -> QIcon:
    """Render high-resolution white action glyphs without external icon dependencies."""
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.scale(2.0, 2.0)
    painter.setPen(QPen(QColor("#FFFFFF"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if action == "view":
        eye = QPainterPath()
        eye.moveTo(2.5, 12)
        eye.cubicTo(7, 5, 17, 5, 21.5, 12)
        eye.cubicTo(17, 19, 7, 19, 2.5, 12)
        painter.drawPath(eye)
        painter.drawEllipse(QRectF(9.2, 9.2, 5.6, 5.6))
    elif action == "edit":
        pencil = QPainterPath()
        pencil.moveTo(5, 17.5)
        pencil.lineTo(6.1, 13.1)
        pencil.lineTo(15.7, 3.5)
        pencil.lineTo(20.5, 8.3)
        pencil.lineTo(10.9, 17.9)
        pencil.closeSubpath()
        painter.drawPath(pencil)
        painter.drawLine(5, 17.5, 10.9, 17.9)
        painter.drawLine(15.7, 3.5, 20.5, 8.3)
    painter.end()
    return QIcon(pixmap)


class CustomerFormDialog(QDialog):
    def __init__(self, customer: dict | None = None, parent: QWidget | None = None, read_only: bool = False) -> None:
        super().__init__(parent)
        self._read_only = read_only
        self.setWindowTitle("Visualizar cliente" if read_only else ("Editar cliente" if customer else "Novo cliente"))
        self.setMinimumSize(760, 620)
        self.resize(900, 760)
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
        title = QLabel("Dados do cliente" if read_only else "Cadastro do cliente")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Consulte as informações cadastradas." if read_only else "Preencha os dados em uma única tela, organizados por seção.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)

        scroll = QScrollArea()
        scroll.setObjectName("customerFormScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 12, 4)
        content_layout.setSpacing(14)

        groups = [
            ("Identificação", [("full_name", "Nome completo *"), ("document", "CPF"), ("birth_date", "Data de nascimento")]),
            ("Contato", [("email", "E-mail"), ("phone", "Telefone"), ("whatsapp", "WhatsApp")]),
            ("Endereço", [("postal_code", "CEP"), ("street", "Logradouro"), ("address_number", "Número"), ("address_complement", "Complemento"), ("neighborhood", "Bairro"), ("city", "Cidade"), ("state", "UF")]),
            ("Preferências", [("preferred_brands", "Marcas preferidas"), ("frame_preferences", "Estilo de armação"), ("lens_preferences", "Preferências de lente")]),
        ]
        for section_name, section_fields in groups:
            section = QLabel(section_name)
            section.setObjectName("formSectionTitle")
            content_layout.addWidget(section)
            form = QFormLayout()
            form.setContentsMargins(10, 0, 10, 0)
            form.setSpacing(10)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            for key, label_text in section_fields:
                if key == "birth_date":
                    widget = QDateEdit()
                    widget.setObjectName("birthDateEdit")
                    widget.setCalendarPopup(True)
                    widget.setDisplayFormat("dd/MM/yyyy")
                    widget.setSpecialValueText("dd/MM/yyyy")
                    widget.setDate(widget.minimumDate())
                    calendar = QCalendarWidget()
                    calendar.setGridVisible(False)
                    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
                    calendar.setNavigationBarVisible(True)
                    widget.setCalendarWidget(calendar)
                    raw = self._customer.get(key)
                    widget.setDate(date.fromisoformat(str(raw)[:10]) if raw else widget.minimumDate())
                else:
                    widget = QLineEdit()
                    widget.setClearButtonEnabled(not read_only)
                    widget.setPlaceholderText(label_text)
                    raw_value = str(self._customer.get(key) or "")
                    if key == "document":
                        widget.setInputMask("000.000.000-00;_")
                        widget.setPlaceholderText("000.000.000-00")
                    elif key in ("phone", "whatsapp"):
                        widget.setInputMask("(00) 00000-0000;_")
                        widget.setPlaceholderText("(00) 00000-0000")
                    elif key == "postal_code":
                        widget.setInputMask("00000-000;_")
                        widget.setPlaceholderText("00000-000")
                        widget.editingFinished.connect(self._lookup_postal_code)
                    elif key == "preferred_brands":
                        widget.setPlaceholderText("Ex.: Ray-Ban, Vogue, Prada")
                    elif key == "frame_preferences":
                        widget.setPlaceholderText("Ex.: acetato, formato gatinho, cores escuras, aro fechado")
                    elif key == "lens_preferences":
                        widget.setPlaceholderText("Ex.: multifocal, antirreflexo, filtro de luz azul")
                    widget.setText(raw_value)
                widget.setMinimumHeight(38)
                self.fields[key] = widget
                form.addRow(label_text, widget)
            content_layout.addLayout(form)

        section = QLabel("Observações e permissões")
        section.setObjectName("formSectionTitle")
        content_layout.addWidget(section)
        crm_form = QFormLayout()
        crm_form.setContentsMargins(10, 0, 10, 0)
        crm_form.setSpacing(10)
        self.preferred_channel = QComboBox()
        for code, caption in (("", "Sem preferência"), ("whatsapp", "WhatsApp"), ("email", "E-mail"), ("telefone", "Telefone")):
            self.preferred_channel.addItem(caption, code)
        self.preferred_channel.setCurrentIndex(max(0, self.preferred_channel.findData(self._customer.get("preferred_channel") or "")))
        crm_form.addRow("Canal de contato preferido", self.preferred_channel)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Preferências, observações e histórico relevante...")
        self.notes.setPlainText(str(self._customer.get("notes") or ""))
        self.notes.setMinimumHeight(90)
        self.notes.setMaximumHeight(130)
        crm_form.addRow("Observações internas", self.notes)
        content_layout.addLayout(crm_form)
        self.email_consent = QCheckBox("Autorizou receber e-mail marketing")
        self.email_consent.setChecked(bool(self._customer.get("marketing_email_consent", False)))
        self.whatsapp_consent = QCheckBox("Autorizou contato pelo WhatsApp")
        self.whatsapp_consent.setChecked(bool(self._customer.get("whatsapp_consent", False)))
        self.active = QCheckBox("Cliente ativo")
        self.active.setChecked(bool(self._customer.get("active", True)))
        for checkbox in (self.email_consent, self.whatsapp_consent, self.active):
            content_layout.addWidget(checkbox)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close if read_only else (QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save))
        if read_only:
            buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
            buttons.rejected.connect(self.reject)
        else:
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar cliente")
            buttons.accepted.connect(self._validate)
            buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if read_only:
            for widget in self.fields.values():
                widget.setEnabled(False)
            self.preferred_channel.setEnabled(False)
            self.notes.setReadOnly(True)
            for checkbox in (self.email_consent, self.whatsapp_consent, self.active):
                checkbox.setEnabled(False)


    def _lookup_postal_code(self) -> None:
        cep_widget = self.fields.get("postal_code")
        if not isinstance(cep_widget, QLineEdit):
            return
        cep = "".join(character for character in cep_widget.text() if character.isdigit())
        if len(cep) != 8:
            return
        try:
            request = Request(
                f"https://viacep.com.br/ws/{cep}/json/",
                headers={"User-Agent": "OticaLindaFashion/1.0"},
            )
            with urlopen(request, timeout=4) as response:
                address = json.loads(response.read().decode("utf-8"))
            if address.get("erro"):
                QMessageBox.information(self, "CEP não encontrado", "Confira o CEP informado e tente novamente.")
                return
            mapping = {
                "street": address.get("logradouro", ""),
                "neighborhood": address.get("bairro", ""),
                "city": address.get("localidade", ""),
                "state": address.get("uf", ""),
            }
            for key, value in mapping.items():
                field = self.fields.get(key)
                if isinstance(field, QLineEdit) and value and not field.text().strip():
                    field.setText(str(value))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            QMessageBox.warning(
                self, "Consulta de CEP indisponível",
                "Não foi possível consultar o CEP agora. Você pode preencher o endereço manualmente.",
            )

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
                text = widget.text().replace("_", "").strip()
                # An empty masked field returns only its separators (e.g. "..-"): store it as empty.
                if widget.inputMask() and not any(character.isdigit() for character in text):
                    text = ""
                record[key] = text
        record["notes"] = self.notes.toPlainText().strip()
        record["marketing_email_consent"] = self.email_consent.isChecked()
        record["whatsapp_consent"] = self.whatsapp_consent.isChecked()
        record["active"] = self.active.isChecked()
        record["preferred_channel"] = str(self.preferred_channel.currentData() or "")
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
        root.addLayout(header)

        metrics = QHBoxLayout()
        metrics.setSpacing(14)
        self.total_label = MetricTile("Clientes cadastrados", "0", "fa5s.users", "primary")
        self.email_label = MetricTile("E-mail autorizado", "0", "fa5s.envelope", "navy", "Consentimento para e-mail marketing")
        self.whatsapp_label = MetricTile("WhatsApp autorizado", "0", "fa5b.whatsapp", "success", "Consentimento para mensagens")
        for tile in (self.total_label, self.email_label, self.whatsapp_label):
            metrics.addWidget(tile, 1)
        root.addLayout(metrics)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nome, CPF, e-mail ou telefone...")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(qta.icon("fa5s.search", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._render_rows)
        filters.addWidget(self.search, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Todos os clientes", "Ativos", "Inativos"])
        self.status_filter.setMinimumWidth(180)
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        filters.addWidget(self.status_filter)
        self.new_button = make_button("Novo cliente", "fa5s.user-plus", "primaryButton")
        self.new_button.clicked.connect(self._new_customer)
        filters.addWidget(self.new_button)
        root.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Cliente", "Telefone / WhatsApp", "E-mail", "Consentimentos", "Situação", "Ações"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        # Reserve enough horizontal and vertical space for both icon buttons.
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 104)
        self.table.horizontalHeader().setMinimumSectionSize(70)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setMinimumSectionSize(48)
        self.table.doubleClicked.connect(self._edit_selected)
        root.addWidget(self.table, 1)

        crm_actions = QHBoxLayout()
        crm_actions.setSpacing(8)
        self.prescriptions_button = make_button("Receitas", "fa5s.eye", "secondaryButton")
        self.prescriptions_button.setToolTip("Histórico de receitas oftálmicas do cliente selecionado")
        self.prescriptions_button.clicked.connect(self._manage_prescriptions)
        crm_actions.addWidget(self.prescriptions_button)
        self.orders_button = make_button("Pedidos e status", "fa5s.clipboard-check", "secondaryButton")
        self.orders_button.setToolTip("Acompanhar pedidos do cliente selecionado")
        self.orders_button.clicked.connect(self._manage_orders)
        crm_actions.addWidget(self.orders_button)
        self.sales_history_button = make_button("Histórico de vendas", "fa5s.receipt", "secondaryButton")
        self.sales_history_button.clicked.connect(self._view_sales_history)
        crm_actions.addWidget(self.sales_history_button)
        self.history_button = make_button("Histórico CRM", "fa5s.history", "secondaryButton")
        self.history_button.clicked.connect(self._view_interactions)
        crm_actions.addWidget(self.history_button)
        self.whatsapp_templates_button = make_button("Mensagens WhatsApp", "fa5b.whatsapp", "secondaryButton")
        self.whatsapp_templates_button.setToolTip("Configurar mensagens automáticas de status de pedido")
        self.whatsapp_templates_button.clicked.connect(self._manage_whatsapp_templates)
        crm_actions.addWidget(self.whatsapp_templates_button)
        crm_actions.addStretch(1)
        self.crm_button = make_button("Registrar interação", "fa5s.comment-dots", "primaryButton")
        self.crm_button.setToolTip("Registrar interação ou follow-up para o cliente selecionado")
        self.crm_button.clicked.connect(self._add_interaction)
        crm_actions.addWidget(self.crm_button)
        root.addLayout(crm_actions)
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
                "  ·  ".join([
                    "E-mail ✓" if record.get("marketing_email_consent") else "E-mail —",
                    "WhatsApp ✓" if record.get("whatsapp_consent") else "WhatsApp —",
                ]),
                "Ativo" if record.get("active", True) else "Inativo",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
                if col == 4:
                    item.setForeground(QColor("#0E8A5B" if record.get("active", True) else "#8A97AB"))
                self.table.setItem(row_index, col, item)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(6)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            view_button = QPushButton()
            view_button.setObjectName("viewCustomerButton")
            view_button.setToolTip("Visualizar cliente")
            view_button.setAccessibleName(f"Visualizar cliente {record.get('full_name', '')}")
            view_button.setIcon(_action_icon("view"))
            view_button.setIconSize(QSize(20, 20))
            view_button.setFixedSize(34, 34)
            view_button.setCursor(Qt.CursorShape.PointingHandCursor)
            view_button.clicked.connect(lambda checked=False, item=record: self._view_customer(item))
            actions_layout.addWidget(view_button)

            edit_button = QPushButton()
            edit_button.setObjectName("editCustomerButton")
            edit_button.setToolTip("Editar cliente")
            edit_button.setAccessibleName(f"Editar cliente {record.get('full_name', '')}")
            edit_button.setIcon(_action_icon("edit"))
            edit_button.setIconSize(QSize(20, 20))
            edit_button.setFixedSize(34, 34)
            edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_button.clicked.connect(lambda checked=False, item=record: self._edit_customer(item))
            actions_layout.addWidget(edit_button)
            actions_widget.setMinimumWidth(100)
            actions_widget.setMinimumHeight(44)
            self.table.setCellWidget(row_index, 5, actions_widget)
            self.table.setRowHeight(row_index, 48)
        total = len(self._rows)
        email_count = sum(bool(row.get("marketing_email_consent") and row.get("email")) for row in self._rows)
        whatsapp_count = sum(bool(row.get("whatsapp_consent") and row.get("whatsapp")) for row in self._rows)
        self.total_label.set_value(str(total))
        self.email_label.set_value(str(email_count))
        self.whatsapp_label.set_value(str(whatsapp_count))

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
    def _view_customer(self, customer: dict) -> None:
        dialog = CustomerFormDialog(customer, self, read_only=True)
        dialog.exec()

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

    def _view_sales_history(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente para consultar o histórico de vendas.")
            return

        if self._preview_mode:
            orders = [
                {"id": "demo-sale-1", "order_number": "V-20261015-001", "status": "completed", "total": 649.90, "discount": 50.00, "payment_method": "Pix", "created_at": "2026-10-15T14:32:00"},
                {"id": "demo-sale-2", "order_number": "V-20260902-002", "status": "completed", "total": 389.00, "discount": 0.00, "payment_method": "Cartão de crédito", "created_at": "2026-09-02T10:10:00"},
            ] if customer.get("id") == "demo-1" else []
        else:
            try:
                orders = (
                    self._client.table("sales_orders")
                    .select("id,order_number,status,total,discount,payment_method,created_at")
                    .eq("organization_id", self._organization_id)
                    .eq("customer_id", customer["id"])
                    .order("created_at", desc=True)
                    .limit(500)
                    .execute()
                    .data or []
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao carregar vendas", f"Não foi possível consultar o histórico de vendas.\\n\\n{exc}")
                return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Histórico de vendas — {customer.get('full_name', 'Cliente')}")
        dialog.resize(980, 620)
        dialog.setMinimumSize(780, 480)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 12, 18, 12)
        heading = QLabel(f"Histórico de vendas de {customer.get('full_name', 'Cliente')}")
        heading.setObjectName("windowTitle")
        subtitle = QLabel("Consulte compras anteriores, valores, pagamentos e os itens de cada venda.")
        subtitle.setObjectName("windowSubtitle")
        title_layout.addWidget(heading)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)

        total_spent = sum(float(order.get("total") or 0) for order in orders)
        last_purchase = str(orders[0].get("created_at") or "")[:10] if orders else "—"
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        for title, value, icon_name, tone in (
            ("Vendas", str(len(orders)), "fa5s.shopping-bag", "primary"),
            ("Total comprado", self._format_sales_history_money(total_spent), "fa5s.coins", "success"),
            ("Última compra", last_purchase, "fa5s.calendar-alt", "navy"),
        ):
            metrics.addWidget(MetricTile(title, value, icon_name, tone), 1)
        root.addLayout(metrics)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Nº venda", "Data", "Status", "Pagamento", "Desconto", "Total"])
        for column in range(6):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        root.addWidget(table, 1)

        status_labels = {
            "completed": "Concluída", "pending": "Pendente", "cancelled": "Cancelada",
            "canceled": "Cancelada", "refunded": "Estornada",
        }
        for index, order in enumerate(orders):
            table.insertRow(index)
            created_at = str(order.get("created_at") or "").replace("T", " ")[:16]
            values = [
                order.get("order_number") or "—", created_at or "—",
                status_labels.get(str(order.get("status") or "").lower(), str(order.get("status") or "—")),
                order.get("payment_method") or "—",
                self._format_sales_history_money(order.get("discount")),
                self._format_sales_history_money(order.get("total")),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, order.get("id"))
                table.setItem(index, column, cell)

        if not orders:
            empty = QLabel("Este cliente ainda não possui vendas registradas.")
            empty.setObjectName("emptyState")
            root.addWidget(empty)

        actions = QHBoxLayout()
        details_button = QPushButton("Ver itens da venda selecionada")
        details_button.setObjectName("primaryButton")
        close_button = QPushButton("Fechar")
        actions.addWidget(details_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        root.addLayout(actions)

        def show_sale_details() -> None:
            row_index = table.currentRow()
            if row_index < 0 or table.item(row_index, 0) is None:
                QMessageBox.information(dialog, "Selecione uma venda", "Selecione uma venda para visualizar seus itens.")
                return
            order_id = table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
            order = next((item for item in orders if item.get("id") == order_id), None)
            if not order:
                return
            if self._preview_mode:
                items = [
                    {"product_name": "Armação premium", "sku": "ARM-001", "quantity": 1, "unit_price": 499.90, "line_total": 449.90},
                    {"product_name": "Lentes antirreflexo", "sku": "LEN-002", "quantity": 1, "unit_price": 200.00, "line_total": 200.00},
                ] if order_id == "demo-sale-1" else [
                    {"product_name": "Óculos de sol", "sku": "SOL-003", "quantity": 1, "unit_price": 389.00, "line_total": 389.00},
                ]
            else:
                try:
                    items = (
                        self._client.table("sales_order_items")
                        .select("product_name,sku,quantity,unit_price,line_total")
                        .eq("organization_id", self._organization_id)
                        .eq("sales_order_id", order_id)
                        .order("created_at")
                        .execute()
                        .data or []
                    )
                except Exception as exc:
                    QMessageBox.critical(dialog, "Erro ao carregar itens", f"Não foi possível consultar os itens da venda.\\n\\n{exc}")
                    return

            detail = QDialog(dialog)
            detail.setWindowTitle(f"Itens da venda {order.get('order_number') or ''}")
            detail.resize(760, 420)
            detail_layout = QVBoxLayout(detail)
            detail_title = QLabel(f"Venda {order.get('order_number') or '—'} · {self._format_sales_history_money(order.get('total'))}")
            detail_title.setObjectName("sectionTitle")
            detail_layout.addWidget(detail_title)
            detail_table = QTableWidget(0, 5)
            detail_table.setHorizontalHeaderLabels(["Produto", "SKU", "Qtd.", "Preço unitário", "Total do item"])
            detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column in range(1, 5):
                detail_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
            detail_table.verticalHeader().setVisible(False)
            detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            detail_table.setRowCount(len(items))
            for row_number, item in enumerate(items):
                values = [
                    item.get("product_name") or "Produto", item.get("sku") or "—",
                    str(item.get("quantity") or 0),
                    self._format_sales_history_money(item.get("unit_price")),
                    self._format_sales_history_money(item.get("line_total")),
                ]
                for column, value in enumerate(values):
                    detail_table.setItem(row_number, column, QTableWidgetItem(str(value)))
            detail_layout.addWidget(detail_table, 1)
            if not items:
                detail_layout.addWidget(QLabel("Não há itens disponíveis para esta venda."))
            done = QPushButton("Fechar")
            done.clicked.connect(detail.accept)
            detail_layout.addWidget(done, alignment=Qt.AlignmentFlag.AlignRight)
            detail.exec()

        details_button.clicked.connect(show_sale_details)
        close_button.clicked.connect(dialog.accept)
        dialog.exec()

    @staticmethod
    def _format_sales_history_money(value: object) -> str:
        from decimal import Decimal, ROUND_HALF_UP
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _manage_orders(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente para consultar ou cadastrar pedidos.")
            return
        try:
            LabOrdersPage(preview_mode=self._preview_mode, customer=customer, parent=self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Pedidos indisponíveis", str(exc))

    def _manage_prescriptions(self) -> None:
        customer = self._selected_customer()
        if not customer:
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente para consultar ou cadastrar receitas.")
            return
        ctx = self._context()
        PrescriptionHistoryDialog(
            customer, PrescriptionRepository(ctx), load_store_settings(ctx).prescription_validity_months, parent=self,
        ).exec()

    def _context(self) -> OrganizationContext | None:
        if self._preview_mode:
            return None
        return OrganizationContext(self._client, str(self._organization_id), str(self._user_id), "member")

    def _manage_whatsapp_templates(self) -> None:
        if self._preview_mode:
            QMessageBox.information(self, "Pré-visualização", "A configuração das mensagens WhatsApp exige uma sessão autenticada.")
            return
        templates = [
            (f"order_{status.code}", status.label, status.default_message) for status in order_statuses.template_statuses()
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
        help_text.setObjectName("infoNotice")
        root.addWidget(help_text)
        editors: dict[str, tuple[QTextEdit, QCheckBox]] = {}
        templates_scroll = QScrollArea()
        templates_scroll.setWidgetResizable(True)
        templates_scroll.setFrameShape(QFrame.Shape.NoFrame)
        templates_host = QWidget()
        templates_layout = QVBoxLayout(templates_host)
        templates_layout.setContentsMargins(0, 0, 8, 0)
        templates_layout.setSpacing(10)
        templates_scroll.setWidget(templates_host)
        root.addWidget(templates_scroll, 1)
        for event_type, label, default_body in templates:
            row = existing_by_type.get(event_type, {})
            section = QFrame()
            section.setObjectName("templateCard")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(12, 10, 12, 10)
            section_layout.setSpacing(6)
            heading = QHBoxLayout()
            heading_label = QLabel(label)
            heading_label.setObjectName("cardHeading")
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
            templates_layout.addWidget(section)
            editors[event_type] = (editor, enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar modelos")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)
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
        status_labels = {status.code: status.label for status in order_statuses.ALL_STATUSES}
        status_labels[""] = "—"
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
        for order_status in order_statuses.ALL_STATUSES:
            status.addItem(order_status.label, order_status.code)
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
