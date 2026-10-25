"""Sales orders, service-order PDF generation and POS entry point."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from urllib.parse import quote
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


def _money(value: object) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class SalesOrderDialog(QDialog):
    def __init__(self, client, organization_id: str, user_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova venda / ordem de serviço — Ótica Linda Fashion")
        self.setMinimumSize(1000, 700)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self._client, self._organization_id, self._user_id = client, organization_id, user_id
        self._products: list[dict] = []
        self._customers: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        title = QFrame()
        title.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title)
        title_layout.setContentsMargins(14, 8, 14, 8)
        title_layout.setSpacing(2)
        heading = QLabel("Nova venda / ordem de serviço")
        heading.setObjectName("windowTitle")
        sub = QLabel("Registre os itens e os dados ópticos; a ordem de serviço será gerada ao finalizar.")
        sub.setObjectName("windowSubtitle")
        title_layout.addWidget(heading)
        title_layout.addWidget(sub)
        root.addWidget(title)

        self.customer = QComboBox()
        self.customer.addItem("Venda sem cliente identificado", None)
        self.product = QComboBox()
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(1, 99999)
        self.quantity.setDecimals(0)
        self.quantity.setValue(1)
        self.unit_price = QDoubleSpinBox()
        self.unit_price.setRange(0, 9999999)
        self.unit_price.setDecimals(2)
        self.unit_price.setPrefix("R$ ")
        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 9999999)
        self.discount.setDecimals(2)
        self.discount.setPrefix("R$ ")

        customer_product_row = QHBoxLayout()
        customer_product_row.setSpacing(8)
        customer_product_row.addWidget(QLabel("Cliente"))
        customer_product_row.addWidget(self.customer, 2)
        customer_product_row.addWidget(QLabel("Produto"))
        customer_product_row.addWidget(self.product, 4)
        root.addLayout(customer_product_row)

        item_entry_row = QHBoxLayout()
        item_entry_row.setSpacing(8)
        item_entry_row.addWidget(QLabel("Qtd."))
        item_entry_row.addWidget(self.quantity)
        item_entry_row.addWidget(QLabel("Preço unit."))
        item_entry_row.addWidget(self.unit_price)
        item_entry_row.addWidget(QLabel("Desconto (R$)"))
        item_entry_row.addWidget(self.discount)
        add_item = QPushButton("Adicionar item")
        add_item.setObjectName("primaryButton")
        add_item.clicked.connect(self._add_item)
        item_entry_row.addWidget(add_item)
        root.addLayout(item_entry_row)

        self._os_fields = {}
        prescription_box = QGroupBox("Receita e medidas ópticas")
        prescription_layout = QHBoxLayout(prescription_box)
        prescription_layout.setContentsMargins(6, 8, 6, 6)
        prescription_layout.setSpacing(8)
        self._add_measurement_table(prescription_layout, "Longe", ["ESF", "CIL", "EIXO", "DNP"], ["OD", "OE"], "longe")
        self._add_measurement_table(prescription_layout, "Perto", ["ESF", "CIL", "EIXO", "DNP", "ALT.", "AD"], ["OD", "OE"], "perto")
        self._add_measurement_table(prescription_layout, "Armação", ["Ponte", "Horiz.", "Vert.", "Diag. Maior", "Diâmetro"], ["Medida"], "armacao")
        root.addWidget(prescription_box)

        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(["Produto", "Qtd.", "Unitário", "Desconto", "Total"])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.items_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.verticalHeader().setDefaultSectionSize(28)
        self.items_table.setMinimumHeight(100)
        root.addWidget(self.items_table, 1)

        payment_notes_row = QHBoxLayout()
        payment_notes_row.setSpacing(8)
        self.payment_method = QComboBox()
        self.payment_method.addItems(["Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência", "A prazo / pendente"])
        payment_notes_row.addWidget(QLabel("Pagamento"))
        payment_notes_row.addWidget(self.payment_method, 1)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(54)
        self.notes.setMinimumHeight(42)
        self.notes.setPlaceholderText("Observações da venda / ordem de serviço")
        payment_notes_row.addWidget(self.notes, 3)
        root.addLayout(payment_notes_row)

        footer = QHBoxLayout()
        self.total_label = QLabel("Total: R$ 0,00")
        self.total_label.setObjectName("sectionTitle")
        footer.addWidget(self.total_label)
        footer.addStretch()
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton("Salvar pedido", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.clicked.connect(self._save)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        root.addLayout(footer)
        self.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { color:#FFFFFF; background:transparent; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { color:#DCE7F7; background:transparent; }
            QLabel#sectionTitle { font-size:14pt; font-weight:700; }
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit { background:#FFFFFF; color:#102957; border:1px solid #D9E3F1; border-radius:7px; padding:7px; min-height:24px; }

            QAbstractSpinBox { padding-right: 7px; }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                subcontrol-origin: border; subcontrol-position: right; width: 25px;
                border: none; border-left: 1px solid #1D4FC4; background: #245DE0;
            }
            QAbstractSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 7px; border-bottom: 1px solid #4A79E8; }
            QAbstractSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 7px; }
            QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: #1749C2; }
            QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed { background: #103A9F; }
            QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {
                width: 8px; height: 8px; color: #FFFFFF;
            }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:7px; padding:9px 14px; }
            QPushButton#primaryButton { background:#2165F5; color:#FFFFFF; border-color:#2165F5; font-weight:700; }
            QHeaderView::section { background:#EEF3FC; color:#102957; padding:8px; border:0; font-weight:700; }
        
            /* Explicit popup styling: local dialog styles must not fall back to a dark native palette. */
            QComboBox QAbstractItemView, QComboBox QListView, QComboBox QAbstractItemView:focus {
                background-color: #FFFFFF;
                color: #172B4D;
                border: 1px solid #D6E0EF;
                selection-background-color: #DCE8FF;
                selection-color: #17365D;
                outline: 0;
            }
            QComboBox QAbstractItemView::item, QComboBox QListView::item {
                background-color: #FFFFFF;
                color: #172B4D;
                min-height: 24px;
                padding: 5px 8px;
            }
            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:selected:active,
            QComboBox QAbstractItemView::item:selected:!active,
            QComboBox QListView::item:selected {
                background-color: #DCE8FF;
                color: #17365D;
            }
            QMenu {
                background-color: #FFFFFF;
                color: #172B4D;
                border: 1px solid #D6E0EF;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                color: #172B4D;
                padding: 7px 28px 7px 10px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #DCE8FF;
                color: #17365D;
            }
            QMenu::item:disabled {
                color: #8793A6;
            }
""")
        self._load_options()

    def _add_measurement_table(self, parent_layout, title: str, columns: list[str], rows: list[str], prefix: str) -> None:
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setContentsMargins(6, 8, 6, 5)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)
        grid.addWidget(QLabel(""), 0, 0)
        for col, column in enumerate(columns, start=1):
            label = QLabel(column)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-weight:700;color:#102957;background:#EEF3FC;padding:5px;border-radius:4px;")
            grid.addWidget(label, 0, col)
        for row_index, row_label in enumerate(rows, start=1):
            label = QLabel(row_label)
            label.setStyleSheet("font-weight:700;color:#102957;")
            grid.addWidget(label, row_index, 0)
            for col_index, column in enumerate(columns, start=1):
                field = QLineEdit()
                field.setPlaceholderText("—")
                field.setMinimumWidth(38)
                field.setMaximumWidth(112)
                field.setMaximumHeight(28)
                field.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(field, row_index, col_index)
                key = column.lower().replace(" ", "_").replace(".", "").replace("diâmetro", "diametro").replace("diâmetro", "diametro")
                self._os_fields[prefix + "." + row_label.lower() + "." + key] = field
        parent_layout.addWidget(group)

    def _prescription_payload(self) -> dict:
        values = {key: field.text().strip() for key, field in self._os_fields.items()}
        return {
            "longe": {eye: {column: values.get("longe." + eye + "." + column, "") for column in ("esf", "cil", "eixo", "dnp")} for eye in ("od", "oe")},
            "perto": {eye: {column: values.get("perto." + eye + "." + column, "") for column in ("esf", "cil", "eixo", "dnp", "alt", "ad")} for eye in ("od", "oe")},
            "armacao": {column: values.get("armacao.medida." + column, "") for column in ("ponte", "horiz", "vert", "diag_maior", "diametro")},
        }

    def _load_options(self) -> None:
        customers = self._client.table("customers").select("id,full_name,whatsapp,whatsapp_consent").eq("organization_id", self._organization_id).eq("active", True).order("full_name").execute().data or []
        self._customers = customers
        for item in customers:
            self.customer.addItem(str(item.get("full_name") or "Cliente"), item["id"])
        products = self._client.table("products").select("id,name,sku,sale_price,stock_quantity,active").eq("organization_id", self._organization_id).eq("active", True).order("name").execute().data or []
        self._products = products
        for item in products:
            self.product.addItem(f'{item.get("name","Produto")} — {_money(item.get("sale_price"))} (estoque: {item.get("stock_quantity", 0)})', item["id"])
        self.product.currentIndexChanged.connect(self._sync_price)
        self._sync_price()

    def _sync_price(self) -> None:
        item = next((p for p in self._products if p["id"] == self.product.currentData()), None)
        if item:
            self.unit_price.setValue(float(item.get("sale_price") or 0))

    def _add_item(self) -> None:
        product = next((p for p in self._products if p["id"] == self.product.currentData()), None)
        if not product:
            QMessageBox.information(self, "Produtos", "Cadastre ou ative ao menos um produto antes de montar a venda.")
            return
        qty = Decimal(str(self.quantity.value()))
        price = Decimal(str(self.unit_price.value()))
        discount = Decimal(str(self.discount.value()))
        line_total = qty * price - discount
        if line_total < 0:
            QMessageBox.warning(self, "Desconto inválido", "O desconto não pode superar o valor do item.")
            return
        if qty != qty.to_integral_value():
            QMessageBox.warning(self, "Quantidade inválida", "A quantidade deve ser um número inteiro para este produto.")
            return
        if qty > Decimal(str(product.get("stock_quantity") or 0)):
            QMessageBox.warning(self, "Estoque insuficiente", f"Estoque disponível: {product.get('stock_quantity', 0)}.")
            return
        row = {"product_id": product["id"], "product_name": product["name"], "sku": product.get("sku") or "", "quantity": float(qty), "unit_price": float(price), "discount": float(discount), "line_total": float(line_total)}
        self._rows.append(row) if hasattr(self, "_rows") else setattr(self, "_rows", [row])
        index = self.items_table.rowCount()
        self.items_table.insertRow(index)
        for col, value in enumerate([row["product_name"], str(row["quantity"]), _money(price), _money(discount), _money(line_total)]):
            self.items_table.setItem(index, col, QTableWidgetItem(value))
        self._refresh_total()
        self.discount.setValue(0)

    def _refresh_total(self) -> None:
        total = sum((Decimal(str(row["line_total"])) for row in getattr(self, "_rows", [])), Decimal("0"))
        self.total_label.setText(f"Total: {_money(total)}")

    def _save(self) -> None:
        rows = getattr(self, "_rows", [])
        if not rows:
            QMessageBox.warning(self, "Venda vazia", "Adicione ao menos um item antes de salvar.")
            return
        subtotal = sum((Decimal(str(r["quantity"])) * Decimal(str(r["unit_price"])) for r in rows), Decimal("0"))
        discount = sum((Decimal(str(r["discount"])) for r in rows), Decimal("0"))
        total = sum((Decimal(str(r["line_total"])) for r in rows), Decimal("0"))
        order_number = "V-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:20]
        payload = [{"product_id": r["product_id"], "quantity": r["quantity"], "unit_price": r["unit_price"], "discount": r["discount"], "line_total": r["line_total"]} for r in rows]
        notes_text = self.notes.toPlainText().strip()
        metadata = {"version": 1, "prescription": self._prescription_payload()}
        stored_notes = "[[LF_OS_DATA]]" + json.dumps(metadata, ensure_ascii=False, separators=(",", ":")) + "\n" + notes_text
        params = {"p_organization_id": self._organization_id, "p_customer_id": self.customer.currentData(), "p_order_number": order_number, "p_subtotal": float(subtotal), "p_discount": float(discount), "p_total": float(total), "p_payment_method": self.payment_method.currentText(), "p_notes": stored_notes, "p_items": payload}
        self.save_button.setEnabled(False)
        try:
            result = self._client.rpc("finalize_sales_order", params).execute().data
            if isinstance(result, list):
                result = result[0] if result else None
            if not isinstance(result, dict) or not result.get("id"):
                raise RuntimeError("O banco não confirmou a finalização da venda.")
        except Exception as exc:
            self.save_button.setEnabled(True)
            QMessageBox.critical(self, "Venda não finalizada", f"Nenhuma confirmação foi recebida.\n\n{exc}")
            return
        self._saved_order = {"id": result["id"], "order_number": result.get("order_number", order_number), "total": float(total), "status": result.get("status", "completed")}
        QMessageBox.information(self, "Venda finalizada", f"Venda {self._saved_order['order_number']} finalizada.\nTotal: {_money(total)}\n\nItens, baixa de estoque e lançamento financeiro foram processados na mesma transação.")
        self.accept()


