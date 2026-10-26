"""Premium sales documents (ordem de serviço, orçamento e comprovante de venda) in PDF.

Pure rendering: receives the already-loaded data and writes the file with reportlab, so it
can be tested and previewed without Supabase. The layout is compact and the density is
reduced automatically until the document fits on a single A4 page.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from modules.lab_orders import statuses as lab_statuses
from modules.prescriptions.models import SOURCES, Prescription, format_diopter, format_number
from modules.products.models import PRODUCT_TYPES
from modules.sales.payments import PAYMENT_METHODS

ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = ROOT / "assets" / "images" / "logootica.png"

# Paleta do sistema.
NAVY = colors.HexColor("#102957")
BLUE = colors.HexColor("#2165F5")
INK = colors.HexColor("#1E2B42")
SLATE = colors.HexColor("#4A5A75")
MUTED = colors.HexColor("#7A889E")
LINE = colors.HexColor("#DCE3EE")
SOFT = colors.HexColor("#F5F7FB")
TINT = colors.HexColor("#EAF0FC")
GREEN = colors.HexColor("#0E8A5B")
RED = colors.HexColor("#C03030")
AMBER = colors.HexColor("#B7791F")

PAGE_W, PAGE_H = A4
MARGIN_X = 14 * mm
HEADER_H = 92
FOOTER_H = 30
CONTENT_W = PAGE_W - 2 * MARGIN_X
# Densidades tentadas, em ordem, até o documento caber em uma página.
DENSITIES = (1.0, 0.94, 0.88, 0.82, 0.76, 0.7)

FRAME_LABELS = [("ponte", "Ponte"), ("horiz", "Horizontal"), ("vert", "Vertical"),
                ("diag_maior", "Diagonal maior"), ("diametro", "Diâmetro")]


# --------------------------------------------------------------------------- fonts
def _register_fonts() -> tuple[str, str]:
    candidates = [
        ("LFSans", "LFSans-Bold", Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        ("LFSans", "LFSans-Bold", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    if "LFSans" in pdfmetrics.getRegisteredFontNames():
        return "LFSans", "LFSans-Bold"
    for regular_name, bold_name, regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
                pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
                pdfmetrics.registerFontFamily(regular_name, normal=regular_name, bold=bold_name,
                                              italic=regular_name, boldItalic=bold_name)
                return regular_name, bold_name
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


# --------------------------------------------------------------------------- data
@dataclass(slots=True)
class StoreIdentity:
    name: str = "Ótica Linda Fashion"
    document: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    address: str = ""
    website: str = ""
    terms: str = ""
    quote_validity_days: int = 7


def store_identity(name: str, settings: Any) -> StoreIdentity:
    """Identity printed on every document, from the store settings (Configurações)."""
    return StoreIdentity(
        name=name, document=settings.store_document, phone=settings.store_phone,
        whatsapp=settings.store_whatsapp, email=settings.store_email, address=settings.store_address,
        website=settings.store_website, terms=settings.document_terms,
        quote_validity_days=settings.quote_validity_days,
    )


@dataclass(slots=True)
class SalesDocument:
    order: dict
    customer: dict = field(default_factory=dict)
    items: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)
    receivables: list[dict] = field(default_factory=list)
    prescription: Prescription | None = None
    legacy_prescription: dict = field(default_factory=dict)
    frame: dict = field(default_factory=dict)
    lab_order: dict | None = None
    seller_name: str = ""
    notes: str = ""
    store: StoreIdentity = field(default_factory=StoreIdentity)

    @property
    def status(self) -> str:
        return str(self.order.get("status") or "")

    @property
    def is_quote(self) -> bool:
        return self.status == "draft"

    @property
    def is_cancelled(self) -> bool:
        return self.status == "cancelled"

    @property
    def has_optical_data(self) -> bool:
        return bool(self.prescription or _legacy_has_values(self.legacy_prescription) or self.frame or self.lab_order)

    @property
    def kind(self) -> str:
        if self.is_quote:
            return "ORÇAMENTO"
        return "ORDEM DE SERVIÇO" if self.has_optical_data else "COMPROVANTE DE VENDA"


# --------------------------------------------------------------------------- helpers
def money(value: object) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dec(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:19])
        except ValueError:
            return None
    return parsed.astimezone() if parsed.tzinfo else parsed


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _fmt_date(value: object) -> str:
    parsed = value if isinstance(value, date) else _parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


def _quantity(value: object) -> str:
    number = _dec(value)
    return str(int(number)) if number == number.to_integral_value() else f"{number:.2f}".replace(".", ",")


def _legacy_has_values(payload: dict) -> bool:
    for section in ("longe", "perto"):
        for eye in ("od", "oe"):
            if any(str(v).strip() for v in ((payload.get(section) or {}).get(eye) or {}).values()):
                return True
    return False


def _join(*parts: str, sep: str = "  ·  ") -> str:
    return sep.join(part for part in parts if part and part.strip())


# --------------------------------------------------------------------------- styles
class _Styles:
    """Paragraph styles scaled by the density factor k (1.0 = full size)."""

    def __init__(self, k: float) -> None:
        self.regular, self.bold = _register_fonts()

        def style(name: str, size: float, leading: float, **kw: Any) -> ParagraphStyle:
            base = {"fontName": self.regular, "textColor": INK}
            base.update(kw)
            return ParagraphStyle(name, fontSize=size * k, leading=leading * k, **base)

        self.body = style("body", 8.2, 10.8)
        self.small = style("small", 7.2, 9.4, textColor=SLATE)
        self.tiny = style("tiny", 6.4, 8.2, textColor=MUTED, alignment=TA_CENTER)
        self.label = style("label", 6.2, 7.8, fontName=self.bold, textColor=MUTED)
        self.value = style("value", 9.2, 11.6, fontName=self.bold, textColor=NAVY)
        self.section = style("section", 9.4, 12, fontName=self.bold, textColor=NAVY)
        self.section_no = style("section_no", 6.8, 8, fontName=self.bold, textColor=colors.white, alignment=TA_CENTER)
        self.th = style("th", 6.5, 8.2, fontName=self.bold, textColor=colors.white)
        self.th_r = style("th_r", 6.5, 8.2, fontName=self.bold, textColor=colors.white, alignment=TA_RIGHT)
        self.th_c = style("th_c", 6.5, 8.2, fontName=self.bold, textColor=colors.white, alignment=TA_CENTER)
        self.th_soft = style("th_soft", 6.4, 8, fontName=self.bold, textColor=NAVY, alignment=TA_CENTER)
        self.td = style("td", 7.9, 10)
        self.td_r = style("td_r", 7.9, 10, alignment=TA_RIGHT)
        self.td_c = style("td_c", 7.9, 10, alignment=TA_CENTER)
        self.td_strong_r = style("td_strong_r", 7.9, 10, fontName=self.bold, textColor=NAVY, alignment=TA_RIGHT)
        self.eye = style("eye", 8.2, 9.6, fontName=self.bold, textColor=NAVY)
        self.total_label = style("total_label", 8.2, 10.4, fontName=self.bold, textColor=colors.white)
        self.total_value = style("total_value", 13.5, 16, fontName=self.bold, textColor=colors.white, alignment=TA_RIGHT)
        self.sum_label = style("sum_label", 7.8, 10, textColor=SLATE)
        self.sum_value = style("sum_value", 8.2, 10, fontName=self.bold, alignment=TA_RIGHT)
        self.sum_warn = style("sum_warn", 8.2, 10, fontName=self.bold, textColor=AMBER, alignment=TA_RIGHT)
        self.sum_ok = style("sum_ok", 8.2, 10, fontName=self.bold, textColor=GREEN, alignment=TA_RIGHT)
        self.sign = style("sign", 7, 9, textColor=SLATE, alignment=TA_CENTER)
        self.terms = style("terms", 6.9, 9.2, textColor=SLATE)
        self.alert = style("alert", 7.6, 10, textColor=RED)
        self.stub_title = style("stub_title", 6.2, 7.8, fontName=self.bold, textColor=BLUE)
        self.stub_number = style("stub_number", 10.5, 13, fontName=self.bold, textColor=NAVY)


# --------------------------------------------------------------------------- canvas
class _NumberedCanvas(pdf_canvas.Canvas):
    """Defers page output so every page can print 'Página X de Y'."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - reportlab API
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            painter = getattr(self, "lf_page_painter", None)
            if painter is not None:
                painter(self, total)
            super().showPage()
        super().save()


