"""Общие виджеты FAMdefense: тема, форматирование, графики и диалоги."""
from __future__ import annotations

import math
import re
import tkinter as tk
from datetime import datetime
from tkinter import ttk

# ───────────────────────────── Тема ─────────────────────────────
BG = "#0A1020"
SIDEBAR = "#101B2E"
CARD = "#141F33"
CARD_LIGHT = "#1D2B43"
FIELD = "#0F192A"
BORDER = "#293B57"
TEXT = "#F4F7FC"
SOFT = "#D5DEEA"
MUTED = "#9AAAC2"
FAINT = "#70819B"
ACCENT = "#6F91FF"
ACCENT_HOVER = "#86A2FF"
GREEN = "#37D39A"
RED = "#FF7782"
YELLOW = "#F5C451"
FONT = "Segoe UI"
PALETTE = ["#6F91FF", "#37D39A", "#FFB86B", "#FF7782", "#B58CFF",
           "#4FD1E8", "#F5C451", "#8FA3C0", "#FF8FD0"]

INCOME_CATEGORIES = ["Зарплата", "Подработка", "Стипендия", "Подарок", "Перевод", "Продажа", "Другое"]
EXPENSE_CATEGORIES = ["Продукты", "Транспорт", "Жильё", "Здоровье", "Образование", "Покупки",
                      "Развлечения", "Связь и интернет", "Другое"]

# Услуга -> (единица измерения или None, примерный тариф за единицу, сум). Тарифы можно менять в программе.
BILL_KINDS: dict[str, tuple[str | None, int]] = {
    "Электричество": ("кВт·ч", 1000),
    "Газ": ("м³", 1500),
    "Вода": ("м³", 1200),
    "Отопление": (None, 0),
    "Интернет": (None, 0),
    "Вывоз мусора": (None, 0),
    "Другое": (None, 0),
}

MONTHS_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
WEEKDAYS_RU = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


# ───────────────────────────── Форматирование ─────────────────────────────
def money(value: float, suffix: bool = True) -> str:
    formatted = f"{value:,.0f}".replace(",", " ")
    return f"{formatted} сум" if suffix else formatted


def signed_money(value: float, income: bool) -> str:
    return ("+ " if income else "− ") + money(value)


def short_money(value: float) -> str:
    a = abs(value)
    if a >= 1e9:
        text = f"{value / 1e9:.1f} млрд"
    elif a >= 1e6:
        text = f"{value / 1e6:.1f} млн"
    elif a >= 1e3:
        text = f"{value / 1e3:.0f} тыс"
    else:
        text = f"{value:.0f}"
    return text.replace(".0 ", " ")


def parse_amount(text: str) -> float | None:
    """Целая положительная сумма (пробелы разрешены) или None."""
    raw = re.sub(r"[\s\u00a0]", "", text).replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0 or value > 1_000_000_000_000 or not value.is_integer():
        return None
    return value


def parse_number(text: str) -> float | None:
    """Положительное число, можно с дробной частью (для кВт·ч, м³)."""
    raw = re.sub(r"[\s\u00a0]", "", text).replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0 or value > 1_000_000_000:
        return None
    return value


def parse_date(text: str) -> str | None:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def month_name(month: str) -> str:
    year, number = month.split("-")
    return f"{MONTHS_RU[int(number) - 1]} {year}"


