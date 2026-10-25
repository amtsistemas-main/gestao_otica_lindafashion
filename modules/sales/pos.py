"""Point of sale: cart, prescription, frame measurements, payments and quotes."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from PySide6.QtCore import QDate, Qt, QStringListModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

from core.organization import OrganizationContext
from core.phone import normalize_br_whatsapp
from modules.lab_orders import statuses as order_statuses
from modules.prescriptions.dialogs import PrescriptionHistoryDialog
from modules.prescriptions.models import Prescription
from modules.prescriptions.repository import PrescriptionRepository
from modules.products.models import PRODUCT_TYPES
from modules.sales.payments import (
    INSTALLMENT_METHODS, PAYMENT_METHODS, RECEIVABLE_METHODS, CartLine, PaymentLine, cart_totals,
    discount_check, installment_schedule, money, remaining_amount, validate_sale,
)
from modules.settings.service import StoreSettings
from ui.components.ui_kit import make_button, notice

SERVICE_ORDER_MARKER = "[[LF_OS_DATA]]"
FRAME_FIELDS = [("ponte", "Ponte"), ("horiz", "Horiz."), ("vert", "Vert."), ("diag_maior", "Diag. maior"), ("diametro", "Diâmetro")]
LENS_TYPES_FOR_LAB = {"lente_oftalmica", "lente_contato"}


def brl(value: Decimal | float) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _preview_catalog() -> tuple[list[dict], list[dict]]:
    products = [
        {"id": "p1", "name": "Armação Ray-Ban RB2140 Preto", "sku": "RB2140-901", "barcode": "7891234567890", "sale_price": 549.90, "discount_percent": 0, "stock_quantity": 6, "tracks_stock": True, "product_type": "armacao"},
        {"id": "p2", "name": "Lente multifocal 1.67 antirreflexo (par)", "sku": "LEN-MF167", "barcode": "7890000000201", "sale_price": 1290.00, "discount_percent": 0, "stock_quantity": 10, "tracks_stock": True, "product_type": "lente_oftalmica"},
        {"id": "p3", "name": "Lente monofocal 1.56 filtro azul (par)", "sku": "LEN-MO156", "barcode": "7890000000202", "sale_price": 390.00, "discount_percent": 0, "stock_quantity": 14, "tracks_stock": True, "product_type": "lente_oftalmica"},
        {"id": "p4", "name": "Montagem e ajuste", "sku": "SRV-MONT", "barcode": "", "sale_price": 60.00, "discount_percent": 0, "stock_quantity": 0, "tracks_stock": False, "product_type": "servico"},
        {"id": "p5", "name": "Estojo rígido premium", "sku": "ACE-EST", "barcode": "7890000000300", "sale_price": 49.90, "discount_percent": 10, "stock_quantity": 25, "tracks_stock": True, "product_type": "acessorio"},
    ]
    customers = [
        {"id": "demo-1", "full_name": "Mariana Costa", "whatsapp": "(82) 99999-1234"},
        {"id": "demo-2", "full_name": "João Santos", "whatsapp": "(82) 98888-4321"},
    ]
    return products, customers


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("surfaceCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 14)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("cardHeading")
    layout.addWidget(heading)
    return frame, layout


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


class PosDialog(QDialog):
    """Sale or quote entry. The database finalizes everything in one transaction."""

    def __init__(self, ctx: OrganizationContext | None, settings: StoreSettings, quote: dict | None = None,
                 quote_items: list[dict] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._settings = settings
        self._quote = quote
        self._idempotency_key = str(uuid4())
        self._prescriptions = PrescriptionRepository(ctx)
        self._lines: list[CartLine] = []
        self._payments: list[PaymentLine] = []
        self._prescription: Prescription | None = None
        self.result: dict | None = None
        self.setWindowTitle("Converter orçamento em venda" if quote else "PDV — nova venda")
        self.setMinimumSize(1180, 720)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self._products, self._customers = self._load_catalog()
        self._products_by_id = {str(row["id"]): row for row in self._products}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)
        title = QFrame()
        title.setObjectName("windowTitleBar")
        title_layout = QHBoxLayout(title)
        title_layout.setContentsMargins(18, 10, 18, 10)
        texts = QVBoxLayout()
        heading = QLabel(f"Converter orçamento {quote.get('order_number')}" if quote else "Ponto de venda")
        heading.setObjectName("windowTitle")
        sub = QLabel("Itens, receita e pagamentos. Estoque, financeiro e pedido de laboratório são gravados juntos ao finalizar.")
        sub.setObjectName("windowSubtitle")
        texts.addWidget(heading)
        texts.addWidget(sub)
        title_layout.addLayout(texts, 1)
        root.addWidget(title)
        if ctx is None:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • catálogo demonstrativo; a venda não será gravada."))

        body = QHBoxLayout()
        body.setSpacing(14)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 6, 0)
        left.setSpacing(12)
        left_scroll.setWidget(left_host)
        body.addWidget(left_scroll, 3)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setMinimumWidth(430)
        right_host = QWidget()
        right = QVBoxLayout(right_host)
        right.setContentsMargins(0, 0, 6, 0)
        right.setSpacing(12)
        right_scroll.setWidget(right_host)
        body.addWidget(right_scroll, 2)
        root.addLayout(body, 1)

        self._build_customer_card(left)
        self._build_items_card(left)
        self._build_optical_card(left)
        left.addStretch(1)
        self._build_totals_card(right)
        self._build_payments_card(right)
        self._build_finish_card(right)
        right.addStretch(1)

        if quote:
            self._load_quote(quote, quote_items or [])
        self._refresh()
        self._update_order_hint()

    # Data -----------------------------------------------------------------
    def _load_catalog(self) -> tuple[list[dict], list[dict]]:
        if self._ctx is None:
            return _preview_catalog()
        client, org = self._ctx.client, self._ctx.organization_id
        products = client.table("products").select(
            "id,name,sku,barcode,sale_price,discount_percent,stock_quantity,tracks_stock,product_type,brand,model,color"
        ).eq("organization_id", org).eq("active", True).order("name").execute().data or []
        customers = client.table("customers").select("id,full_name,whatsapp,whatsapp_consent").eq(
            "organization_id", org).eq("active", True).order("full_name").execute().data or []
        return list(products), list(customers)

    # Layout ---------------------------------------------------------------
    def _build_customer_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Cliente e receita")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.customer.addItem("Venda sem cliente identificado", None)
        for customer in self._customers:
            self.customer.addItem(str(customer.get("full_name") or "Cliente"), customer.get("id"))
        completer = self.customer.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.customer.currentIndexChanged.connect(self._customer_changed)
        row.addWidget(_field_label("Cliente"))
        row.addWidget(self.customer, 1)
        self.prescription_button = make_button("Receitas", "fa5s.eye", "secondaryButton")
        self.prescription_button.setToolTip("Selecionar ou cadastrar a receita usada nesta venda")
        self.prescription_button.clicked.connect(self._choose_prescription)
        row.addWidget(self.prescription_button)
        layout.addLayout(row)
        self.prescription_summary = QLabel("Selecione o cliente para sugerir a receita mais recente.")
        self.prescription_summary.setObjectName("emptyState")
        self.prescription_summary.setWordWrap(True)
        layout.addWidget(self.prescription_summary)
        parent.addWidget(card)

    def _build_items_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Itens")
        entry = QHBoxLayout()
        entry.setSpacing(8)
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Bipe o código de barras ou digite nome/SKU e pressione Enter")
        self.product_search.addAction(qta.icon("fa5s.barcode", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        labels = [self._product_label(product) for product in self._products]
        self._completer_model = QStringListModel(labels)
        product_completer = QCompleter(self._completer_model, self)
        product_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        product_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.product_search.setCompleter(product_completer)
        product_completer.activated.connect(self._add_from_search)
        self.product_search.returnPressed.connect(self._add_from_search)
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 999)
        self.quantity.setFixedWidth(84)
        self.item_discount = QDoubleSpinBox()
        self.item_discount.setRange(0, 100)
        self.item_discount.setDecimals(1)
        self.item_discount.setSuffix(" %")
        self.item_discount.setFixedWidth(104)
        self.item_discount.setToolTip("Desconto percentual aplicado ao item adicionado")
        add = make_button("Adicionar", "fa5s.cart-plus", "primaryButton")
        add.clicked.connect(self._add_from_search)
        entry.addWidget(self.product_search, 1)
        entry.addWidget(_field_label("Qtd."))
        entry.addWidget(self.quantity)
        entry.addWidget(_field_label("Desc."))
        entry.addWidget(self.item_discount)
        entry.addWidget(add)
        layout.addLayout(entry)

        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(["Produto", "Tipo", "Qtd.", "Unitário", "Desconto", "Total", ""])
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.items_table.setColumnWidth(6, 56)
        self.items_table.setMinimumHeight(220)
        layout.addWidget(self.items_table)
        self.items_empty = QLabel("Nenhum item na venda. Use o leitor de código de barras ou a busca acima.")
        self.items_empty.setObjectName("emptyState")
        layout.addWidget(self.items_empty)
        parent.addWidget(card, 1)

    def _build_optical_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Medidas da armação e laboratório")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        self._frame_fields: dict[str, QLineEdit] = {}
        for column, (key, caption) in enumerate(FRAME_FIELDS):
            header = QLabel(caption)
            header.setObjectName("measureHeader")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field = QLineEdit()
            field.setObjectName("measureInput")
            field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field.setPlaceholderText("mm")
            grid.addWidget(header, 0, column)
            grid.addWidget(field, 1, column)
            self._frame_fields[key] = field
        layout.addLayout(grid)
        # Every sale with an identified customer creates its linked order in the chosen status.
        lab_row = QHBoxLayout()
        lab_row.setSpacing(8)
        lab_row.addWidget(_field_label("Status do pedido"))
        self.order_status = QComboBox()
        for status in order_statuses.FLOW:
            self.order_status.addItem(status.label, status.code)
        self.order_status.setToolTip("Etapa atual do pedido desta venda. Mudanças de status avisam o cliente pelo WhatsApp.")
        self.order_status.activated.connect(lambda _index: setattr(self, "_status_chosen", True))
        self.order_status.currentIndexChanged.connect(self._update_order_hint)
        lab_row.addWidget(self.order_status, 1)
        lab_row.addSpacing(8)
        lab_row.addWidget(_field_label("Prazo para o cliente"))
        self.lab_expected = QDateEdit()
        self.lab_expected.setCalendarPopup(True)
        self.lab_expected.setDisplayFormat("dd/MM/yyyy")
        self.lab_expected.setDate(QDate.currentDate().addDays(7))
        lab_row.addWidget(self.lab_expected)
        layout.addLayout(lab_row)
        self.lens_description = QLineEdit()
        self.lens_description.setPlaceholderText("Descrição do pedido (preenchida a partir das lentes; aparece na mensagem ao cliente)")
        layout.addWidget(self.lens_description)
        self.order_hint = QLabel("")
        self.order_hint.setObjectName("muted")
        self.order_hint.setWordWrap(True)
        layout.addWidget(self.order_hint)
        parent.addWidget(card)

    def _build_totals_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Resumo")
        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        self.subtotal_label = QLabel("R$ 0,00")
        self.discount_label = QLabel("R$ 0,00")
        for row, (caption, widget) in enumerate((("Subtotal", self.subtotal_label), ("Descontos", self.discount_label))):
            label = QLabel(caption)
            label.setObjectName("muted")
            grid.addWidget(label, row, 0)
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(widget, row, 1)
        layout.addLayout(grid)
        total_card = QFrame()
        total_card.setObjectName("totalCard")
        total_layout = QHBoxLayout(total_card)
        total_layout.setContentsMargins(14, 10, 14, 10)
        caption = QLabel("TOTAL")
        caption.setObjectName("priceSummaryLabel")
        self.total_label = QLabel("R$ 0,00")
        self.total_label.setObjectName("totalValue")
        total_layout.addWidget(caption)
        total_layout.addStretch(1)
        total_layout.addWidget(self.total_label)
        layout.addWidget(total_card)
        self.discount_status = QLabel("")
        self.discount_status.setWordWrap(True)
        self.discount_status.setVisible(False)
        layout.addWidget(self.discount_status)
        self.discount_reason = QLineEdit()
        self.discount_reason.setPlaceholderText("Motivo do desconto (obrigatório acima do limite da loja)")
        self.discount_reason.setVisible(False)
        layout.addWidget(self.discount_reason)
        parent.addWidget(card)

    def _build_payments_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Pagamento")
        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        self.method = QComboBox()
        for code, label in PAYMENT_METHODS.items():
            self.method.addItem(label, code)
        self.method.currentIndexChanged.connect(self._sync_payment_fields)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 9_999_999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("R$ ")
        self.amount.valueChanged.connect(self._sync_change)
        self.installments = QSpinBox()
        self.installments.setRange(1, 24)
        self.installments.setSuffix("x")
        self.first_due = QDateEdit()
        self.first_due.setCalendarPopup(True)
        self.first_due.setDisplayFormat("dd/MM/yyyy")
        self.first_due.setDate(QDate.currentDate().addDays(30))
        self.down_payment = QCheckBox("Sinal / entrada")
        form.addWidget(_field_label("Forma"), 0, 0)
        form.addWidget(self.method, 0, 1, 1, 3)
        form.addWidget(_field_label("Valor"), 1, 0)
        form.addWidget(self.amount, 1, 1)
        form.addWidget(_field_label("Parcelas"), 1, 2)
        form.addWidget(self.installments, 1, 3)
        self.first_due_label = _field_label("1º vencimento")
        form.addWidget(self.first_due_label, 2, 0)
        form.addWidget(self.first_due, 2, 1)
        form.addWidget(self.down_payment, 2, 2, 1, 2)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        layout.addLayout(form)
        self.change_label = QLabel("")
        self.change_label.setObjectName("infoNotice")
        self.change_label.setVisible(False)
        layout.addWidget(self.change_label)
        add = make_button("Adicionar pagamento", "fa5s.plus-circle", "secondaryButton")
        add.clicked.connect(self._add_payment)
        layout.addWidget(add)
        self.payments_table = QTableWidget(0, 3)
        self.payments_table.setHorizontalHeaderLabels(["Forma", "Valor", ""])
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.payments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.payments_table.setColumnWidth(2, 56)
        self.payments_table.setMinimumHeight(130)
        layout.addWidget(self.payments_table)
        self.remaining_label = QLabel("")
        self.remaining_label.setObjectName("summaryStrong")
        layout.addWidget(self.remaining_label)
        self.schedule_label = QLabel("")
        self.schedule_label.setObjectName("muted")
        self.schedule_label.setWordWrap(True)
        layout.addWidget(self.schedule_label)
        parent.addWidget(card)
        self._sync_payment_fields()

    def _build_finish_card(self, parent: QVBoxLayout) -> None:
        card, layout = _card("Observações")
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Observações da venda / ordem de serviço")
        self.notes.setMaximumHeight(70)
        layout.addWidget(self.notes)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        cancel = make_button("Cancelar", None, "secondaryButton")
        cancel.clicked.connect(self.reject)
        self.quote_button = make_button("Salvar orçamento", "fa5s.file-alt", "secondaryButton")
        self.quote_button.setToolTip("Grava sem baixar estoque nem lançar no financeiro; pode ser convertido em venda depois.")
        self.quote_button.clicked.connect(lambda: self._finalize(as_quote=True))
        self.finish_button = make_button("Finalizar venda", "fa5s.check", "primaryButton")
        self.finish_button.setMinimumHeight(44)
        self.finish_button.clicked.connect(lambda: self._finalize(as_quote=False))
        buttons.addWidget(cancel)
        buttons.addWidget(self.quote_button)
        buttons.addWidget(self.finish_button, 1)
        layout.addLayout(buttons)
        parent.addWidget(card)

    # Customer and prescription -----------------------------------------
    def _customer(self) -> dict | None:
        customer_id = self.customer.currentData()
        return next((row for row in self._customers if row.get("id") == customer_id), None)

    def _customer_changed(self, *_args: object) -> None:
        self._prescription = None
        customer = self._customer()
        if customer:
            try:
                self._prescription = self._prescriptions.latest_for_customer(str(customer["id"]))
            except Exception:
                self._prescription = None
        self._render_prescription()
        self._refresh()
        self._update_order_hint()

    def _choose_prescription(self) -> None:
        customer = self._customer()
        if not customer:
            QMessageBox.information(self, "Selecione o cliente", "A receita é vinculada ao cliente. Selecione o cliente primeiro.")
            return
        dialog = PrescriptionHistoryDialog(customer, self._prescriptions, self._settings.prescription_validity_months, select_mode=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected is not None:
            self._prescription = dialog.selected
        else:
            try:
                self._prescription = self._prescription or self._prescriptions.latest_for_customer(str(customer["id"]))
            except Exception:
                pass
        self._render_prescription()
        self._refresh()

    def _render_prescription(self) -> None:
        item = self._prescription
        if item is None:
            text = ("Cliente sem receita cadastrada — use “Receitas” para registrar." if self._customer()
                    else "Selecione o cliente para sugerir a receita mais recente.")
            self.prescription_summary.setObjectName("emptyState")
            self.prescription_summary.setText(text)
        else:
            notes = item.warnings(self._settings.prescription_validity_months)
            expiry = item.effective_expiry(self._settings.prescription_validity_months)
            text = (f"Receita de {item.prescribed_at.strftime('%d/%m/%Y')} (válida até {expiry.strftime('%d/%m/%Y')})\n"
                    f"OD {item.eye_summary('od')}    |    OE {item.eye_summary('oe')}")
            if item.od_dnp or item.oe_dnp:
                text += f"\nDNP {item.od_dnp or '—'} / {item.oe_dnp or '—'} mm"
            if notes:
                text += "\n⚠ " + " ".join(notes)
            self.prescription_summary.setObjectName("previewNotice" if expiry < date.today() else "infoNotice")
            self.prescription_summary.setText(text)
        self.prescription_summary.style().unpolish(self.prescription_summary)
        self.prescription_summary.style().polish(self.prescription_summary)

    # Cart -----------------------------------------------------------------
    @staticmethod
    def _product_label(product: dict) -> str:
        code = product.get("barcode") or product.get("sku") or ""
        return f"{product.get('name')}" + (f"  [{code}]" if code else "")

    def _find_product(self, text: str) -> dict | None:
        term = text.strip()
        if not term:
            return None
        for product in self._products:
            if term in (product.get("barcode") or "", product.get("sku") or ""):
                return product
        for product in self._products:
            if self._product_label(product) == term:
                return product
        matches = [p for p in self._products if term.casefold() in str(p.get("name") or "").casefold()]
        return matches[0] if len(matches) == 1 else None

    def _add_from_search(self, *_args: object) -> None:
        product = self._find_product(self.product_search.text())
        if product is None:
            if self.product_search.text().strip():
                QMessageBox.information(self, "Produto não encontrado",
                                        "Nenhum produto ativo corresponde ao código ou nome informado. Refine a busca.")
            return
        quantity = self.quantity.value()
        sale_price = money(product.get("sale_price") or 0)
        catalog_discount = Decimal(str(product.get("discount_percent") or 0))
        unit_price = money(sale_price * (1 - catalog_discount / 100))
        existing = next((line for line in self._lines if line.product_id == str(product["id"])), None)
        if existing:
            existing.quantity += quantity
            existing.discount = money(existing.gross * Decimal(str(self.item_discount.value())) / 100) if self.item_discount.value() else existing.discount
        else:
            line = CartLine(
                product_id=str(product["id"]), name=str(product.get("name") or "Produto"), quantity=quantity,
                unit_price=unit_price, product_type=str(product.get("product_type") or ""),
                tracks_stock=bool(product.get("tracks_stock", True)), stock=int(product.get("stock_quantity") or 0),
            )
            line.discount = money(line.gross * Decimal(str(self.item_discount.value())) / 100)
            self._lines.append(line)
        self.product_search.clear()
        self.quantity.setValue(1)
        self.item_discount.setValue(0)
        self._auto_lab_order()
        self._refresh()
        self.product_search.setFocus()

    def _remove_line(self, index: int) -> None:
        if 0 <= index < len(self._lines):
            self._lines.pop(index)
            self._refresh()

    def _auto_lab_order(self) -> None:
        """Suggests the order status from the cart until the user picks one."""
        lens_lines = [line for line in self._lines if line.product_type in LENS_TYPES_FOR_LAB]
        if not getattr(self, "_status_chosen", False):
            suggested = "aguardando_envio" if lens_lines else "entregue"
            self.order_status.setCurrentIndex(max(0, self.order_status.findData(suggested)))
        if lens_lines and not self.lens_description.text().strip():
            self.lens_description.setText(" + ".join(line.name for line in lens_lines))
        self._update_order_hint()

    def _update_order_hint(self, *_args: object) -> None:
        customer = self._customer()
        if not customer:
            text = "Venda avulsa: o pedido é registrado quando a venda tiver cliente identificado."
        else:
            status = order_statuses.BY_CODE.get(str(self.order_status.currentData()))
            label = status.label if status else "—"
            if not customer.get("whatsapp_consent") or not normalize_br_whatsapp(customer.get("whatsapp")):
                text = (f"O pedido será registrado como “{label}”. Este cliente não autorizou ou não tem WhatsApp "
                        "cadastrado: as atualizações não serão enviadas.")
            else:
                text = (f"O pedido será registrado como “{label}” e o cliente recebe as atualizações de status "
                        "pelo WhatsApp da loja (quando a etapa tiver mensagem ativa).")
        self.order_hint.setText(text)

    # Payments -------------------------------------------------------------
    def _sync_payment_fields(self, *_args: object) -> None:
        method = self.method.currentData()
        allows_installments = method in INSTALLMENT_METHODS
        self.installments.setEnabled(allows_installments)
        if not allows_installments:
            self.installments.setValue(1)
        receivable = method in RECEIVABLE_METHODS
        self.first_due.setVisible(receivable)
        self.first_due_label.setVisible(receivable)
        self._sync_change()

    def _sync_change(self, *_args: object) -> None:
        totals = cart_totals(self._lines)
        remaining = remaining_amount(totals.total, self._payments)
        typed = money(self.amount.value())
        if self.method.currentData() == "dinheiro" and remaining > 0 and typed > remaining:
            self.change_label.setText(f"Troco: {brl(typed - remaining)} — será registrado {brl(remaining)} em dinheiro.")
            self.change_label.setVisible(True)
        else:
            self.change_label.setVisible(False)

    def _add_payment(self) -> None:
        totals = cart_totals(self._lines)
        remaining = remaining_amount(totals.total, self._payments)
        if remaining <= 0:
            QMessageBox.information(self, "Pagamento completo", "O total da venda já está coberto pelos pagamentos.")
            return
        amount = money(self.amount.value())
        method = str(self.method.currentData())
        if amount <= 0:
            QMessageBox.warning(self, "Valor inválido", "Informe o valor do pagamento.")
            return
        if amount > remaining:
            if method != "dinheiro":
                QMessageBox.warning(self, "Valor acima do saldo", f"O saldo a pagar é {brl(remaining)}.")
                return
            amount = remaining  # cash change is handed back, not recorded
        self._payments.append(PaymentLine(
            method=method, amount=amount, installments=self.installments.value(),
            is_down_payment=self.down_payment.isChecked(),
            first_due_date=self.first_due.date().toPython() if method in RECEIVABLE_METHODS else None,
        ))
        self.down_payment.setChecked(False)
        self._refresh()

    def _remove_payment(self, index: int) -> None:
        if 0 <= index < len(self._payments):
            self._payments.pop(index)
            self._refresh()

    # Rendering ------------------------------------------------------------
    def _row_button(self, callback) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(4, 2, 4, 2)
        button = QPushButton()
        button.setObjectName("dangerButton")
        button.setIcon(qta.icon("fa5s.trash-alt", color="#D64545"))
        button.setFixedSize(34, 30)
        button.setToolTip("Remover")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return host

    def _refresh(self) -> None:
        totals = cart_totals(self._lines)
        self.items_table.setRowCount(len(self._lines))
        for row, line in enumerate(self._lines):
            values = [line.name, PRODUCT_TYPES.get(line.product_type, "—"), str(line.quantity), brl(line.unit_price),
                      brl(line.discount) if line.discount else "—", brl(line.total)]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column >= 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 2 and line.tracks_stock and line.quantity > line.stock:
                    cell.setForeground(QColor("#C03030"))
                    cell.setToolTip(f"Estoque disponível: {line.stock}")
                self.items_table.setItem(row, column, cell)
            if self.items_table.cellWidget(row, 6) is None:
                self.items_table.setCellWidget(row, 6, self._row_button(lambda checked=False, index=row: self._remove_line(index)))
        self.items_empty.setVisible(not self._lines)

        self.subtotal_label.setText(brl(totals.subtotal))
        self.discount_label.setText(f"{brl(totals.discount)}  ({str(totals.discount_percent).replace('.', ',')}%)")
        self.total_label.setText(brl(totals.total))
        limit = Decimal(str(self._settings.max_discount_percent))
        is_manager = bool(self._ctx and self._ctx.is_manager) or self._ctx is None
        allowed, message = discount_check(totals.discount_percent, limit, is_manager, self.discount_reason.text() or " ")
        above = totals.discount_percent > limit
        self.discount_reason.setVisible(totals.discount > 0)
        if above:
            self.discount_status.setObjectName("previewNotice")
            self.discount_status.setText(message if not allowed else
                                         f"Desconto acima do limite da loja ({str(limit).replace('.', ',')}%) — será registrado como autorizado por administrador.")
        elif totals.discount > 0:
            self.discount_status.setObjectName("infoNotice")
            self.discount_status.setText(f"Desconto dentro do limite da loja ({str(limit).replace('.', ',')}%).")
        self.discount_status.setVisible(totals.discount > 0)
        self.discount_status.style().unpolish(self.discount_status)
        self.discount_status.style().polish(self.discount_status)

        self.payments_table.setRowCount(len(self._payments))
        for row, payment in enumerate(self._payments):
            label = payment.label + (" — a receber" if payment.receivable else "")
            self.payments_table.setItem(row, 0, QTableWidgetItem(label))
            value = QTableWidgetItem(brl(payment.amount))
            value.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.payments_table.setItem(row, 1, value)
            if self.payments_table.cellWidget(row, 2) is None:
                self.payments_table.setCellWidget(row, 2, self._row_button(lambda checked=False, index=row: self._remove_payment(index)))
        remaining = remaining_amount(totals.total, self._payments)
        if remaining > 0:
            self.remaining_label.setText(f"Falta receber: {brl(remaining)}")
        elif remaining < 0:
            self.remaining_label.setText(f"Pagamentos excedem o total em {brl(-remaining)}")
        else:
            self.remaining_label.setText("Pagamento completo ✓" if self._lines else "")
        self.amount.setValue(float(max(remaining, Decimal("0"))))
        schedule_lines = []
        for payment in self._payments:
            if payment.receivable and payment.first_due_date:
                parts = installment_schedule(payment.amount, payment.installments, payment.first_due_date)
                schedule_lines.append(
                    f"{payment.label}: " + "; ".join(f"{due.strftime('%d/%m/%Y')} {brl(value)}" for due, value in parts)
                )
        self.schedule_label.setText("Contas a receber geradas: " + " | ".join(schedule_lines) if schedule_lines else "")
        self.schedule_label.setVisible(bool(schedule_lines))
        self.finish_button.setEnabled(bool(self._lines) and remaining == 0)

    # Quote ------------------------------------------------------------------
    def _load_quote(self, quote: dict, items: list[dict]) -> None:
        if quote.get("customer_id"):
            self.customer.setCurrentIndex(max(0, self.customer.findData(quote.get("customer_id"))))
        for item in items:
            product = self._products_by_id.get(str(item.get("product_id")), {})
            self._lines.append(CartLine(
                product_id=str(item.get("product_id")), name=str(item.get("product_name") or product.get("name") or "Produto"),
                quantity=int(Decimal(str(item.get("quantity") or 1))), unit_price=money(item.get("unit_price") or 0),
                discount=money(item.get("discount") or 0), product_type=str(product.get("product_type") or ""),
                tracks_stock=bool(product.get("tracks_stock", True)), stock=int(product.get("stock_quantity") or 0),
            ))
        for key, value in (quote.get("frame_measurements") or {}).items():
            if key in self._frame_fields:
                self._frame_fields[key].setText(str(value))
        self.discount_reason.setText(str(quote.get("discount_reason") or ""))
        notes = str(quote.get("notes") or "")
        if notes.startswith(SERVICE_ORDER_MARKER):
            notes = notes.partition("\n")[2]
        self.notes.setPlainText(notes)
        if quote.get("prescription_id"):
            try:
                self._prescription = self._prescriptions.get(str(quote["prescription_id"])) or self._prescription
            except Exception:
                pass
            self._render_prescription()
        self._auto_lab_order()
        self.quote_button.setText("Atualizar orçamento")

    # Finalization -----------------------------------------------------------
    def _frame_measurements(self) -> dict:
        return {key: field.text().strip() for key, field in self._frame_fields.items() if field.text().strip()}

    def _stored_notes(self) -> str:
        frame = self._frame_measurements()
        prescription_payload = (self._prescription.to_service_order_payload(frame) if self._prescription
                                else {"longe": {}, "perto": {}, "armacao": frame})
        metadata = {"version": 2, "prescription": prescription_payload}
        return SERVICE_ORDER_MARKER + json.dumps(metadata, ensure_ascii=False, separators=(",", ":")) + "\n" + self.notes.toPlainText().strip()

    def _finalize(self, as_quote: bool) -> None:
        totals = cart_totals(self._lines)
        if not self._lines:
            QMessageBox.warning(self, "Venda vazia", "Adicione ao menos um item.")
            return
        limit = Decimal(str(self._settings.max_discount_percent))
        is_manager = bool(self._ctx and self._ctx.is_manager) or self._ctx is None
        allowed, message = discount_check(totals.discount_percent, limit, is_manager, self.discount_reason.text())
        if not allowed:
            QMessageBox.warning(self, "Desconto não autorizado", message)
            return
        if not as_quote:
            problems = validate_sale(self._lines, self._payments, totals)
            if problems:
                QMessageBox.warning(self, "Confira a venda", "\n".join(f"• {item}" for item in problems))
                return
        params = {
            "p_organization_id": self._ctx.organization_id if self._ctx else None,
            "p_customer_id": self.customer.currentData(),
            "p_items": [line.to_payload() for line in self._lines],
            "p_payments": [] if as_quote else [payment.to_payload() for payment in self._payments],
            "p_notes": self._stored_notes(),
            "p_discount_reason": self.discount_reason.text().strip(),
            "p_prescription_id": self._prescription.id if self._prescription else None,
            "p_frame_measurements": self._frame_measurements(),
            "p_idempotency_key": self._idempotency_key,
            "p_as_quote": as_quote,
            "p_quote_id": (self._quote or {}).get("id"),
            "p_create_lab_order": (not as_quote) and bool(self._customer()),
            "p_order_status": str(self.order_status.currentData() or "aguardando_envio"),
            "p_lab_expected_at": self.lab_expected.date().toPython().isoformat(),
            "p_lens_description": self.lens_description.text().strip(),
        }
        if self._ctx is None:
            kind = "Orçamento" if as_quote else "Venda"
            QMessageBox.information(
                self, "Pré-visualização",
                f"{kind} simulado(a): {len(self._lines)} item(ns), total {brl(totals.total)}.\n"
                + ("" if as_quote else "Pagamentos: " + ", ".join(p.label for p in self._payments) + ".\n")
                + "Nada foi gravado no modo de pré-visualização.",
            )
            return
        self.finish_button.setEnabled(False)
        self.quote_button.setEnabled(False)
        try:
            result = self._ctx.client.rpc("finalize_sales_order_v2", params).execute().data
            if isinstance(result, list):
                result = result[0] if result else None
            if not isinstance(result, dict) or not result.get("id"):
                raise RuntimeError("O banco não confirmou a operação.")
        except Exception as exc:
            self.quote_button.setEnabled(True)
            self._refresh()
            QMessageBox.critical(
                self, "Operação não concluída",
                f"Nada foi gravado parcialmente — a venda é transacional.\n\n{exc}\n\n"
                "Se o erro mencionar 'finalize_sales_order_v2', aplique a migration 202610250004.",
            )
            return
        self.result = {**result, "as_quote": as_quote}
        if as_quote:
            QMessageBox.information(self, "Orçamento salvo", f"Orçamento {result.get('order_number')} salvo — total {brl(totals.total)}.")
        else:
            status = order_statuses.label(str(result.get("order_status") or ""))
            extra = f"\nPedido vinculado registrado como “{status}”." if result.get("lab_order_id") else ""
            duplicate = "\n(Esta venda já havia sido registrada; nenhuma duplicidade foi criada.)" if result.get("duplicate") else ""
            QMessageBox.information(
                self, "Venda finalizada",
                f"Venda {result.get('order_number')} finalizada — total {brl(totals.total)}.\n"
                "Estoque, financeiro e histórico foram atualizados na mesma transação." + extra + duplicate,
            )
        self.accept()
