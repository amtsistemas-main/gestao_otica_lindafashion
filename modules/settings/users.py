"""Multilogin: the owner/admin creates logins and chooses the modules each user sees.

Logins are created by the Edge Function ``admin-users`` (server-side key); the desktop
app only sends the signed-in user's token, so no privileged secret ships with it.
"""
from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext
from core.permissions import DEFAULT_MEMBER_MODULES, MODULES, ROLE_LABELS, modules_summary
from ui.components.ui_kit import make_button, notice

FUNCTION_NAME = "admin-users"


class UserAdminError(RuntimeError):
    pass


class UserAdminService:
    def __init__(self, ctx: OrganizationContext | None) -> None:
        self._ctx = ctx

    def _call(self, payload: dict) -> dict:
        if self._ctx is None:
            raise UserAdminError("Disponível somente com login no Supabase.")
        client = self._ctx.client
        headers = {}
        try:
            session = client.auth.get_session()
            if session and session.access_token:
                headers["Authorization"] = f"Bearer {session.access_token}"
        except Exception:
            pass
        try:
            result = client.functions.invoke(FUNCTION_NAME, invoke_options={
                "body": {**payload, "organization_id": self._ctx.organization_id},
                "headers": headers, "responseType": "json",
            })
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            try:
                message = json.loads(message).get("error", message)
            except (ValueError, AttributeError, TypeError):
                pass
            if "404" in str(getattr(exc, "status", "")) or "not found" in str(message).lower():
                message = "A função de usuários (admin-users) não está publicada no Supabase."
            raise UserAdminError(str(message)) from exc
        if isinstance(result, (bytes, str)):
            try:
                result = json.loads(result)
            except ValueError:
                result = {}
        if isinstance(result, dict) and result.get("error"):
            raise UserAdminError(str(result["error"]))
        return result if isinstance(result, dict) else {}

    def list(self) -> list[dict]:
        return list(self._call({"action": "list"}).get("members") or [])

    def create(self, email: str, password: str, display_name: str, role: str, modules: list[str] | None) -> dict:
        return self._call({"action": "create", "email": email, "password": password, "display_name": display_name,
                           "role": role, "allowed_modules": modules})

    def update(self, user_id: str, **changes: object) -> dict:
        return self._call({"action": "update", "user_id": user_id, **changes})

    def reset_password(self, user_id: str, password: str) -> dict:
        return self._call({"action": "reset_password", "user_id": user_id, "password": password})


