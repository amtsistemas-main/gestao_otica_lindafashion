"""Complete supplier registry with organization-scoped persistence."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QFrame, QHeaderView, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QTextEdit,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client

SUPPLIER_FIELDS = (
    "name", "legal_name", "trade_name", "document", "state_registration",
    "municipal_registration", "contact_name", "phone", "whatsapp", "email",
    "website", "postal_code", "street", "address_number", "address_complement",
    "neighborhood", "city", "state", "payment_terms", "pix_key", "bank_name",
    "bank_branch", "bank_account", "notes", "active",
)
FIELD_LABELS = {
    "name": "Nome de exibição *", "legal_name": "Razão social", "trade_name": "Nome fantasia",
    "document": "CPF / CNPJ", "state_registration": "Inscrição estadual",
    "municipal_registration": "Inscrição municipal", "contact_name": "Pessoa de contato",
    "phone": "Telefone", "whatsapp": "WhatsApp", "email": "E-mail",
    "website": "Site", "postal_code": "CEP", "street": "Logradouro",
    "address_number": "Número", "address_complement": "Complemento",
    "neighborhood": "Bairro", "city": "Cidade", "state": "UF",
    "payment_terms": "Condições de pagamento", "pix_key": "Chave PIX",
    "bank_name": "Banco", "bank_branch": "Agência", "bank_account": "Conta bancária",
    "notes": "Observações internas",
}


class SupplierFormDialog(QDialog):
    def __init__(self, supplier: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar fornecedor" if supplier else "Novo fornecedor")
        self.setMinimumSize(820, 640)
        self.resize(980, 740)
        self._supplier = supplier or {}
        self.fields: dict[str, QWidget] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 13, 18, 13)
        title_layout.setSpacing(4)
        title = QLabel("Cadastro do fornecedor")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Dados cadastrais, fiscais, contato, endereço e condições comerciais.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        root.addWidget(title_bar)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        groups = [
            ("Identificação", [
                ("name", "Nome de exibição *"), ("legal_name", "Razão social"),
                ("trade_name", "Nome fantasia"), ("document", "CPF / CNPJ"),
                ("state_registration", "Inscrição estadual"), ("municipal_registration", "Inscrição municipal"),
            ]),
            ("Contato e endereço", [
                ("contact_name", "Pessoa de contato"), ("phone", "Telefone"),
                ("whatsapp", "WhatsApp"), ("email", "E-mail"), ("website", "Site"),
                ("postal_code", "CEP"), ("street", "Logradouro"), ("address_number", "Número"),
                ("address_complement", "Complemento"), ("neighborhood", "Bairro"),
                ("city", "Cidade"), ("state", "UF"),
            ]),
            ("Comercial e pagamento", [
                ("payment_terms", "Condições de pagamento"), ("pix_key", "Chave PIX"),
                ("bank_name", "Banco"), ("bank_branch", "Agência"), ("bank_account", "Conta bancária"),
                ("notes", "Observações internas"),
            ]),
        ]
        for tab_name, fields in groups:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(18, 18, 18, 18)
            form.setSpacing(12)
            for key, label in fields:
                if key == "notes":
                    widget = QTextEdit()
                    widget.setMaximumHeight(120)
                else:
                    widget = QLineEdit()
                    widget.setClearButtonEnabled(True)
                    widget.setPlaceholderText(label)
                widget.setMinimumWidth(260)
                
                widget.setText(self._supplier.get(key, "") or "") if isinstance(widget, QLineEdit) else widget.setPlainText(self._supplier.get(key, "") or "")
                self.fields[key] = widget
                form.addRow(label, widget)
            scroll.setWidget(page)
            tabs.addTab(scroll, tab_name)
        self.active = QCheckBox("Fornecedor ativo para novas operações")
        self.active.setChecked(bool(self._supplier.get("active", True)))
        root.addWidget(self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar fornecedor")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; font-size:10pt; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
            QLineEdit, QTextEdit { background:#FFFFFF; color:#102957; border:1px solid #D9E3F1; border-radius:8px; padding:8px; selection-background-color:#2165F5; selection-color:#FFFFFF; }
            QLineEdit:focus, QTextEdit:focus { border:1px solid #2165F5; }
            QTabWidget::pane { border:1px solid #E4EAF5; border-radius:8px; background:#FFFFFF; }
            QTabBar::tab { background:#FFFFFF; color:#4B5675; padding:10px 16px; border:1px solid #E4EAF5; }
            QTabBar::tab:selected { color:#FFFFFF; background:#2165F5; }
            QCheckBox { spacing:8px; padding:5px; color:#102957; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 14px; font-weight:650; }
            QPushButton:hover { background:#F3F7FF; }
            QPushButton#primaryButton { background:#2165F5; color:#FFFFFF; border:1px solid #2165F5; }
        """)

    def _validate(self) -> None:
        name = self.fields["name"].text().strip()
        if not name:
            QMessageBox.warning(self, "Campo obrigatório", "Informe o nome de exibição do fornecedor.")
            self.fields["name"].setFocus()
            return
        email = self.fields["email"].text().strip()
        if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
            QMessageBox.warning(self, "E-mail inválido", "Confira o endereço de e-mail informado.")
            self.fields["email"].setFocus()
            return
        state = self.fields["state"].text().strip()
        if state and len(state) != 2:
            QMessageBox.warning(self, "UF inválida", "Informe a UF com duas letras.")
            self.fields["state"].setFocus()
            return
        self.accept()

    def record(self) -> dict:
        result = {}
        for key, widget in self.fields.items():
            result[key] = widget.toPlainText().strip() if isinstance(widget, QTextEdit) else widget.text().strip()
        result["active"] = self.active.isChecked()
        return result


