"""Products catalog page and product editor dialog."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from modules.products.models import Product
from modules.products.repository import MemoryProductRepository, SupabaseProductRepository
from modules.products.service import ProductService


def _currency(value: Decimal | float | int) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ProductFormDialog(QDialog):
    def __init__(self, product: Product | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setMinimumWidth(560)
        self.setModal(True)
        self._product = product

        root = QVBoxLayout(self)
        title = QLabel("Dados do produto")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("Use o leitor USB no campo de código de barras ou digite o código.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.barcode = QLineEdit()
        self.barcode.setPlaceholderText("Bipe o produto ou digite o código")
        self.barcode.setClearButtonEnabled(True)
        self.sku = QLineEdit()
        self.sku.setPlaceholderText("Código interno (opcional)")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex.: Óculos de sol feminino")
        self.category = QLineEdit()
        self.category.setPlaceholderText("Ex.: Óculos de sol")
        self.brand = QLineEdit()
        self.brand.setPlaceholderText("Marca")
        self.cost_price = self._money_input()
        self.sale_price = self._money_input()
        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setDecimals(2)
        self.discount.setSuffix(" %")
        self.stock = QSpinBox()
        self.stock.setRange(0, 2_000_000_000)
        self.minimum_stock = QSpinBox()
        self.minimum_stock.setRange(0, 2_000_000_000)
        self.description = QTextEdit()
        self.description.setPlaceholderText("Detalhes adicionais, cor, tamanho, material...")
        self.description.setMaximumHeight(78)
        self.active = QCheckBox("Produto ativo para venda")
        self.active.setChecked(True)

        form.addRow("Código de barras", self.barcode)
        form.addRow("Código interno / SKU", self.sku)
        form.addRow("Nome *", self.name)
        form.addRow("Categoria", self.category)
        form.addRow("Marca", self.brand)
        form.addRow("Preço de custo", self.cost_price)
        form.addRow("Preço de venda", self.sale_price)
        form.addRow("Desconto padrão", self.discount)
        form.addRow("Quantidade em estoque", self.stock)
        form.addRow("Estoque mínimo", self.minimum_stock)
        form.addRow("Descrição", self.description)
        form.addRow("", self.active)
        root.addLayout(form)

        self.final_price_label = QLabel("Preço final: R$ 0,00")
        self.final_price_label.setStyleSheet("font-size: 13pt; font-weight: 700; color: #2457d6;")
        root.addWidget(self.final_price_label)
        self.sale_price.valueChanged.connect(self._update_final_price)
        self.discount.valueChanged.connect(self._update_final_price)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar produto")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if product:
            self.barcode.setText(product.barcode)
            self.sku.setText(product.sku)
            self.name.setText(product.name)
            self.category.setText(product.category)
            self.brand.setText(product.brand)
            self.cost_price.setValue(float(product.cost_price))
            self.sale_price.setValue(float(product.sale_price))
            self.discount.setValue(float(product.discount_percent))
            self.stock.setValue(product.stock_quantity)
            self.minimum_stock.setValue(product.minimum_stock)
            self.description.setPlainText(product.description)
            self.active.setChecked(product.active)
        else:
            self.barcode.setFocus()
        self._update_final_price()

    @staticmethod
    def _money_input() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(0, 99_999_999.99)
        field.setDecimals(2)
        field.setSingleStep(5)
        field.setPrefix("R$ ")
        return field

    def _update_final_price(self, *_args: object) -> None:
        final = (
            Decimal(str(self.sale_price.value()))
            * (Decimal("1") - Decimal(str(self.discount.value())) / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.final_price_label.setText(f"Preço final com desconto: {_currency(final)}")

    def _validate_and_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Dados obrigatórios", "Informe o nome do produto.")
            self.name.setFocus()
            return
        if self.stock.value() < 0 or self.minimum_stock.value() < 0:
            QMessageBox.warning(self, "Estoque inválido", "As quantidades não podem ser negativas.")
            return
        self.accept()

    def build_product(self) -> Product:
        previous = self._product
        product = Product(
            id=previous.id if previous else None,
            organization_id=previous.organization_id if previous else None,
            barcode=self.barcode.text().strip(),
            sku=self.sku.text().strip(),
            name=self.name.text().strip(),
            category=self.category.text().strip(),
            brand=self.brand.text().strip(),
            cost_price=Decimal(str(self.cost_price.value())).quantize(Decimal("0.01")),
            sale_price=Decimal(str(self.sale_price.value())).quantize(Decimal("0.01")),
            discount_percent=Decimal(str(self.discount.value())).quantize(Decimal("0.01")),
            stock_quantity=self.stock.value(),
            minimum_stock=self.minimum_stock.value(),
            description=self.description.toPlainText().strip(),
            active=self.active.isChecked(),
        )
        product.validate()
        return product


class ProductsPage(QDialog):
    """Product catalog; preview uses disposable memory, normal mode uses Supabase."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setWindowTitle("Produtos — Ótica Linda Fashion")
        self.resize(1120, 720)
        self.setMinimumSize(860, 600)

        if preview_mode:
            repository = MemoryProductRepository()
        else:
            if not session_manager.is_authenticated or not get_settings().supabase_configured:
                raise ConfigurationError("O catálogo online exige login e configuração do Supabase.")
            repository = SupabaseProductRepository.for_current_user()
        self._service = ProductService(repository)
        self._visible_products: list[Product] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        headings = QVBoxLayout()
        title = QLabel("Produtos")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Catálogo, preços, descontos e identificação por código de barras")
        subtitle.setObjectName("muted")
        headings.addWidget(title)
        headings.addWidget(subtitle)
        header.addLayout(headings)
        header.addStretch()
        self.new_button = QPushButton("+ Novo produto")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new_product)
        header.addWidget(self.new_button)
        root.addLayout(header)

        if preview_mode:
            preview_note = QLabel("PRÉ-VISUALIZAÇÃO • os produtos cadastrados aqui ficam apenas na memória e são apagados ao fechar.")
            preview_note.setWordWrap(True)
            preview_note.setStyleSheet("background:#fff7df; color:#79550b; padding:10px; border-radius:8px;")
            root.addWidget(preview_note)

        summary = QHBoxLayout()
        self.count_label = QLabel("0 produtos")
        self.count_label.setStyleSheet("font-weight:700;")
        self.stock_alert_label = QLabel("0 abaixo do estoque mínimo")
        self.stock_alert_label.setObjectName("muted")
        summary.addWidget(self.count_label)
        summary.addStretch()
        summary.addWidget(self.stock_alert_label)
        root.addLayout(summary)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar por nome, código de barras, SKU, marca ou categoria")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._search_from_barcode)
        self.search.textChanged.connect(self._search_products)
        search_button = QPushButton("Pesquisar / ler código")
        search_button.clicked.connect(self._search_from_barcode)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(search_button)
        root.addLayout(search_row)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Código / SKU", "Produto", "Categoria", "Custo", "Venda", "Desconto", "Preço final", "Estoque",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 150)
        for column in (3, 4, 5, 6, 7):
            self.table.setColumnWidth(column, 105)
        self.table.doubleClicked.connect(lambda *_: self._edit_product())
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.edit_button = QPushButton("Editar selecionado")
        self.edit_button.clicked.connect(self._edit_product)
        self.archive_button = QPushButton("Desativar produto")
        self.archive_button.clicked.connect(self._archive_product)
        self.refresh_button = QPushButton("Atualizar lista")
        self.refresh_button.clicked.connect(self._search_products)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.archive_button)
        actions.addStretch()
        actions.addWidget(self.refresh_button)
        root.addLayout(actions)

        self._search_products()

    def _search_products(self, *_args: object) -> None:
        """Refresh results while typing without interrupting a scanner input."""
        self._load_products(offer_barcode=False)

    def _search_from_barcode(self, *_args: object) -> None:
        """Search on Enter/button and optionally offer to create an unknown barcode."""
        self._load_products(offer_barcode=True)

    def _load_products(self, offer_barcode: bool) -> None:
        term = self.search.text().strip()
        try:
            self._visible_products = self._service.list_products(term)
            self._render_table()
            # A scanner usually appends Enter; if the exact barcode isn't present,
            # offer to start a new product with the scanned value prefilled.
            if offer_barcode and term and not self._visible_products:
                exact = term
                if len(exact) >= 8 and " " not in exact and exact.isalnum():
                    answer = QMessageBox.question(
                        self,
                        "Código não encontrado",
                        f"Nenhum produto encontrado para “{exact}”. Deseja cadastrar este código?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        self._new_product(prefill_barcode=exact)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar produtos", str(exc))

    def _render_table(self) -> None:
        self.table.setRowCount(len(self._visible_products))
        for row, product in enumerate(self._visible_products):
            values = [
                product.barcode or product.sku or "—",
                product.name,
                product.category or "—",
                _currency(product.cost_price),
                _currency(product.sale_price),
                f"{product.discount_percent:.2f}%".replace(".", ","),
                _currency(product.final_price),
                str(product.stock_quantity),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, product.id)
                if column in (3, 4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
            if product.stock_quantity <= product.minimum_stock:
                self.table.item(row, 7).setForeground(QBrush(QColor("#b42318")))
            if not product.active:
                for column in range(self.table.columnCount()):
                    self.table.item(row, column).setForeground(QBrush(QColor("#8a94a6")))
        self.count_label.setText(f"{len(self._visible_products)} produto(s)")
        low_stock = sum(1 for item in self._visible_products if item.stock_quantity <= item.minimum_stock)
        self.stock_alert_label.setText(f"{low_stock} no estoque mínimo ou abaixo")

    def _selected_product(self) -> Product | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._visible_products):
            QMessageBox.information(self, "Selecione um produto", "Selecione um produto na tabela para continuar.")
            return None
        selected_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((item for item in self._visible_products if item.id == selected_id), None)

    def _new_product(self, prefill_barcode: str = "") -> None:
        dialog = ProductFormDialog(parent=self)
        if prefill_barcode:
            dialog.barcode.setText(prefill_barcode)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_dialog_product(dialog)

    def _edit_product(self) -> None:
        product = self._selected_product()
        if product is None:
            return
        dialog = ProductFormDialog(product, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_dialog_product(dialog)

    def _save_dialog_product(self, dialog: ProductFormDialog) -> None:
        try:
            self._service.save_product(dialog.build_product())
            self.search.clear()
            self._search_products()
            QMessageBox.information(self, "Produto salvo", "Os dados do produto foram salvos.")
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))

    def _archive_product(self) -> None:
        product = self._selected_product()
        if product is None:
            return
        answer = QMessageBox.question(
            self,
            "Desativar produto",
            f'Deseja desativar “{product.name}”? O registro será mantido para preservar o histórico.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.archive_product(product.id or "")
            self._search_products()
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível desativar", str(exc))
