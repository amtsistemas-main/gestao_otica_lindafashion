"""Products catalog page and product editor dialog."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pathlib import Path
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QBrush, QColor, QPixmap, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QGridLayout, QHeaderView, QScrollArea,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSpinBox,
    QFrame, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client
from modules.products.catalog_io import create_template, export_pdf, read_products
from modules.products.models import (
    CONTACT_REPLACEMENTS, FRAME_TYPES, GENDERS, LENS_INDEXES, LENS_TYPES, PRODUCT_TYPES, Product,
)
from modules.products.repository import MemoryProductRepository, SupabaseProductRepository
from modules.products.service import ProductService
from ui.components.ui_kit import make_button, notice
import qtawesome as qta


def _currency(value: Decimal | float | int) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ProductFormDialog(QDialog):
    def __init__(self, product: Product | None = None, parent: QWidget | None = None, suppliers: list[dict] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setMinimumSize(900, 620)
        self.setModal(True)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self._product = product
        self.image_path = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)
        scroll = QScrollArea(self)
        scroll.setObjectName("productFormScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        content.setObjectName("productFormContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Identification
        self.product_type = QComboBox()
        for code, label in PRODUCT_TYPES.items():
            self.product_type.addItem(label, code)
        self.barcode = QLineEdit()
        self.barcode.setPlaceholderText("Bipe o produto ou digite o código")
        self.barcode.setClearButtonEnabled(True)
        # The reader's Enter jumps to the next field instead of saving the form.
        self.barcode.returnPressed.connect(self.focusNextChild)
        self.sku = QLineEdit()
        self.sku.setPlaceholderText("Código interno (opcional)")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex.: Armação Ray-Ban Wayfarer RB2140")
        self.category = QLineEdit()
        self.category.setPlaceholderText("Ex.: Armações de grau, Solar, Lentes multifocais")
        self.brand = QLineEdit()
        self.brand.setPlaceholderText("Marca / fabricante")
        self.supplier = QComboBox()
        self.supplier.addItem("Sem fornecedor vinculado", None)
        for supplier_row in suppliers or []:
            supplier_label = str(supplier_row.get("trade_name") or supplier_row.get("name") or supplier_row.get("legal_name") or "Fornecedor")
            if not supplier_row.get("active", True):
                supplier_label += " (inativo)"
            self.supplier.addItem(supplier_label, supplier_row.get("id"))

        # Optical characteristics
        self.model = QLineEdit()
        self.model.setPlaceholderText("Ex.: RB2140")
        self.color = QLineEdit()
        self.color.setPlaceholderText("Ex.: Preto fosco / 901")
        self.size = QLineEdit()
        self.size.setPlaceholderText("Aro□ponte haste — ex.: 52□18 145")
        self.material = QLineEdit()
        self.material.setPlaceholderText("Ex.: Acetato, Metal, TR90, Policarbonato")
        self.gender = QComboBox()
        for code, label in GENDERS.items():
            self.gender.addItem(label, code)
        self.lens_type = QComboBox()
        for code, label in LENS_TYPES.items():
            self.lens_type.addItem(label, code)
        self.lens_index = QComboBox()
        self.lens_index.setEditable(True)
        for value in LENS_INDEXES:
            self.lens_index.addItem(value or "Não informado", value)
        self.lens_treatment = QLineEdit()
        self.lens_treatment.setPlaceholderText("Ex.: Antirreflexo, filtro de luz azul, fotossensível")
        self.contact_replacement = QComboBox()
        for value in CONTACT_REPLACEMENTS:
            self.contact_replacement.addItem(value or "Não informado", value)

        # Price and stock
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
        self.minimum_stock.setToolTip("Ao atingir este saldo, o produto entra no alerta de reposição.")
        self.reorder_quantity = QSpinBox()
        self.reorder_quantity.setRange(0, 2_000_000_000)
        self.reorder_quantity.setSpecialValueText("Automática")
        self.reorder_quantity.setToolTip("Quantidade sugerida na solicitação de compra. 'Automática' = 2 × ponto de reposição − saldo.")
        self.tracks_stock = QCheckBox("Controlar estoque deste item")
        self.tracks_stock.setChecked(True)
        self.tracks_stock.setToolTip("Desmarque para serviços (montagem, ajuste) que não movimentam estoque.")
        self.tracks_stock.toggled.connect(self._sync_stock_fields)
        self.description = QTextEdit()
        self.description.setPlaceholderText("Detalhes adicionais, garantia, observações comerciais...")
        self.description.setMaximumHeight(78)
        self.active = QCheckBox("Produto ativo para venda")
        self.active.setChecked(True)

        root.addWidget(self._form_card(
            "Identificação",
            "Tipo, códigos de rastreamento (código de barras e SKU), marca e fornecedor.",
            [
                ("Tipo de produto *", self.product_type), ("Nome *", self.name),
                ("Código de barras", self.barcode), ("Código interno / SKU", self.sku),
                ("Marca", self.brand), ("Categoria", self.category),
                ("Fornecedor principal", self.supplier),
            ],
        ))

        self._frame_card = self._form_card(
            "Características",
            "Modelo, cor, tamanho e material — usados na busca e na identificação da peça.",
            [
                ("Modelo", self.model), ("Cor", self.color),
                ("Tamanho", self.size), ("Material", self.material),
                ("Público", self.gender),
            ],
        )
        root.addWidget(self._frame_card)

        self._lens_card = self._form_card(
            "Especificação da lente",
            "Tipo, índice de refração e tratamentos da lente oftálmica.",
            [("Tipo de lente", self.lens_type), ("Índice de refração", self.lens_index), ("Tratamentos", self.lens_treatment)],
        )
        root.addWidget(self._lens_card)

        self._contact_card = self._form_card(
            "Lente de contato",
            "Período de descarte recomendado pelo fabricante.",
            [("Descarte", self.contact_replacement)],
        )
        root.addWidget(self._contact_card)

        stock_card = self._form_card(
            "Preço e estoque",
            "Valores comerciais, saldo atual e ponto de reposição.",
            [
                ("Preço de custo", self.cost_price), ("Preço de venda", self.sale_price),
                ("Desconto padrão", self.discount), ("Quantidade em estoque", self.stock),
                ("Ponto de reposição", self.minimum_stock), ("Qtde. de reposição", self.reorder_quantity),
            ],
        )
        stock_layout = stock_card.layout()
        stock_layout.addWidget(self.tracks_stock)
        description_label = QLabel("Descrição")
        description_label.setObjectName("productFieldLabel")
        stock_layout.addWidget(description_label)
        stock_layout.addWidget(self.description)
        stock_layout.addWidget(self.active)
        root.addWidget(stock_card)

        image_card = QFrame()
        image_card.setObjectName("productImageCard")
        image_card_layout = QVBoxLayout(image_card)
        image_card_layout.setContentsMargins(18, 16, 18, 16)
        image_card_layout.setSpacing(10)
        image_section = QVBoxLayout()
        image_section.setSpacing(8)
        image_heading = QLabel("Imagem do produto")
        image_heading.setObjectName("sectionTitle")
        image_section.addWidget(image_heading)
        image_description = QLabel("Adicione uma imagem para facilitar a identificação no catálogo.")
        image_description.setObjectName("sectionDescription")
        image_description.setWordWrap(True)
        image_section.addWidget(image_description)
        image_row = QHBoxLayout()
        self.image_preview = QLabel("Sem imagem")
        self.image_preview.setObjectName("productImagePreview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFixedSize(112, 92)
        image_row.addWidget(self.image_preview)
        image_controls = QVBoxLayout()
        self.image_url = QLineEdit()
        self.image_url.setPlaceholderText("https://... URL pública da imagem")
        self.image_url.setClearButtonEnabled(True)
        self.image_url.textChanged.connect(self._show_image_url_hint)
        self.upload_image_button = make_button("Enviar do computador", "fa5s.upload", "primaryButton")
        self.upload_image_button.clicked.connect(self._choose_image)
        self.clear_image_button = make_button("Remover", "fa5s.trash-alt", "dangerButton")
        self.clear_image_button.clicked.connect(self._clear_image)
        image_buttons = QHBoxLayout()
        image_buttons.setSpacing(8)
        image_buttons.addWidget(self.upload_image_button, 1)
        image_buttons.addWidget(self.clear_image_button)
        image_controls.addWidget(self.image_url)
        image_controls.addLayout(image_buttons)
        image_row.addLayout(image_controls, 1)
        image_section.addLayout(image_row)
        image_hint = QLabel("PNG, JPG ou WEBP • máximo 8 MB. Upload online usa o armazenamento da organização.")
        image_hint.setObjectName("muted")
        image_hint.setWordWrap(True)
        image_section.addWidget(image_hint)
        image_card_layout.addLayout(image_section)

        price_card = QFrame()
        price_card.setObjectName("priceSummaryCard")
        price_layout = QHBoxLayout(price_card)
        price_layout.setContentsMargins(20, 15, 20, 15)
        price_layout.setSpacing(12)
        price_text_layout = QVBoxLayout()
        price_text_layout.setSpacing(4)
        price_caption = QLabel("PREÇO FINAL COM DESCONTO")
        price_caption.setObjectName("priceSummaryLabel")
        price_text_layout.addWidget(price_caption)
        self.final_price_label = QLabel("R$ 0,00")
        self.final_price_label.setObjectName("priceSummaryValue")
        price_text_layout.addWidget(self.final_price_label)
        self.margin_label = QLabel("Margem bruta: —")
        self.margin_label.setObjectName("muted")
        price_text_layout.addWidget(self.margin_label)
        price_text_layout.addStretch(1)
        price_layout.addLayout(price_text_layout, 1)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)
        bottom_row.addWidget(image_card, 3)
        bottom_row.addWidget(price_card, 2)
        root.addLayout(bottom_row)
        root.addStretch(1)
        for field in (self.sale_price, self.discount, self.cost_price):
            field.valueChanged.connect(self._update_final_price)
        self.product_type.currentIndexChanged.connect(self._sync_type_sections)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar produto")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        if product:
            self.product_type.setCurrentIndex(max(0, self.product_type.findData(product.product_type)))
            self.barcode.setText(product.barcode)
            self.sku.setText(product.sku)
            self.name.setText(product.name)
            self.category.setText(product.category)
            self.brand.setText(product.brand)
            self.model.setText(product.model)
            self.color.setText(product.color)
            self.size.setText(product.size)
            self.material.setText(product.material)
            self.gender.setCurrentIndex(max(0, self.gender.findData(product.gender)))
            self.lens_type.setCurrentIndex(max(0, self.lens_type.findData(product.lens_type)))
            index_position = self.lens_index.findData(product.lens_index)
            if index_position >= 0:
                self.lens_index.setCurrentIndex(index_position)
            else:
                self.lens_index.setEditText(product.lens_index)
            self.lens_treatment.setText(product.lens_treatment)
            self.contact_replacement.setCurrentIndex(max(0, self.contact_replacement.findData(product.contact_replacement)))
            supplier_index = self.supplier.findData(product.supplier_id)
            self.supplier.setCurrentIndex(max(0, supplier_index))
            self.cost_price.setValue(float(product.cost_price))
            self.sale_price.setValue(float(product.sale_price))
            self.discount.setValue(float(product.discount_percent))
            self.stock.setValue(product.stock_quantity)
            self.minimum_stock.setValue(product.minimum_stock)
            self.reorder_quantity.setValue(product.reorder_quantity)
            self.tracks_stock.setChecked(product.tracks_stock)
            self.description.setPlainText(product.description)
            self.image_url.setText(product.image_url)
            if product.image_url.startswith(("https://", "http://")):
                self._show_image_url_hint(product.image_url)
            else:
                self._render_image(product.image_url)
            self.active.setChecked(product.active)
        else:
            self.product_type.setCurrentIndex(self.product_type.findData("armacao"))
            self.barcode.setFocus()
        self._sync_type_sections()
        self._update_final_price()

    @staticmethod
    def _form_card(title: str, description: str, fields: list[tuple[str, QWidget]]) -> QFrame:
        card = QFrame()
        card.setObjectName("productFormCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        caption = QLabel(description)
        caption.setObjectName("sectionDescription")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        for index, (label_text, field) in enumerate(fields):
            row, column = divmod(index, 2)
            label = QLabel(label_text)
            label.setObjectName("productFieldLabel")
            label.setMinimumWidth(150)
            grid.addWidget(label, row, column * 2)
            grid.addWidget(field, row, column * 2 + 1)
        layout.addLayout(grid)
        return card

    def _sync_type_sections(self, *_args: object) -> None:
        """Show only the attributes that make sense for the selected product type."""
        product_type = self.product_type.currentData()
        self._frame_card.setVisible(product_type in FRAME_TYPES or product_type in ("acessorio", "outro"))
        self._lens_card.setVisible(product_type == "lente_oftalmica")
        self._contact_card.setVisible(product_type == "lente_contato")
        if product_type == "servico":
            self.tracks_stock.setChecked(False)
        self.tracks_stock.setEnabled(product_type != "servico")
        self._sync_stock_fields()

    def _sync_stock_fields(self, *_args: object) -> None:
        enabled = self.tracks_stock.isChecked()
        for field in (self.stock, self.minimum_stock, self.reorder_quantity):
            field.setEnabled(enabled)

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
        self.final_price_label.setText(_currency(final))
        cost = Decimal(str(self.cost_price.value()))
        if final > 0:
            margin = ((final - cost) / final * Decimal("100")).quantize(Decimal("0.1"))
            self.margin_label.setText(f"Margem bruta sobre o preço final: {str(margin).replace('.', ',')}% • lucro bruto {_currency(final - cost)}")
        else:
            self.margin_label.setText("Margem bruta: —")

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar imagem do produto", "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        if Path(path).stat().st_size > 8 * 1024 * 1024:
            QMessageBox.warning(self, "Imagem muito grande", "Selecione uma imagem de até 8 MB.")
            return
        self.image_path = path
        self.image_url.clear()
        self._render_image(path)

    def _clear_image(self) -> None:
        self.image_path = ""
        self.image_url.clear()
        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("Sem imagem")

    def _show_image_url_hint(self, value: str) -> None:
        if value.strip():
            self.image_path = ""
            parsed = QUrl(value.strip())
            if parsed.scheme().lower() in {"http", "https"} and parsed.host():
                self.image_preview.setPixmap(QPixmap())
                self.image_preview.setText("URL definida\nA imagem será usada no catálogo")
            else:
                self._render_image(value.strip())

    def _render_image(self, source: str) -> None:
        pixmap = QPixmap(source)
        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Prévia indisponível")
            return
        self.image_preview.setText("")
        self.image_preview.setPixmap(pixmap.scaled(
            QSize(104, 84), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _validate_and_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Dados obrigatórios", "Informe o nome do produto.")
            self.name.setFocus()
            return
        if self.stock.value() < 0 or self.minimum_stock.value() < 0:
            QMessageBox.warning(self, "Estoque inválido", "As quantidades não podem ser negativas.")
            return
        if self.sale_price.value() > 0 and self.cost_price.value() > self.sale_price.value():
            answer = QMessageBox.question(
                self, "Preço abaixo do custo",
                "O preço de venda está abaixo do custo. Deseja salvar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.sale_price.setFocus()
                return
        image_url = self.image_url.text().strip()
        if image_url and not image_url.startswith(("https://", "http://")):
            QMessageBox.warning(self, "URL de imagem inválida", "Informe uma URL pública iniciada por http:// ou https://.")
            self.image_url.setFocus()
            return
        self.accept()

    def _lens_index_value(self) -> str:
        text = self.lens_index.currentText().strip().replace(",", ".")
        return "" if text in ("", "Não informado") else text

    def build_product(self) -> Product:
        previous = self._product
        product = Product(
            id=previous.id if previous else None,
            organization_id=previous.organization_id if previous else None,
            barcode=self.barcode.text().strip(),
            sku=self.sku.text().strip(),
            name=self.name.text().strip(),
            product_type=str(self.product_type.currentData() or "outro"),
            category=self.category.text().strip(),
            brand=self.brand.text().strip(),
            model=self.model.text().strip(),
            color=self.color.text().strip(),
            size=self.size.text().strip(),
            material=self.material.text().strip(),
            gender=str(self.gender.currentData() or ""),
            lens_type=str(self.lens_type.currentData() or ""),
            lens_index=self._lens_index_value(),
            lens_treatment=self.lens_treatment.text().strip(),
            contact_replacement=str(self.contact_replacement.currentData() or ""),
            reorder_quantity=self.reorder_quantity.value(),
            tracks_stock=self.tracks_stock.isChecked(),
            supplier_id=str(self.supplier.currentData()) if self.supplier.currentData() else None,
            supplier_name=self.supplier.currentText() if self.supplier.currentData() else "",
            cost_price=Decimal(str(self.cost_price.value())).quantize(Decimal("0.01")),
            sale_price=Decimal(str(self.sale_price.value())).quantize(Decimal("0.01")),
            discount_percent=Decimal(str(self.discount.value())).quantize(Decimal("0.01")),
            stock_quantity=self.stock.value(),
            minimum_stock=self.minimum_stock.value(),
            description=self.description.toPlainText().strip(),
            image_url=self.image_url.text().strip(),
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
        self._repository = repository
        self._service = ProductService(repository)
        self._visible_products: list[Product] = []
        self._suppliers: list[dict] = []
        self._image_network = QNetworkAccessManager(self)
        self._image_cache: dict[str, QPixmap] = {}
        self._image_requests: set[str] = set()
        if not preview_mode:
            self._load_suppliers()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_bar = QFrame()
        title_bar.setObjectName("windowTitleBar")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 13, 18, 13)
        title_layout.setSpacing(4)
        title = QLabel("Produtos")
        title.setObjectName("windowTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Catálogo, preços, descontos e identificação por código de barras")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addWidget(title_bar, 1)
        root.addLayout(header)

        self.export_button = make_button("Exportar PDF", "fa5s.file-pdf", "secondaryButton")
        self.export_button.setToolTip("Exportar a lista atual como catálogo em PDF")
        self.export_button.clicked.connect(self._export_pdf)
        self.template_button = make_button("Modelo XLS", "fa5s.file-download", "secondaryButton")
        self.template_button.setToolTip("Baixar a planilha modelo para importação")
        self.template_button.clicked.connect(self._download_template)
        self.import_button = make_button("Importar", "fa5s.file-import", "secondaryButton")
        self.import_button.setToolTip("Importar produtos de uma planilha .xlsx ou .xls")
        self.import_button.clicked.connect(self._import_spreadsheet)
        self.new_button = make_button("Novo produto", "fa5s.plus", "primaryButton")
        self.new_button.clicked.connect(self._new_product)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar por nome, código de barras, SKU, marca ou categoria")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(qta.icon("fa5s.search", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.returnPressed.connect(self._search_from_barcode)
        self.search.textChanged.connect(self._search_products)
        search_button = make_button("Ler código", "fa5s.barcode", "secondaryButton")
        search_button.setToolTip("Pesquisar o código bipado ou digitado")
        search_button.clicked.connect(self._search_from_barcode)
        self.type_filter = QComboBox()
        self.type_filter.addItem("Todos os tipos", "")
        for code, label in PRODUCT_TYPES.items():
            self.type_filter.addItem(label, code)
        self.type_filter.setMinimumWidth(170)
        self.type_filter.setToolTip("Filtrar o catálogo por tipo de produto")
        self.type_filter.currentIndexChanged.connect(self._search_products)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.type_filter)
        toolbar.addWidget(search_button)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.template_button)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.new_button)
        root.addLayout(toolbar)

        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • os produtos cadastrados aqui ficam apenas na memória e são apagados ao fechar."))

        summary = QHBoxLayout()
        self.count_label = QLabel("0 produtos")
        self.count_label.setObjectName("summaryStrong")
        self.stock_alert_label = QLabel("0 abaixo do estoque mínimo")
        self.stock_alert_label.setObjectName("muted")
        summary.addWidget(self.count_label)
        summary.addStretch()
        summary.addWidget(self.stock_alert_label)
        root.addLayout(summary)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Imagem", "Código / SKU", "Produto", "Tipo", "Categoria", "Custo", "Venda", "Desconto", "Preço final", "Estoque", "Fornecedor",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (3, 4, 10):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 68)
        self.table.setColumnWidth(1, 135)
        for column in (5, 6, 7, 8, 9):
            self.table.setColumnWidth(column, 100)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.doubleClicked.connect(lambda *_: self._edit_product())
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.edit_button = make_button("Editar selecionado", "fa5s.pen", "secondaryButton")
        self.edit_button.clicked.connect(self._edit_product)
        self.archive_button = make_button("Desativar produto", "fa5s.ban", "dangerButton")
        self.archive_button.clicked.connect(self._archive_product)
        self.refresh_button = make_button("Atualizar lista", "fa5s.sync-alt", "secondaryButton")
        self.refresh_button.clicked.connect(self._search_products)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.archive_button)
        actions.addStretch()
        actions.addWidget(self.refresh_button)
        root.addLayout(actions)

        self._search_products()

    def _load_suppliers(self) -> None:
        """Load active suppliers from the current organization for product assignment."""
        try:
            session = session_manager.current
            if session is None:
                return
            memberships = (
                get_supabase_client().table("organization_members")
                .select("organization_id").eq("user_id", session.user_id)
                .eq("active", True).limit(1).execute().data or []
            )
            if not memberships:
                return
            organization_id = memberships[0].get("organization_id")
            self._suppliers = list(
                get_supabase_client().table("suppliers")
                .select("id,name,legal_name,trade_name,active")
                .eq("organization_id", organization_id)
                .order("name").execute().data or []
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Fornecedores indisponíveis",
                f"Não foi possível carregar a lista de fornecedores. Você ainda pode consultar produtos, mas não poderá vincular um fornecedor agora.\n\n{exc}",
            )
            self._suppliers = []

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
            type_code = self.type_filter.currentData() if hasattr(self, "type_filter") else ""
            if type_code:
                self._visible_products = [item for item in self._visible_products if item.product_type == type_code]
            supplier_names = {str(row.get("id")): str(row.get("trade_name") or row.get("name") or row.get("legal_name") or "") for row in self._suppliers}
            for product in self._visible_products:
                product.supplier_name = supplier_names.get(str(product.supplier_id), "") if product.supplier_id else ""
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
            image_item = QTableWidgetItem()
            image_item.setData(Qt.ItemDataRole.UserRole, product.id)
            image_item.setToolTip(product.image_url or "")
            if product.image_url.startswith("file://"):
                image_path = QUrl(product.image_url).toLocalFile()
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    image_item.setData(Qt.ItemDataRole.DecorationRole, QIcon(pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            elif product.image_url.startswith(("https://", "http://")):
                cached = self._image_cache.get(product.image_url)
                if cached is not None:
                    image_item.setData(Qt.ItemDataRole.DecorationRole, QIcon(cached))
                elif product.image_url not in self._image_requests:
                    self._image_requests.add(product.image_url)
                    reply = self._image_network.get(QNetworkRequest(QUrl(product.image_url)))
                    reply.finished.connect(
                        lambda current=reply, image_url=product.image_url, product_id=product.id:
                        self._finish_image_request(current, image_url, product_id)
                    )
            self.table.setItem(row, 0, image_item)
            characteristics = product.characteristics
            values = [
                product.barcode or product.sku or "—",
                product.name + (f"\n{characteristics}" if characteristics else ""),
                product.type_label, product.category or "—",
                _currency(product.cost_price), _currency(product.sale_price),
                f"{product.discount_percent:.2f}%".replace(".", ","), _currency(product.final_price),
                str(product.stock_quantity) if product.tracks_stock else "Não controla",
                product.supplier_name or "—",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, product.id)
                if offset == 2 and characteristics:
                    item.setToolTip(f"{product.name}\n{characteristics}")
                if offset in (5, 6, 7, 8, 9):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, offset, item)
            if product.needs_reorder:
                stock_item = self.table.item(row, 9)
                stock_item.setForeground(QBrush(QColor("#b42318")))
                stock_item.setToolTip(f"Atingiu o ponto de reposição ({product.minimum_stock}). Sugestão de compra: {product.suggested_reorder_quantity} un.")
            if not product.active:
                for column in range(self.table.columnCount()):
                    self.table.item(row, column).setForeground(QBrush(QColor("#8a94a6")))
        self.count_label.setText(f"{len(self._visible_products)} produto(s)")
        low_stock = sum(1 for item in self._visible_products if item.needs_reorder)
        self.stock_alert_label.setText(f"{low_stock} no ponto de reposição ou abaixo")

    def _finish_image_request(self, reply: QNetworkReply, image_url: str, product_id: str | None) -> None:
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap = QPixmap()
                if pixmap.loadFromData(bytes(reply.readAll())):
                    scaled = pixmap.scaled(
                        44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._image_cache[image_url] = scaled
                    for row, product in enumerate(self._visible_products):
                        if product.id == product_id:
                            item = self.table.item(row, 0)
                            if item is not None:
                                item.setData(Qt.ItemDataRole.DecorationRole, QIcon(scaled))
                            break
        finally:
            self._image_requests.discard(image_url)
            reply.deleteLater()

    def _selected_product(self) -> Product | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._visible_products):
            QMessageBox.information(self, "Selecione um produto", "Selecione um produto na tabela para continuar.")
            return None
        selected_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        return next((item for item in self._visible_products if item.id == selected_id), None)

    def _new_product(self, prefill_barcode: str = "") -> None:
        dialog = ProductFormDialog(parent=self, suppliers=self._suppliers)
        if prefill_barcode:
            dialog.barcode.setText(prefill_barcode)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_dialog_product(dialog)

    def _edit_product(self) -> None:
        product = self._selected_product()
        if product is None:
            return
        dialog = ProductFormDialog(product, self, self._suppliers)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_dialog_product(dialog)

    def _save_dialog_product(self, dialog: ProductFormDialog) -> None:
        try:
            product = dialog.build_product()
            if dialog.image_path:
                if self._preview_mode:
                    product.image_url = Path(dialog.image_path).resolve().as_uri()
                else:
                    uploader = getattr(self._repository, "upload_product_image", None)
                    if uploader is None:
                        raise ConfigurationError("O repositório atual não permite upload de imagens.")
                    product.image_url = uploader(dialog.image_path)
            self._service.save_product(product)
            self.search.clear()
            self._search_products()
            QMessageBox.information(self, "Produto salvo", "Os dados do produto foram salvos.")
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))

    def _download_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar modelo da planilha", "modelo_produtos.xlsx",
            "Planilha Excel (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            create_template(path)
            QMessageBox.information(self, "Modelo criado", f"Modelo salvo em:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao criar modelo", str(exc))

    def _import_spreadsheet(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar produtos", "", "Planilhas Excel (*.xlsx *.xls)",
        )
        if not path:
            return
        try:
            products = read_products(path)
            current = self._service.list_products("", include_inactive=True)
            barcodes = {item.barcode for item in current if item.barcode}
            skus = {item.sku for item in current if item.sku}
            incoming_barcodes: set[str] = set()
            incoming_skus: set[str] = set()
            for product in products:
                if product.barcode and (product.barcode in barcodes or product.barcode in incoming_barcodes):
                    raise ValueError(f"Código de barras duplicado na base ou na planilha: {product.barcode}")
                if product.sku and (product.sku in skus or product.sku in incoming_skus):
                    raise ValueError(f"SKU duplicado na base ou na planilha: {product.sku}")
                if product.barcode:
                    incoming_barcodes.add(product.barcode)
                if product.sku:
                    incoming_skus.add(product.sku)
            answer = QMessageBox.question(
                self, "Confirmar importação",
                f"Foram validados {len(products)} produtos. Deseja importá-los agora?\n\n"
                "A importação adiciona novos produtos; não atualiza registros existentes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            imported = 0
            for product in products:
                self._service.save_product(product)
                imported += 1
            self.search.clear()
            self._search_products()
            QMessageBox.information(self, "Importação concluída", f"{imported} produto(s) importado(s).")
        except Exception as exc:
            QMessageBox.critical(
                self, "Falha na importação",
                f"{exc}\n\nSe o erro ocorreu durante a gravação, verifique a lista de produtos: "
                "operações remotas já concluídas não são revertidas automaticamente.",
            )

    def _export_pdf(self) -> None:
        if not self._visible_products:
            QMessageBox.information(self, "Catálogo vazio", "Não há produtos na lista atual para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar catálogo em PDF", "catalogo_produtos.pdf", "Documento PDF (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_pdf(path, self._visible_products)
            QMessageBox.information(self, "Catálogo exportado", f"PDF salvo em:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar catálogo", str(exc))

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