class SuppliersPage(QDialog):
    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Fornecedores — Ótica Linda Fashion")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)
        self.setStyleSheet("""
            QDialog { background:#F3F5F8; color:#24334B; font-family:"Arial"; font-size:10pt; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { background:transparent; color:#FFFFFF; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { background:transparent; color:#DCE7F7; font-size:9pt; }
            QHeaderView::section { background:#102957; color:#FFFFFF; border:none; border-right:1px solid #28456F; padding:11px 8px; min-height:22px; font-weight:700; }
            QLabel#pageTitle { color:#102957; font-size:23pt; font-weight:800; }
            QLabel#muted { color:#7184A1; }
            QLineEdit { background:#FFFFFF; color:#172B4D; border:1px solid #D9E3F1; border-radius:8px; padding:9px; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 13px; font-weight:650; }
            QPushButton#primaryButton { background:#245DE0; color:#FFFFFF; border:1px solid #245DE0; }
            QTableWidget { background:#FFFFFF; alternate-background-color:#F7F9FD; border:1px solid #E0E8F4; gridline-color:#EDF1F7; selection-background-color:#E8F0FF; selection-color:#102957; }
            QHeaderView::section { background:#EFF4FC; color:#42577B; border:none; padding:10px; font-weight:750; }
        """)
        self._client = None
        self._organization_id = None
        self._rows: list[dict] = []
        self._products: list[dict] = []
        if not preview_mode:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O módulo Fornecedores exige login e configuração do Supabase.")
            self._client = get_supabase_client()
            session = session_manager.current
            rows = self._client.table("organization_members").select("organization_id").eq("user_id", session.user_id).eq("active", True).limit(1).execute().data or []
            if not rows:
                raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
            self._organization_id = str(rows[0]["organization_id"])

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 13, 18, 13)
        title_layout.setSpacing(4)
        title = QLabel("Fornecedores")
        title.setObjectName("windowTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Centralize dados fiscais, contatos, endereço, condições comerciais e produtos fornecidos.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        titles.addWidget(title_bar)
        header.addLayout(titles, 1)
        self.new_button = QPushButton("+ Novo fornecedor")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new)
        header.addWidget(self.new_button)
        root.addLayout(header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nome, razão social, CPF/CNPJ, contato, e-mail ou cidade…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render)
        root.addWidget(self.search)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Fornecedor", "CPF / CNPJ", "Contato", "Telefone / WhatsApp", "E-mail", "Cidade / UF", "Produtos", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setMinimumSectionSize(92)
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view.setStretchLastSection(False)
        for column, width in enumerate((210, 125, 145, 175, 205, 135, 82, 88)):
            self.table.setColumnWidth(column, width)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.doubleClicked.connect(self._edit)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.edit_button = QPushButton("Editar selecionado")
        self.edit_button.clicked.connect(self._edit)
        self.toggle_button = QPushButton("Ativar / desativar")
        self.toggle_button.clicked.connect(self._toggle_active)
        self.products_button = QPushButton("Ver produtos vinculados")
        self.products_button.clicked.connect(self._show_products)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._load)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.products_button)
        actions.addStretch()
        actions.addWidget(self.refresh_button)
        root.addLayout(actions)
        if preview_mode:
            note = QLabel("PRÉ-VISUALIZAÇÃO • o cadastro e a persistência de fornecedores exigem conexão com o Supabase.")
            note.setWordWrap(True)
            note.setStyleSheet("background:#FFF7DF;color:#79550B;padding:10px;border-radius:8px;")
            root.addWidget(note)
            for button in (self.new_button, self.edit_button, self.toggle_button, self.products_button):
                button.setEnabled(False)
        self._load()

    def _load(self) -> None:
        if self._client is None:
            self._rows = []
            self._render()
            return
        try:
            self._rows = list(self._client.table("suppliers").select("*").eq("organization_id", self._organization_id).order("name").execute().data or [])
            self._products = list(self._client.table("products").select("id,name,sku,barcode,supplier_id,active").eq("organization_id", self._organization_id).order("name").execute().data or [])
            self._render()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar fornecedores", f"{exc}\n\nConfirme se a migration 202610240005_complete_supplier_catalog_and_product_link.sql foi aplicada.")

    def _render(self, *_args: object) -> None:
        term = self.search.text().strip().casefold()
        rows = [row for row in self._rows if not term or any(term in str(row.get(key) or "").casefold() for key in ("name", "legal_name", "trade_name", "document", "contact_name", "phone", "whatsapp", "email", "city"))]
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.get("trade_name") or row.get("name") or row.get("legal_name") or "—",
                row.get("document") or "—",
                row.get("contact_name") or "—",
                " / ".join(value for value in (row.get("phone") or "", row.get("whatsapp") or "") if value) or "—",
                row.get("email") or "—",
                " / ".join(value for value in (row.get("city") or "", row.get("state") or "") if value) or "—",
                str(sum(1 for product in self._products if product.get("supplier_id") == row.get("id"))),
                "Ativo" if row.get("active", True) else "Inativo",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                if col == 6:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(index, col, item)
        self._visible_rows = rows

    def _selected(self) -> dict | None:
        index = self.table.currentRow()
        if index < 0 or index >= len(getattr(self, "_visible_rows", [])):
            QMessageBox.information(self, "Selecione um fornecedor", "Selecione um fornecedor na tabela.")
            return None
        return self._visible_rows[index]

    def _new(self) -> None:
        self._edit_dialog(None)

    def _edit(self) -> None:
        supplier = self._selected()
        if supplier:
            self._edit_dialog(supplier)

    def _edit_dialog(self, supplier: dict | None) -> None:
        dialog = SupplierFormDialog(supplier, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        record = dialog.record()
        try:
            if supplier:
                rows = self._client.table("suppliers").update(record).eq("id", supplier["id"]).eq("organization_id", self._organization_id).select("*").execute().data or []
            else:
                record["organization_id"] = self._organization_id
                rows = self._client.table("suppliers").insert(record).select("*").execute().data or []
            if not rows:
                raise RuntimeError("O fornecedor não foi retornado após salvar. Confira as permissões da organização.")
            self._load()
            QMessageBox.information(self, "Fornecedor salvo", "Os dados do fornecedor foram salvos.")
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar o fornecedor", str(exc))

    def _show_products(self) -> None:
        supplier = self._selected()
        if not supplier:
            return
        products = [
            product for product in self._products
            if product.get("supplier_id") == supplier.get("id")
        ]
        if not products:
            QMessageBox.information(
                self, "Nenhum produto vinculado",
                f"Não há produtos vinculados ao fornecedor {supplier.get('name')}. "
                "Para vincular, abra Produtos, edite o cadastro e selecione este fornecedor.",
            )
            return
        lines = [
            f"{product.get('name', 'Produto')} — "
            f"SKU: {product.get('sku') or '—'} — "
            f"Código: {product.get('barcode') or '—'} — "
            f"{'Ativo' if product.get('active', True) else 'Inativo'}"
            for product in products
        ]
        QMessageBox.information(
            self, f"Produtos de {supplier.get('trade_name') or supplier.get('name')}",
            f"{len(products)} produto(s) vinculado(s):\n\n" + "\n".join(lines),
        )

    def _toggle_active(self) -> None:
        supplier = self._selected()
        if not supplier:
            return
        active = not bool(supplier.get("active", True))
        action = "ativar" if active else "desativar"
        answer = QMessageBox.question(self, f"Confirmar {action}", f"Deseja {action} o fornecedor {supplier.get('name')}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.table("suppliers").update({"active": active}).eq("id", supplier["id"]).eq("organization_id", self._organization_id).execute()
            self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível atualizar o fornecedor", str(exc))