def shift_month(month: str, delta: int) -> str:
    year, number = map(int, month.split("-"))
    index = year * 12 + (number - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def nice_ceiling(value: float, ticks: int = 4) -> float:
    if value <= 0:
        return float(ticks)
    raw = value / ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * magnitude * ticks >= value:
            return m * magnitude * ticks
    return 10 * magnitude * ticks


def meter_color(ratio: float) -> str:
    return GREEN if ratio < 0.8 else YELLOW if ratio <= 1 else RED


# ───────────────────────────── Стили ttk ─────────────────────────────
def apply_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("FAM.Treeview", background="#101A2B", foreground=TEXT,
                    fieldbackground="#101A2B", borderwidth=0, rowheight=34, font=(FONT, 10))
    style.configure("FAM.Treeview.Heading", background=CARD_LIGHT, foreground=TEXT,
                    relief="flat", borderwidth=0, font=(FONT, 9, "bold"), padding=(9, 10))
    style.map("FAM.Treeview", background=[("selected", "#30466B")],
              foreground=[("selected", "#FFFFFF")])
    style.map("FAM.Treeview.Heading", background=[("active", BORDER)])
    style.configure("FAM.TCombobox", fieldbackground=FIELD, background=CARD_LIGHT,
                    foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, padding=8, font=(FONT, 10))
    style.map("FAM.TCombobox", fieldbackground=[("readonly", FIELD)],
              foreground=[("readonly", TEXT)], selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)])
    style.configure("FAM.Vertical.TScrollbar", background=CARD_LIGHT, troughcolor=CARD,
                    bordercolor=CARD, arrowcolor=MUTED, lightcolor=CARD_LIGHT, darkcolor=CARD_LIGHT)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))


# ───────────────────────────── Простые элементы ─────────────────────────────
def make_label(parent: tk.Misc, text: str = "", size: int = 10, bold: bool = False,
               fg: str = TEXT, bg: str = CARD, **kw) -> tk.Label:
    return tk.Label(parent, text=text, bg=bg, fg=fg,
                    font=(FONT, size, "bold" if bold else "normal"), **kw)


def make_card(parent: tk.Misc, **kw) -> tk.Frame:
    return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, **kw)


_BUTTONS = {
    "primary": (ACCENT, "white", ACCENT_HOVER),
    "ghost": (CARD_LIGHT, TEXT, BORDER),
    "green": (GREEN, "#07111F", "#5BE2B1"),
    "red": (RED, "#07111F", "#FF949C"),
    "danger": ("#3A2430", RED, "#50303D"),
}


def make_button(parent: tk.Misc, text: str, command, kind: str = "primary", **opts) -> tk.Button:
    bg, fg, hover = _BUTTONS[kind]
    button = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                       activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                       cursor="hand2", font=(FONT, 10, "bold"), padx=14, pady=9,
                       disabledforeground=FAINT)
    button.config(**opts)
    button.bind("<Enter>", lambda e: button.config(bg=hover) if str(button["state"]) != "disabled" else None)
    button.bind("<Leave>", lambda e: button.config(bg=bg))
    return button


def make_entry(parent: tk.Misc, variable: tk.StringVar, show: str = "", size: int = 10) -> tk.Entry:
    return tk.Entry(parent, textvariable=variable, show=show, bg=FIELD, fg=TEXT,
                    insertbackground=TEXT, relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ACCENT, font=(FONT, size))


def make_combo(parent: tk.Misc, variable: tk.StringVar, values: list[str]) -> ttk.Combobox:
    return ttk.Combobox(parent, textvariable=variable, values=values, state="readonly",
                        style="FAM.TCombobox", font=(FONT, 10))


def make_clickable(widget: tk.Misc, command) -> None:
    widget.config(cursor="hand2")
    widget.bind("<Button-1>", lambda e: command())
    for child in widget.winfo_children():
        make_clickable(child, command)


def make_tree(parent: tk.Misc, columns: list[tuple[str, str, int, str]], height: int | None = None):
    """columns: (id, заголовок, ширина, выравнивание). Возвращает (контейнер, Treeview)."""
    holder = tk.Frame(parent, bg=CARD)
    options = {"height": height} if height else {}
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns], show="headings",
                        style="FAM.Treeview", **options)
    for column_id, title, width, anchor in columns:
        tree.heading(column_id, text=title)
        tree.column(column_id, width=width, minwidth=60, anchor=anchor)
    scrollbar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview,
                              style="FAM.Vertical.TScrollbar")
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return holder, tree


