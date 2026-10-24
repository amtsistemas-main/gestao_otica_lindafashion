"""Sales orders, service-order PDF generation and POS entry point."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import quote
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
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
        self.setMinimumSize(820, 620)
        self._client, self._organization_id, self._user_id = client, organization_id, user_id
        self._products: list[dict] = []
        self._customers: list[dict] = []
        root = QVBoxLayout(self)
        title = QFrame()
        title.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title)
        heading = QLabel("Nova venda / ordem de serviço")
        heading.setObjectName("windowTitle")
        sub = QLabel("Registre os itens, gere o documento em PDF e prepare o contato com o cliente.")
        sub.setObjectName("windowSubtitle")
        title_layout.addWidget(heading)
        title_layout.addWidget(sub)
        root.addWidget(title)
        form = QFormLayout()
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
        form.addRow("Cliente", self.customer)
        form.addRow("Produto", self.product)
        form.addRow("Quantidade", self.quantity)
        form.addRow("Preço unitário", self.unit_price)
        form.addRow("Desconto do item (R$)", self.discount)
        root.addLayout(form)
        item_actions = QHBoxLayout()
        add_item = QPushButton("Adicionar item")
        add_item.setObjectName("primaryButton")
        add_item.clicked.connect(self._add_item)
        item_actions.addWidget(add_item)
        item_actions.addStretch()
        root.addLayout(item_actions)
        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(["Produto", "Qtd.", "Unitário", "Desconto", "Total"])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.items_table, 1)
        self.payment_method = QComboBox()
        self.payment_method.addItems(["Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência", "A prazo / pendente"])
        root.addWidget(QLabel("Forma de pagamento"))
        root.addWidget(self.payment_method)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(85)
        self.notes.setPlaceholderText("Observações da venda ou da ordem de serviço")
        root.addWidget(self.notes)
        self.total_label = QLabel("Total: R$ 0,00")
        self.total_label.setObjectName("sectionTitle")
        root.addWidget(self.total_label)
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton("Salvar pedido", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.clicked.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
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
        params = {"p_organization_id": self._organization_id, "p_customer_id": self.customer.currentData(), "p_order_number": order_number, "p_subtotal": float(subtotal), "p_discount": float(discount), "p_total": float(total), "p_payment_method": self.payment_method.currentText(), "p_notes": self.notes.toPlainText().strip(), "p_items": payload}
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
                choice = QMessageBox.question(self, "Ordem de serviço", "Pedido salvo. Deseja gerar a ordem de serviço em PDF agora?")
                if choice == QMessageBox.StandardButton.Yes:
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
            path, _ = QFileDialog.getSaveFileName(self, "Salvar ordem de serviço", f'{order["order_number"]}.pdf', "Documento PDF (*.pdf)")
            if not path:
                return
            customer = order.get("customers") or {}
            lines = "".join(f"<tr><td>{r['product_name']}</td><td>{r.get('sku','')}</td><td>{r['quantity']}</td><td>{_money(r['unit_price'])}</td><td>{_money(r['discount'])}</td><td>{_money(r['line_total'])}</td></tr>" for r in items)
            html = f"""<html><meta charset="utf-8"><style>body{{font-family:Arial;color:#102957}}h1{{background:#102957;color:white;padding:16px}}table{{width:100%;border-collapse:collapse}}th{{background:#eaf0fb}}td,th{{border:1px solid #ccd6e6;padding:8px;text-align:left}}.total{{font-size:18px;font-weight:bold;text-align:right;padding:16px}}</style><h1>ÓTICA LINDA FASHION<br><small>ORDEM DE SERVIÇO / PEDIDO</small></h1><p><b>Número:</b> {order['order_number']} &nbsp; <b>Data:</b> {str(order['created_at'])[:10]}</p><h3>Cliente</h3><p>{customer.get('full_name') or 'Venda avulsa'}<br>{customer.get('document') or ''}<br>{customer.get('phone') or ''}<br>{customer.get('street') or ''} {customer.get('address_number') or ''} — {customer.get('city') or ''}/{customer.get('state') or ''}</p><table><thead><tr><th>Produto</th><th>SKU</th><th>Qtd.</th><th>Unitário</th><th>Desc.</th><th>Total</th></tr></thead><tbody>{lines}</tbody></table><p class="total">Subtotal: {_money(order['subtotal'])}<br>Descontos: {_money(order['discount'])}<br>Total: {_money(order['total'])}</p><p><b>Observações:</b><br>{order.get('notes') or '—'}</p><hr><p>Documento gerado pelo sistema Ótica Linda Fashion.</p></html>"""
            document = QTextDocument(); document.setHtml(html)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(path)
            document.print_(printer)
            QMessageBox.information(self, "PDF gerado", f"Ordem de serviço salva em:\n{path}")
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