# --------------------------------------------------------------------------- shared page chrome
def spaced(text: str, markup: bool = False) -> str:
    """Small-caps style letter spacing that keeps the gap between words visible.

    Paragraph markup collapses repeated spaces, so word gaps use &nbsp; there.
    """
    gap = " &nbsp;&nbsp;" if markup else "   "
    return gap.join(" ".join(word) for word in text.split())


def paint_store_header(c: pdf_canvas.Canvas, store: StoreIdentity, regular: str, bold: str, *, page_w: float,
                       page_h: float, margin_x: float, header_h: float, kind: str, title: str, issued: str,
                       badge: tuple[str, colors.Color] | None = None) -> None:
    """Store header shared by every document: logo, store identity, document kind/number/date and badge."""
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, page_h - 4.5, page_w, 4.5, stroke=0, fill=1)
    c.setFillColor(BLUE)
    c.rect(0, page_h - 6, page_w * 0.34, 1.5, stroke=0, fill=1)

    top = page_h - 18
    logo_h = 34
    if LOGO_PATH.is_file():
        reader = ImageReader(str(LOGO_PATH))
        iw, ih = reader.getSize()
        c.drawImage(reader, margin_x, top - logo_h, width=logo_h * iw / ih, height=logo_h, mask="auto")
    else:
        c.setFont(bold, 16)
        c.setFillColor(NAVY)
        c.drawString(margin_x, top - 22, store.name.upper())
    lines = [
        (bold, _join(store.name if store.document else "", f"CNPJ {store.document}" if store.document else "")),
        (regular, _join(store.phone, f"WhatsApp {store.whatsapp}" if store.whatsapp else "", store.email, store.website)),
        (regular, store.address),
    ]
    y = top - logo_h - 9.5
    c.setFillColor(SLATE)
    for font, text in lines:
        if text:
            c.setFont(font, 6.7)
            c.drawString(margin_x, y, text[:150])
            y -= 8.4

    right = page_w - margin_x
    c.setFont(bold, 7.2)
    c.setFillColor(BLUE)
    c.drawRightString(right, top - 5, spaced(kind))
    c.setFont(bold, 15.5)
    c.setFillColor(NAVY)
    c.drawRightString(right, top - 23, title)
    c.setFont(regular, 7)
    c.setFillColor(SLATE)
    c.drawRightString(right, top - 34, issued)
    if badge is not None:
        label, tone = badge
        c.setFont(bold, 6.4)
        badge_w = pdfmetrics.stringWidth(label, bold, 6.4) + 14
        c.setFillColor(tone)
        c.roundRect(right - badge_w, top - 50, badge_w, 11.5, 5.7, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.drawCentredString(right - badge_w / 2, top - 46.2, label)

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(margin_x, page_h - header_h + 5, right, page_h - header_h + 5)
    c.restoreState()


def paint_store_footer(c: pdf_canvas.Canvas, store: StoreIdentity, regular: str, bold: str, *, page_w: float,
                       margin_x: float, footer_h: float, generated: datetime, total_pages: int,
                       note: str = "Documento sem valor fiscal") -> None:
    c.saveState()
    right = page_w - margin_x
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(margin_x, footer_h - 4, right, footer_h - 4)
    c.setFont(regular, 6.3)
    c.setFillColor(MUTED)
    c.drawString(margin_x, footer_h - 13, _join(
        store.name, f"CNPJ {store.document}" if store.document else "", note,
        "Gerado em " + generated.strftime("%d/%m/%Y %H:%M"),
    ))
    c.setFont(bold, 6.6)
    c.setFillColor(NAVY)
    c.drawRightString(right, footer_h - 13, f"Página {c.getPageNumber()} de {total_pages}")
    c.restoreState()




class _DashedCut(Flowable):
    """Tear-off line for the customer stub."""

    def __init__(self, width: float, font: str) -> None:
        super().__init__()
        self.width, self.font = width, font
        self.height = 10

    def draw(self) -> None:
        c = self.canv
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.6)
        c.setDash(3, 3)
        c.line(0, 5, self.width, 5)
        c.setDash()
        label = "RECORTE AQUI"
        c.setFont(self.font, 5.8)
        text_w = pdfmetrics.stringWidth(label, self.font, 5.8)
        c.setFillColor(colors.white)
        c.rect(self.width / 2 - text_w / 2 - 6, 0.5, text_w + 12, 9, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.drawCentredString(self.width / 2, 2.9, label)


def _box_style(background: colors.Color = SOFT, radius: float = 6, pad_x: float = 9, pad_y: float = 6,
               border: bool = True) -> list[tuple]:
    commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, -1), background), ("ROUNDEDCORNERS", [radius] * 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), pad_x), ("RIGHTPADDING", (0, 0), (-1, -1), pad_x),
        ("TOPPADDING", (0, 0), (-1, -1), pad_y), ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y),
    ]
    if border:
        commands.append(("BOX", (0, 0), (-1, -1), 0.6, LINE))
    return commands