def metric_card(parent: tk.Misc, title: str, value: str, subtitle: str = "",
                accent: str | None = ACCENT, sub_color: str = MUTED, value_color: str = TEXT,
                value_size: int = 20, command=None) -> tk.Frame:
    card = make_card(parent)
    if accent:
        tk.Frame(card, bg=accent, height=4).pack(fill="x")
    make_label(card, title, 9, True, MUTED).pack(anchor="w", padx=18, pady=(14, 6))
    card.value_label = make_label(card, value, value_size, True, value_color)
    card.value_label.pack(anchor="w", padx=18)
    card.sub_label = make_label(card, subtitle, 9, False, sub_color)
    card.sub_label.pack(anchor="w", padx=18, pady=(5, 14))
    if command:
        make_clickable(card, command)
    return card


def empty_state(parent: tk.Misc, icon: str, title: str, text: str, bg: str = CARD) -> tk.Frame:
    box = tk.Frame(parent, bg=bg)
    make_label(box, icon, 30, False, "#526782", bg).pack()
    make_label(box, title, 12, True, TEXT, bg).pack(pady=(8, 4))
    make_label(box, text, 10, False, MUTED, bg, wraplength=320, justify="center").pack()
    return box


def bind_amount_format(entry: tk.Entry, variable: tk.StringVar) -> None:
    """Пока пользователь печатает, цифры группируются: 1500000 -> 1 500 000."""
    busy = {"on": False}

    def reformat(*_args) -> None:
        if busy["on"]:
            return
        digits = re.sub(r"\D", "", variable.get())
        text = f"{int(digits):,}".replace(",", " ") if digits else ""
        if text != variable.get():
            busy["on"] = True
            variable.set(text)
            entry.icursor("end")
            busy["on"] = False

    variable.trace_add("write", reformat)
    reformat()


# ───────────────────────────── Прокручиваемая область ─────────────────────────────
class ScrollFrame(tk.Frame):
    """Фрейм с вертикальной прокруткой колесом мыши. Содержимое кладём в .inner."""

    def __init__(self, parent: tk.Misc, bg: str = BG) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style="FAM.Vertical.TScrollbar")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(sequence)

    def _on_wheel(self, event) -> None:
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while widget is not None and widget is not self:
            widget = widget.master
        if widget is None:
            return
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return
        up = getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0
        self.canvas.yview_scroll(-3 if up else 3, "units")


# ───────────────────────────── Переключатель и индикатор ─────────────────────────────
class Segmented(tk.Frame):
    """Группа кнопок-переключателей. options: [(значение, подпись), ...]."""

    def __init__(self, parent: tk.Misc, options: list[tuple], command=None, value=None) -> None:
        super().__init__(parent, bg=FIELD, highlightbackground=BORDER, highlightthickness=1)
        self.command = command
        self.value = value if value is not None else options[0][0]
        self.buttons: dict = {}
        for option_value, label in options:
            button = tk.Button(self, text=label, relief="flat", bd=0, cursor="hand2",
                               font=(FONT, 9, "bold"), padx=12, pady=6,
                               command=lambda v=option_value: self.select(v))
            button.pack(side="left", fill="x", expand=True, padx=2, pady=2)
            self.buttons[option_value] = button
        self._paint()

    def _paint(self) -> None:
        for option_value, button in self.buttons.items():
            active = option_value == self.value
            button.config(bg=ACCENT if active else FIELD, fg="white" if active else MUTED,
                          activebackground=ACCENT_HOVER if active else CARD_LIGHT,
                          activeforeground="white")

    def select(self, value, notify: bool = True) -> None:
        self.value = value
        self._paint()
        if notify and self.command:
            self.command(value)


class ProgressBar(tk.Canvas):
    def __init__(self, parent: tk.Misc, value: float = 0.0, color: str = ACCENT,
                 height: int = 8, bg: str = CARD, track: str = BORDER) -> None:
        super().__init__(parent, height=height, bg=bg, highlightthickness=0)
        self.value, self.color, self.track = value, color, track
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, value: float, color: str | None = None) -> None:
        self.value = value
        if color:
            self.color = color
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        self.create_rectangle(0, 0, width, height, fill=self.track, outline="")
        filled = width * max(0.0, min(self.value, 1.0))
        if filled > 0:
            self.create_rectangle(0, 0, filled, height, fill=self.color, outline="")