class UserFormDialog(QDialog):
    """New login or access editing: profile and released modules."""

    def __init__(self, can_create_admin: bool, member: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._member = member
        editing = member is not None
        self.setWindowTitle("Editar acesso" if editing else "Novo usuário")
        self.resize(640, 600)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Editar acesso" if editing else "Novo usuário")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Defina o perfil e os módulos que aparecem para este usuário."
                          if editing else "Crie o login e escolha os módulos que este usuário poderá usar.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)

        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit(str((member or {}).get("display_name") or ""))
        self.name.setMaxLength(80)
        self.name.setPlaceholderText("Nome exibido nas vendas e indicadores")
        form.addRow("Nome *", self.name)
        self.email = QLineEdit(str((member or {}).get("email") or ""))
        self.email.setMaxLength(160)
        self.email.setPlaceholderText("email@exemplo.com")
        self.email.setEnabled(not editing)
        form.addRow("E-mail de acesso *", self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mínimo de 8 caracteres")
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("Repita a senha")
        if not editing:
            form.addRow("Senha inicial *", self.password)
            form.addRow("Confirmar senha *", self.confirm)
        self.role = QComboBox()
        self.role.addItem("Vendedor (módulos escolhidos)", "member")
        if can_create_admin or (member or {}).get("role") == "admin":
            self.role.addItem("Administrador (todos os módulos e configurações)", "admin")
        self.role.setCurrentIndex(max(0, self.role.findData((member or {}).get("role") or "member")))
        self.role.setEnabled(can_create_admin)
        form.addRow("Perfil", self.role)
        root.addLayout(form)

        modules_title = QLabel("Módulos liberados")
        modules_title.setObjectName("sectionTitle")
        root.addWidget(modules_title)
        card = QFrame()
        card.setObjectName("surfaceCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        current = (member or {}).get("allowed_modules")
        selected = set(DEFAULT_MEMBER_MODULES if member is None else (current if current is not None else [k for k, _l, _n in MODULES]))
        self._checks: dict[str, QCheckBox] = {}
        for index, (key, label, _nav) in enumerate(MODULES):
            check = QCheckBox(label)
            check.setChecked(key in selected)
            self._checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        root.addWidget(card)
        self.admin_hint = QLabel("Administradores acessam todos os módulos, gerenciam usuários e alteram as configurações da loja.")
        self.admin_hint.setObjectName("muted")
        self.admin_hint.setWordWrap(True)
        root.addWidget(self.admin_hint)
        hint = QLabel("A visão geral aparece para todos. O Financeiro também é protegido no banco: sem esse módulo, "
                      "o usuário não consegue ler nem alterar lançamentos.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar acesso" if editing else "Criar login")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.role.currentIndexChanged.connect(self._sync_role)
        self._sync_role()

    def _sync_role(self) -> None:
        is_admin = self.role.currentData() == "admin"
        for check in self._checks.values():
            check.setEnabled(not is_admin)
            if is_admin:
                check.setChecked(True)
        self.admin_hint.setVisible(is_admin)

    def values(self) -> dict:
        role = str(self.role.currentData())
        return {
            "display_name": self.name.text().strip(),
            "email": self.email.text().strip().lower(),
            "password": self.password.text(),
            "role": role,
            "allowed_modules": None if role == "admin" else [key for key, check in self._checks.items() if check.isChecked()],
        }

    def _accept(self) -> None:
        data = self.values()
        problems = []
        if not data["display_name"]:
            problems.append("Informe o nome do usuário.")
        if self._member is None:
            if "@" not in data["email"] or "." not in data["email"].split("@")[-1]:
                problems.append("Informe um e-mail válido.")
            if len(data["password"]) < 8:
                problems.append("A senha precisa ter pelo menos 8 caracteres.")
            elif data["password"] != self.confirm.text():
                problems.append("A confirmação não confere com a senha.")
        if problems:
            QMessageBox.warning(self, "Revise os dados", "\n".join(problems))
            return
        self.accept()


class PasswordDialog(QDialog):
    def __init__(self, user_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Redefinir senha")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Redefinir senha")
        title.setObjectName("windowTitle")
        info = QLabel(f"Nova senha para {user_label}. Informe-a ao usuário por um canal seguro.")
        info.setObjectName("windowSubtitle")
        info.setWordWrap(True)
        bar_layout.addWidget(title)
        bar_layout.addWidget(info)
        layout.addWidget(bar)
        form = QFormLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mínimo de 8 caracteres")
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Nova senha", self.password)
        form.addRow("Confirmar", self.confirm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Redefinir senha")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if len(self.password.text()) < 8:
            QMessageBox.warning(self, "Senha curta", "A senha precisa ter pelo menos 8 caracteres.")
            return
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Senhas diferentes", "A confirmação não confere com a senha.")
            return
        self.accept()


def _fmt_datetime(value: object) -> str:
    if not value:
        return "Nunca entrou"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)[:16]


class UsersPanel(QWidget):
    """Users and access management shown in Settings for owners and admins."""

    def __init__(self, ctx: OrganizationContext | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._service = UserAdminService(ctx)
        self._members: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        if ctx is None:
            layout.addWidget(notice("PRÉ-VISUALIZAÇÃO • usuários demonstrativos; a criação de logins exige conexão com o Supabase."))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nome", "E-mail", "Perfil", "Módulos liberados", "Último acesso", "Situação"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(200)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        self.table.itemDoubleClicked.connect(lambda *_: self._edit())
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.new_button = make_button("Novo usuário", "fa5s.user-plus", "primaryButton")
        self.new_button.clicked.connect(self._create)
        self.edit_button = make_button("Editar acesso", "fa5s.user-cog", "secondaryButton")
        self.edit_button.clicked.connect(self._edit)
        self.password_button = make_button("Redefinir senha", "fa5s.key", "secondaryButton")
        self.password_button.clicked.connect(self._reset_password)
        self.toggle_button = make_button("Desativar", "fa5s.user-slash", "dangerButton")
        self.toggle_button.clicked.connect(self._toggle_active)
        for button in (self.new_button, self.edit_button, self.password_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self.toggle_button)
        layout.addLayout(actions)
        self.reload()

    # ---- data -------------------------------------------------------------
    def reload(self) -> None:
        if self._ctx is None:
            self._members = [
                {"user_id": "preview-owner", "display_name": "Ana Silva", "email": "ana@oticalindafashion.com.br",
                 "role": "owner", "active": True, "allowed_modules": None, "last_sign_in_at": datetime.now().isoformat()},
                {"user_id": "preview-seller", "display_name": "Carlos Souza", "email": "carlos@oticalindafashion.com.br",
                 "role": "member", "active": True, "allowed_modules": list(DEFAULT_MEMBER_MODULES), "last_sign_in_at": None},
            ]
        else:
            try:
                self._members = self._service.list()
            except UserAdminError as exc:
                self._members = []
                QMessageBox.warning(self, "Usuários indisponíveis", str(exc))
        self.table.setRowCount(len(self._members))
        for row, member in enumerate(self._members):
            is_self = self._ctx is not None and member.get("user_id") == self._ctx.user_id
            values = [
                str(member.get("display_name") or "—") + (" (você)" if is_self else ""),
                str(member.get("email") or "—"),
                ROLE_LABELS.get(str(member.get("role")), str(member.get("role"))),
                modules_summary(str(member.get("role")), member.get("allowed_modules")),
                _fmt_datetime(member.get("last_sign_in_at")),
                "Ativo" if member.get("active", True) else "Desativado",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 5 and not member.get("active", True):
                    item.setForeground(Qt.GlobalColor.darkRed)
                self.table.setItem(row, column, item)
        self._sync_buttons()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        return self._members[row] if 0 <= row < len(self._members) else None

    def _manageable(self, member: dict | None) -> bool:
        if member is None or member.get("role") == "owner":
            return False
        if self._ctx is not None and self._ctx.role == "admin" and member.get("role") == "admin" \
                and member.get("user_id") != self._ctx.user_id:
            return False
        return True

    def _sync_buttons(self) -> None:
        member = self._selected()
        manageable = self._manageable(member)
        is_self = bool(member and self._ctx and member.get("user_id") == self._ctx.user_id)
        self.edit_button.setEnabled(manageable)
        self.password_button.setEnabled(manageable)
        self.toggle_button.setEnabled(manageable and not is_self)
        active = bool((member or {}).get("active", True))
        self.toggle_button.setText("Desativar" if active else "Reativar")

    @property
    def _can_create_admin(self) -> bool:
        return self._ctx is None or self._ctx.is_owner

    def _run(self, title: str, action) -> bool:
        if self._ctx is None:
            QMessageBox.information(self, "Pré-visualização", "Nada foi gravado no modo de pré-visualização.")
            return False
        try:
            action()
        except UserAdminError as exc:
            QMessageBox.critical(self, title, str(exc))
            return False
        return True

    # ---- actions ----------------------------------------------------------
    def _create(self) -> None:
        dialog = UserFormDialog(self._can_create_admin, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.values()
        if self._run("Login não criado", lambda: self._service.create(
                data["email"], data["password"], data["display_name"], data["role"], data["allowed_modules"])):
            QMessageBox.information(self, "Login criado",
                                    f"{data['display_name']} já pode entrar com o e-mail {data['email']} e a senha definida.")
            self.reload()

    def _edit(self) -> None:
        member = self._selected()
        if not self._manageable(member):
            return
        dialog = UserFormDialog(self._can_create_admin, member=member, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.values()
        changes = {"display_name": data["display_name"], "allowed_modules": data["allowed_modules"]}
        if self._can_create_admin:
            changes["role"] = data["role"]
        if self._run("Acesso não alterado", lambda: self._service.update(member["user_id"], **changes)):
            self.reload()

    def _reset_password(self) -> None:
        member = self._selected()
        if not self._manageable(member):
            return
        dialog = PasswordDialog(str(member.get("display_name") or member.get("email")), self)
        if dialog.exec() == QDialog.DialogCode.Accepted and self._run(
                "Senha não redefinida", lambda: self._service.reset_password(member["user_id"], dialog.password.text())):
            QMessageBox.information(self, "Senha redefinida", "A nova senha já está valendo.")

    def _toggle_active(self) -> None:
        member = self._selected()
        if not self._manageable(member):
            return
        activate = not member.get("active", True)
        verb = "reativar" if activate else "desativar"
        answer = QMessageBox.question(
            self, f"{verb.capitalize()} usuário",
            f"Deseja {verb} {member.get('display_name') or member.get('email')}?"
            + ("" if activate else "\nO usuário perde o acesso imediatamente; o histórico de vendas é mantido."),
        )
        if answer == QMessageBox.StandardButton.Yes and self._run(
                "Situação não alterada", lambda: self._service.update(member["user_id"], active=activate)):
            self.reload()
