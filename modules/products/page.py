"""Products catalog page and product editor dialog."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pathlib import Path
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QBrush, QColor, QPixmap, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from modules.products.catalog_io import create_template, export_pdf, read_products
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
        self.image_path = ""

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

        image_section = QVBoxLayout()
        image_section.setSpacing(8)
        image_heading = QLabel("Imagem do produto")
        image_heading.setObjectName("sectionTitle")
        image_section.addWidget(image_heading)
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
        self.upload_image_button = QPushButton("Enviar imagem do computador")
        self.upload_image_button.clicked.connect(self._choose_image)
        self.clear_image_button = QPushButton("Remover imagem")
        self.clear_image_button.clicked.connect(self._clear_image)
        image_controls.addWidget(self.image_url)
        image_controls.addWidget(self.upload_image_button)
        image_controls.addWidget(self.clear_image_button)
        image_row.addLayout(image_controls, 1)
        image_section.addLayout(image_row)
        image_section.addWidget(QLabel("PNG, JPG ou WEBP • máximo 8 MB. Upload online usa o armazenamento da organização."))
        root.addLayout(image_section)

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
            self.image_url.setText(product.image_url)
            self._render_image(product.image_url)
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
        image_url = self.image_url.text().strip()
        if image_url and not image_url.startswith(("https://", "http://")):
            QMessageBox.warning(self, "URL de imagem inválida", "Informe uma URL pública iniciada por http:// ou https://.")
            self.image_url.setFocus()
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
        self._image_network = QNetworkAccessManager(self)
        self._image_cache: dict[str, QPixmap] = {}
        self._image_requests: set[str] = set()

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
        self.export_button = QPushButton("Exportar catálogo PDF")
        self.export_button.setObjectName("secondaryQuickAction")
        self.export_button.clicked.connect(self._export_pdf)
        self.template_button = QPushButton("Baixar modelo XLS")
        self.template_button.setObjectName("secondaryQuickAction")
        self.template_button.clicked.connect(self._download_template)
        self.import_button = QPushButton("Importar planilha")
        self.import_button.setObjectName("secondaryQuickAction")
        self.import_button.clicked.connect(self._import_spreadsheet)
        self.new_button = QPushButton("+ Novo produto")
        self.new_button.setObjectName("primaryButton")
        self.new_button.clicked.connect(self._new_product)
        header.addWidget(self.export_button)
        header.addWidget(self.template_button)
        header.addWidget(self.import_button)
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

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Imagem", "Código / SKU", "Produto", "Categoria", "Custo", "Venda", "Desconto", "Preço final", "Estoque",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 68)
        self.table.setColumnWidth(1, 135)
        for column in (4, 5, 6, 7, 8):
            self.table.setColumnWidth(column, 105)
        self.table.verticalHeader().setDefaultSectionSize(58)
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
            values = [
                product.barcode or product.sku or "—", product.name, product.category or "—",
                _currency(product.cost_price), _currency(product.sale_price),
                f"{product.discount_percent:.2f}%".replace(".", ","), _currency(product.final_price),
                str(product.stock_quantity),
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, product.id)
                if offset in (4, 5, 6, 7, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, offset, item)
            if product.stock_quantity <= product.minimum_stock:
                self.table.item(row, 8).setForeground(QBrush(QColor("#b42318")))
            if not product.active:
                for column in range(self.table.columnCount()):
                    self.table.item(row, column).setForeground(QBrush(QColor("#8a94a6")))
        self.count_label.setText(f"{len(self._visible_products)} produto(s)")
        low_stock = sum(1 for item in self._visible_products if item.stock_quantity <= item.minimum_stock)
        self.stock_alert_label.setText(f"{low_stock} no estoque mínimo ou abaixo")

    def _finish_image_request(self, reply: object, image_url: str, product_id: str | None) -> None:
        try:
            if reply.error() == reply.NetworkError.NoError:
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