# ───────────────────────────── Графики ─────────────────────────────
class ChartCanvas(tk.Canvas):
    """Базовый класс: перерисовка при изменении размера и всплывающая подсказка."""

    def __init__(self, parent: tk.Misc, height: int = 230) -> None:
        super().__init__(parent, bg=CARD, height=height, highlightthickness=0)
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Leave>", lambda e: self._on_leave())

    def redraw(self) -> None:  # переопределяется
        pass

    def size(self) -> tuple[int, int]:
        return max(self.winfo_width(), 1), max(self.winfo_height(), 1)

    def empty(self, text: str = "Нет данных") -> None:
        width, height = self.size()
        self.create_text(width / 2, height / 2, text=text, fill=MUTED, font=(FONT, 10))

    def _on_leave(self) -> None:
        self.hide_tip()

    def hide_tip(self) -> None:
        self.delete("tip")
        self.delete("hover")

    def show_tip(self, x: float, y: float, text: str) -> None:
        self.delete("tip")
        width, height = self.size()
        label = self.create_text(0, 0, text=text, fill=TEXT, font=(FONT, 9), anchor="nw",
                                 justify="left", tags="tip")
        x1, y1, x2, y2 = self.bbox(label)
        box_w, box_h = x2 - x1 + 18, y2 - y1 + 14
        px = min(max(x + 14, 4), max(width - box_w - 4, 4))
        py = min(max(y - box_h - 10, 4), max(height - box_h - 4, 4))
        box = self.create_rectangle(px, py, px + box_w, py + box_h, fill=CARD_LIGHT,
                                    outline=BORDER, tags="tip")
        self.coords(label, px + 9, py + 7)
        self.tag_raise(label, box)


class BarChart(ChartCanvas):
    """Сгруппированные столбцы «доходы / расходы» по месяцам. Данные: (ключ 'ГГГГ-ММ', подпись, доход, расход)."""

    def __init__(self, parent: tk.Misc, on_click=None, height: int = 240) -> None:
        super().__init__(parent, height)
        self.data: list[tuple] = []
        self.selected: str | None = None
        self.on_click = on_click
        self._groups: list[tuple] = []
        self.bind("<Motion>", self._motion)
        self.bind("<Button-1>", self._click)

    def set_data(self, data: list[tuple], selected: str | None = None) -> None:
        self.data, self.selected = data, selected
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._groups = []
        width, height = self.size()
        peak = max((max(d[2], d[3]) for d in self.data), default=0)
        if width < 80 or peak <= 0:
            self.empty("Пока нет операций за этот период")
            return
        left, right, top, bottom = 56, 14, 12, 28
        top_value = nice_ceiling(peak)
        plot_h = height - top - bottom
        for i in range(5):
            y = top + plot_h - plot_h * i / 4
            self.create_line(left, y, width - right, y, fill="#3A4D6B" if i == 0 else BORDER)
            self.create_text(left - 8, y, text=short_money(top_value * i / 4), fill=MUTED,
                             font=(FONT, 8), anchor="e")
        slot = (width - left - right) / len(self.data)
        bar_w = max(4, min(26, slot * 0.3))
        for index, (key, label, income, expense) in enumerate(self.data):
            x0 = left + slot * index
            center = x0 + slot / 2
            if key == self.selected:
                self.create_rectangle(x0 + 3, top, x0 + slot - 3, height - bottom,
                                      fill=CARD_LIGHT, outline="")
            for offset, value, color in ((-bar_w - 1, income, GREEN), (1, expense, RED)):
                bar_h = plot_h * value / top_value
                if bar_h > 0:
                    self.create_rectangle(center + offset, height - bottom - bar_h,
                                          center + offset + bar_w, height - bottom,
                                          fill=color, outline="")
            self.create_text(center, height - bottom + 14, text=label,
                             fill=TEXT if key == self.selected else MUTED, font=(FONT, 9))
            self._groups.append((x0, x0 + slot, key, income, expense))

    def _group_at(self, x: float):
        for group in self._groups:
            if group[0] <= x < group[1]:
                return group
        return None

    def _motion(self, event) -> None:
        group = self._group_at(event.x)
        self.delete("hover")
        if group is None:
            self.delete("tip")
            return
        _, height = self.size()
        rect = self.create_rectangle(group[0] + 3, 12, group[1] - 3, height - 28,
                                     fill=CARD_LIGHT, outline="", tags="hover")
        self.tag_lower(rect)
        diff = group[3] - group[4]
        sign = "+" if diff >= 0 else "−"
        self.show_tip(event.x, event.y,
                      f"{month_name(group[2])}\nДоходы:  {money(group[3])}\n"
                      f"Расходы: {money(group[4])}\nИтог:  {sign} {money(abs(diff))}")
        self.config(cursor="hand2" if self.on_click else "")

    def _click(self, event) -> None:
        group = self._group_at(event.x)
        if group and self.on_click:
            self.on_click(group[2])


