"""Inventory monitoring, stock movements and supplier purchase requests."""
from __future__ import annotations

from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


class InventoryPage(QDialog):
    """Organization-scoped inventory workspace. Preview mode is intentionally read-only."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Estoque — Ótica Linda Fashion")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)
        self.setStyleSheet("""
            QDialog { background:#F5F8FD; color:#172B4D; font-family:"Segoe UI"; font-size:10pt; }
            QLabel#pageTitle { color:#102957; font-size:23pt; font-weight:800; }
            QLabel#muted { color:#7184A1; }
            QLabel#metric { background:#FFFFFF; color:#17365D; border:1px solid #DFE7F3; border-radius:10px; padding:14px; font-size:12pt; font-weight:700; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { background:#FFFFFF; color:#172B4D; border:1px solid #D9E3F1; border-radius:8px; padding:8px; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 13px; font-weight:650; }
            QPushButton:hover { background:#F0F5FF; }
            QPushButton#primaryButton { background:#245DE0; color:#FFFFFF; border:1px solid #245DE0; font-weight:750; }
            QTableWidget { background:#FFFFFF; alternate-background-color:#F7F9FD; border:1px solid #E0E8F4; border-radius:10px; gridline-color:#EDF1F7; selection-background-color:#E8F0FF; selection-color:#102957; }
            QHeaderView::section { background:#EFF4FC; color:#42577B; border:none; padding:10px; font-weight:750; }
            QTabWidget::pane { border:1px solid #DFE7F3; background:#FFFFFF; border-radius:10px; }
            QTabBar::tab { background:#EAF0F9; color:#526782; padding:10px 18px; margin-right:4px; border-top-left-radius:7px; border-top-right-radius:7px; }
            QTabBar::tab:selected { background:#FFFFFF; color:#2457D6; font-weight:750; }
        """)
        self._client = None
        self._organization_id = None
        self._products: list[dict] = []
        self._suppliers: list[dict] = []
        if not preview_mode:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O módulo Estoque online exige login e configuração do Supabase.")
            self._client = get_supabase_client()
            session = session_manager.current
            response = self._client.table("organization_members").select("organization_id").eq("user_id", session.user_id).eq("active", True).limit(1).execute()
            rows = response.data or []
            if not rows:
                raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
            self._organization_id = str(rows[0]["organization_id"])

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Controle de estoque")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        subtitle = QLabel("Acompanhe saldos, registre movimentações e transforme alertas em solicitações de compra.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._load)
        header.addWidget(self.refresh_button)
        self.movement_button = QPushButton("Registrar movimentação")
        self.movement_button.setObjectName("primaryButton")
        self.movement_button.clicked.connect(self._movement_dialog)
        header.addWidget(self.movement_button)
        self.request_button = QPushButton("Criar solicitação de compra")
        self.request_button.clicked.connect(self._purchase_request_dialog)
        header.addWidget(self.request_button)
        root.addLayout(header)

        metrics = QHBoxLayout()
        self.total_metric = QLabel("Produtos monitorados\n—")
        self.total_metric.setObjectName("metric")
        self.low_metric = QLabel("Estoque baixo\n—")
        self.low_metric.setObjectName("metric")
        self.out_metric = QLabel("Sem estoque\n—")
        self.out_metric.setObjectName("metric")
        for label in (self.total_metric, self.low_metric, self.out_metric):
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            metrics.addWidget(label, 1)
        root.addLayout(metrics)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por produto, código, SKU, marca ou categoria…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render_inventory)
        search_row.addWidget(self.search, 1)
        root.addLayout(search_row)

        self.tabs = QTabWidget()
        inventory_tab = QWidget()
        inventory_layout = QVBoxLayout(inventory_tab)
        self.inventory_table = self._table(["Código / SKU", "Produto", "Categoria", "Saldo", "Mínimo", "Situação", "Custo estimado"])
        self.inventory_table.doubleClicked.connect(lambda *_: self._purchase_request_dialog())
        inventory_layout.addWidget(self.inventory_table)
        self.tabs.addTab(inventory_tab, "Visão do estoque")

        movements_tab = QWidget()
        movements_layout = QVBoxLayout(movements_tab)
        self.movements_table = self._table(["Data", "Produto", "Tipo", "Quantidade", "Saldo anterior", "Saldo final", "Motivo"])
        movements_layout.addWidget(self.movements_table)
        self.tabs.addTab(movements_tab, "Histórico de movimentações")

        requests_tab = QWidget()
        requests_layout = QVBoxLayout(requests_tab)
        request_actions = QHBoxLayout()
        request_hint = QLabel("Selecione uma solicitação para registrar o recebimento das mercadorias.")
        request_hint.setObjectName("muted")
        request_actions.addWidget(request_hint, 1)
        self.receive_button = QPushButton("Receber mercadoria")
        self.receive_button.setObjectName("primaryButton")
        self.receive_button.clicked.connect(self._receive_purchase_request_item)
        request_actions.addWidget(self.receive_button)
        requests_layout.addLayout(request_actions)
        self.requests_table = self._table(["Solicitação", "Fornecedor", "Status", "Criada em", "Itens"])
        self.requests_table.doubleClicked.connect(self._show_request_details)
        requests_layout.addWidget(self.requests_table)
        self.tabs.addTab(requests_tab, "Solicitações de compra")
        root.addWidget(self.tabs, 1)

        if preview_mode:
            note = QLabel("PRÉ-VISUALIZAÇÃO • para proteger a integridade do catálogo, estoque e compras só podem ser alterados após conectar o Supabase e aplicar a migration do módulo.")
            note.setWordWrap(True)
            note.setStyleSheet("background:#FFF7DF;color:#79550B;padding:10px;border-radius:8px;")
            root.addWidget(note)
            self.movement_button.setEnabled(False)
            self.request_button.setEnabled(False)
            self._load_preview()
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
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _load_preview(self) -> None:
        self._products = []
        self._render_inventory()
        self.total_metric.setText("Produtos monitorados\nPrévia")
        self.low_metric.setText("Estoque baixo\n—")
        self.out_metric.setText("Sem estoque\n—")
        for table in (self.movements_table, self.requests_table):
            table.setRowCount(0)

    def _load(self) -> None:
        if self._client is None:
            return
        try:
            self._products = list((self._client.table("products").select("id,barcode,sku,name,category,brand,cost_price,stock_quantity,minimum_stock,active").eq("organization_id", self._organization_id).eq("active", True).order("name").execute().data or []))
            self._suppliers = list((self._client.table("suppliers").select("*").eq("organization_id", self._organization_id).eq("active", True).order("name").execute().data or []))
            self._render_inventory()
            self._load_movements()
            self._load_requests()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar estoque", f"{exc}\n\nConfirme se a migration do módulo Estoque foi aplicada no Supabase.")

    def _render_inventory(self, *_args: object) -> None:
        term = self.search.text().strip().casefold()
        products = [p for p in self._products if not term or any(term in str(p.get(k) or "").casefold() for k in ("name","barcode","sku","category","brand"))]
        low = [p for p in self._products if int(p.get("stock_quantity") or 0) <= int(p.get("minimum_stock") or 0)]
        out = [p for p in self._products if int(p.get("stock_quantity") or 0) == 0]
        self.total_metric.setText(f"Produtos monitorados\n{len(self._products)}")
        self.low_metric.setText(f"Estoque baixo\n{len(low)}")
        self.out_metric.setText(f"Sem estoque\n{len(out)}")
        self.inventory_table.setRowCount(len(products))
        for row, product in enumerate(products):
            stock = int(product.get("stock_quantity") or 0)
            minimum = int(product.get("minimum_stock") or 0)
            status = "Sem estoque" if stock == 0 else "Estoque baixo" if stock <= minimum else "Normal"
            values = [product.get("barcode") or product.get("sku") or "—", product.get("name",""), product.get("category") or "—", str(stock), str(minimum), status, f"R$ {Decimal(str(product.get('cost_price') or 0))*stock:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, product.get("id"))
                if col in (3,4,6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 5 and status != "Normal":
                    item.setForeground(QBrush(QColor("#B42318" if stock == 0 else "#9A6700")) )
                self.inventory_table.setItem(row, col, item)

    def _load_movements(self) -> None:
        if self._client is None:
            return
        try:
            rows = self._client.table("stock_movements").select("*,products(name)").eq("organization_id", self._organization_id).order("created_at", desc=True).limit(200).execute().data or []
            self.movements_table.setRowCount(len(rows))
            for row_index, movement in enumerate(rows):
                product = movement.get("products") or {}
                values = [str(movement.get("created_at",""))[:16].replace("T"," "), product.get("name","Produto"), movement.get("movement_type",""), str(movement.get("quantity",0)), str(movement.get("previous_quantity",0)), str(movement.get("resulting_quantity",0)), movement.get("reason","")]
                for col, value in enumerate(values):
                    self.movements_table.setItem(row_index, col, QTableWidgetItem(value))
        except Exception:
            self.movements_table.setRowCount(0)

    def _load_requests(self) -> None:
        if self._client is None:
            return
        try:
            rows = self._client.table("purchase_requests").select("*,suppliers(name),purchase_request_items(id)").eq("organization_id", self._organization_id).order("created_at", desc=True).limit(200).execute().data or []
            self.requests_table.setRowCount(len(rows))
            for row_index, request in enumerate(rows):
                supplier = request.get("suppliers") or {}
                items = request.get("purchase_request_items") or []
                values = [f"PC-{request.get('request_number',request.get('id',''))}", supplier.get("name","Fornecedor não definido"), request.get("status",""), str(request.get("created_at",""))[:16].replace("T"," "), str(len(items))]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, request.get("id"))
                    self.requests_table.setItem(row_index, col, item)
        except Exception:
            self.requests_table.setRowCount(0)

    def _movement_dialog(self) -> None:
        if not self._products:
            QMessageBox.information(self, "Sem produtos", "Cadastre produtos ativos antes de registrar movimentações.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar movimentação de estoque")
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        product = QComboBox()
        for item in self._products:
            product.addItem(f"{item.get('name')} • saldo {item.get('stock_quantity',0)}", item.get("id"))
        movement_type = QComboBox()
        movement_type.addItem("Entrada", "entrada")
        movement_type.addItem("Saída", "saida")
        movement_type.addItem("Ajuste para quantidade exata", "ajuste")
        quantity = QSpinBox()
        quantity.setRange(1, 2_000_000_000)
        movement_type.currentIndexChanged.connect(
            lambda _index: quantity.setMinimum(0 if movement_type.currentData() == "ajuste" else 1)
        )
        reason = QLineEdit()
        reason.setPlaceholderText("Ex.: compra, venda, avaria, inventário")
        reference = QLineEdit()
        reference.setPlaceholderText("Nota fiscal / referência (opcional)")
        form.addRow("Produto", product)
        form.addRow("Tipo", movement_type)
        form.addRow("Quantidade", quantity)
        form.addRow("Motivo", reason)
        form.addRow("Referência", reference)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_product = next((item for item in self._products if item.get("id") == product.currentData()), None)
        if movement_type.currentData() == "ajuste" and selected_product and quantity.value() == int(selected_product.get("stock_quantity") or 0):
            QMessageBox.information(dialog, "Nenhuma alteração", "A quantidade informada já corresponde ao saldo atual.")
            return
        try:
            self._client.rpc("record_stock_movement", {"p_product_id": product.currentData(), "p_movement_type": movement_type.currentData(), "p_quantity": quantity.value(), "p_reason": reason.text().strip(), "p_reference": reference.text().strip()}).execute()
            self._load()
            QMessageBox.information(self, "Estoque atualizado", "Movimentação registrada e saldo atualizado.")
        except Exception as exc:
            QMessageBox.critical(self, "Falha na movimentação", str(exc))

    def _purchase_request_dialog(self) -> None:
        selected_row = self.inventory_table.currentRow()
        selected_id = self.inventory_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole) if selected_row >= 0 else None
        selected_product = next((p for p in self._products if p.get("id") == selected_id), None)
        candidates = [selected_product] if selected_product else [p for p in self._products if int(p.get("stock_quantity") or 0) <= int(p.get("minimum_stock") or 0)]
        candidates = [p for p in candidates if p]
        if not candidates:
            QMessageBox.information(self, "Nenhum produto selecionado", "Selecione um produto na tabela ou não há itens abaixo do estoque mínimo.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Solicitação de compra")
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        supplier = QComboBox()
        supplier.addItem("Selecionar fornecedor…", None)
        for item in self._suppliers:
            supplier.addItem(item.get("name",""), item.get("id"))
        new_supplier = QPushButton("Cadastrar fornecedor")
        supplier_row = QHBoxLayout()
        supplier_row.addWidget(supplier, 1)
        supplier_row.addWidget(new_supplier)
        form.addRow("Fornecedor", supplier_row)
        product_list = QComboBox()
        for item in candidates:
            product_list.addItem(f"{item.get('name')} • saldo {item.get('stock_quantity')} / mínimo {item.get('minimum_stock')}", item.get("id"))
        form.addRow("Produto para reposição", product_list)
        quantity = QSpinBox()
        quantity.setRange(1, 2_000_000_000)
        initial = max(1, int(candidates[0].get("minimum_stock") or 0) * 2 - int(candidates[0].get("stock_quantity") or 0))
        quantity.setValue(initial)
        product_list.currentIndexChanged.connect(lambda index: quantity.setValue(max(1, int(candidates[index].get("minimum_stock") or 0) * 2 - int(candidates[index].get("stock_quantity") or 0))))
        form.addRow("Quantidade sugerida", quantity)
        unit_cost = QDoubleSpinBox()
        unit_cost.setRange(0, 99_999_999.99)
        unit_cost.setDecimals(2)
        unit_cost.setPrefix("R$ ")
        unit_cost.setValue(float(candidates[0].get("cost_price") or 0))
        form.addRow("Custo unitário estimado", unit_cost)
        notes = QTextEdit()
        notes.setMaximumHeight(72)
        notes.setPlaceholderText("Observações para o fornecedor…")
        form.addRow("Observações", notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Criar solicitação")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def create_supplier() -> None:
            supplier_dialog = QDialog(dialog)
            supplier_dialog.setWindowTitle("Novo fornecedor")
            supplier_form = QFormLayout(supplier_dialog)
            name = QLineEdit()
            contact = QLineEdit()
            phone = QLineEdit()
            email = QLineEdit()
            supplier_form.addRow("Nome *", name)
            supplier_form.addRow("Contato", contact)
            supplier_form.addRow("Telefone", phone)
            supplier_form.addRow("E-mail", email)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
            buttons.accepted.connect(supplier_dialog.accept)
            buttons.rejected.connect(supplier_dialog.reject)
            supplier_form.addRow(buttons)
            if supplier_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if not name.text().strip():
                QMessageBox.warning(dialog, "Nome obrigatório", "Informe o nome do fornecedor.")
                return
            try:
                result = self._client.table("suppliers").insert({"organization_id":self._organization_id,"name":name.text().strip(),"contact_name":contact.text().strip(),"phone":phone.text().strip(),"email":email.text().strip()}).select("*").execute().data or []
                if not result:
                    raise RuntimeError("O fornecedor não foi retornado após salvar.")
                self._suppliers.append(result[0])
                supplier.addItem(result[0]["name"], result[0]["id"])
                supplier.setCurrentIndex(supplier.count()-1)
            except Exception as exc:
                QMessageBox.critical(dialog, "Erro ao cadastrar fornecedor", str(exc))
        new_supplier.clicked.connect(create_supplier)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not supplier.currentData():
            QMessageBox.warning(self, "Fornecedor obrigatório", "Selecione ou cadastre um fornecedor para vincular à solicitação.")
            return
        product_id = product_list.currentData()
        product = next(p for p in candidates if p.get("id") == product_id)
        try:
            request_rows = self._client.table("purchase_requests").insert({"organization_id":self._organization_id,"supplier_id":supplier.currentData(),"status":"solicitada","notes":notes.toPlainText().strip(),"created_by":session_manager.current.user_id}).select("*").execute().data or []
            if not request_rows:
                raise RuntimeError("A solicitação não foi retornada após salvar.")
            request = request_rows[0]
            self._client.table("purchase_request_items").insert({"organization_id":self._organization_id,"purchase_request_id":request["id"],"product_id":product_id,"quantity_requested":quantity.value(),"unit_cost":str(Decimal(str(unit_cost.value())).quantize(Decimal("0.01")))}).execute()
            self._load_requests()
            self.tabs.setCurrentIndex(2)
            QMessageBox.information(self, "Solicitação criada", f"Solicitação PC-{request.get('request_number',request['id'])} criada e vinculada ao fornecedor {supplier.currentText()}.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao criar solicitação", f"{exc}\n\nVerifique se a migration foi aplicada. Se a solicitação foi criada mas os itens falharam, confira a lista antes de tentar novamente.")

    def _receive_purchase_request_item(self) -> None:
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Selecione uma solicitação", "Selecione uma solicitação de compra para registrar o recebimento.")
            return
        request_id = self.requests_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            rows = self._client.table("purchase_requests").select("*,suppliers(name),purchase_request_items(*,products(name,sku,barcode))").eq("id", request_id).eq("organization_id", self._organization_id).limit(1).execute().data or []
            if not rows:
                raise RuntimeError("A solicitação não foi encontrada.")
            request = rows[0]
            if request.get("status") not in ("solicitada", "aprovada", "recebida_parcial"):
                QMessageBox.information(self, "Recebimento indisponível", "Esta solicitação não aceita recebimento no status atual.")
                return
            pending_items = []
            for item in request.get("purchase_request_items") or []:
                remaining = int(item.get("quantity_requested") or 0) - int(item.get("quantity_received") or 0)
                if remaining > 0:
                    pending_items.append((item, remaining))
            if not pending_items:
                QMessageBox.information(self, "Pedido completo", "Todos os itens desta solicitação já foram recebidos.")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Receber mercadoria — PC-{request.get('request_number', request_id)}")
            dialog.setMinimumWidth(540)
            layout = QVBoxLayout(dialog)
            form = QFormLayout()
            item_combo = QComboBox()
            for item, remaining in pending_items:
                product = item.get("products") or {}
                item_combo.addItem(
                    f"{product.get('name', 'Produto')} • pendente: {remaining}",
                    item.get("id"),
                )
            quantity = QSpinBox()
            quantity.setRange(1, pending_items[0][1])
            quantity.setValue(pending_items[0][1])
            item_combo.currentIndexChanged.connect(
                lambda index: (
                    quantity.setRange(1, pending_items[index][1]),
                    quantity.setValue(pending_items[index][1]),
                )
            )
            reference = QLineEdit()
            reference.setPlaceholderText("Número da nota fiscal ou referência (opcional)")
            form.addRow("Item pendente", item_combo)
            form.addRow("Quantidade recebida agora", quantity)
            form.addRow("Nota fiscal / referência", reference)
            layout.addLayout(form)
            hint = QLabel("O recebimento atualiza o saldo do produto, registra a entrada no histórico e recalcula o status da solicitação em uma única transação.")
            hint.setWordWrap(True)
            hint.setObjectName("muted")
            layout.addWidget(hint)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Confirmar recebimento")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            result = self._client.rpc(
                "receive_purchase_request_item",
                {
                    "p_purchase_request_item_id": item_combo.currentData(),
                    "p_quantity": quantity.value(),\n                    "p_reason": "Recebimento de compra",
                    "p_reference": reference.text().strip(),
                },
            ).execute()
            self._load()
            self.tabs.setCurrentIndex(1)
            data = result.data if isinstance(result.data, dict) else {}
            QMessageBox.information(
                self,
                "Recebimento registrado",
                f"Entrada de {quantity.value()} unidade(s) registrada. "
                f"Saldo atualizado de {data.get('stock_quantity', '—')} para {data.get('stock_quantity', '—')}. "
                f"Status da solicitação: {data.get('request_status', 'atualizado')}.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Falha no recebimento",
                f"{exc}\\n\\nConfirme se a migration 202610240003_receive_purchase_items.sql foi aplicada no Supabase.",
            )

    def _show_request_details(self) -> None:
        row = self.requests_table.currentRow()
        if row < 0:
            return
        request_id = self.requests_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            rows = self._client.table("purchase_requests").select("*,suppliers(name),purchase_request_items(*,products(name,sku,barcode))").eq("id",request_id).eq("organization_id",self._organization_id).limit(1).execute().data or []
            if not rows:
                return
            request = rows[0]
            supplier = request.get("suppliers") or {}
            items = request.get("purchase_request_items") or []
            detail_lines = [f"Fornecedor: {supplier.get('name','Não definido')}", f"Status: {request.get('status','')}", f"Observações: {request.get('notes') or '—'}", "", "Itens:"]
            for item in items:
                product = item.get("products") or {}
                detail_lines.append(f"• {product.get('name','Produto')} — solicitado: {item.get('quantity_requested',0)}; recebido: {item.get('quantity_received',0)}")
            QMessageBox.information(self, f"Solicitação PC-{request.get('request_number',request_id)}", "\n".join(detail_lines))
        except Exception as exc:
            QMessageBox.warning(self, "Não foi possível abrir a solicitação", str(exc))
