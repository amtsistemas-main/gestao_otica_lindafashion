"""Prescription input widgets: optional numeric fields and the OD/OE editor grid."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGridLayout, QLabel, QSpinBox, QVBoxLayout, QWidget,
)

from modules.prescriptions.models import EYES, Prescription

_NUMBER_PATTERN = re.compile(r"^[+-]?\d*[.,]?\d*$")


class OptionalDoubleSpinBox(QDoubleSpinBox):
    """Numeric field whose minimum means 'not informed' (shown as —).

    Diopter fields snap to 0.25 D steps when editing finishes and always show the sign,
    which avoids the most common transcription mistakes.
    """

    def __init__(self, low: float, high: float, step: float, decimals: int = 2,
                 signed: bool = False, quarter_steps: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._signed = signed
        self._decimals = decimals
        self._quarter = quarter_steps
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setRange(low - step, high)
        self.setSpecialValueText("—")
        self.setValue(self.minimum())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("measureInput")
        self.setMinimumWidth(78)
        self.editingFinished.connect(self._snap)

    def value_or_none(self) -> float | None:
        if self.value() <= self.minimum() + 1e-9:
            return None
        return round(self.value(), self._decimals)

    def set_optional(self, value: float | None) -> None:
        self.setValue(self.minimum() if value is None else float(value))

    def clear_value(self) -> None:
        self.setValue(self.minimum())

    def _snap(self) -> None:
        value = self.value_or_none()
        if value is not None and self._quarter:
            snapped = round(value * 4) / 4
            if abs(snapped - value) > 1e-9:
                self.setValue(snapped)

    def textFromValue(self, value: float) -> str:  # noqa: N802 - Qt override
        if self._signed:
            return f"{value:+.{self._decimals}f}".replace(".", ",")
        return f"{value:.{self._decimals}f}".replace(".", ",")

    def valueFromText(self, text: str) -> float:  # noqa: N802 - Qt override
        cleaned = text.strip().replace(",", ".").replace(" ", "")
        if cleaned.casefold() in ("plano", "pl"):
            return 0.0
        if cleaned in ("", "—", "+", "-", "."):
            return self.minimum()
        try:
            return float(cleaned)
        except ValueError:
            return self.minimum()

    def validate(self, text: str, pos: int) -> object:  # noqa: D401 - Qt override
        cleaned = text.strip().replace(" ", "")
        if cleaned in ("", "—"):
            # Clearing the field means "not informed".
            return QValidator.State.Acceptable, text, pos
        if cleaned.casefold() in ("plano", "pl"):
            return QValidator.State.Acceptable, text, pos
        if "plano".startswith(cleaned.casefold()):
            return QValidator.State.Intermediate, text, pos
        if not _NUMBER_PATTERN.match(cleaned):
            return QValidator.State.Invalid, text, pos
        value = self.valueFromText(cleaned)
        if value == self.minimum():
            return QValidator.State.Intermediate, text, pos
        if self.minimum() < value <= self.maximum():
            return QValidator.State.Acceptable, text, pos
        return QValidator.State.Intermediate, text, pos


class OptionalAxisSpinBox(QSpinBox):
    """Axis 0–180°; -1 means not informed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(-1, 180)
        self.setSpecialValueText("—")
        self.setValue(-1)
        self.setSuffix("°")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("measureInput")
        self.setMinimumWidth(72)

    def value_or_none(self) -> int | None:
        return None if self.value() < 0 else self.value()

    def set_optional(self, value: int | None) -> None:
        self.setValue(-1 if value is None else int(value))