class DonutChart(ChartCanvas):
    """Кольцевая диаграмма. Данные: (название, значение, цвет). Наведение показывает детали в центре."""

    def __init__(self, parent: tk.Misc, title: str = "Всего", on_click=None, height: int = 240) -> None:
        super().__init__(parent, height)
        self.items: list[tuple] = []
        self.total = 0.0
        self.title = title
        self.hover: int | None = None
        self.on_click = on_click
        self._geometry = (0.0, 0.0, 0.0, 0.0)
        self.bind("<Motion>", self._motion)
        self.bind("<Button-1>", self._click)

    def set_data(self, items: list[tuple]) -> None:
        self.items = [item for item in items if item[1] > 0]
        self.total = sum(item[1] for item in self.items)
        self.hover = None
        self.redraw()

    def set_hover(self, index: int | None) -> None:
        if index != self.hover:
            self.hover = index
            self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.size()
        if not self.items:
            self.empty("Нет данных за период")
            return
        radius = min(width, height) / 2 - 10
        if radius < 30:
            return
        ring = max(14.0, radius * 0.30)
        cx, cy = width / 2, height / 2
        self._geometry = (cx, cy, radius, ring)
        start = 90.0
        many = len(self.items) > 1
        for index, (_label, value, color) in enumerate(self.items):
            sweep = 360 * value / self.total
            active = index == self.hover
            center_radius = radius - ring / 2 + (3 if active else 0)
            extent = -(max(sweep - 1.2, 0.5)) if many else -359.9
            self.create_arc(cx - center_radius, cy - center_radius, cx + center_radius,
                            cy + center_radius, start=start - (0.6 if many else 0), extent=extent,
                            style="arc", outline=color, width=ring + (6 if active else 0))
            start -= sweep
        if self.hover is not None:
            label, value, color = self.items[self.hover]
            shown = label if len(label) <= 16 else label[:15] + "…"
            self.create_text(cx, cy - 22, text=shown, fill=color, font=(FONT, 10, "bold"))
            self.create_text(cx, cy, text=money(value), fill=TEXT, font=(FONT, 12, "bold"))
            self.create_text(cx, cy + 22, text=f"{value / self.total * 100:.1f}%", fill=MUTED,
                             font=(FONT, 10))
        else:
            self.create_text(cx, cy - 12, text=self.title, fill=MUTED, font=(FONT, 9, "bold"))
            self.create_text(cx, cy + 9, text=money(self.total), fill=TEXT, font=(FONT, 13, "bold"))

    def _index_at(self, x: float, y: float) -> int | None:
        cx, cy, radius, ring = self._geometry
        dx, dy = x - cx, y - cy
        distance = math.hypot(dx, dy)
        if not self.items or distance > radius + 6 or distance < radius - ring - 4:
            return None
        angle = math.degrees(math.atan2(dx, -dy)) % 360  # по часовой стрелке от «12 часов»
        accumulated = 0.0
        for index, item in enumerate(self.items):
            accumulated += 360 * item[1] / self.total
            if angle < accumulated:
                return index
        return len(self.items) - 1

    def _motion(self, event) -> None:
        index = self._index_at(event.x, event.y)
        self.set_hover(index)
        self.config(cursor="hand2" if index is not None and self.on_click else "")

    def _click(self, event) -> None:
        index = self._index_at(event.x, event.y)
        if index is not None and self.on_click:
            self.on_click(self.items[index][0])

    def _on_leave(self) -> None:
        self.set_hover(None)


