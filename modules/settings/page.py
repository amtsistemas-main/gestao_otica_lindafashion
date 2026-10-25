"""Store settings: discount limit, prescription validity, follow-up timing and team names."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHeaderView, QLabel, QMessageBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from modules.settings.service import StoreSettings, load_store_settings, save_store_settings
from ui.components.ui_kit import notice

ROLE_LABELS = {"owner": "Dono", "admin": "Administrador", "member": "Vendedor"}


class SettingsDialog(QDialog):
    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("As configurações")
        self._members: list[dict] = []
        self.setWindowTitle("Configurações — Ótica Linda Fashion")
        self.resize(860, 720)
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
        subtitle = QLabel("Regras comerciais usadas pelo PDV, pelas receitas e pela agenda de relacionamento.")
        subtitle.setObjectName("windowSubtitle")
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • valores padrão; nada é gravado."))
        elif not can_edit:
            root.addWidget(notice("Somente donos e administradores podem alterar as configurações. Você pode editar o seu nome de exibição.", "info"))

        card = QFrame()
        card.setObjectName("surfaceCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(12)
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
        form.addRow("Desconto máximo sem autorização", self.max_discount)
        form.addRow("Validade padrão da receita", self.validity)
        form.addRow("Contato de pós-venda", self.followup)
        form.addRow("Lembrete de revisão da receita", self.review)
        for widget in (self.max_discount, self.validity, self.followup, self.review):
            widget.setEnabled(can_edit)
        root.addWidget(card)

        team_title = QLabel("Equipe (nome exibido nas vendas e indicadores)")
        team_title.setObjectName("sectionTitle")
        root.addWidget(team_title)
        self.team = QTableWidget(0, 3)
        self.team.setHorizontalHeaderLabels(["Nome de exibição (editável)", "Perfil", "Situação"])
        self.team.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.team.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.team.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.team, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar configurações")
        buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self._ctx is not None)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_team()

    def _load_team(self) -> None:
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
                ))
            for row, member in enumerate(self._members):
                item = self.team.item(row, 0)
                new_name = item.text().strip() if item else ""
                if new_name != str(member.get("display_name") or "") and item and item.flags() & Qt.ItemFlag.ItemIsEditable:
                    self._ctx.client.table("organization_members").update({"display_name": new_name}).eq(
                        "organization_id", self._ctx.organization_id).eq("user_id", member["user_id"]).execute()
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", f"{exc}\n\nConfirme se a migration 202610250004 foi aplicada.")
            return
        QMessageBox.information(self, "Configurações salvas", "As configurações foram atualizadas.")
        self.accept()