class PrescriptionEditor(QWidget):
    """OD/OE grid with live validation feedback."""

    changed = Signal()

    COLUMNS = [
        ("sphere", "ESF"), ("cylinder", "CIL"), ("axis", "EIXO"), ("addition", "ADIÇÃO"),
        ("dnp", "DNP LONGE"), ("near_dnp", "DNP PERTO"), ("height", "ALTURA"),
        ("prism", "PRISMA"), ("prism_base", "BASE"),
    ]

    def __init__(self, validity_months: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._validity_months = validity_months
        self._fields: dict[str, QWidget] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for column, (_key, title) in enumerate(self.COLUMNS, start=1):
            header = QLabel(title)
            header.setObjectName("measureHeader")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(header, 0, column)
        for row, eye in enumerate(EYES, start=1):
            label = QLabel(eye.upper())
            label.setObjectName("measureRowLabel")
            label.setToolTip("Olho direito" if eye == "od" else "Olho esquerdo")
            grid.addWidget(label, row, 0)
            for column, (key, _title) in enumerate(self.COLUMNS, start=1):
                widget = self._make_field(key)
                self._fields[f"{eye}_{key}"] = widget
                grid.addWidget(widget, row, column)
        for column in range(1, len(self.COLUMNS) + 1):
            grid.setColumnStretch(column, 1)
        root.addLayout(grid)

        hint = QLabel("Digite os valores com sinal (ex.: -1,25). Esférico, cilíndrico e adição são ajustados para passos de 0,25. "
                      "Use “—” para campos não informados e “plano” para esférico zero.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.feedback.setVisible(False)
        root.addWidget(self.feedback)

        od_addition = self._fields["od_addition"]
        od_addition.editingFinished.connect(self._mirror_addition)
        for widget in self._fields.values():
            signal = getattr(widget, "valueChanged", None) or getattr(widget, "currentIndexChanged", None)
            if signal is not None:
                signal.connect(self._on_changed)

    @staticmethod
    def _make_field(key: str) -> QWidget:
        if key == "sphere":
            return OptionalDoubleSpinBox(-30, 30, 0.25, 2, signed=True, quarter_steps=True)
        if key == "cylinder":
            return OptionalDoubleSpinBox(-15, 15, 0.25, 2, signed=True, quarter_steps=True)
        if key == "axis":
            return OptionalAxisSpinBox()
        if key == "addition":
            return OptionalDoubleSpinBox(0.25, 4.5, 0.25, 2, signed=True, quarter_steps=True)
        if key in ("dnp", "near_dnp"):
            return OptionalDoubleSpinBox(18 if key == "near_dnp" else 20, 45, 0.5, 1)
        if key == "height":
            return OptionalDoubleSpinBox(8, 45, 0.5, 1)
        if key == "prism":
            return OptionalDoubleSpinBox(0, 15, 0.25, 2)
        combo = QComboBox()
        for value in ("", "Nasal", "Temporal", "Superior", "Inferior"):
            combo.addItem(value or "—", value)
        combo.setMinimumWidth(96)
        return combo

    def _mirror_addition(self) -> None:
        """Addition is almost always the same for both eyes: copy OD to an empty OE."""
        od, oe = self._fields["od_addition"], self._fields["oe_addition"]
        if od.value_or_none() is not None and oe.value_or_none() is None:
            oe.set_optional(od.value_or_none())

    def _on_changed(self, *_args: object) -> None:
        self.refresh_feedback()
        self.changed.emit()

    def apply_to(self, prescription: Prescription) -> Prescription:
        for key, widget in self._fields.items():
            if isinstance(widget, QComboBox):
                setattr(prescription, key, str(widget.currentData() or ""))
            else:
                setattr(prescription, key, widget.value_or_none())
        return prescription

    def load(self, prescription: Prescription | None) -> None:
        for key, widget in self._fields.items():
            value = getattr(prescription, key) if prescription else None
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value or "")))
            else:
                widget.set_optional(value)
        self.refresh_feedback()

    def refresh_feedback(self, base: Prescription | None = None) -> None:
        prescription = self.apply_to(base or Prescription())
        prescription.normalize()
        problems = [item for item in prescription.errors() if not item.startswith("Informe ao menos")]
        notes = prescription.warnings(self._validity_months) if base is not None else [
            item for item in prescription.warnings(self._validity_months) if not item.startswith("Receita vencida")
        ]
        if problems:
            self.feedback.setObjectName("previewNotice")
            self.feedback.setText("Corrija antes de salvar:\n• " + "\n• ".join(problems + notes))
        elif notes:
            self.feedback.setObjectName("infoNotice")
            self.feedback.setText("Atenção:\n• " + "\n• ".join(notes))
        else:
            self.feedback.setText("")
        self.feedback.setVisible(bool(problems or notes))
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