class LineChart(ChartCanvas):
    """Линия с заливкой. Данные: (подпись, значение). zero_base=False — шкала по min/max (для баланса)."""

    def __init__(self, parent: tk.Misc, color: str = ACCENT, height: int = 230,
                 zero_base: bool = True, value_format=money) -> None:
        super().__init__(parent, height)
        self.color, self.zero_base, self.value_format = color, zero_base, value_format
        self.points: list[tuple[str, float]] = []
        self._xs: list[float] = []
        self._ys: list[float] = []
        self.bind("<Motion>", self._motion)

    def set_data(self, points: list[tuple[str, float]], color: str | None = None) -> None:
        self.points = points
        if color:
            self.color = color
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._xs, self._ys = [], []
        width, height = self.size()
        if not self.points or width < 80:
            self.empty("Недостаточно данных")
            return
        left, right, top, bottom = 56, 18, 14, 28
        values = [p[1] for p in self.points]
        if self.zero_base:
            low, high = min(0.0, min(values)), max(values) * 1.1 if max(values) > 0 else 1.0
        else:
            low, high = min(values), max(values)
            pad = (high - low) * 0.12 or max(abs(high) * 0.1, 1.0)
            low, high = low - pad, high + pad
        span = (high - low) or 1.0
        plot_h = height - top - bottom
        plot_w = width - left - right
        for i in range(5):
            y = top + plot_h - plot_h * i / 4
            self.create_line(left, y, width - right, y, fill=BORDER)
            self.create_text(left - 8, y, text=short_money(low + span * i / 4), fill=MUTED,
                             font=(FONT, 8), anchor="e")
        if low < 0 < high:
            zero_y = top + plot_h * (high - 0) / span
            self.create_line(left, zero_y, width - right, zero_y, fill="#3A4D6B", dash=(4, 3))
        count = len(self.points)
        for i, (_label, value) in enumerate(self.points):
            self._xs.append(left + (plot_w * i / (count - 1) if count > 1 else plot_w / 2))
            self._ys.append(top + plot_h * (high - value) / span)
        base_y = top + plot_h
        if count > 1:
            coords = [c for xy in zip(self._xs, self._ys) for c in xy]
            self.create_polygon(self._xs[0], base_y, *coords, self._xs[-1], base_y,
                                fill=blend(CARD, self.color, 0.16), outline="")
            self.create_line(*coords, fill=self.color, width=2.5, joinstyle="round")
        for x, y in zip(self._xs, self._ys):
            self.create_oval(x - 3.5, y - 3.5, x + 3.5, y + 3.5, fill=self.color, outline=CARD)
        step = max(1, math.ceil(count / 8))
        for i in range(0, count, step):
            self.create_text(self._xs[i], height - bottom + 14, text=self.points[i][0],
                             fill=MUTED, font=(FONT, 9))

    def _motion(self, event) -> None:
        if not self._xs:
            return
        index = min(range(len(self._xs)), key=lambda i: abs(self._xs[i] - event.x))
        x, y = self._xs[index], self._ys[index]
        _, height = self.size()
        self.delete("hover")
        self.create_line(x, 14, x, height - 28, fill=BORDER, dash=(3, 3), tags="hover")
        self.create_oval(x - 6, y - 6, x + 6, y + 6, fill=self.color, outline=TEXT, width=2,
                         tags="hover")
        label, value = self.points[index]
        self.show_tip(x, y, f"{label}\n{self.value_format(value)}")


