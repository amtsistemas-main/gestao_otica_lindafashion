"""Sales orders, service-order PDF generation and POS entry point."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from urllib.parse import quote
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextDocument
from PySide6.QtPrintSupport import QPrinter
import qtawesome as qta
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from modules.sales.pos import PosDialog
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
            document_kind = "ORÇAMENTO" if order.get("status") == "draft" else "ORDEM DE SERVIÇO"
            order_number = esc(order.get("order_number") or "")
            order_date = esc(str(order.get("created_at") or "")[:10])
            customer_name = esc(customer.get("full_name") or "Venda avulsa")
            customer_document = esc(customer.get("document") or "")
            customer_phone = esc(customer.get("phone") or customer.get("whatsapp") or "")
            customer_address = esc(str(customer.get("street") or "") + " " + str(customer.get("address_number") or "") + " — " + str(customer.get("city") or "") + "/" + str(customer.get("state") or ""))
            notes_html = esc(notes_text).replace("\n", "<br>") or "—"
            html = """<html><head><meta charset="utf-8"><style>
            @page { margin: 28px; }
            body { font-family: Arial, sans-serif; color: #233653; font-size: 8.5pt; }
            .brand { width:100%; border-collapse:collapse; background:#102957; color:#FFFFFF; }
            .brand td { border:0; padding:14px 16px; vertical-align:middle; }
            .brand-title { color:#FFFFFF; font-size:19pt; font-weight:bold; letter-spacing:1px; }
            .brand-sub { color:#DCE7F7; font-size:8pt; padding-top:4px; }
            .doc-label { color:#DCE7F7; font-size:8pt; text-align:right; }
            .doc-number { color:#FFFFFF; font-size:12pt; font-weight:bold; text-align:right; }
            .accent { height:4px; background:#2165F5; }
            .meta { width:100%; border-collapse:collapse; margin:12px 0; }
            .meta td { width:50%; border:1px solid #DFE7F2; background:#F7F9FD; padding:9px 10px; vertical-align:top; }
            .label { color:#72819A; font-size:7pt; font-weight:bold; text-transform:uppercase; }
            .value { color:#102957; font-size:9pt; font-weight:bold; padding-top:3px; }
            h3 { color:#102957; font-size:9.5pt; margin:13px 0 6px; padding-bottom:4px; border-bottom:2px solid #DCE7F7; }
            table.data { width:100%; border-collapse:collapse; margin:0 0 8px; }
            table.data th { background:#EAF0FB; color:#102957; font-size:7.5pt; font-weight:bold; }
            table.data td, table.data th { border:1px solid #D5DFED; padding:5px 6px; text-align:left; }
            table.data tr:nth-child(even) td { background:#F8FAFE; }
            .optical-wrap { width:100%; border-collapse:collapse; }
            .optical-wrap td { border:0; padding:0 5px 0 0; vertical-align:top; }
            .optical-title { color:#244B86; font-size:8pt; font-weight:bold; margin:4px 0; }
            .totals { width:100%; border-collapse:collapse; margin-top:8px; }
            .totals td { border:0; padding:4px 7px; text-align:right; }
            .grand-total { background:#102957; color:#FFFFFF; font-size:13pt; font-weight:bold; padding:9px; }
            .notes { border:1px solid #DFE7F2; background:#FAFBFE; padding:8px 10px; }
            .tear { border-top:1px dashed #7890B4; margin-top:20px; padding-top:10px; }
            .stub-title { color:#102957; font-size:9pt; font-weight:bold; }
            .stub { color:#405575; font-size:8pt; }
            .signature { color:#60718D; font-size:7.5pt; padding-top:10px; }
            </style></head><body>
            <table class="brand"><tr>
              <td width="112">""" + logo_html + """</td>
              <td><div class="brand-title">ÓTICA LINDA FASHION</div><div class="brand-sub">VISÃO • ESTILO • VOCÊ &nbsp; | &nbsp; CUIDADO ÓPTICO COM QUALIDADE</div></td>
              <td width="160"><div class="doc-label">""" + document_kind + """</div><div class="doc-number">""" + order_number + """</div><div class="doc-label">EMITIDA EM """ + order_date + """</div></td>
            </tr></table><div class="accent"></div>
            <table class="meta"><tr>
              <td><div class="label">Cliente</div><div class="value">""" + (customer_name or "Venda avulsa") + """</div><div>""" + customer_document + """</div></td>
              <td><div class="label">Contato</div><div class="value">""" + (customer_phone or "Não informado") + """</div><div>""" + (customer_address or "Endereço não informado") + """</div></td>
            </tr></table>
            <h3>01 &nbsp; Produtos e serviços</h3>
            <table class="data"><thead><tr><th>Produto</th><th>Referência</th><th>Qtd.</th><th>Preço unitário</th><th>Desconto</th><th>Total</th></tr></thead><tbody>""" + lines + """</tbody></table>
            <h3>02 &nbsp; Receita e medidas ópticas</h3>
            <table class="optical-wrap"><tr>
              <td width="34%"><div class="optical-title">VISÃO DE LONGE</div>""" + prescription_table("Longe", ["ESF", "CIL", "EIXO", "DNP"], [("OD", longe.get("od") or {}), ("OE", longe.get("oe") or {})]) + """</td>
              <td width="42%"><div class="optical-title">VISÃO DE PERTO</div>""" + prescription_table("Perto", ["ESF", "CIL", "EIXO", "DNP", "ALT.", "AD"], [("OD", perto.get("od") or {}), ("OE", perto.get("oe") or {})]) + """</td>
              <td width="24%"><div class="optical-title">ARMAÇÃO</div>""" + prescription_table("Medidas", ["Ponte", "Horiz.", "Vert.", "Diag. Maior", "Diâmetro"], [("Medida", armacao)]) + """</td>
            </tr></table>
            <table class="totals">
              <tr><td>Subtotal: """ + _money(order.get("subtotal")) + """</td></tr>
              <tr><td>Descontos: """ + _money(order.get("discount")) + """</td></tr>
              <tr><td class="grand-total">TOTAL DA VENDA &nbsp; """ + _money(order.get("total")) + """</td></tr>
            </table>
            <h3>03 &nbsp; Observações</h3><div class="notes">""" + notes_html + """</div>
            <div class="tear"><div class="stub-title">CANHOTO DO CLIENTE &nbsp; | &nbsp; COMPROVANTE DE PEDIDO</div>
              <div class="stub">Ordem: <b>""" + order_number + """</b> &nbsp; • &nbsp; Cliente: <b>""" + customer_name + """</b> &nbsp; • &nbsp; Data: """ + order_date + """<br>
              Valor do pedido: <b>""" + _money(order.get("total")) + """</b> &nbsp; • &nbsp; Contato: """ + customer_phone + """</div>
              <div class="signature">Assinatura / retirada: ______________________________________ &nbsp;&nbsp; Data: ____/____/________</div>
            </div></body></html>"""
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
