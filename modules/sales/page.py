"""Sales orders, service-order PDF generation and POS entry point."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from urllib.parse import quote
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
import qtawesome as qta
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from modules.prescriptions.repository import PrescriptionRepository
from modules.sales.document_pdf import SalesDocument, StoreIdentity, build_sales_pdf
from modules.sales.pos import SERVICE_ORDER_MARKER, PosDialog
from modules.settings.service import load_store_settings
from ui.components.ui_kit import make_button, notice


STATUS_LABELS = {
    "draft": "Orçamento", "confirmed": "Confirmada", "completed": "Concluída", "cancelled": "Cancelada",
}
STATUS_COLORS = {
    "draft": "#8A97AB", "confirmed": "#1749C2", "completed": "#0E8A5B", "cancelled": "#C03030",
}


def _money(value: object) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class SalesPage(QDialog):
    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("O módulo Vendas")
        self._client = self._ctx.client if self._ctx else None
        self._organization_id = self._ctx.organization_id if self._ctx else None
        self._user_id = self._ctx.user_id if self._ctx else None
        self._settings = load_store_settings(self._ctx)
        self._orders: list[dict] = []
        self.setWindowTitle("Vendas e PDV — Ótica Linda Fashion")
        self.resize(1260, 800)
        self.setMinimumSize(1000, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        titlebar = QFrame()
        titlebar.setObjectName("windowTitleBar")
        h = QVBoxLayout(titlebar)
        h.setContentsMargins(18, 13, 18, 13)
        h.setSpacing(4)
        title = QLabel("Vendas")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Vendas, orçamentos, ordens de serviço em PDF e ponto de venda integrado ao estoque e ao financeiro.")
        subtitle.setObjectName("windowSubtitle")
        h.addWidget(title); h.addWidget(subtitle)
        header.addWidget(titlebar, 1)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por número do pedido ou cliente…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(qta.icon("fa5s.search", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._filter_orders)
        toolbar.addWidget(self.search, 1)
        self.kind_filter = QComboBox()
        self.kind_filter.addItem("Vendas e orçamentos", "")
        self.kind_filter.addItem("Vendas concluídas", "completed")
        self.kind_filter.addItem("Orçamentos em aberto", "draft")
        self.kind_filter.addItem("Canceladas", "cancelled")
        self.kind_filter.setMinimumWidth(200)
        self.kind_filter.currentIndexChanged.connect(self._filter_orders)
        toolbar.addWidget(self.kind_filter)
        self.refresh_button = make_button("Atualizar", "fa5s.sync-alt", "secondaryButton")
        self.refresh_button.clicked.connect(self._load_orders)
        toolbar.addWidget(self.refresh_button)
        self.new_button = make_button("Nova venda (PDV)", "fa5s.cash-register", "primaryButton")
        self.new_button.clicked.connect(self._new_order)
        toolbar.addWidget(self.new_button)
        root.addLayout(toolbar)
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • o PDV abre com catálogo demonstrativo; o histórico de vendas exige conexão com o Supabase."))
        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setHorizontalHeaderLabels(["Pedido", "Data", "Cliente", "Situação", "Pagamento", "Total", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col in (0, 1, 3, 4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.convert_button = make_button("Converter orçamento em venda", "fa5s.exchange-alt", "primaryButton")
        self.convert_button.clicked.connect(self._convert_quote)
        self.cancel_sale_button = make_button("Cancelar venda", "fa5s.undo", "dangerButton")
        self.cancel_sale_button.setToolTip("Devolve os itens ao estoque, cancela recebíveis e gera estorno do valor recebido (somente administradores).")
        self.cancel_sale_button.clicked.connect(self._cancel_sale)
        actions.addWidget(self.convert_button)
        actions.addStretch(1)
        actions.addWidget(self.cancel_sale_button)
        root.addLayout(actions)
        self._load_orders()

    def _load_orders(self) -> None:
        self.table.setRowCount(0)
        if self._preview_mode:
            self._orders = []
            self._sync_actions()
            return
        try:
            orders = self._client.table("sales_orders").select(
                "id,order_number,status,total,created_at,customer_id,payment_method,quoted_at,customers(full_name,whatsapp,whatsapp_consent)"
            ).eq("organization_id", self._organization_id).order("created_at", desc=True).limit(500).execute().data or []
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar vendas", f"{exc}\n\nConfirme se a migration 202610250004 foi aplicada.")
            orders = []
        self._orders = list(orders)
        for order in orders:
            customer = order.get("customers") or {}
            row = self.table.rowCount(); self.table.insertRow(row)
            status_code = str(order.get("status") or "")
            values = [order.get("order_number",""), str(order.get("created_at",""))[:16].replace("T"," "), (customer.get("full_name") or "Venda avulsa"), STATUS_LABELS.get(status_code, status_code or "—"), order.get("payment_method") or "—", _money(order.get("total"))]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, order.get("id"))
                if col == 3 and status_code in STATUS_COLORS:
                    item.setForeground(QColor(STATUS_COLORS[status_code]))
                if col == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(6, 4, 6, 4)
            actions_layout.setSpacing(6)
            pdf = make_button("PDF", "fa5s.file-pdf", "actionButton")
            pdf.setToolTip("Gerar ou visualizar a ordem de serviço / orçamento em PDF")
            pdf.clicked.connect(lambda checked=False, oid=order["id"]: self._export_pdf(oid))
            wa = make_button("WhatsApp", "fa5b.whatsapp", "actionButton")
            wa.setToolTip("Preparar contato com o cliente no WhatsApp")
            wa.clicked.connect(lambda checked=False, oid=order["id"]: self._prepare_whatsapp(oid))
            actions_layout.addWidget(pdf); actions_layout.addWidget(wa)
            self.table.setCellWidget(row, 6, actions)
        self._filter_orders()

    def _filter_orders(self, *_args: object) -> None:
        term = self.search.text().strip().casefold()
        kind = self.kind_filter.currentData() or ""
        for row in range(self.table.rowCount()):
            haystack = " ".join(
                (self.table.item(row, col).text() if self.table.item(row, col) else "")
                for col in (0, 2)
            ).casefold()
            order = self._order_at(row)
            hidden = (bool(term) and term not in haystack) or (bool(kind) and (order or {}).get("status") != kind)
            self.table.setRowHidden(row, hidden)
        self._sync_actions()

    def _order_at(self, row: int) -> dict | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        order_id = item.data(Qt.ItemDataRole.UserRole)
        return next((order for order in self._orders if order.get("id") == order_id), None)

    def _selected_order(self) -> dict | None:
        row = self.table.currentRow()
        return self._order_at(row) if row >= 0 else None

    def _sync_actions(self) -> None:
        order = self._selected_order()
        status = (order or {}).get("status")
        self.convert_button.setEnabled(status == "draft")
        is_manager = bool(self._ctx and self._ctx.is_manager)
        self.cancel_sale_button.setEnabled(status in ("completed", "draft") and is_manager)

    def _after_pos(self, dialog: PosDialog) -> None:
        self._load_orders()
        result = dialog.result or {}
        if result.get("id") and not result.get("as_quote"):
            # Every completed sale immediately offers the service-order PDF for saving and printing.
            self._export_pdf(result["id"])

    def _new_order(self) -> None:
        dialog = PosDialog(self._ctx, self._settings, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._after_pos(dialog)

    def _convert_quote(self) -> None:
        order = self._selected_order()
        if not order or order.get("status") != "draft":
            QMessageBox.information(self, "Selecione um orçamento", "Selecione um orçamento em aberto para convertê-lo em venda.")
            return
        try:
            quote = self._client.table("sales_orders").select("*").eq("id", order["id"]).eq(
                "organization_id", self._organization_id).limit(1).execute().data or []
            items = self._client.table("sales_order_items").select("product_id,product_name,quantity,unit_price,discount").eq(
                "sales_order_id", order["id"]).eq("organization_id", self._organization_id).execute().data or []
        except Exception as exc:
            QMessageBox.critical(self, "Orçamento indisponível", str(exc))
            return
        if not quote:
            QMessageBox.warning(self, "Orçamento não encontrado", "O orçamento não foi localizado.")
            return
        dialog = PosDialog(self._ctx, self._settings, quote=quote[0], quote_items=list(items), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._after_pos(dialog)

    def _cancel_sale(self) -> None:
        order = self._selected_order()
        if not order:
            return
        reason, accepted = QInputDialog.getText(
            self, "Cancelar venda",
            f"Motivo do cancelamento de {order.get('order_number')}:\n"
            "Os itens voltam ao estoque, recebíveis são cancelados e o valor já recebido gera um estorno a pagar.",
        )
        if not accepted:
            return
        if not reason.strip():
            QMessageBox.warning(self, "Motivo obrigatório", "Informe o motivo do cancelamento.")
            return
        try:
            result = self._client.rpc("cancel_sales_order", {"p_order_id": order["id"], "p_reason": reason.strip()}).execute().data
        except Exception as exc:
            QMessageBox.critical(self, "Cancelamento não realizado", str(exc))
            return
        refund = (result or {}).get("refund", 0) if isinstance(result, dict) else 0
        QMessageBox.information(
            self, "Venda cancelada",
            f"Venda {order.get('order_number')} cancelada. Estoque devolvido."
            + (f"\nEstorno de {_money(refund)} lançado em contas a pagar." if refund else ""),
        )
        self._load_orders()

    def _order_data(self, order_id: str) -> tuple[dict, list[dict]]:
        order_rows = self._client.table("sales_orders").select("*,customers(full_name,document,phone,whatsapp,address_number,street,city,state)").eq("id", order_id).eq("organization_id", self._organization_id).limit(1).execute().data or []
        if not order_rows:
            raise RuntimeError("Pedido não encontrado ou sem permissão.")
        items = self._client.table("sales_order_items").select("product_name,sku,quantity,unit_price,discount,line_total").eq("sales_order_id", order_id).eq("organization_id", self._organization_id).execute().data or []
        return order_rows[0], items

    def _optional_rows(self, query) -> list[dict]:
        """Complementary data (payments, lab order...) must never block the document."""
        try:
            return list(query.execute().data or [])
        except Exception:
            return []

    def _sales_document(self, order_id: str) -> SalesDocument:
        client, org = self._client, self._organization_id
        order_rows = client.table("sales_orders").select(
            "*,customers(full_name,document,phone,whatsapp,email,street,address_number,address_complement,"
            "neighborhood,city,state,postal_code)"
        ).eq("id", order_id).eq("organization_id", org).limit(1).execute().data or []
        if not order_rows:
            raise RuntimeError("Pedido não encontrado ou sem permissão.")
        order = order_rows[0]
        items = client.table("sales_order_items").select(
            "product_name,sku,quantity,unit_price,discount,line_total,product_type"
        ).eq("sales_order_id", order_id).eq("organization_id", org).order("created_at").execute().data or []
        payments = self._optional_rows(
            client.table("sales_order_payments").select("method,amount,installments,is_down_payment,receivable,first_due_date")
            .eq("sales_order_id", order_id).eq("organization_id", org).order("created_at")
        )
        receivables = []
        if any(payment.get("receivable") for payment in payments) and order.get("status") != "cancelled":
            receivables = self._optional_rows(
                client.table("financial_entries").select("due_date,amount,status")
                .eq("organization_id", org).eq("sales_order_id", order_id).eq("direction", "entrada")
                .eq("status", "pendente").order("due_date")
            )
        lab_rows = self._optional_rows(
            client.table("customer_orders").select("expected_at,lens_description,description,status")
            .eq("organization_id", org).eq("sales_order_id", order_id).order("created_at").limit(1)
        )
        prescription = None
        if order.get("prescription_id"):
            try:
                prescription = PrescriptionRepository(self._ctx).get(str(order["prescription_id"]))
            except Exception:
                prescription = None
        seller_id = order.get("seller_id") or order.get("created_by")
        seller_rows = self._optional_rows(
            client.table("organization_members").select("display_name").eq("organization_id", org).eq("user_id", seller_id).limit(1)
        ) if seller_id else []

        notes_text, legacy = str(order.get("notes") or ""), {}
        if notes_text.startswith(SERVICE_ORDER_MARKER):
            metadata_text, _sep, rest = notes_text[len(SERVICE_ORDER_MARKER):].partition("\n")
            try:
                legacy = (json.loads(metadata_text) or {}).get("prescription") or {}
                notes_text = rest
            except (json.JSONDecodeError, TypeError, AttributeError):
                legacy = {}
        frame = order.get("frame_measurements") or legacy.get("armacao") or {}

        settings = load_store_settings(self._ctx)
        store_name = settings.store_name
        if not store_name:
            org_rows = self._optional_rows(client.table("organizations").select("name").eq("id", org).limit(1))
            store_name = (org_rows[0].get("name") if org_rows else "") or "Ótica Linda Fashion"
        store = StoreIdentity(
            name=store_name, document=settings.store_document, phone=settings.store_phone,
            whatsapp=settings.store_whatsapp, email=settings.store_email, address=settings.store_address,
            website=settings.store_website, terms=settings.document_terms,
            quote_validity_days=settings.quote_validity_days,
        )
        return SalesDocument(
            order=order, customer=order.get("customers") or {}, items=list(items), payments=payments,
            receivables=receivables, prescription=prescription, legacy_prescription=legacy,
            frame=frame if isinstance(frame, dict) else {}, lab_order=lab_rows[0] if lab_rows else None,
            seller_name=str((seller_rows[0].get("display_name") if seller_rows else "") or ""),
            notes=notes_text, store=store,
        )

    def _export_pdf(self, order_id: str) -> None:
        try:
            document = self._sales_document(order_id)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao gerar PDF", f"Não foi possível carregar os dados do pedido.\n\n{exc}")
            return
        prefix = {"ORÇAMENTO": "Orçamento", "ORDEM DE SERVIÇO": "OS"}.get(document.kind, "Venda")
        default_name = f"{prefix} {document.order.get('order_number') or 'documento'}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, f"Salvar {document.kind.lower()}", default_name, "Documento PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            build_sales_pdf(path, document)
        except PermissionError:
            QMessageBox.critical(self, "Arquivo em uso", "Não foi possível salvar: o arquivo está aberto em outro programa. "
                                 "Feche-o ou escolha outro nome.")
            return
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao gerar PDF", f"Não foi possível gerar o documento.\n\n{exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

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