# ───────────────────────────── Универсальный диалог ─────────────────────────────
class FormDialog(tk.Toplevel):
    """Модальное окно с полями. on_submit(values) -> текст ошибки или None (тогда окно закроется).

    Поле: {"key", "label", "kind": entry|password|combo|segment, "value", "values",
           "hint", "amount": True (разделители тысяч), "on_change": функция(dialog, значение)}
    """

    def __init__(self, parent: tk.Misc, title: str, fields: list[dict], on_submit,
                 submit_text: str = "Сохранить", submit_kind: str = "primary",
                 subtitle: str = "", width: int = 400) -> None:
        top = parent.winfo_toplevel()
        super().__init__(top, bg=CARD)
        self.title(title)
        self.transient(top)
        self.resizable(False, False)
        self._on_submit = on_submit
        self.vars: dict[str, tk.StringVar] = {}
        self.kinds: dict[str, str] = {}
        self.widgets: dict[str, tk.Misc] = {}

        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=26, pady=22)
        make_label(body, title, 15, True).pack(anchor="w")
        if subtitle:
            make_label(body, subtitle, 9, False, MUTED, wraplength=width - 60,
                       justify="left").pack(anchor="w", pady=(4, 0))
        tk.Frame(body, bg=CARD, height=14).pack()

        first_entry: tk.Entry | None = None
        for field in fields:
            key, kind = field["key"], field.get("kind", "entry")
            var = tk.StringVar(value=str(field.get("value", "")))
            self.vars[key], self.kinds[key] = var, kind
            make_label(body, field["label"], 9, True, SOFT).pack(anchor="w", pady=(0, 5))
            if kind == "segment":
                widget = Segmented(body, field["values"], value=var.get() or None,
                                   command=lambda v, f=field, s=var: self._segment(f, s, v))
                widget.pack(fill="x", pady=(0, 12))
            elif kind == "combo":
                widget = make_combo(body, var, field["values"])
                widget.pack(fill="x", pady=(0, 12), ipady=4)
                widget.bind("<<ComboboxSelected>>",
                            lambda e, f=field, s=var: self._changed(f, s.get()))
            else:
                widget = make_entry(body, var, show="•" if kind == "password" else "")
                widget.pack(fill="x", pady=(0, 12), ipady=8, ipadx=8)
                if field.get("amount"):
                    bind_amount_format(widget, var)
                first_entry = first_entry or widget
            if field.get("hint"):
                make_label(body, field["hint"], 8, False, MUTED, wraplength=width - 60,
                           justify="left").pack(anchor="w", pady=(0, 10))
            self.widgets[key] = widget

        self.error_label = make_label(body, "", 9, False, RED, wraplength=width - 60, justify="left")
        self.error_label.pack(anchor="w", pady=(2, 8))
        buttons = tk.Frame(body, bg=CARD)
        buttons.pack(fill="x")
        make_button(buttons, "Отмена", self.destroy, "ghost").pack(side="right", padx=(8, 0))
        make_button(buttons, submit_text, self.submit, submit_kind).pack(side="right")

        self.bind("<Return>", self.submit)
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - width) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"{width}x{self.winfo_reqheight()}+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        (first_entry or self).focus_set()

    def _segment(self, field: dict, var: tk.StringVar, value) -> None:
        var.set(str(value))
        self._changed(field, value)

    def _changed(self, field: dict, value) -> None:
        handler = field.get("on_change")
        if handler:
            handler(self, value)

    def set_choices(self, key: str, values: list[str]) -> None:
        widget = self.widgets[key]
        widget.config(values=values)
        if self.vars[key].get() not in values:
            self.vars[key].set(values[0])

    def submit(self, _event=None) -> None:
        values = {
            key: (var.get() if self.kinds[key] == "password" else var.get().strip())
            for key, var in self.vars.items()
        }
        error = self._on_submit(values)
        if error:
            self.error_label.config(text=error)
            return
        self.destroy()
