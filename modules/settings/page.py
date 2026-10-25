"""Store settings: discount limit, prescription validity, follow-up timing, document identity and team names."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from core.permissions import ROLE_LABELS
from modules.settings.service import StoreSettings, load_store_settings, save_store_settings
from modules.settings.users import UsersPanel
from modules.whatsapp.dialogs import WhatsAppSettingsCard
from modules.whatsapp.service import WhatsAppService
from ui.components.ui_kit import notice


class SettingsDialog(QDialog):
    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("As configurações")
        self._members: list[dict] = []
        self.setWindowTitle("Configurações — Ótica Linda Fashion")
        self.resize(880, 760)
        self.setMinimumSize(640, 480)
        settings = load_store_settings(self._ctx)
        can_edit = self._ctx is not None and self._ctx.is_manager

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Configurações da loja")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Regras comerciais, identificação nos documentos, WhatsApp da loja, usuários e acessos.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • valores padrão; nada é gravado."))
        elif not can_edit:
            root.addWidget(notice("Somente donos e administradores podem alterar as configurações. Você pode editar o seu nome de exibição.", "info"))

        # O conteúdo rola dentro da janela: nada fica cortado em telas menores.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        rules_title = QLabel("Regras comerciais")
        rules_title.setObjectName("sectionTitle")
        body.addWidget(rules_title)
        card = QFrame()
        card.setObjectName("surfaceCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.max_discount = QDoubleSpinBox()
        self.max_discount.setRange(0, 100)
        self.max_discount.setDecimals(1)
        self.max_discount.setSuffix(" %")
        self.max_discount.setValue(settings.max_discount_percent)
        self.max_discount.setToolTip("Vendedores não conseguem finalizar vendas acima deste desconto; administradores podem exceder informando o motivo.")
        self.validity = QSpinBox()
        self.validity.setRange(1, 60)
        self.validity.setSuffix(" meses")
        self.validity.setValue(settings.prescription_validity_months)
        self.followup = QSpinBox()
        self.followup.setRange(1, 90)
        self.followup.setSuffix(" dias após a entrega")
        self.followup.setValue(settings.followup_days_after_delivery)
        self.review = QSpinBox()
        self.review.setRange(0, 180)
        self.review.setSuffix(" dias antes do vencimento")
        self.review.setValue(settings.review_reminder_days_before)
        self.quote_validity = QSpinBox()
        self.quote_validity.setRange(1, 90)
        self.quote_validity.setSuffix(" dias")
        self.quote_validity.setValue(settings.quote_validity_days)
        form.addRow("Desconto máximo sem autorização", self.max_discount)
        form.addRow("Validade padrão da receita", self.validity)
        form.addRow("Validade do orçamento", self.quote_validity)
        form.addRow("Contato de pós-venda", self.followup)
        form.addRow("Lembrete de revisão da receita", self.review)
        body.addWidget(card)

        identity_title = QLabel("Identificação nos documentos (ordem de serviço, orçamento e comprovante)")
        identity_title.setObjectName("sectionTitle")
        identity_title.setWordWrap(True)
        body.addWidget(identity_title)
        identity = QFrame()
        identity.setObjectName("surfaceCard")
        identity_form = QFormLayout(identity)
        identity_form.setContentsMargins(18, 16, 18, 16)
        identity_form.setSpacing(12)
        identity_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.store_name = self._line(settings.store_name, "Ótica Linda Fashion", 120)
        self.store_document = self._line(settings.store_document, "00.000.000/0001-00", 30)
        self.store_phone = self._line(settings.store_phone, "(00) 0000-0000", 30)
        self.store_whatsapp = self._line(settings.store_whatsapp, "(00) 00000-0000", 30)
        self.store_email = self._line(settings.store_email, "contato@sualoja.com.br", 160)
        self.store_address = self._line(settings.store_address, "Rua, número — bairro, cidade/UF — CEP", 240)
        self.store_website = self._line(settings.store_website, "@instagram ou site", 160)
        self.document_terms = QPlainTextEdit(settings.document_terms)
        self.document_terms.setPlaceholderText(
            "Opcional: uma condição por linha (garantia, prazo de retirada, trocas...).\n"
            "Em branco, o documento usa o texto padrão do aplicativo."
        )
        self.document_terms.setFixedHeight(96)
        identity_form.addRow("Nome da loja", self.store_name)
        identity_form.addRow("CNPJ", self.store_document)
        identity_form.addRow("Telefone", self.store_phone)
        identity_form.addRow("WhatsApp", self.store_whatsapp)
        identity_form.addRow("E-mail", self.store_email)
        identity_form.addRow("Endereço", self.store_address)
        identity_form.addRow("Instagram / site", self.store_website)
        identity_form.addRow("Condições impressas", self.document_terms)
        body.addWidget(identity)
        self._editable = [
            self.max_discount, self.validity, self.followup, self.review, self.quote_validity, self.store_name,
            self.store_document, self.store_phone, self.store_whatsapp, self.store_email, self.store_address,
            self.store_website, self.document_terms,
        ]
        for widget in self._editable:
            widget.setEnabled(can_edit)

        whatsapp_title = QLabel("WhatsApp da loja")
        whatsapp_title.setObjectName("sectionTitle")
        body.addWidget(whatsapp_title)
        body.addWidget(WhatsAppSettingsCard(WhatsAppService(self._ctx), can_manage=can_edit))

        self.team: QTableWidget | None = None
        if can_edit or preview_mode:
            # Multilogin: owners/admins create logins and choose each user's modules.
            users_title = QLabel("Usuários e acessos")
            users_title.setObjectName("sectionTitle")
            body.addWidget(users_title)
            users_hint = QLabel("Crie um login para cada pessoa da equipe e escolha os módulos que ela pode usar.")
            users_hint.setObjectName("muted")
            users_hint.setWordWrap(True)
            body.addWidget(users_hint)
            body.addWidget(UsersPanel(self._ctx))
        else:
            team_title = QLabel("Equipe (nome exibido nas vendas e indicadores)")
            team_title.setObjectName("sectionTitle")
            body.addWidget(team_title)
            self.team = QTableWidget(0, 3)
            self.team.setHorizontalHeaderLabels(["Nome de exibição (editável)", "Perfil", "Situação"])
            self.team.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.team.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.team.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.team.setMinimumHeight(180)
            body.addWidget(self.team)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar configurações")
        buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self._ctx is not None)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_team()

    @staticmethod
    def _line(value: str, placeholder: str, max_length: int) -> QLineEdit:
        field = QLineEdit(value)
        field.setPlaceholderText(placeholder)
        field.setMaxLength(max_length)
        return field

    def _load_team(self) -> None:
        if self.team is None:
            return
        if self._ctx is None:
            self._members = [{"user_id": "preview", "display_name": "Ana Silva", "role": "owner", "active": True}]
        else:
            try:
                self._members = list(
                    self._ctx.client.table("organization_members").select("user_id,display_name,role,active")
                    .eq("organization_id", self._ctx.organization_id).execute().data or []
                )
            except Exception:
                self._members = []
        self.team.setRowCount(len(self._members))
        for row, member in enumerate(self._members):
            is_self = self._ctx is not None and member.get("user_id") == self._ctx.user_id
            name = QTableWidgetItem(str(member.get("display_name") or ""))
            editable = self._ctx is not None and (self._ctx.is_manager or is_self)
            flags = name.flags() | Qt.ItemFlag.ItemIsEditable if editable else name.flags() & ~Qt.ItemFlag.ItemIsEditable
            name.setFlags(flags)
            name.setToolTip("Você" if is_self else "")
            self.team.setItem(row, 0, name)
            role = QTableWidgetItem(ROLE_LABELS.get(member.get("role", ""), member.get("role", "")) + (" (você)" if is_self else ""))
            role.setFlags(role.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.team.setItem(row, 1, role)
            status = QTableWidgetItem("Ativo" if member.get("active", True) else "Inativo")
            status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.team.setItem(row, 2, status)

    def _save(self) -> None:
        if self._ctx is None:
            return
        try:
            if self._ctx.is_manager:
                save_store_settings(self._ctx, StoreSettings(
                    max_discount_percent=round(self.max_discount.value(), 1),
                    prescription_validity_months=self.validity.value(),
                    followup_days_after_delivery=self.followup.value(),
                    review_reminder_days_before=self.review.value(),
                    store_name=self.store_name.text().strip(),
                    store_document=self.store_document.text().strip(),
                    store_phone=self.store_phone.text().strip(),
                    store_whatsapp=self.store_whatsapp.text().strip(),
                    store_email=self.store_email.text().strip(),
                    store_address=self.store_address.text().strip(),
                    store_website=self.store_website.text().strip(),
                    quote_validity_days=self.quote_validity.value(),
                    document_terms=self.document_terms.toPlainText().strip()[:2000],
                ))
            for row, member in enumerate(self._members if self.team is not None else []):
                item = self.team.item(row, 0)
                new_name = item.text().strip() if item else ""
                if new_name != str(member.get("display_name") or "") and item and item.flags() & Qt.ItemFlag.ItemIsEditable:
                    self._ctx.client.table("organization_members").update({"display_name": new_name}).eq(
                        "organization_id", self._ctx.organization_id).eq("user_id", member["user_id"]).execute()
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", f"{exc}\n\nConfirme se as migrations 202610250004 e 202610250009 foram aplicadas.")
            return
        QMessageBox.information(self, "Configurações salvas", "As configurações foram atualizadas.")
        self.accept()
