"""Relationship hub: follow-up agenda, repurchase segments and campaign actions."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from core.phone import format_br_phone, normalize_br_whatsapp
from modules.crm.segments import SEGMENTS, TASK_TYPES, CustomerInsight, segment_customers, whatsapp_message
from modules.lab_orders.page import StageChip
from modules.settings.service import load_store_settings, store_display_name
from modules.whatsapp.service import WhatsAppService, describe_result
from ui.components.ui_kit import MetricTile, make_button, notice


def _fmt(value: object) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y") if value else "—"
    except ValueError:
        return "—"


def brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _preview_data(today: date) -> dict:
    customers = [
        {"id": "demo-1", "full_name": "Mariana Costa", "whatsapp": "(82) 99999-1234", "whatsapp_consent": True, "birth_date": f"1990-{today.month:02d}-12", "preferred_brands": "Ray-Ban, Vogue", "active": True},
        {"id": "demo-2", "full_name": "João Santos", "whatsapp": "(82) 98888-4321", "whatsapp_consent": True, "birth_date": "1985-03-02", "preferred_brands": "Oakley", "active": True},
        {"id": "demo-3", "full_name": "Beatriz Almeida", "whatsapp": "(82) 97777-2222", "whatsapp_consent": False, "birth_date": None, "preferred_brands": "", "active": True},
        {"id": "demo-4", "full_name": "Carlos Lima", "whatsapp": "", "whatsapp_consent": False, "birth_date": None, "preferred_brands": "Prada", "active": True},
    ]
    orders = [
        {"customer_id": "demo-1", "status": "completed", "total": 1890, "created_at": (today - timedelta(days=20)).isoformat()},
        {"customer_id": "demo-1", "status": "completed", "total": 620, "created_at": (today - timedelta(days=400)).isoformat()},
        {"customer_id": "demo-1", "status": "completed", "total": 980, "created_at": (today - timedelta(days=700)).isoformat()},
        {"customer_id": "demo-2", "status": "completed", "total": 790, "created_at": (today - timedelta(days=330)).isoformat()},
        {"customer_id": "demo-4", "status": "completed", "total": 450, "created_at": (today - timedelta(days=640)).isoformat()},
    ]
    prescriptions = [
        {"customer_id": "demo-2", "prescribed_at": (today - timedelta(days=350)).isoformat(), "expires_at": None, "active": True},
        {"customer_id": "demo-1", "prescribed_at": (today - timedelta(days=30)).isoformat(), "expires_at": None, "active": True},
    ]
    tasks = [
        {"id": "t1", "customer_id": "demo-1", "task_type": "pos_venda", "title": "Pós-venda: adaptação aos óculos (V-20261005-001)", "due_date": (today - timedelta(days=1)).isoformat(), "status": "aberta", "notes": ""},
        {"id": "t2", "customer_id": "demo-2", "task_type": "revisao_receita", "title": "Revisão da receita (vence em breve)", "due_date": today.isoformat(), "status": "aberta", "notes": ""},
        {"id": "t3", "customer_id": "demo-4", "task_type": "reativacao", "title": "Reativação — cliente inativo", "due_date": (today + timedelta(days=4)).isoformat(), "status": "aberta", "notes": ""},
    ]
    return {"customers": customers, "orders": orders, "prescriptions": prescriptions, "tasks": tasks}


class CrmPage(QDialog):
    """Agenda de relacionamento e segmentação para recompra."""

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("O módulo Relacionamento")
        self._settings = load_store_settings(self._ctx)
        self._customers: dict[str, dict] = {}
        self._tasks: list[dict] = []
        self._visible_tasks: list[dict] = []
        self._insights: dict[str, CustomerInsight] = {}
        self._segment = "receita_vencendo"
        self._segment_rows: list[CustomerInsight] = []
        self._preview: dict = _preview_data(date.today()) if preview_mode else {}
        self.setWindowTitle("Relacionamento — Ótica Linda Fashion")
        self.resize(1320, 840)
        self.setMinimumSize(1080, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Relacionamento e recompra")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Pós-venda, revisão de receita, aniversários e reativação — com segmentos para gerar novas vendas sem depender de tráfego pago.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • clientes e tarefas demonstrativos; alterações não são gravadas."))

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.today_tile = MetricTile("Follow-ups para hoje", "—", "fa5s.calendar-check", "primary")
        self.late_tile = MetricTile("Follow-ups atrasados", "—", "fa5s.exclamation-circle", "danger")
        self.review_tile = MetricTile("Receitas vencendo", "—", "fa5s.eye", "warning")
        self.risk_tile = MetricTile("Clientes em risco", "—", "fa5s.user-clock", "navy")
        for tile in (self.today_tile, self.late_tile, self.review_tile, self.risk_tile):
            tiles.addWidget(tile, 1)
        root.addLayout(tiles)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_agenda(), "Agenda de follow-ups")
        self.tabs.addTab(self._build_segments(), "Segmentos para recompra")
        root.addWidget(self.tabs, 1)
        self._load()

    # Layout ---------------------------------------------------------------
    def _build_agenda(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        toolbar = QHBoxLayout()
        self.agenda_filter = QComboBox()
        self.agenda_filter.addItems(["Hoje e atrasadas", "Próximos 7 dias", "Todas em aberto", "Concluídas recentemente"])
        self.agenda_filter.setMinimumWidth(210)
        self.agenda_filter.currentIndexChanged.connect(self._render_tasks)
        self.task_type_filter = QComboBox()
        self.task_type_filter.addItem("Todos os tipos", "")
        for code, caption in TASK_TYPES.items():
            self.task_type_filter.addItem(caption, code)
        self.task_type_filter.currentIndexChanged.connect(self._render_tasks)
        toolbar.addWidget(self.agenda_filter)
        toolbar.addWidget(self.task_type_filter)
        toolbar.addStretch(1)
        refresh = make_button("Atualizar", "fa5s.sync-alt", "secondaryButton")
        refresh.clicked.connect(self._load)
        new = make_button("Nova tarefa", "fa5s.plus", "primaryButton")
        new.clicked.connect(self._new_task)
        toolbar.addWidget(refresh)
        toolbar.addWidget(new)
        layout.addLayout(toolbar)
        self.tasks_table = QTableWidget(0, 6)
        self.tasks_table.setHorizontalHeaderLabels(["Vencimento", "Cliente", "Tipo", "Tarefa", "WhatsApp", "Situação"])
        self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.tasks_table.horizontalHeader()
        for column in range(6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tasks_table, 1)
        actions = QHBoxLayout()
        whatsapp = make_button("Abrir WhatsApp", "fa5b.whatsapp", "secondaryButton")
        whatsapp.setToolTip("Abre a conversa com mensagem sugerida (somente clientes com consentimento)")
        whatsapp.clicked.connect(self._task_whatsapp)
        reschedule = make_button("Reagendar", "fa5s.calendar-alt", "secondaryButton")
        reschedule.clicked.connect(self._reschedule)
        complete = make_button("Concluir e registrar contato", "fa5s.check", "primaryButton")
        complete.clicked.connect(self._complete_task)
        cancel = make_button("Descartar", "fa5s.times", "dangerButton")
        cancel.clicked.connect(lambda: self._set_task_status("cancelada"))
        actions.addWidget(whatsapp)
        actions.addWidget(reschedule)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(complete)
        layout.addLayout(actions)
        return host

    def _build_segments(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self._chips: list[StageChip] = []
        for code, (caption, _description, icon, color) in SEGMENTS.items():
            chip = StageChip(code, caption, color, icon)
            chip.clicked.connect(lambda checked=False, value=code: self._set_segment(value))
            chips.addWidget(chip, 1)
            self._chips.append(chip)
        layout.addLayout(chips)
        self.segment_description = QLabel("")
        self.segment_description.setObjectName("infoNotice")
        self.segment_description.setWordWrap(True)
        layout.addWidget(self.segment_description)
        self.segment_table = QTableWidget(0, 7)
        self.segment_table.setHorizontalHeaderLabels(["Cliente", "Compras", "Total gasto", "Última compra", "Receita vence", "WhatsApp", "Preferências"])
        self.segment_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.segment_table.horizontalHeader()
        for column in range(7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.segment_table, 1)
        actions = QHBoxLayout()
        whatsapp = make_button("WhatsApp do selecionado", "fa5b.whatsapp", "secondaryButton")
        whatsapp.clicked.connect(self._segment_whatsapp)
        export = make_button("Exportar lista (CSV)", "fa5s.file-csv", "secondaryButton")
        export.clicked.connect(self._export_segment)
        campaign = make_button("Criar tarefas para o segmento", "fa5s.bullhorn", "primaryButton")
        campaign.setToolTip("Agenda uma tarefa de contato para cada cliente do segmento (evita duplicar tarefas abertas)")
        campaign.clicked.connect(self._create_campaign)
        actions.addWidget(whatsapp)
        actions.addWidget(export)
        actions.addStretch(1)
        actions.addWidget(campaign)
        layout.addLayout(actions)
        return host

    # Data -----------------------------------------------------------------
    def _load(self) -> None:
        if self._ctx is None:
            data = self._preview
        else:
            client, org = self._ctx.client, self._ctx.organization_id
            try:
                data = {
                    "customers": client.table("customers").select(
                        "id,full_name,whatsapp,whatsapp_consent,email,marketing_email_consent,birth_date,preferred_brands,frame_preferences,lens_preferences,preferred_channel,active"
                    ).eq("organization_id", org).execute().data or [],
                    "orders": client.table("sales_orders").select("customer_id,status,total,created_at").eq(
                        "organization_id", org).eq("status", "completed").limit(50000).execute().data or [],
                    "prescriptions": client.table("customer_prescriptions").select(
                        "customer_id,prescribed_at,expires_at,active").eq("organization_id", org).execute().data or [],
                    "tasks": client.table("crm_tasks").select("*").eq("organization_id", org).gte(
                        "due_date", (date.today() - timedelta(days=120)).isoformat()).order("due_date").limit(5000).execute().data or [],
                }
            except Exception as exc:
                QMessageBox.critical(self, "Relacionamento indisponível",
                                     f"{exc}\n\nConfirme se as migrations 202610250002 e 202610250006 foram aplicadas.")
                return
        self._customers = {str(row["id"]): row for row in data["customers"]}
        self._tasks = list(data["tasks"])
        self._insights = segment_customers(
            list(data["customers"]), list(data["orders"]), list(data["prescriptions"]),
            validity_months=self._settings.prescription_validity_months,
            review_days=self._settings.review_reminder_days_before,
        )
        today = date.today()
        open_tasks = [t for t in self._tasks if t.get("status") == "aberta"]
        self.today_tile.set_value(str(sum(1 for t in open_tasks if str(t.get("due_date"))[:10] == today.isoformat())))
        self.late_tile.set_value(str(sum(1 for t in open_tasks if str(t.get("due_date"))[:10] < today.isoformat())))
        self.review_tile.set_value(str(sum(1 for i in self._insights.values() if "receita_vencendo" in i.segments)))
        self.risk_tile.set_value(str(sum(1 for i in self._insights.values() if "em_risco" in i.segments)))
        self._render_tasks()
        self._render_segment()

    def _render_tasks(self, *_args: object) -> None:
        today = date.today().isoformat()
        week = (date.today() + timedelta(days=7)).isoformat()
        mode = self.agenda_filter.currentIndex()
        type_code = self.task_type_filter.currentData() or ""
        rows = []
        for task in self._tasks:
            due = str(task.get("due_date") or "")[:10]
            status = task.get("status")
            if mode == 0 and not (status == "aberta" and due <= today):
                continue
            if mode == 1 and not (status == "aberta" and due <= week):
                continue
            if mode == 2 and status != "aberta":
                continue
            if mode == 3 and status != "concluida":
                continue
            if type_code and task.get("task_type") != type_code:
                continue
            rows.append(task)
        rows.sort(key=lambda t: str(t.get("due_date")))
        self._visible_tasks = rows
        self.tasks_table.setRowCount(len(rows))
        for row, task in enumerate(rows):
            customer = self._customers.get(str(task.get("customer_id")), {})
            insight = self._insights.get(str(task.get("customer_id")))
            due = str(task.get("due_date") or "")[:10]
            late = task.get("status") == "aberta" and due < today
            values = [
                _fmt(due), customer.get("full_name") or "—", TASK_TYPES.get(task.get("task_type", ""), task.get("task_type", "")),
                task.get("title") or "", "Autorizado" if insight and insight.can_whatsapp else "Sem consentimento",
                "Atrasada" if late else {"aberta": "Em aberto", "concluida": "Concluída", "cancelada": "Descartada"}.get(task.get("status"), ""),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 5 and late:
                    cell.setForeground(QColor("#C03030"))
                if column == 4:
                    cell.setForeground(QColor("#0E8A5B" if insight and insight.can_whatsapp else "#8A97AB"))
                self.tasks_table.setItem(row, column, cell)

    def _set_segment(self, code: str) -> None:
        self._segment = code
        self._render_segment()

    def _render_segment(self) -> None:
        counts = {code: 0 for code in SEGMENTS}
        for insight in self._insights.values():
            for tag in insight.segments:
                counts[tag] = counts.get(tag, 0) + 1
        for chip in self._chips:
            chip.count.setText(str(counts.get(chip.code, 0)))
            chip.setChecked(chip.code == self._segment)
        caption, description, _icon, _color = SEGMENTS[self._segment]
        self.segment_description.setText(f"{caption}: {description}")
        rows = [i for i in self._insights.values() if self._segment in i.segments]
        rows.sort(key=lambda i: (i.prescription_expiry or date.max) if self._segment == "receita_vencendo" else -i.total_spent)
        self._segment_rows = rows
        self.segment_table.setRowCount(len(rows))
        for row, insight in enumerate(rows):
            customer = insight.customer
            preferences = " · ".join(filter(None, [customer.get("preferred_brands"), customer.get("frame_preferences"), customer.get("lens_preferences")]))
            values = [
                customer.get("full_name") or "—", str(insight.purchases), brl(insight.total_spent),
                insight.last_purchase.strftime("%d/%m/%Y") if insight.last_purchase else "—",
                insight.prescription_expiry.strftime("%d/%m/%Y") if insight.prescription_expiry else "—",
                "Autorizado" if insight.can_whatsapp else "Sem consentimento", preferences or "—",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column in (1, 2):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 4 and insight.prescription_expiry and insight.prescription_expiry < date.today():
                    cell.setForeground(QColor("#C03030"))
                if column == 5:
                    cell.setForeground(QColor("#0E8A5B" if insight.can_whatsapp else "#8A97AB"))
                self.segment_table.setItem(row, column, cell)

    # Agenda actions -------------------------------------------------------
    def _selected_task(self) -> dict | None:
        row = self.tasks_table.currentRow()
        if row < 0 or row >= len(self._visible_tasks):
            QMessageBox.information(self, "Selecione uma tarefa", "Selecione uma tarefa na agenda.")
            return None
        return self._visible_tasks[row]

    def _update_task(self, task: dict, changes: dict) -> bool:
        if self._ctx is None:
            task.update(changes)
            return True
        try:
            self._ctx.client.table("crm_tasks").update(changes).eq("id", task["id"]).eq(
                "organization_id", self._ctx.organization_id).execute()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível atualizar a tarefa", str(exc))
            return False

    def _open_whatsapp(self, customer: dict, task_type: str) -> None:
        insight = self._insights.get(str(customer.get("id")))
        if not insight or not insight.can_whatsapp:
            QMessageBox.information(self, "Contato não autorizado",
                                    "Este cliente não tem WhatsApp cadastrado ou não autorizou contato. Respeite o consentimento (LGPD).")
            return
        phone = normalize_br_whatsapp(str(customer.get("whatsapp") or ""))
        message = whatsapp_message(task_type, str(customer.get("full_name") or ""), store_display_name(self._ctx, self._settings))
        service = WhatsAppService(self._ctx)
        if customer.get("id") and service.available and service.cached_status().is_connected:
            text, accepted = QInputDialog.getMultiLineText(
                self, "Mensagem pelo WhatsApp da loja",
                f"Para {customer.get('full_name') or 'o cliente'} • {format_br_phone(phone)}", message)
            if not accepted or not text.strip():
                return
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                sent, info = describe_result(service.send_text(str(customer["id"]), text.strip(), "crm_message"))
            except Exception as exc:
                sent, info = False, str(exc)
            finally:
                QApplication.restoreOverrideCursor()
            if sent:
                QMessageBox.information(self, "WhatsApp", info)
                return
            answer = QMessageBox.question(
                self, "Envio não concluído", f"{info}\n\nAbrir o WhatsApp no computador para enviar manualmente?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            message = text.strip()
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{phone}?text={quote(message)}"))

    def _task_whatsapp(self) -> None:
        task = self._selected_task()
        if task:
            self._open_whatsapp(self._customers.get(str(task.get("customer_id")), {}), str(task.get("task_type") or ""))

    def _complete_task(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        note, accepted = QInputDialog.getMultiLineText(self, "Concluir tarefa", "Resumo do contato (fica no histórico CRM do cliente):")
        if not accepted:
            return
        changes = {"status": "concluida", "completed_at": datetime.now().astimezone().isoformat(),
                   "notes": ((task.get("notes") or "") + ("\n" if task.get("notes") and note else "") + note.strip()).strip()}
        if not self._update_task(task, changes):
            return
        if self._ctx is not None and note.strip():
            try:
                self._ctx.client.table("customer_interactions").insert({
                    "organization_id": self._ctx.organization_id, "customer_id": task["customer_id"],
                    "interaction_type": "follow_up", "subject": task.get("title") or "Follow-up",
                    "body": note.strip(), "order_status": "", "created_by": self._ctx.user_id,
                }).execute()
            except Exception:
                pass
        self._load()

    def _set_task_status(self, status: str) -> None:
        task = self._selected_task()
        if task and self._update_task(task, {"status": status}):
            self._load()

    def _reschedule(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Reagendar tarefa")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        picker = QDateEdit()
        picker.setCalendarPopup(True)
        picker.setDisplayFormat("dd/MM/yyyy")
        picker.setDate(QDate.currentDate().addDays(3))
        form = QFormLayout()
        form.addRow("Nova data", picker)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and self._update_task(task, {"due_date": picker.date().toPython().isoformat()}):
            self._load()

    def _insert_tasks(self, records: list[dict]) -> int:
        if not records:
            return 0
        if self._ctx is None:
            for record in records:
                self._tasks.append({"id": str(uuid4()), "status": "aberta", "notes": "", **record})
            return len(records)
        payload = [{**record, "organization_id": self._ctx.organization_id, "created_by": self._ctx.user_id} for record in records]
        self._ctx.client.table("crm_tasks").insert(payload).execute()
        return len(records)

    def _new_task(self) -> None:
        if not self._customers:
            QMessageBox.information(self, "Sem clientes", "Cadastre clientes antes de criar tarefas.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Nova tarefa de relacionamento")
        dialog.resize(560, 380)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        form = QFormLayout()
        customer = QComboBox()
        customer.setEditable(True)
        customer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        customer.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        for row in sorted(self._customers.values(), key=lambda c: str(c.get("full_name") or "")):
            customer.addItem(str(row.get("full_name") or "Cliente"), row["id"])
        kind = QComboBox()
        for code, caption in TASK_TYPES.items():
            kind.addItem(caption, code)
        title = QLineEdit()
        title.setPlaceholderText("Ex.: Apresentar nova coleção solar")
        due = QDateEdit()
        due.setCalendarPopup(True)
        due.setDisplayFormat("dd/MM/yyyy")
        due.setDate(QDate.currentDate())
        notes = QTextEdit()
        notes.setMaximumHeight(80)
        form.addRow("Cliente", customer)
        form.addRow("Tipo", kind)
        form.addRow("Tarefa *", title)
        form.addRow("Data", due)
        form.addRow("Observações", notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not title.text().strip() or not customer.currentData():
            QMessageBox.warning(self, "Dados obrigatórios", "Selecione o cliente e descreva a tarefa.")
            return
        try:
            self._insert_tasks([{"customer_id": customer.currentData(), "task_type": kind.currentData(), "title": title.text().strip(),
                                 "due_date": due.date().toPython().isoformat(), "notes": notes.toPlainText().strip()}])
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível criar a tarefa", f"{exc}\n\nConfirme se a migration 202610250006 foi aplicada.")
            return
        self._load()

    # Segment actions ------------------------------------------------------
    def _selected_insight(self) -> CustomerInsight | None:
        row = self.segment_table.currentRow()
        if row < 0 or row >= len(self._segment_rows):
            QMessageBox.information(self, "Selecione um cliente", "Selecione um cliente no segmento.")
            return None
        return self._segment_rows[row]

    def _segment_task_type(self) -> str:
        return {"receita_vencendo": "revisao_receita", "aniversariantes": "aniversario", "em_risco": "reativacao",
                "inativos": "reativacao", "novos": "pos_venda"}.get(self._segment, "campanha")

    def _segment_whatsapp(self) -> None:
        insight = self._selected_insight()
        if insight:
            self._open_whatsapp(insight.customer, self._segment_task_type())

    def _create_campaign(self) -> None:
        if not self._segment_rows:
            QMessageBox.information(self, "Segmento vazio", "Não há clientes neste segmento.")
            return
        caption = SEGMENTS[self._segment][0]
        title, accepted = QInputDialog.getText(self, "Criar tarefas para o segmento", "Título da tarefa:", text=f"Contato — {caption}")
        if not accepted or not title.strip():
            return
        task_type = self._segment_task_type()
        already_open = {(str(t.get("customer_id")), t.get("task_type")) for t in self._tasks if t.get("status") == "aberta"}
        records = [
            {"customer_id": insight.customer["id"], "task_type": task_type, "title": title.strip(), "due_date": date.today().isoformat()}
            for insight in self._segment_rows if (str(insight.customer["id"]), task_type) not in already_open
        ]
        try:
            created = self._insert_tasks(records)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível criar as tarefas", str(exc))
            return
        skipped = len(self._segment_rows) - created
        QMessageBox.information(self, "Tarefas criadas", f"{created} tarefa(s) agendada(s) para hoje."
                                + (f"\n{skipped} cliente(s) já tinham tarefa do mesmo tipo em aberto." if skipped else ""))
        self._load()
        self.tabs.setCurrentIndex(0)

    def _export_segment(self) -> None:
        if not self._segment_rows:
            QMessageBox.information(self, "Segmento vazio", "Não há clientes neste segmento.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar segmento", f"segmento_{self._segment}.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(["Cliente", "WhatsApp", "Autoriza WhatsApp", "E-mail", "Autoriza e-mail", "Compras", "Total gasto", "Última compra", "Receita vence", "Preferências"])
                for insight in self._segment_rows:
                    c = insight.customer
                    writer.writerow([
                        c.get("full_name", ""), c.get("whatsapp", ""), "Sim" if c.get("whatsapp_consent") else "Não",
                        c.get("email", ""), "Sim" if c.get("marketing_email_consent") else "Não", insight.purchases,
                        f"{insight.total_spent:.2f}".replace(".", ","),
                        insight.last_purchase.strftime("%d/%m/%Y") if insight.last_purchase else "",
                        insight.prescription_expiry.strftime("%d/%m/%Y") if insight.prescription_expiry else "",
                        " · ".join(filter(None, [c.get("preferred_brands"), c.get("frame_preferences"), c.get("lens_preferences")])),
                    ])
        except OSError as exc:
            QMessageBox.critical(self, "Falha ao exportar", str(exc))
            return
        QMessageBox.information(self, "Lista exportada",
                                f"{len(self._segment_rows)} cliente(s) exportado(s). Use somente os contatos com consentimento (LGPD).")