_NO_PAD = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]


# --------------------------------------------------------------------------- builder
class _Builder:
    def __init__(self, doc: SalesDocument, k: float = 1.0) -> None:
        self.doc = doc
        self.k = k
        self.s = _Styles(k)
        self.created = _parse_datetime(doc.order.get("created_at")) or datetime.now()
        self.generated = datetime.now()
        self.total_pages = 0

    def u(self, value: float) -> float:
        """Spacing scaled by the density."""
        return value * self.k

    # ---- page chrome ------------------------------------------------------
    def paint_page(self, c: pdf_canvas.Canvas, total_pages: int) -> None:
        self.total_pages = total_pages
        doc, s, store = self.doc, self.s, self.doc.store
        label, tone = self._status_badge()
        paint_store_header(
            c, store, s.regular, s.bold, page_w=PAGE_W, page_h=PAGE_H, margin_x=MARGIN_X, header_h=HEADER_H,
            kind=doc.kind, title=str(doc.order.get("order_number") or "—"),
            issued="Emitido em " + self.created.strftime("%d/%m/%Y às %H:%M"), badge=(label, tone),
        )
        if doc.is_cancelled:
            c.saveState()
            c.setFillColor(colors.Color(0.75, 0.19, 0.19, alpha=0.09))
            c.setFont(s.bold, 92)
            c.translate(PAGE_W / 2, PAGE_H / 2 - 40)
            c.rotate(32)
            c.drawCentredString(0, 0, "CANCELADA")
            c.restoreState()
        paint_store_footer(c, store, s.regular, s.bold, page_w=PAGE_W, margin_x=MARGIN_X, footer_h=FOOTER_H,
                           generated=self.generated, total_pages=total_pages)

    @staticmethod
    def _spaced(text: str, markup: bool = False) -> str:
        return spaced(text, markup)

    def _status_badge(self) -> tuple[str, colors.Color]:
        status = self.doc.status
        if status == "draft":
            return "ORÇAMENTO EM ABERTO", BLUE
        if status == "cancelled":
            return "CANCELADA", RED
        if status == "confirmed":
            return "CONFIRMADA", AMBER
        return "VENDA CONCLUÍDA", GREEN

    # ---- building blocks --------------------------------------------------
    def p(self, text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(text, style)

    def table(self, rows: list[list[Any]], widths: list[float], commands: list[tuple]) -> Table:
        table = Table(rows, colWidths=widths)
        table.setStyle(TableStyle(commands))
        return table

    def section(self, number: int, title: str) -> Table:
        chip = self.table([[self.p(f"{number:02d}", self.s.section_no)]], [self.u(18)], [
            ("BACKGROUND", (0, 0), (-1, -1), BLUE), ("ROUNDEDCORNERS", [3.5] * 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), *_NO_PAD,
            ("TOPPADDING", (0, 0), (-1, -1), self.u(2.5)), ("BOTTOMPADDING", (0, 0), (-1, -1), self.u(3)),
        ])
        return self.table([[chip, self.p(escape(title), self.s.section)]], [self.u(25), CONTENT_W - self.u(25)], [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), *_NO_PAD,
            ("BOTTOMPADDING", (0, 0), (-1, -1), self.u(4)), ("LINEBELOW", (0, 0), (-1, -1), 0.6, LINE),
        ])

    def block(self, number: int, title: str, *content: Flowable) -> list[Flowable]:
        return [Spacer(1, self.u(10)), KeepTogether([self.section(number, title), Spacer(1, self.u(5)), *content])]

    def card(self, label: str, value: str, lines: list[str], width: float) -> Table:
        content = [self.p(self._spaced(label.upper(), markup=True), self.s.label), Spacer(1, self.u(1.5)),
                   self.p(value, self.s.value)]
        content += [self.p(line, self.s.small) for line in lines if line]
        return self.table([[content]], [width], _box_style(pad_x=self.u(9), pad_y=self.u(6)))

    def row_of(self, cells: list[Any], widths: list[float], gap: float = 8) -> Table:
        data, col_widths = [], []
        for index, (cell, width) in enumerate(zip(cells, widths)):
            if index:
                data.append("")
                col_widths.append(gap)
            data.append(cell)
            col_widths.append(width)
        return self.table([data], col_widths, [("VALIGN", (0, 0), (-1, -1), "TOP"), *_NO_PAD])

    def grid(self, rows: list[list[Any]], widths: list[float], header_soft: bool = False,
             first_col_label: bool = False, zebra: bool = True, padding: float = 5) -> Table:
        pad_y = self.u(3.4)
        commands: list[tuple] = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
            ("TOPPADDING", (0, 0), (-1, -1), pad_y), ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE), ("ROUNDEDCORNERS", [4, 4, 0, 0]),
            ("BACKGROUND", (0, 0), (-1, 0), TINT if header_soft else NAVY),
        ]
        if zebra:
            commands += [("BACKGROUND", (0, index), (-1, index), SOFT) for index in range(2, len(rows), 2)]
        if first_col_label:
            commands.append(("BACKGROUND", (0, 1), (0, -1), TINT))
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle(commands))
        return table

    # ---- sections ---------------------------------------------------------
    def info_cards(self) -> Table:
        doc = self.doc
        customer = doc.customer or {}
        width = (CONTENT_W - 16) / 3
        contact = customer.get("whatsapp") or customer.get("phone") or ""
        customer_lines = [
            f"CPF/CNPJ {escape(customer['document'])}" if customer.get("document") else "",
            escape(_join(contact, customer.get("email") or "")),
        ]
        if not any(customer_lines):
            customer_lines = ["Cliente não identificado" if not customer else "Contato não informado"]
        street = _join(customer.get("street") or "", customer.get("address_number") or "", sep=", ")
        address_lines = [
            escape(_join(customer.get("address_complement") or "", customer.get("neighborhood") or "", sep=" · ")),
            escape(_join(_join(customer.get("city") or "", customer.get("state") or "", sep=" / "),
                         f"CEP {customer['postal_code']}" if customer.get("postal_code") else "")),
        ]
        service_lines = [f"Data: {self.created.strftime('%d/%m/%Y')}"]
        if doc.is_quote:
            valid_until = self.created.date() + timedelta(days=max(1, doc.store.quote_validity_days))
            service_lines.append(f"<b>Válido até {valid_until.strftime('%d/%m/%Y')}</b>")
        elif doc.lab_order and doc.lab_order.get("expected_at"):
            service_lines.append(f"<b>Previsão de entrega: {_fmt_date(doc.lab_order['expected_at'])}</b>")
        return self.row_of([
            self.card("Cliente", escape(customer.get("full_name") or "Venda avulsa"), customer_lines, width),
            self.card("Endereço", escape(street) if street else "Não informado", address_lines, width),
            self.card("Atendimento", escape(doc.seller_name) if doc.seller_name else "Equipe da loja", service_lines, width),
        ], [width] * 3)

    def items_table(self) -> Table:
        s = self.s
        widths = [20, CONTENT_W - 20 - 34 - 70 - 62 - 74, 34, 70, 62, 74]
        rows: list[list[Any]] = [[
            self.p("#", s.th_c), self.p("DESCRIÇÃO", s.th), self.p("QTD.", s.th_c),
            self.p("VALOR UNIT.", s.th_r), self.p("DESCONTO", s.th_r), self.p("TOTAL", s.th_r),
        ]]
        for index, item in enumerate(self.doc.items, start=1):
            kind = str(item.get("product_type") or "")
            detail = _join(
                f"Ref. {escape(item['sku'])}" if item.get("sku") else "",
                escape(PRODUCT_TYPES.get(kind, "")) if kind not in ("", "outro") else "",
            )
            description = f"<b>{escape(str(item.get('product_name') or 'Item'))}</b>"
            if detail:
                # Compact densities keep the reference on the same line to save height.
                joiner = "  " if self.k <= 0.82 else "<br/>"
                description += f"{joiner}<font size='{6.6 * self.k:.1f}' color='#7A889E'>{detail}</font>"
            discount = _dec(item.get("discount"))
            rows.append([
                self.p(str(index), s.td_c), self.p(description, s.td), self.p(_quantity(item.get("quantity")), s.td_c),
                self.p(money(item.get("unit_price")), s.td_r),
                self.p("—" if discount == 0 else "− " + money(discount), s.td_r),
                self.p(money(item.get("line_total")), s.td_strong_r),
            ])
        if len(rows) == 1:
            rows.append(["", self.p("Nenhum item registrado.", s.small), "", "", "", ""])
        return self.grid(rows, widths)

    def _paid_and_due(self) -> tuple[Decimal, Decimal]:
        doc = self.doc
        if not doc.payments:
            return (_dec(doc.order.get("total")) if doc.status == "completed" else Decimal("0")), Decimal("0")
        paid = sum((_dec(p.get("amount")) for p in doc.payments if not p.get("receivable")), Decimal("0"))
        due = sum((_dec(p.get("amount")) for p in doc.payments if p.get("receivable")), Decimal("0"))
        return paid, due

    def payment_block(self) -> Table:
        doc, s = self.doc, self.s
        left_w, right_w = CONTENT_W * 0.57, CONTENT_W * 0.43 - 12
        left: list[Flowable] = []
        if doc.payments:
            rows: list[list[Any]] = [[self.p("FORMA DE PAGAMENTO", s.th), self.p("CONDIÇÃO", s.th_c), self.p("VALOR", s.th_r)]]
            for payment in doc.payments:
                method = PAYMENT_METHODS.get(str(payment.get("method") or ""), "Outro")
                installments = int(payment.get("installments") or 1)
                amount = _dec(payment.get("amount"))
                tag = "  <font color='#2165F5'><b>SINAL</b></font>" if payment.get("is_down_payment") else ""
                condition = f"{installments}x de {money(amount / installments)}" if installments > 1 else "À vista"
                if payment.get("receivable") and payment.get("first_due_date") and not doc.receivables:
                    condition += f" · 1º venc. {_fmt_date(payment['first_due_date'])}"
                rows.append([self.p(f"<b>{escape(method)}</b>{tag}", s.td), self.p(condition, s.td_c),
                             self.p(money(amount), s.td_strong_r)])
            left.append(self.grid(rows, [left_w * 0.36, left_w * 0.42, left_w * 0.22]))
            if doc.receivables:
                schedule = "  ·  ".join(
                    f"<b>{index}/{len(doc.receivables)}</b> {_fmt_date(entry.get('due_date'))} {money(entry.get('amount'))}"
                    for index, entry in enumerate(doc.receivables, start=1)
                )
                left += [Spacer(1, self.u(4)), self.p(f"<b>Parcelas a receber:</b> {schedule}", s.small)]
        elif doc.is_quote:
            left += [self.p("<b>Condições de pagamento</b>", s.body),
                     self.p("Definidas no fechamento da venda. Consulte as opções de parcelamento disponíveis.", s.small)]
        else:
            left += [self.p("<b>Forma de pagamento</b>", s.body),
                     self.p(escape(str(doc.order.get("payment_method") or "Não informada")), s.small)]

        subtotal, discount, total = _dec(doc.order.get("subtotal")), _dec(doc.order.get("discount")), _dec(doc.order.get("total"))
        pct = _dec(doc.order.get("discount_percent"))
        if not pct and subtotal:
            pct = (discount / subtotal * 100).quantize(Decimal("0.01"))
        pad = [("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
               ("TOPPADDING", (0, 0), (-1, -1), self.u(2.5)), ("BOTTOMPADDING", (0, 0), (-1, -1), self.u(2.5))]
        summary = self.table([
            [self.p("Subtotal", s.sum_label), self.p(money(subtotal), s.sum_value)],
            [self.p("Descontos" + (f" ({format_number(float(pct), 1)}%)" if discount else ""), s.sum_label),
             self.p(("− " + money(discount)) if discount else money(0), s.sum_value)],
        ], [right_w * 0.5] * 2, [*pad, ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE)])
        total_box = self.table(
            [[self.p("TOTAL DO ORÇAMENTO" if doc.is_quote else "TOTAL", s.total_label), self.p(money(total), s.total_value)]],
            [right_w * 0.45, right_w * 0.55],
            [*_box_style(NAVY, 5, 10, self.u(6.5), border=False), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")],
        )
        right: list[Flowable] = [summary, Spacer(1, self.u(4)), total_box]
        if not doc.is_quote and not doc.is_cancelled:
            paid, due = self._paid_and_due()
            right += [Spacer(1, self.u(3)), self.table([
                [self.p("Pago no ato", s.sum_label), self.p(money(paid), s.sum_value)],
                [self.p("Saldo a receber", s.sum_label), self.p(money(due), s.sum_warn if due else s.sum_ok)],
            ], [right_w * 0.5] * 2, [*pad, ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE)])]
        right_box = self.table([[right]], [right_w], [*_box_style(radius=7, pad_x=0, pad_y=self.u(4))])
        return self.row_of([left, right_box], [left_w, right_w], gap=12)

    def prescription_block(self) -> list[Flowable]:
        doc, s = self.doc, self.s
        rx = doc.prescription
        first = 52
        if rx is not None:
            meta = _join(
                f"Receita de <b>{rx.prescribed_at.strftime('%d/%m/%Y')}</b>",
                f"válida até <b>{rx.effective_expiry().strftime('%d/%m/%Y')}</b>",
                escape(_join(rx.prescriber_name, rx.prescriber_registry, sep=" — ")),
                escape(SOURCES.get(rx.source, "")),
            )
            headers = ["OLHO", "ESFÉRICO", "CILÍNDRICO", "EIXO", "ADIÇÃO", "DNP LONGE", "DNP PERTO", "ALTURA", "PRISMA"]
            rows: list[list[Any]] = [[self.p(h, s.th_soft) for h in headers]]
            for eye in ("od", "oe"):
                axis, prism = rx.eye(eye, "axis"), rx.eye(eye, "prism")
                base = str(getattr(rx, f"{eye}_prism_base") or "")
                values = [
                    format_diopter(rx.eye(eye, "sphere"), plano=True), format_diopter(rx.eye(eye, "cylinder")),
                    f"{axis}°" if axis is not None else "—", format_diopter(rx.eye(eye, "addition")),
                    format_number(rx.eye(eye, "dnp"), 1, " mm"), format_number(rx.eye(eye, "near_dnp"), 1, " mm"),
                    format_number(rx.eye(eye, "height"), 1, " mm"),
                    (format_number(prism, 2, "Δ") + (f" {base[:3]}." if base else "")) if prism else "—",
                ]
                rows.append([self.p(eye.upper(), s.eye)] + [self.p(value, s.td_c) for value in values])
            other = (CONTENT_W - first) / (len(headers) - 1)
            flow: list[Flowable] = [self.p(meta, s.small), Spacer(1, self.u(4)),
                                    self.grid(rows, [first] + [other] * (len(headers) - 1), header_soft=True,
                                              first_col_label=True, zebra=False)]
            if rx.lens_recommendation:
                flow += [Spacer(1, self.u(3)), self.p(f"<b>Indicação de lente:</b> {escape(rx.lens_recommendation)}", s.small)]
            return flow
        if _legacy_has_values(doc.legacy_prescription):
            headers = ["OLHO", "ESF. LONGE", "CIL.", "EIXO", "DNP LONGE", "ESF. PERTO", "DNP PERTO", "ALTURA", "ADIÇÃO"]
            rows = [[self.p(h, s.th_soft) for h in headers]]
            far, near = doc.legacy_prescription.get("longe") or {}, doc.legacy_prescription.get("perto") or {}
            for eye in ("od", "oe"):
                f, n = far.get(eye) or {}, near.get(eye) or {}
                values = [f.get("esf"), f.get("cil"), f.get("eixo"), f.get("dnp"), n.get("esf"), n.get("dnp"), n.get("alt"), n.get("ad")]
                rows.append([self.p(eye.upper(), s.eye)] + [self.p(escape(str(v)) if v else "—", s.td_c) for v in values])
            other = (CONTENT_W - first) / (len(headers) - 1)
            return [self.grid(rows, [first] + [other] * (len(headers) - 1), header_soft=True,
                              first_col_label=True, zebra=False)]
        return []

    def frame_lab_block(self) -> Table | None:
        doc, s = self.doc, self.s
        frame = {key: str(value).strip() for key, value in (doc.frame or {}).items() if str(value).strip()}
        lab = doc.lab_order or {}
        if not frame and not lab:
            return None
        left_w, right_w = CONTENT_W * 0.5, CONTENT_W * 0.5 - 12
        col = left_w / len(FRAME_LABELS)
        frame_table = self.grid(
            [[self.p(label.upper(), s.th_soft) for _key, label in FRAME_LABELS],
             [self.p((escape(frame[key]) + " mm") if frame.get(key) else "—", s.td_c) for key, _label in FRAME_LABELS]],
            [col] * len(FRAME_LABELS), header_soft=True, zebra=False, padding=2,
        )
        lens = lab.get("lens_description") or lab.get("description") or ""
        lab_rows = [
            [self.p("LENTES", s.label), self.p(escape(str(lens)) if lens else "A definir", s.td)],
            [self.p("PREVISÃO", s.label), self.p(_fmt_date(lab.get("expected_at")) if lab.get("expected_at") else "A confirmar", s.td)],
            [self.p("SITUAÇÃO", s.label), self.p(escape(lab_statuses.label(str(lab.get("status")))) if lab.get("status") else "—", s.td)],
        ]
        lab_table = self.table(lab_rows, [right_w * 0.26, right_w * 0.74], [
            *_box_style(radius=5, pad_x=8, pad_y=self.u(2.6)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ])
        return self.row_of(
            [[self.p("<b>Medidas da armação</b>", s.body), Spacer(1, self.u(3)), frame_table],
             [self.p("<b>Laboratório e entrega</b>", s.body), Spacer(1, self.u(3)), lab_table]],
            [left_w, right_w], gap=12,
        )

    def terms_text(self) -> list[str]:
        doc = self.doc
        lines: list[str] = []
        if doc.is_quote:
            valid_until = self.created.date() + timedelta(days=max(1, doc.store.quote_validity_days))
            lines.append(f"Orçamento válido por {doc.store.quote_validity_days} dia(s), até {valid_until.strftime('%d/%m/%Y')}. "
                         "Preços e disponibilidade sujeitos a confirmação no fechamento da venda.")
        if doc.store.terms.strip():
            lines += [line.strip() for line in doc.store.terms.splitlines() if line.strip()]
        elif doc.kind == "ORDEM DE SERVIÇO":
            lines += [
                "Confira receita e medidas antes de assinar: a confecção segue este documento. "
                "O prazo de entrega é uma previsão e depende do laboratório.",
                "A retirada é feita com este comprovante ou documento do titular. "
                "A adaptação a lentes novas pode levar alguns dias; em caso de desconforto, procure a loja.",
            ]
        elif not doc.is_quote:
            lines.append("Guarde este comprovante. Trocas e garantias seguem a política da loja e o Código de Defesa do Consumidor.")
        return lines

    def signatures(self) -> Table:
        s = self.s
        width = (CONTENT_W - 40) / 2
        customer = escape((self.doc.customer or {}).get("full_name") or "Cliente")
        store = escape(self.doc.store.name)
        return self.table(
            [[Spacer(1, self.u(22)), "", Spacer(1, self.u(22))],
             [self.p(f"<b>{customer}</b> · Assinatura do cliente", s.sign), "",
              self.p(f"<b>{store}</b> · Responsável pela loja", s.sign)]],
            [width, 40, width],
            [("LINEBELOW", (0, 0), (0, 0), 0.6, SLATE), ("LINEBELOW", (2, 0), (2, 0), 0.6, SLATE),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), *_NO_PAD, ("TOPPADDING", (0, 1), (-1, 1), 3)],
        )

    def stub(self) -> list[Flowable]:
        doc, s = self.doc, self.s
        number = str(doc.order.get("order_number") or "")
        paid, due = self._paid_and_due()
        forecast = _fmt_date(doc.lab_order.get("expected_at")) if doc.lab_order and doc.lab_order.get("expected_at") else "—"
        left = [
            self.p(self._spaced("COMPROVANTE DO CLIENTE", markup=True), s.stub_title), Spacer(1, self.u(2)),
            self.p(f"<b>{escape(number)}</b>", s.stub_number),
            self.p(escape(_join((doc.customer or {}).get("full_name") or "Venda avulsa",
                                f"Emitido em {self.created.strftime('%d/%m/%Y')}", f"Previsão {forecast}")), s.small),
        ]
        values = self.table([
            [self.p("Total", s.sum_label), self.p(money(doc.order.get("total")), s.sum_value)],
            [self.p("Pago", s.sum_label), self.p(money(paid), s.sum_value)],
            [self.p("Saldo", s.sum_label), self.p(money(due), s.sum_warn if due else s.sum_ok)],
        ], [44, 80], [*_NO_PAD, ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)])
        widths = [CONTENT_W * 0.42, 148, CONTENT_W * 0.58 - 148]
        barcode_cell: list[Flowable] = []
        if number:
            # Code 128 lido pelo leitor do balcão: localiza o pedido na busca de Vendas.
            available = widths[2] - 22
            barcode = Code128(number, barHeight=self.u(22), barWidth=1.0, humanReadable=False, quiet=False)
            if barcode.width > available:
                barcode = Code128(number, barHeight=self.u(22), barWidth=available / barcode.width, humanReadable=False, quiet=False)
            barcode_cell = [barcode, Spacer(1, 1.5), self.p(escape(number), s.tiny)]
        box = self.table([[left, values, barcode_cell]], widths, [
            *_box_style(radius=7, pad_x=11, pad_y=self.u(6)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"), ("LINEAFTER", (0, 0), (1, 0), 0.4, LINE),
        ])
        return [Spacer(1, self.u(9)), _DashedCut(CONTENT_W, s.regular), Spacer(1, self.u(5)), box]

    # ---- story ------------------------------------------------------------
    def story(self) -> list[Flowable]:
        doc, s = self.doc, self.s
        flow: list[Flowable] = [self.info_cards()]
        number = 1
        if doc.is_cancelled:
            cancelled_at = _parse_datetime(doc.order.get("cancelled_at"))
            reason = escape(str(doc.order.get("cancel_reason") or "Não informado"))
            text = (f"<b>Venda cancelada</b>{' em ' + cancelled_at.strftime('%d/%m/%Y às %H:%M') if cancelled_at else ''}. "
                    f"Motivo: {reason}. Os itens retornaram ao estoque e os valores foram estornados.")
            flow += [Spacer(1, self.u(8)), self.table([[self.p(text, s.alert)]], [CONTENT_W], [
                *_box_style(colors.HexColor("#FDF1F1"), 5, 9, self.u(5), border=False),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#F2C4C4")),
            ])]

        flow += self.block(number, "Produtos e serviços", self.items_table())
        number += 1
        flow += self.block(number, "Valores" if doc.is_quote else "Pagamento", self.payment_block())
        number += 1
        prescription = self.prescription_block()
        if prescription:
            flow += self.block(number, "Receita oftálmica", *prescription)
            number += 1
        frame_lab = self.frame_lab_block()
        if frame_lab is not None:
            flow += self.block(number, "Armação e laboratório", frame_lab)
            number += 1

        closing: list[Flowable] = []
        notes = doc.notes.strip()
        terms = self.terms_text()
        if notes:
            closing.append(self.p("<b>Observações:</b> " + escape(notes).replace("\n", "<br/>"), s.body))
        if terms:
            if closing:
                closing.append(Spacer(1, self.u(3)))
            closing += [self.p("•&nbsp;&nbsp;" + escape(line), s.terms) for line in terms]
        if closing:
            flow += self.block(number, "Observações e condições" if notes else "Condições", *closing)
        if not doc.is_quote and not doc.is_cancelled:
            flow += [Spacer(1, self.u(4)), KeepTogether([self.signatures(), *self.stub()])]
        return flow


def _render(target: Any, document: SalesDocument, k: float) -> int:
    """Renders the document at density k into target and returns the page count."""
    builder = _Builder(document, k)
    template = BaseDocTemplate(
        target, pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=HEADER_H, bottomMargin=FOOTER_H + 4,
        title=f"{document.kind.title()} {document.order.get('order_number') or ''}".strip(),
        author=document.store.name, subject=f"{document.kind.title()} — {document.store.name}",
        creator="Ótica Linda Fashion — Gestão",
    )
    frame = Frame(MARGIN_X, FOOTER_H + 4, CONTENT_W, PAGE_H - HEADER_H - FOOTER_H - 4,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body")

    def on_page(canvas: pdf_canvas.Canvas, _doc: BaseDocTemplate) -> None:
        canvas.lf_page_painter = builder.paint_page  # painted at save() when the page total is known

    template.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=on_page)])
    template.build(builder.story(), canvasmaker=_NumberedCanvas)
    return builder.total_pages


def build_sales_pdf(path: str | Path, document: SalesDocument) -> Path:
    """Writes the sales document, on a single page whenever the content allows it.

    Tries decreasing densities until everything fits on one A4 page; only very long
    orders (dozens of items) fall back to multiple pages at the most compact density.
    """
    target = Path(path)
    data = b""
    for k in DENSITIES:
        buffer = BytesIO()
        pages = _render(buffer, document, k)
        data = buffer.getvalue()
        if pages <= 1:
            break
    target.write_bytes(data)
    return target