class SalesPage(QDialog):
    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Vendas e PDV — Ótica Linda Fashion")
        self.resize(1200, 780)
        self.setMinimumSize(960, 640)
        self._client = None
        self._organization_id = None
        self._user_id = None
        if not preview_mode:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O módulo Vendas exige login e configuração do Supabase.")
            self._client = get_supabase_client()
            session = session_manager.current
            self._user_id = session.user_id
            memberships = self._client.table("organization_members").select("organization_id").eq("user_id", session.user_id).eq("active", True).limit(1).execute().data or []
            if not memberships:
                raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
            self._organization_id = str(memberships[0]["organization_id"])
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        titlebar = QFrame()
        titlebar.setObjectName("windowTitleBar")
        h = QVBoxLayout(titlebar)
        title = QLabel("Vendas")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Pedidos, ordens de serviço em PDF e ponto de venda.")
        subtitle.setObjectName("windowSubtitle")
        h.addWidget(title); h.addWidget(subtitle)
        header.addWidget(titlebar, 1)
        self.new_button = QPushButton("+ Nova venda / pedido")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new_order)
        header.addWidget(self.new_button)
        self.pos_button = QPushButton("Abrir PDV")
        self.pos_button.clicked.connect(self._new_order)
        header.addWidget(self.pos_button)
        root.addLayout(header)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Pedido", "Data", "Cliente", "Status", "Total", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col in (1,3,4,5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)
        self.setStyleSheet("""
            QDialog, QWidget { background:#FFFFFF; color:#102957; font-family:"Segoe UI"; }
            QFrame#windowTitleBar { background:#102957; border:1px solid #203D68; border-radius:8px; }
            QLabel#windowTitle { color:#FFFFFF; background:transparent; font-size:16pt; font-weight:700; }
            QLabel#windowSubtitle { color:#DCE7F7; background:transparent; }
            QPushButton { background:#FFFFFF; color:#244BAA; border:1px solid #DCE5F5; border-radius:8px; padding:9px 14px; font-weight:600; }
            QPushButton#primaryButton { background:#2165F5; color:#FFFFFF; border-color:#2165F5; }
            QHeaderView::section { background:#EEF3FC; color:#102957; padding:9px; border:0; font-weight:700; }
        """)
        self._load_orders()

    def _load_orders(self) -> None:
        self.table.setRowCount(0)
        if self._preview_mode:
            return
        orders = self._client.table("sales_orders").select("id,order_number,status,total,created_at,customer_id,customers(full_name,whatsapp,whatsapp_consent)").eq("organization_id", self._organization_id).order("created_at", desc=True).limit(250).execute().data or []
        for order in orders:
            customer = order.get("customers") or {}
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [order.get("order_number",""), str(order.get("created_at",""))[:16].replace("T"," "), customer.get("full_name","Venda avulsa"), order.get("status",""), _money(order.get("total"))]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
            actions = QWidget(); actions_layout = QHBoxLayout(actions); actions_layout.setContentsMargins(2,2,2,2)
            pdf = QPushButton("Gerar PDF"); pdf.clicked.connect(lambda checked=False, oid=order["id"]: self._export_pdf(oid))
            wa = QPushButton("WhatsApp"); wa.clicked.connect(lambda checked=False, oid=order["id"]: self._prepare_whatsapp(oid))
            actions_layout.addWidget(pdf); actions_layout.addWidget(wa)
            self.table.setCellWidget(row, 5, actions)

    def _new_order(self) -> None:
        if self._preview_mode:
            QMessageBox.information(self, "Pré-visualização", "O PDV exige sessão autenticada e conexão com o Supabase.")
            return
        dialog = SalesOrderDialog(self._client, self._organization_id, self._user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_orders()
            saved = getattr(dialog, "_saved_order", None)
            if saved:
                # Every completed sale immediately offers the service-order PDF for saving and printing.
                self._export_pdf(saved["id"])

    def _order_data(self, order_id: str) -> tuple[dict, list[dict]]:
        order_rows = self._client.table("sales_orders").select("*,customers(full_name,document,phone,whatsapp,address_number,street,city,state)").eq("id", order_id).eq("organization_id", self._organization_id).limit(1).execute().data or []
        if not order_rows:
            raise RuntimeError("Pedido não encontrado ou sem permissão.")
        items = self._client.table("sales_order_items").select("product_name,sku,quantity,unit_price,discount,line_total").eq("sales_order_id", order_id).eq("organization_id", self._organization_id).execute().data or []
        return order_rows[0], items

    def _export_pdf(self, order_id: str) -> None:
        try:
            order, items = self._order_data(order_id)
            default_name = str(order.get("order_number") or "ordem_servico") + ".pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Salvar ordem de serviço", default_name, "Documento PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            customer = order.get("customers") or {}
            def esc(value) -> str:
                return (str(value) if value is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
            lines = "".join(
                "<tr><td>" + esc(r.get("product_name")) + "</td><td>" + esc(r.get("sku")) + "</td><td>" + esc(r.get("quantity")) + "</td><td>" + _money(r.get("unit_price")) + "</td><td>" + _money(r.get("discount")) + "</td><td>" + _money(r.get("line_total")) + "</td></tr>"
                for r in items
            )
            notes_raw = str(order.get("notes") or "")
            notes_text = notes_raw
            metadata = {}
            marker = "[[LF_OS_DATA]]"
            if notes_raw.startswith(marker):
                metadata_text, separator, notes_text = notes_raw[len(marker):].partition("\n")
                try:
                    metadata = json.loads(metadata_text)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
                    notes_text = notes_raw
            prescription = metadata.get("prescription") or {}

            def prescription_table(title: str, columns: list[str], rows: list[tuple[str, dict]]) -> str:
                header = "".join("<th>" + esc(column) + "</th>" for column in columns)
                body = ""
                for row_name, values in rows:
                    body += "<tr><th>" + esc(row_name) + "</th>"
                    for column in columns:
                        key = column.lower().replace(" ", "_").replace(".", "")
                        body += "<td>" + esc(values.get(key) or "—") + "</td>"
                    body += "</tr>"
                return "<h3>" + esc(title) + "</h3><table class='data'><thead><tr><th></th>" + header + "</tr></thead><tbody>" + body + "</tbody></table>"

            longe = prescription.get("longe") or {}
            perto = prescription.get("perto") or {}
            armacao = prescription.get("armacao") or {}
            optical_html = prescription_table("Tabela 1 — Longe", ["ESF", "CIL", "EIXO", "DNP"], [("OD", longe.get("od") or {}), ("OE", longe.get("oe") or {})])
            optical_html += prescription_table("Tabela 2 — Perto", ["ESF", "CIL", "EIXO", "DNP", "ALT.", "AD"], [("OD", perto.get("od") or {}), ("OE", perto.get("oe") or {})])
            optical_html += prescription_table("Medidas das armações", ["Ponte", "Horiz.", "Vert.", "Diag. Maior", "Diâmetro"], [("Medida", armacao)])

            root = Path(__file__).resolve().parents[2]
            logo_candidates = [root / "assets" / "images" / "logootica.png", root / "assets" / "images" / "logo_linda_fashion.png", root / "assets" / "images" / "logo.png", root / "assets" / "logo.png"]
            logo_path = next((candidate for candidate in logo_candidates if candidate.is_file()), None)
            logo_html = '<img src="' + QUrl.fromLocalFile(str(logo_path)).toString() + '" width="100" height="48">' if logo_path else '<b style="color:white">LINDA FASHION</b>'
            order_number = esc(order.get("order_number") or "")
            order_date = esc(str(order.get("created_at") or "")[:10])
            customer_name = esc(customer.get("full_name") or "Venda avulsa")
            customer_document = esc(customer.get("document") or "")
            customer_phone = esc(customer.get("phone") or customer.get("whatsapp") or "")
            customer_address = esc(str(customer.get("street") or "") + " " + str(customer.get("address_number") or "") + " — " + str(customer.get("city") or "") + "/" + str(customer.get("state") or ""))
            notes_html = esc(notes_text).replace("\n", "<br>") or "—"
            html = """<html><meta charset="utf-8"><style>
            body{font-family:Arial,sans-serif;color:#102957;font-size:9pt}
            .brand{width:100%;background:#102957;color:white;border-collapse:collapse}
            .brand td{border:0;padding:12px;vertical-align:middle}
            .brand-title{color:white;font-size:16pt;font-weight:bold}
            h3{color:#102957;font-size:10pt;margin:10px 0 5px}
            table.data{width:100%;border-collapse:collapse;margin-bottom:8px}
            th{background:#EAF0FB;color:#102957}td,th{border:1px solid #CCD6E6;padding:5px;text-align:left}
            .total{font-size:12pt;font-weight:bold;text-align:right;padding:10px}
            .tear{border-top:1px dashed #526079;margin-top:18px;padding-top:10px}
            .stub{font-size:8pt;color:#33496C}
            </style>
            <table class="brand"><tr><td width="120">""" + logo_html + """</td><td><div class="brand-title">ÓTICA LINDA FASHION</div><div>ORDEM DE SERVIÇO / PEDIDO</div></td></tr></table>
            <p><b>Número:</b> """ + order_number + """ &nbsp; <b>Data:</b> """ + order_date + """</p>
            <h3>Dados do cliente</h3><p>""" + customer_name + "<br>" + customer_document + "<br>" + customer_phone + "<br>" + customer_address + """</p>
            <h3>Itens da venda</h3><table class="data"><thead><tr><th>Produto</th><th>SKU</th><th>Qtd.</th><th>Unitário</th><th>Desc.</th><th>Total</th></tr></thead><tbody>""" + lines + """</tbody></table>
            """ + optical_html + """
            <p class="total">Subtotal: """ + _money(order.get("subtotal")) + """<br>Descontos: """ + _money(order.get("discount")) + """<br>Total: """ + _money(order.get("total")) + """</p>
            <p><b>Observações:</b><br>""" + notes_html + """</p>
            <div class="tear"><b>CANHOTO — COMPROVANTE DO CLIENTE</b><div class="stub">
            Ordem: """ + order_number + """ &nbsp; | &nbsp; Cliente: """ + customer_name + """ &nbsp; | &nbsp; Data: """ + order_date + """<br>
            Valor: """ + _money(order.get("total")) + """ &nbsp; | &nbsp; Telefone: """ + customer_phone + """<br>
            Assinatura/retirada: ____________________________________ &nbsp; Data: ____/____/________
            </div></div></html>"""
            document = QTextDocument()
            document.setHtml(html)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            document.print_(printer)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
            QMessageBox.information(self, "PDF gerado", "Ordem de serviço salva e aberta para visualização/impressão:\n" + path)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao gerar PDF", f"Não foi possível gerar o documento.\n\n{exc}")

    def _prepare_whatsapp(self, order_id: str) -> None:
        try:
            order, _items = self._order_data(order_id)
            customer = order.get("customers") or {}
            phone = re.sub(r"\D", "", str(customer.get("whatsapp") or customer.get("phone") or ""))
            if not phone:
                QMessageBox.warning(self, "WhatsApp ausente", "Cadastre o telefone/WhatsApp do cliente antes de iniciar o contato.")
                return
            if len(phone) in (10, 11):
                phone = "55" + phone
            message = f"Olá, {customer.get('full_name') or 'tudo bem'}! Segue a atualização do pedido {order['order_number']} da Ótica Linda Fashion. Valor: {_money(order['total'])}. Para receber a ordem de serviço em PDF, anexe o documento salvo no sistema nesta conversa."
            QDesktopServices.openUrl(QUrl("https://wa.me/" + phone + "?text=" + quote(message)))
            QMessageBox.information(self, "WhatsApp aberto", "A conversa foi aberta com a mensagem preparada. Anexe o PDF manualmente antes de enviar. O sistema não enviou a mensagem nem o arquivo automaticamente.")
        except Exception as exc:
            QMessageBox.critical(self, "WhatsApp", f"Não foi possível preparar a conversa.\n\n{exc}")
