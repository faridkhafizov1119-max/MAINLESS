"""Страницы FAMdefense: Обзор, Доходы/Расходы, Коммунальные, Статистика, Бюджеты и цели, Настройки."""
from __future__ import annotations

import calendar
import math
import re
import tkinter as tk
from collections import defaultdict
from datetime import date, timedelta
from tkinter import filedialog, messagebox

import database
from security import hash_password, verify_password
from widgets import (
    ACCENT, ACCENT_HOVER, BG, BILL_KINDS, BORDER, CARD, CARD_LIGHT, EXPENSE_CATEGORIES, FAINT,
    GREEN, INCOME_CATEGORIES, MONTHS_SHORT, MUTED, PALETTE, RED, SOFT, TEXT, WEEKDAYS_RU, YELLOW,
    BarChart, DonutChart, FormDialog, LineChart, ProgressBar, ScrollFrame, Segmented,
    bind_amount_format, empty_state, make_button, make_card, make_clickable, make_combo,
    make_entry, make_label, make_tree, meter_color, metric_card, money, month_name,
    parse_amount, parse_date, parse_number, shift_month, signed_money,
)


# ───────────────────────────── Вспомогательные функции ─────────────────────────────
def current_month() -> str:
    return date.today().strftime("%Y-%m")


def sum_rows(rows: list[dict], transaction_type: str) -> float:
    return sum(r["amount"] for r in rows if r["transaction_type"] == transaction_type)


def group_by_category(rows: list[dict], transaction_type: str) -> list[tuple[str, float]]:
    totals: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["transaction_type"] == transaction_type:
            totals[r["category"]] += r["amount"]
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def month_list(end_month: str, count: int) -> list[str]:
    return [shift_month(end_month, -i) for i in range(count - 1, -1, -1)]


def monthly_series(rows: list[dict], end_month: str, count: int) -> list[tuple]:
    months = month_list(end_month, count)
    income: dict[str, float] = defaultdict(float)
    expense: dict[str, float] = defaultdict(float)
    for r in rows:
        bucket = income if r["transaction_type"] == "income" else expense
        bucket[r["transaction_date"][:7]] += r["amount"]
    return [(m, MONTHS_SHORT[int(m[5:7]) - 1], income[m], expense[m]) for m in months]


def balance_series(rows: list[dict], end_month: str, count: int) -> list[tuple[str, float]]:
    months = month_list(end_month, count)
    first_day = database.month_bounds(months[0])[0]
    running = 0.0
    delta: dict[str, float] = defaultdict(float)
    for r in rows:
        signed = r["amount"] if r["transaction_type"] == "income" else -r["amount"]
        if r["transaction_date"] < first_day:
            running += signed
        else:
            delta[r["transaction_date"][:7]] += signed
    points = []
    for m in months:
        running += delta[m]
        points.append((f"{MONTHS_SHORT[int(m[5:7]) - 1]} {m[2:4]}", running))
    return points


def delta_text(current: float, previous: float, good_up: bool) -> tuple[str, str]:
    if previous <= 0:
        return "Прошлый месяц — без данных", MUTED
    change = (current - previous) / previous * 100
    arrow = "▲" if change >= 0 else "▼"
    good = (change >= 0) == good_up
    return f"{arrow} {abs(change):.0f}% к прошлому месяцу", GREEN if good else RED


def bill_status(bill: dict) -> tuple[str, str, str]:
    """(код, подпись, цвет)."""
    if bill["paid_date"]:
        return "paid", "Оплачено", GREEN
    try:
        days_left = (date.fromisoformat(bill["due_date"]) - date.today()).days
    except ValueError:
        return "open", "К оплате", TEXT
    if days_left < 0:
        return "overdue", "Просрочено", RED
    if days_left <= 3:
        return "soon", "Скоро срок", YELLOW
    return "open", "К оплате", TEXT


def tariff(user_id: int, kind: str) -> float:
    default = BILL_KINDS[kind][1]
    try:
        return float(database.get_setting(user_id, f"tariff:{kind}", str(default)))
    except (TypeError, ValueError):
        return float(default)


# ───────────────────────────── Базовая страница ─────────────────────────────
class Page(tk.Frame):
    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, bg=BG)
        self.shell = shell
        self.uid: int = shell.user["id"]

    def header(self, parent: tk.Misc, title: str, subtitle: str) -> tk.Frame:
        """Заголовок страницы. Возвращает правую часть — туда кладём кнопки."""
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=(0, 20))
        left = tk.Frame(top, bg=BG)
        left.pack(side="left")
        make_label(left, title, 22, True, TEXT, BG).pack(anchor="w")
        make_label(left, subtitle, 10, False, MUTED, BG).pack(anchor="w", pady=(5, 0))
        right = tk.Frame(top, bg=BG)
        right.pack(side="right")
        return right

    def refresh(self) -> None:
        self.shell.show_page(self.shell.active_page)


# ───────────────────────────── Обзор ─────────────────────────────
class DashboardPage(Page):
    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, shell)
        self.rows = database.list_transactions(self.uid)
        self.by_id = {r["id"]: r for r in self.rows}
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        self.wrap = tk.Frame(scroll.inner, bg=BG)
        self.wrap.pack(fill="both", expand=True, padx=32, pady=28)
        self._build()

    def set_month(self, month: str) -> None:
        self.shell.month = month
        self.shell.show_page("Обзор")

    def _build(self) -> None:
        shell, month = self.shell, self.shell.month
        name = shell.user.get("full_name") or "пользователь"
        right = self.header(self.wrap, f"Привет, {name}!", f"Финансовый обзор · {month_name(month)}")

        nav = tk.Frame(right, bg=BG)
        nav.pack(side="left", padx=(0, 14))
        make_button(nav, "◀", lambda: self.set_month(shift_month(month, -1)), "ghost", padx=11).pack(side="left")
        make_label(nav, month_name(month), 10, True, TEXT, BG, width=17).pack(side="left", padx=4)
        forward = make_button(nav, "▶", lambda: self.set_month(shift_month(month, 1)), "ghost", padx=11)
        forward.pack(side="left")
        if month >= current_month():
            forward.config(state="disabled")
        else:
            make_button(nav, "Сегодня", lambda: self.set_month(current_month()),
                        "ghost").pack(side="left", padx=(8, 0))
        make_button(right, "＋  Новая операция", lambda: shell.open_transaction("expense"),
                    "primary").pack(side="left")

        summary = database.get_financial_summary(self.uid, month)
        previous = database.get_financial_summary(self.uid, shift_month(month, -1))
        income, expense = summary["month_income"], summary["month_expense"]
        income_sub, income_color = delta_text(income, previous["month_income"], True)
        expense_sub, expense_color = delta_text(expense, previous["month_expense"], False)
        saved = income - expense
        rate = f"{saved / income * 100:.0f}%" if income > 0 else "—"

        metrics = tk.Frame(self.wrap, bg=BG)
        metrics.pack(fill="x")
        cards = [
            metric_card(metrics, "ОБЩИЙ БАЛАНС", money(summary["balance"]), "Все операции за всё время",
                        ACCENT, value_color=TEXT if summary["balance"] >= 0 else RED),
            metric_card(metrics, "ДОХОДЫ", money(income), income_sub, GREEN, income_color,
                        command=lambda: shell.show_page("Доходы")),
            metric_card(metrics, "РАСХОДЫ", money(expense), expense_sub, RED, expense_color,
                        command=lambda: shell.show_page("Расходы")),
            metric_card(metrics, "НОРМА СБЕРЕЖЕНИЙ", rate,
                        f"Отложено: {'+' if saved >= 0 else '−'} {money(abs(saved))}", YELLOW,
                        GREEN if saved >= 0 else RED),
        ]
        for i, card in enumerate(cards):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 7 if i < 3 else 0))
            metrics.grid_columnconfigure(i, weight=1, uniform="metric")

        grid = tk.Frame(self.wrap, bg=BG)
        grid.pack(fill="both", expand=True, pady=(18, 0))
        grid.grid_columnconfigure(0, weight=3, uniform="g")
        grid.grid_columnconfigure(1, weight=2, uniform="g")
        self._bars_card(grid).grid(row=0, column=0, sticky="nsew", padx=(0, 9), pady=(0, 18))
        self._donut_card(grid).grid(row=0, column=1, sticky="nsew", padx=(9, 0), pady=(0, 18))
        self._recent_card(grid).grid(row=1, column=0, sticky="nsew", padx=(0, 9))
        self._side_card(grid).grid(row=1, column=1, sticky="nsew", padx=(9, 0))

        make_label(self.wrap, "Учебная офлайн-версия • Данные хранятся на этом компьютере", 9, False,
                   FAINT, BG).pack(anchor="w", pady=(16, 0))

    # ---- карточки ----
    def _set_range(self, months: int) -> None:
        self.shell.chart_months = months
        self.shell.show_page("Обзор")

    def _bars_card(self, parent: tk.Misc) -> tk.Frame:
        card = make_card(parent)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=20, pady=(16, 6))
        make_label(top, "Доходы и расходы", 13, True).pack(side="left")
        Segmented(top, [(3, "3 мес."), (6, "6 мес."), (12, "12 мес.")], command=self._set_range,
                  value=self.shell.chart_months).pack(side="right")
        legend = tk.Frame(card, bg=CARD)
        legend.pack(fill="x", padx=20)
        for color, text in ((GREEN, "Доходы"), (RED, "Расходы")):
            make_label(legend, "●", 10, False, color).pack(side="left")
            make_label(legend, text, 9, False, MUTED).pack(side="left", padx=(4, 14))
        make_label(legend, "клик по столбцу — открыть месяц", 9, False, FAINT).pack(side="right")
        chart = BarChart(card, on_click=self.set_month, height=240)
        chart.pack(fill="both", expand=True, padx=14, pady=(4, 14))
        chart.set_data(monthly_series(self.rows, self.shell.month, self.shell.chart_months),
                       selected=self.shell.month)
        return card

    def _donut_card(self, parent: tk.Misc) -> tk.Frame:
        month = self.shell.month
        month_rows = [r for r in self.rows if r["transaction_date"].startswith(month)]
        categories = group_by_category(month_rows, "expense")
        items = [(c, v, PALETTE[i % len(PALETTE)]) for i, (c, v) in enumerate(categories)]
        total = sum(v for _, v in categories)

        card = make_card(parent)
        make_label(card, "Структура расходов", 13, True).pack(anchor="w", padx=20, pady=(16, 0))
        make_label(card, "Наведи на сегмент или на строку ниже", 9, False, MUTED).pack(anchor="w", padx=20)
        donut = DonutChart(card, title="Расходы", height=210)
        donut.pack(fill="x", padx=14, pady=8)
        donut.set_data(items)
        for i, (name, value, color) in enumerate(items[:5]):
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=20, pady=2)
            make_label(row, "●", 10, False, color).pack(side="left")
            make_label(row, name, 10, False, SOFT).pack(side="left", padx=(6, 0))
            make_label(row, f"{value / total * 100:.0f}%", 9, False, MUTED).pack(side="right")
            for widget in [row, *row.winfo_children()]:
                widget.bind("<Enter>", lambda e, idx=i: donut.set_hover(idx))
            row.bind("<Leave>", lambda e: donut.set_hover(None))
        tk.Frame(card, bg=CARD, height=14).pack()
        return card

    def _recent_card(self, parent: tk.Misc) -> tk.Frame:
        card = make_card(parent)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=20, pady=(16, 10))
        make_label(top, "Последние операции", 13, True).pack(side="left")
        make_label(top, "двойной клик — изменить", 9, False, MUTED).pack(side="right")
        if not self.rows:
            empty_state(card, "◷", "Пока нет операций",
                        "Нажми «Новая операция», чтобы начать учёт.").pack(expand=True, pady=40)
            return card
        holder, tree = make_tree(card, [("date", "ДАТА", 100, "w"), ("category", "КАТЕГОРИЯ", 140, "w"),
                                        ("note", "КОММЕНТАРИЙ", 190, "w"), ("amount", "СУММА", 130, "e")],
                                 height=8)
        holder.pack(fill="both", expand=True, padx=14, pady=(0, 16))
        tree.tag_configure("income", foreground=GREEN)
        tree.tag_configure("expense", foreground=RED)
        for r in self.rows[:8]:
            income = r["transaction_type"] == "income"
            tree.insert("", "end", iid=str(r["id"]), tags=("income" if income else "expense",),
                        values=(r["transaction_date"], r["category"], r["note"] or "—",
                                signed_money(r["amount"], income)))
        tree.bind("<Double-1>", lambda e: self._edit(tree))
        return card

    def _edit(self, tree) -> None:
        selected = tree.selection()
        if selected:
            self.shell.open_transaction(record=self.by_id[int(selected[0])])

    def _side_card(self, parent: tk.Misc) -> tk.Frame:
        shell = self.shell
        card = make_card(parent)
        make_label(card, "Быстрые действия", 13, True).pack(anchor="w", padx=18, pady=(16, 10))
        actions = (
            ("＋  Добавить доход", lambda: shell.open_transaction("income"), GREEN),
            ("－  Добавить расход", lambda: shell.open_transaction("expense"), RED),
            ("▤  Счета за свет / газ", lambda: shell.show_page("Коммунальные"), ACCENT_HOVER),
        )
        for text, command, color in actions:
            make_button(card, text, command, "ghost", anchor="w", fg=color).pack(fill="x", padx=16, pady=4)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=18, pady=14)
        make_label(card, "Ближайшие платежи", 10, True).pack(anchor="w", padx=18)
        bills = database.list_bills(self.uid, unpaid_only=True)[:3]
        if not bills:
            make_label(card, "Все счета оплачены ✓", 9, False, GREEN).pack(anchor="w", padx=18, pady=(6, 0))
        for bill in bills:
            _code, label, color = bill_status(bill)
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=18, pady=(6, 0))
            make_label(row, f"{bill['kind']} · до {bill['due_date'][5:]}", 9, False, SOFT).pack(side="left")
            make_label(row, money(bill["amount"]), 9, True, color).pack(side="right")

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=18, pady=14)
        make_label(card, "Лимиты бюджета", 10, True).pack(anchor="w", padx=18)
        budgets = database.get_budgets(self.uid)
        month_rows = [r for r in self.rows if r["transaction_date"].startswith(self.shell.month)]
        spent = dict(group_by_category(month_rows, "expense"))
        if not budgets:
            make_label(card, "Задай лимиты в разделе «Бюджеты и цели».", 9, False, MUTED,
                       wraplength=250, justify="left").pack(anchor="w", padx=18, pady=(6, 0))
        else:
            alerts = sorted(((spent.get(c, 0) / limit, c) for c, limit in budgets.items()
                             if limit > 0 and spent.get(c, 0) / limit >= 0.8), reverse=True)[:3]
            if not alerts:
                make_label(card, "Всё в рамках лимитов ✓", 9, False, GREEN).pack(anchor="w", padx=18, pady=(6, 0))
            for ratio, category in alerts:
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=18, pady=(6, 0))
                make_label(row, category, 9, False, SOFT).pack(side="left")
                make_label(row, f"{ratio * 100:.0f}% лимита", 9, True, meter_color(ratio)).pack(side="right")
                ProgressBar(card, ratio, meter_color(ratio), height=5).pack(fill="x", padx=18, pady=(3, 0))
        tk.Frame(card, bg=CARD, height=16).pack()
        return card


# ───────────────────────────── Доходы / Расходы ─────────────────────────────
SORT_KEYS = {
    "date": lambda r: (r["transaction_date"], r["id"]),
    "category": lambda r: (r["category"].lower(), r["id"]),
    "note": lambda r: ((r["note"] or "").lower(), r["id"]),
    "amount": lambda r: (r["amount"], r["id"]),
}
HEADINGS = {"date": "ДАТА", "category": "КАТЕГОРИЯ", "note": "КОММЕНТАРИЙ", "amount": "СУММА"}
ALL_PERIODS, THIS_MONTH, ALL_CATEGORIES = "Все периоды", "Этот месяц", "Все категории"


class TransactionsPage(Page):
    def __init__(self, parent: tk.Misc, shell, transaction_type: str) -> None:
        super().__init__(parent, shell)
        self.ttype = transaction_type
        self.is_income = transaction_type == "income"
        self.accent = GREEN if self.is_income else RED
        self.categories = INCOME_CATEGORIES if self.is_income else EXPENSE_CATEGORIES
        self.sort_col, self.sort_desc = "date", True
        self.records: list[dict] = []
        self.shown: list[dict] = []
        self.by_id: dict[int, dict] = {}
        self.month_map: dict[str, str | None] = {ALL_PERIODS: None}
        self._build()
        self.reload()

    # ---- построение ----
    def _build(self) -> None:
        title = "Доходы" if self.is_income else "Расходы"
        subtitle = ("Добавляй поступления денег и следи за источниками дохода." if self.is_income
                    else "Записывай покупки и платежи, чтобы контролировать расходы.")
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=30, pady=26)
        right = self.header(wrap, title, subtitle)
        make_button(right, "⭳  Экспорт в CSV", self.export_csv, "ghost").pack()

        stats = tk.Frame(wrap, bg=BG)
        stats.pack(fill="x", pady=(0, 16))
        self.stats: dict[str, tk.Frame] = {}
        specs = (("total", "ИТОГО ПО ФИЛЬТРУ", self.accent), ("count", "ЗАПИСЕЙ", None),
                 ("avg", "СРЕДНЯЯ СУММА", None), ("max", "КРУПНЕЙШАЯ", None))
        for i, (key, label, color) in enumerate(specs):
            card = metric_card(stats, label, "—", "", accent=None, value_color=color or TEXT, value_size=17)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 6 if i < 3 else 0))
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            self.stats[key] = card

        body = tk.Frame(wrap, bg=BG)
        body.pack(fill="both", expand=True)
        self._build_form(body)
        self._build_history(body)

    def _form_label(self, parent: tk.Misc, text: str) -> None:
        make_label(parent, text, 9, True, SOFT).pack(anchor="w", padx=18, pady=(0, 6))

    def _build_form(self, body: tk.Misc) -> None:
        form = make_card(body, width=320)
        form.pack(side="left", fill="y", padx=(0, 14))
        form.pack_propagate(False)
        make_label(form, "Новая операция", 13, True).pack(anchor="w", padx=18, pady=(19, 16))

        self.category_var = tk.StringVar(value=self.categories[0])
        self.amount_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.note_var = tk.StringVar()

        self._form_label(form, "Категория")
        make_combo(form, self.category_var, self.categories).pack(fill="x", padx=18, pady=(0, 14), ipady=4)
        self._form_label(form, "Сумма (сум)")
        self.amount_entry = make_entry(form, self.amount_var)
        self.amount_entry.pack(fill="x", padx=18, pady=(0, 14), ipady=9, ipadx=10)
        bind_amount_format(self.amount_entry, self.amount_var)
        self._form_label(form, "Дата (ГГГГ-ММ-ДД)")
        date_entry = make_entry(form, self.date_var)
        date_entry.pack(fill="x", padx=18, pady=(0, 6), ipady=9, ipadx=10)
        chips = tk.Frame(form, bg=CARD)
        chips.pack(fill="x", padx=18, pady=(0, 14))
        for text, days in (("Сегодня", 0), ("Вчера", 1), ("−7 дней", 7)):
            make_button(chips, text, lambda d=days: self.date_var.set(
                (date.today() - timedelta(days=d)).isoformat()), "ghost", padx=9, pady=4,
                font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        self._form_label(form, "Комментарий (необязательно)")
        note_entry = make_entry(form, self.note_var)
        note_entry.pack(fill="x", padx=18, pady=(0, 14), ipady=9, ipadx=10)

        self.error_label = make_label(form, "", 9, False, RED, wraplength=275, justify="left")
        self.error_label.pack(anchor="w", padx=18, pady=(0, 8))
        text = "＋  Сохранить доход" if self.is_income else "－  Сохранить расход"
        make_button(form, text, self.save, "green" if self.is_income else "red",
                    pady=13).pack(fill="x", padx=18, pady=(4, 18))
        for entry in (self.amount_entry, date_entry, note_entry):
            entry.bind("<Return>", lambda e: self.save())

    def _build_history(self, body: tk.Misc) -> None:
        history = make_card(body)
        history.pack(side="left", fill="both", expand=True)
        top = tk.Frame(history, bg=CARD)
        top.pack(fill="x", padx=18, pady=(17, 10))
        make_label(top, "История операций", 13, True).pack(side="left")
        make_label(top, "клик по заголовку — сортировка • правая кнопка — меню", 9, False, MUTED).pack(side="right")

        filters = tk.Frame(history, bg=CARD)
        filters.pack(fill="x", padx=14, pady=(0, 10))
        self.search_var = tk.StringVar()
        self.month_var = tk.StringVar(value=ALL_PERIODS)
        self.cat_var = tk.StringVar(value=ALL_CATEGORIES)
        make_label(filters, "Поиск:", 9, False, MUTED).pack(side="left", padx=(4, 6))
        make_entry(filters, self.search_var).pack(side="left", fill="x", expand=True, ipady=6, ipadx=8)
        self.month_combo = make_combo(filters, self.month_var, [ALL_PERIODS])
        self.month_combo.config(width=15)
        self.month_combo.pack(side="left", padx=(8, 0))
        cat_combo = make_combo(filters, self.cat_var, [ALL_CATEGORIES, *self.categories])
        cat_combo.config(width=16)
        cat_combo.pack(side="left", padx=(8, 0))
        make_button(filters, "Сбросить", self.reset_filters, "ghost", padx=10, pady=6).pack(side="left", padx=(8, 0))

        holder, self.tree = make_tree(history, [("date", "ДАТА", 100, "w"), ("category", "КАТЕГОРИЯ", 130, "w"),
                                                ("note", "КОММЕНТАРИЙ", 180, "w"), ("amount", "СУММА", 125, "e")])
        holder.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.tree.tag_configure("amount", foreground=self.accent)
        for column in HEADINGS:
            self.tree.heading(column, command=lambda c=column: self.set_sort(c))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Delete>", self.delete_selected)
        self.tree.bind("<Button-3>", self._popup)
        self.tree.bind("<Button-2>", self._popup)

        self.menu = tk.Menu(self, tearoff=0, bg=CARD_LIGHT, fg=TEXT, activebackground=ACCENT,
                            activeforeground="white", bd=0)
        self.menu.add_command(label="Изменить", command=self.edit_selected)
        self.menu.add_command(label="Копировать сумму", command=self.copy_amount)
        self.menu.add_separator()
        self.menu.add_command(label="Удалить", command=self.delete_selected)

        bottom = tk.Frame(history, bg=CARD)
        bottom.pack(fill="x", padx=14, pady=(0, 14))
        self.count_label = make_label(bottom, "", 9, False, MUTED)
        self.count_label.pack(side="left", padx=5)
        make_button(bottom, "Удалить выбранные", self.delete_selected, "danger", padx=12, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="right")
        make_button(bottom, "Изменить", self.edit_selected, "ghost", padx=12, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="right", padx=(0, 8))

        self.search_var.trace_add("write", lambda *_: self.apply_filters())
        self.month_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

    # ---- данные ----
    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.records = database.list_transactions(self.uid, transaction_type=self.ttype)
        self.by_id = {r["id"]: r for r in self.records}
        self.month_map = {ALL_PERIODS: None, THIS_MONTH: current_month()}
        for month in sorted({r["transaction_date"][:7] for r in self.records}, reverse=True):
            self.month_map.setdefault(month_name(month), month)
        self.month_combo.config(values=list(self.month_map))
        if self.month_var.get() not in self.month_map:
            self.month_var.set(ALL_PERIODS)
        self.apply_filters()

    def reset_filters(self) -> None:
        self.search_var.set("")
        self.month_var.set(ALL_PERIODS)
        self.cat_var.set(ALL_CATEGORIES)
        self.apply_filters()

    def set_sort(self, column: str) -> None:
        if self.sort_col == column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = column, column in ("date", "amount")
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search_var.get().strip().lower()
        month = self.month_map.get(self.month_var.get())
        category = self.cat_var.get()
        rows = []
        for r in self.records:
            if month and not r["transaction_date"].startswith(month):
                continue
            if category != ALL_CATEGORIES and r["category"] != category:
                continue
            if query and query not in f"{r['category']} {r['note'] or ''} {r['transaction_date']}".lower():
                continue
            rows.append(r)
        rows.sort(key=SORT_KEYS[self.sort_col], reverse=self.sort_desc)
        self.shown = rows

        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=str(r["id"]), tags=("amount",),
                             values=(r["transaction_date"], r["category"], r["note"] or "—", money(r["amount"])))
        for column, title in HEADINGS.items():
            arrow = (" ▼" if self.sort_desc else " ▲") if column == self.sort_col else ""
            self.tree.heading(column, text=title + arrow)
        self._update_stats(rows)

    def _update_stats(self, rows: list[dict]) -> None:
        total = sum(r["amount"] for r in rows)
        biggest = max(rows, key=lambda r: r["amount"], default=None)

        def put(key: str, value: str, sub: str) -> None:
            self.stats[key].value_label.config(text=value)
            self.stats[key].sub_label.config(text=sub)

        put("total", money(total), "Сумма записей в таблице")
        put("count", str(len(rows)), f"Всего записей: {len(self.records)}")
        put("avg", money(total / len(rows)) if rows else "—", "На одну запись")
        put("max", money(biggest["amount"]) if biggest else "—", biggest["category"] if biggest else "")
        self.count_label.config(text=f"Показано: {len(rows)} из {len(self.records)}")

    # ---- действия ----
    def save(self) -> None:
        amount = parse_amount(self.amount_var.get())
        if amount is None:
            self.error_label.config(text="Введи целую сумму в сумах, больше нуля.")
            return
        tx_date = parse_date(self.date_var.get())
        if tx_date is None:
            self.error_label.config(text="Проверь дату. Используй формат ГГГГ-ММ-ДД.")
            return
        category = self.category_var.get()
        try:
            database.add_transaction(self.uid, self.ttype, category, amount, self.note_var.get(), tx_date)
        except Exception as error:  # noqa: BLE001 — показываем причину пользователю
            self.error_label.config(text=f"Не удалось сохранить операцию: {error}")
            return
        self.error_label.config(text="")
        self.amount_var.set("")
        self.note_var.set("")
        warning = None if self.is_income else self.shell.budget_warning(category, tx_date)
        if warning:
            self.shell.toast(warning, "warn")
        else:
            self.shell.toast("Доход сохранён" if self.is_income else "Расход сохранён", "ok")
        self.reload()
        self.amount_entry.focus_set()

    def _selected_ids(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def edit_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            self.shell.toast("Сначала выбери операцию в таблице", "warn")
            return
        self.shell.open_transaction(record=self.by_id[ids[0]])

    def delete_selected(self, _event=None) -> None:
        ids = self._selected_ids()
        if not ids:
            self.shell.toast("Сначала выбери операцию в таблице", "warn")
            return
        text = ("Удалить выбранную операцию?" if len(ids) == 1
                else f"Удалить выбранные операции ({len(ids)})?")
        if not messagebox.askyesno("Удаление", f"{text} Это действие нельзя отменить."):
            return
        deleted = sum(1 for tid in ids if database.delete_transaction(self.uid, tid))
        self.shell.toast(f"Удалено операций: {deleted}", "ok")
        self.reload()

    def copy_amount(self) -> None:
        ids = self._selected_ids()
        if ids:
            self.clipboard_clear()
            self.clipboard_append(str(int(self.by_id[ids[0]]["amount"])))
            self.shell.toast("Сумма скопирована", "info")

    def _popup(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def export_csv(self) -> None:
        if not self.shown:
            self.shell.toast("Нечего экспортировать — таблица пуста", "warn")
            return
        name = "доходы" if self.is_income else "расходы"
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"{name}_{date.today().isoformat()}.csv")
        if not path:
            return
        try:
            database.export_transactions_csv(path, self.shown)
        except OSError as error:
            self.shell.toast(f"Не удалось сохранить файл: {error}", "error")
            return
        self.shell.toast(f"Экспортировано записей: {len(self.shown)}", "ok")


# ───────────────────────────── Коммунальные платежи ─────────────────────────────
class UtilitiesPage(Page):
    METERED = [kind for kind, (unit, _) in BILL_KINDS.items() if unit]
    STATUS_COLORS = {"paid": GREEN, "overdue": RED, "soon": YELLOW, "open": TEXT}

    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, shell)
        self.status_filter = "all"
        self.bills: list[dict] = []
        self.by_id: dict[int, dict] = {}
        self.calc_kind = tk.StringVar(value=self.METERED[0])
        self.calc_use = tk.StringVar()
        self.calc_tariff = tk.StringVar(value=f"{tariff(self.uid, self.METERED[0]):g}")
        self.kind_filter = tk.StringVar(value="Все услуги")
        self._build()
        self.reload()

    def _build(self) -> None:
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=30, pady=26)
        right = self.header(wrap, "Коммунальные платежи",
                            "Счета за свет, газ, воду и интернет: сроки, оплата и динамика потребления.")
        make_button(right, "＋  Добавить счёт", self.open_bill_dialog, "primary").pack()

        stats = tk.Frame(wrap, bg=BG)
        stats.pack(fill="x", pady=(0, 16))
        self.stats: dict[str, tk.Frame] = {}
        for i, (key, label, color) in enumerate((("open", "К ОПЛАТЕ", YELLOW), ("overdue", "ПРОСРОЧЕНО", RED),
                                                 ("paid", "ОПЛАЧЕНО В ЭТОМ МЕСЯЦЕ", GREEN))):
            card = metric_card(stats, label, "—", "", accent=color, value_size=18)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 7 if i < 2 else 0))
            stats.grid_columnconfigure(i, weight=1, uniform="u")
            self.stats[key] = card

        body = tk.Frame(wrap, bg=BG)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)
        self._build_list(body).grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        side = tk.Frame(body, bg=BG)
        side.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        self._build_calculator(side).pack(fill="x")
        self._build_chart(side).pack(fill="both", expand=True, pady=(14, 0))

    def _build_list(self, parent: tk.Misc) -> tk.Frame:
        card = make_card(parent)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=18, pady=(16, 10))
        make_label(top, "Счета", 13, True).pack(side="left")
        combo = make_combo(top, self.kind_filter, ["Все услуги", *BILL_KINDS])
        combo.config(width=14)
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        Segmented(top, [("all", "Все"), ("open", "К оплате"), ("paid", "Оплачено")],
                  command=self._set_status, value="all").pack(side="right", padx=(0, 10))

        holder, self.tree = make_tree(card, [("period", "ПЕРИОД", 80, "w"), ("kind", "УСЛУГА", 120, "w"),
                                             ("usage", "РАСХОД", 95, "w"), ("amount", "СУММА", 115, "e"),
                                             ("due", "СРОК", 95, "w"), ("status", "СТАТУС", 105, "w")])
        holder.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        for code, color in self.STATUS_COLORS.items():
            self.tree.tag_configure(code, foreground=color)
        self.tree.bind("<Double-1>", lambda e: self.pay_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        bottom = tk.Frame(card, bg=CARD)
        bottom.pack(fill="x", padx=14, pady=(0, 14))
        self.count_label = make_label(bottom, "", 9, False, MUTED)
        self.count_label.pack(side="left", padx=5)
        make_button(bottom, "Удалить", self.delete_selected, "danger", padx=12, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="right")
        make_button(bottom, "✓  Оплатить", self.pay_selected, "green", padx=12, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="right", padx=(0, 8))
        return card

    def _build_calculator(self, parent: tk.Misc) -> tk.Frame:
        card = make_card(parent)
        make_label(card, "Калькулятор платежа", 13, True).pack(anchor="w", padx=20, pady=(16, 10))
        make_label(card, "Услуга", 9, True, SOFT).pack(anchor="w", padx=20, pady=(0, 5))
        combo = make_combo(card, self.calc_kind, self.METERED)
        combo.pack(fill="x", padx=20, pady=(0, 10), ipady=3)
        combo.bind("<<ComboboxSelected>>", lambda e: self._calc_kind_changed())
        self.unit_label = make_label(card, "", 9, True, SOFT)
        self.unit_label.pack(anchor="w", padx=20, pady=(0, 5))
        make_entry(card, self.calc_use).pack(fill="x", padx=20, pady=(0, 10), ipady=7, ipadx=8)
        make_label(card, "Тариф, сум за единицу (примерный — поправь под свой)", 9, True, SOFT).pack(
            anchor="w", padx=20, pady=(0, 5))
        make_entry(card, self.calc_tariff).pack(fill="x", padx=20, pady=(0, 12), ipady=7, ipadx=8)
        self.calc_result = make_label(card, "—", 20, True, GREEN)
        self.calc_result.pack(anchor="w", padx=20)
        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", padx=20, pady=(12, 18))
        make_button(buttons, "Сохранить тариф", self.save_tariff, "ghost", padx=10, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="left")
        make_button(buttons, "Создать счёт", self._bill_from_calc, "primary", padx=10, pady=8,
                    font=("Segoe UI", 9, "bold")).pack(side="right")
        self.calc_use.trace_add("write", lambda *_: self.update_calc())
        self.calc_tariff.trace_add("write", lambda *_: self.update_calc())
        return card

    def _build_chart(self, parent: tk.Misc) -> tk.Frame:
        card = make_card(parent)
        self.chart_title = make_label(card, "Динамика потребления", 13, True)
        self.chart_title.pack(anchor="w", padx=20, pady=(16, 0))
        make_label(card, "Наведи на точку, чтобы увидеть значение", 9, False, MUTED).pack(anchor="w", padx=20)
        self.chart = LineChart(card, color=ACCENT_HOVER, height=170)
        self.chart.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        return card

    # ---- данные ----
    def reload(self) -> None:
        self.bills = database.list_bills(self.uid)
        self.by_id = {b["id"]: b for b in self.bills}
        unpaid = [b for b in self.bills if not b["paid_date"]]
        overdue = [b for b in unpaid if bill_status(b)[0] == "overdue"]
        paid_now = [b for b in self.bills if b["paid_date"] and b["paid_date"].startswith(current_month())]

        def put(key: str, items: list[dict], sub: str) -> None:
            self.stats[key].value_label.config(text=money(sum(b["amount"] for b in items)))
            self.stats[key].sub_label.config(text=f"{len(items)} {sub}")

        put("open", unpaid, "счетов ждут оплаты")
        put("overdue", overdue, "счетов с просрочкой")
        put("paid", paid_now, "счетов оплачено")
        self.apply_filter()
        self._calc_kind_changed(reset_tariff=False)

    def _set_status(self, value: str) -> None:
        self.status_filter = value
        self.apply_filter()

    def apply_filter(self) -> None:
        kind = self.kind_filter.get()
        rows = []
        for b in self.bills:
            code = bill_status(b)[0]
            if kind != "Все услуги" and b["kind"] != kind:
                continue
            if self.status_filter == "open" and code == "paid":
                continue
            if self.status_filter == "paid" and code != "paid":
                continue
            rows.append(b)
        self.tree.delete(*self.tree.get_children())
        for b in rows:
            code, label, _color = bill_status(b)
            unit = BILL_KINDS.get(b["kind"], (None, 0))[0]
            usage = f"{b['consumption']:g} {unit or ''}".strip() if b["consumption"] else "—"
            self.tree.insert("", "end", iid=str(b["id"]), tags=(code,),
                             values=(b["period"], b["kind"], usage, money(b["amount"]), b["due_date"], label))
        self.count_label.config(text=f"Показано: {len(rows)} из {len(self.bills)}  •  двойной клик — оплатить")

    # ---- калькулятор и график ----
    def _calc_kind_changed(self, reset_tariff: bool = True) -> None:
        kind = self.calc_kind.get()
        unit = BILL_KINDS[kind][0]
        self.unit_label.config(text=f"Потребление, {unit}")
        if reset_tariff:
            self.calc_tariff.set(f"{tariff(self.uid, kind):g}")
        self.update_calc()
        self.update_chart()

    def update_calc(self) -> None:
        use, price = parse_number(self.calc_use.get()), parse_number(self.calc_tariff.get())
        self.calc_result.config(text=money(round(use * price)) if use and price else "—")

    def save_tariff(self) -> None:
        price = parse_number(self.calc_tariff.get())
        if price is None:
            self.shell.toast("Тариф должен быть положительным числом", "warn")
            return
        database.set_setting(self.uid, f"tariff:{self.calc_kind.get()}", str(price))
        self.shell.toast(f"Тариф «{self.calc_kind.get()}» сохранён", "ok")

    def update_chart(self) -> None:
        kind = self.calc_kind.get()
        unit = BILL_KINDS[kind][0]
        items = sorted((b for b in self.bills if b["kind"] == kind and b["consumption"]),
                       key=lambda b: b["period"])[-8:]
        self.chart.value_format = lambda v, u=unit: f"{v:g} {u}"
        self.chart_title.config(text=f"Потребление: {kind.lower()}")
        self.chart.set_data([(f"{MONTHS_SHORT[int(b['period'][5:7]) - 1]} {b['period'][2:4]}", b["consumption"])
                             for b in items])

    def _bill_from_calc(self) -> None:
        self.open_bill_dialog(kind=self.calc_kind.get(), consumption=self.calc_use.get())

    # ---- диалоги ----
    def open_bill_dialog(self, kind: str | None = None, consumption: str = "") -> None:
        kind = kind or self.calc_kind.get()
        fields = [
            {"key": "service", "label": "Услуга", "kind": "combo", "values": list(BILL_KINDS), "value": kind},
            {"key": "period", "label": "Период (ГГГГ-ММ)", "value": current_month()},
            {"key": "consumption", "label": "Потребление (необязательно)", "value": consumption,
             "hint": "кВт·ч для света, м³ для газа и воды."},
            {"key": "amount", "label": "Сумма, сум", "amount": True,
             "hint": "Оставь пустым — сумма посчитается по сохранённому тарифу."},
            {"key": "due", "label": "Оплатить до (ГГГГ-ММ-ДД)", "value": f"{shift_month(current_month(), 1)}-15"},
        ]

        def submit(values: dict) -> str | None:
            service, period = values["service"], values["period"]
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
                return "Период указывай в формате ГГГГ-ММ, например 2026-11."
            use = None
            if values["consumption"]:
                use = parse_number(values["consumption"])
                if use is None:
                    return "Потребление — положительное число (можно с запятой)."
            price = tariff(self.uid, service)
            if values["amount"]:
                amount = parse_amount(values["amount"])
            elif use is not None and price > 0:
                amount = float(round(use * price))
            else:
                return "Укажи сумму или потребление (сумму посчитаем по тарифу)."
            if amount is None:
                return "Сумма должна быть целым числом больше нуля."
            due = parse_date(values["due"])
            if due is None:
                return "Проверь срок оплаты. Формат: ГГГГ-ММ-ДД."
            database.add_bill(self.uid, service, period, use, amount, due)
            self.shell.toast("Счёт добавлен", "ok")
            self.reload()
            return None

        FormDialog(self, "Новый счёт", fields, submit, "Добавить")

    def _selected_bill(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            self.shell.toast("Сначала выбери счёт в таблице", "warn")
            return None
        return self.by_id.get(int(selected[0]))

    def pay_selected(self) -> None:
        bill = self._selected_bill()
        if bill is None:
            return
        if bill["paid_date"]:
            self.shell.toast(f"Этот счёт уже оплачен {bill['paid_date']}", "info")
            return
        category = "Связь и интернет" if bill["kind"] == "Интернет" else "Жильё"
        fields = [
            {"key": "paid", "label": "Дата оплаты (ГГГГ-ММ-ДД)", "value": date.today().isoformat()},
            {"key": "record", "label": "Записать как расход?", "kind": "segment",
             "values": [("yes", "Да"), ("no", "Нет")], "value": "yes",
             "hint": f"Операция попадёт в «Расходы», категория «{category}»."},
        ]

        def submit(values: dict) -> str | None:
            paid = parse_date(values["paid"])
            if paid is None:
                return "Проверь дату. Формат: ГГГГ-ММ-ДД."
            database.set_bill_paid(self.uid, bill["id"], paid)
            message = "Счёт отмечен как оплаченный"
            if values["record"] == "yes":
                database.add_transaction(self.uid, "expense", category, bill["amount"],
                                         f"{bill['kind']}, {bill['period']}", paid)
                warning = self.shell.budget_warning(category, paid)
                message = warning or "Счёт оплачен и записан в расходы"
                self.shell.toast(message, "warn" if warning else "ok")
            else:
                self.shell.toast(message, "ok")
            self.reload()
            return None

        FormDialog(self, "Оплата счёта", fields, submit, "Оплатить", "green",
                   subtitle=f"{bill['kind']} за {bill['period']} — {money(bill['amount'])}")

    def delete_selected(self) -> None:
        bill = self._selected_bill()
        if bill is None:
            return
        if messagebox.askyesno("Удаление счёта", "Удалить выбранный счёт? Записанный расход останется в истории."):
            database.delete_bill(self.uid, bill["id"])
            self.shell.toast("Счёт удалён", "ok")
            self.reload()


# ───────────────────────────── Статистика ─────────────────────────────
PERIODS = [("month", "Месяц"), ("quarter", "3 мес."), ("half", "6 мес."), ("year", "Год"), ("all", "Всё время")]
PERIOD_MONTHS = {"month": 1, "quarter": 3, "half": 6, "year": 12}


class StatsPage(Page):
    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, shell)
        self.period, self.kind = "month", "expense"
        self.rows = database.list_transactions(self.uid)
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        wrap = tk.Frame(scroll.inner, bg=BG)
        wrap.pack(fill="both", expand=True, padx=32, pady=28)
        right = self.header(wrap, "Статистика", "Куда уходят деньги и как меняется баланс.")
        Segmented(right, PERIODS, command=self._set_period, value=self.period).pack()
        self.body = tk.Frame(wrap, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.render()

    def _set_period(self, value: str) -> None:
        self.period = value
        self.render()

    def _set_kind(self, value: str) -> None:
        self.kind = value
        self.render()

    def render(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        today, this_month = date.today(), current_month()
        if self.period == "all":
            start = min((r["transaction_date"] for r in self.rows), default=today.isoformat())
        else:
            start = database.month_bounds(shift_month(this_month, -(PERIOD_MONTHS[self.period] - 1)))[0]
        end = database.month_bounds(this_month)[1]
        rows = [r for r in self.rows if start <= r["transaction_date"] <= end]
        days = max((today - date.fromisoformat(start)).days + 1, 1)
        income, expense = sum_rows(rows, "income"), sum_rows(rows, "expense")

        kpis = tk.Frame(self.body, bg=BG)
        kpis.pack(fill="x")
        saved = income - expense
        specs = (("ДОХОДЫ", money(income), f"Операций: {sum(1 for r in rows if r['transaction_type'] == 'income')}", GREEN, TEXT),
                 ("РАСХОДЫ", money(expense), f"Операций: {sum(1 for r in rows if r['transaction_type'] == 'expense')}", RED, TEXT),
                 ("НАКОПЛЕНО", signed_money(abs(saved), saved >= 0), "Доходы минус расходы", ACCENT,
                  GREEN if saved >= 0 else RED),
                 ("СРЕДНИЙ РАСХОД В ДЕНЬ", money(expense / days), f"За {days} дн.", YELLOW, TEXT))
        for i, (title, value, sub, accent, value_color) in enumerate(specs):
            metric_card(kpis, title, value, sub, accent, value_color=value_color).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 7 if i < 3 else 0))
            kpis.grid_columnconfigure(i, weight=1, uniform="k")

        grid = tk.Frame(self.body, bg=BG)
        grid.pack(fill="both", expand=True, pady=(18, 0))
        for column in (0, 1):
            grid.grid_columnconfigure(column, weight=1, uniform="s")
        self._structure_card(grid, rows).grid(row=0, column=0, sticky="nsew", padx=(0, 9), pady=(0, 18))
        right_col = tk.Frame(grid, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(9, 0), pady=(0, 18))
        chart_months = self._chart_months()
        self._chart_card(right_col, "Доходы и расходы по месяцам", lambda c: BarChart(c, height=200),
                         monthly_series(self.rows, this_month, chart_months)).pack(fill="x")
        self._chart_card(right_col, "Динамика баланса",
                         lambda c: LineChart(c, color=GREEN, height=200, zero_base=False),
                         balance_series(self.rows, this_month, chart_months)).pack(fill="x", pady=(14, 0))
        self._analytics_card(grid, rows, days).grid(row=1, column=0, sticky="nsew", padx=(0, 9))
        self._top_card(grid, rows).grid(row=1, column=1, sticky="nsew", padx=(9, 0))

    def _chart_months(self) -> int:
        if self.period == "year":
            return 12
        if self.period == "all" and self.rows:
            first = min(r["transaction_date"] for r in self.rows)[:7]
            y1, m1 = map(int, first.split("-"))
            y2, m2 = map(int, current_month().split("-"))
            return max(6, min(24, (y2 - y1) * 12 + (m2 - m1) + 1))
        return 6

    def _chart_card(self, parent: tk.Misc, title: str, factory, data) -> tk.Frame:
        """factory(card) создаёт график внутри карточки; data передаётся в set_data."""
        card = make_card(parent)
        make_label(card, title, 13, True).pack(anchor="w", padx=20, pady=(16, 0))
        chart = factory(card)
        chart.pack(fill="x", padx=14, pady=(6, 14))
        chart.set_data(data)
        return card

    def _structure_card(self, parent: tk.Misc, rows: list[dict]) -> tk.Frame:
        card = make_card(parent)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=20, pady=(16, 4))
        make_label(top, "Структура", 13, True).pack(side="left")
        Segmented(top, [("expense", "Расходы"), ("income", "Доходы")], command=self._set_kind,
                  value=self.kind).pack(side="right")
        categories = group_by_category(rows, self.kind)
        total = sum(v for _, v in categories)
        items = [(c, v, PALETTE[i % len(PALETTE)]) for i, (c, v) in enumerate(categories)]
        donut = DonutChart(card, title="Расходы" if self.kind == "expense" else "Доходы", height=230)
        donut.pack(fill="x", padx=14, pady=(6, 8))
        donut.set_data(items)
        for i, (name, value, color) in enumerate(items):
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=20, pady=(4, 0))
            make_label(row, "●", 10, False, color).pack(side="left")
            make_label(row, name, 10, False, SOFT).pack(side="left", padx=(6, 0))
            make_label(row, f"{value / total * 100:.1f}%", 9, False, MUTED).pack(side="right")
            make_label(row, money(value), 10, True).pack(side="right", padx=(0, 12))
            bar = ProgressBar(card, value / total, color, height=5)
            bar.pack(fill="x", padx=20, pady=(3, 0))
            for widget in (row, bar, *row.winfo_children()):
                widget.bind("<Enter>", lambda e, idx=i: donut.set_hover(idx))
            row.bind("<Leave>", lambda e: donut.set_hover(None))
        tk.Frame(card, bg=CARD, height=16).pack()
        return card

    def _kv(self, parent: tk.Misc, label: str, value: str, color: str = TEXT) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=20, pady=7)
        make_label(row, label, 10, False, MUTED).pack(side="left")
        make_label(row, value, 10, True, color).pack(side="right")
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20)

    def _analytics_card(self, parent: tk.Misc, rows: list[dict], days: int) -> tk.Frame:
        card = make_card(parent)
        make_label(card, "Аналитика", 13, True).pack(anchor="w", padx=20, pady=(16, 6))
        income, expense = sum_rows(rows, "income"), sum_rows(rows, "expense")
        categories = group_by_category(rows, "expense")
        if categories:
            name, value = categories[0]
            self._kv(card, "Самая затратная категория", f"{name} · {value / expense * 100:.0f}%")
            weekdays: dict[int, float] = defaultdict(float)
            for r in rows:
                if r["transaction_type"] == "expense":
                    weekdays[date.fromisoformat(r["transaction_date"]).weekday()] += r["amount"]
            day = max(weekdays, key=weekdays.get)
            self._kv(card, "Больше всего тратишь", ("во " if day == 1 else "в ") + WEEKDAYS_RU[day])
        else:
            self._kv(card, "Самая затратная категория", "нет данных", MUTED)
        self._kv(card, "Средний расход в день", money(expense / days))
        today = date.today()
        month_expense = sum_rows([r for r in self.rows if r["transaction_date"].startswith(current_month())], "expense")
        forecast = month_expense / today.day * calendar.monthrange(today.year, today.month)[1]
        self._kv(card, "Прогноз расходов на конец месяца", money(forecast), YELLOW)
        if income > 0:
            rate = (income - expense) / income * 100
            self._kv(card, "Норма сбережений", f"{rate:.0f}%", GREEN if rate >= 0 else RED)
        else:
            self._kv(card, "Норма сбережений", "нет доходов", MUTED)
        tk.Frame(card, bg=CARD, height=14).pack()
        return card

    def _top_card(self, parent: tk.Misc, rows: list[dict]) -> tk.Frame:
        card = make_card(parent)
        label = "расходов" if self.kind == "expense" else "доходов"
        make_label(card, f"Крупнейшие операции · {label}", 13, True).pack(anchor="w", padx=20, pady=(16, 6))
        top = sorted((r for r in rows if r["transaction_type"] == self.kind),
                     key=lambda r: r["amount"], reverse=True)[:5]
        if not top:
            empty_state(card, "▥", "Нет данных", "Добавь операции, и здесь появится рейтинг.").pack(pady=30)
        color = RED if self.kind == "expense" else GREEN
        for r in top:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=20, pady=7)
            text = tk.Frame(row, bg=CARD)
            text.pack(side="left")
            make_label(text, r["category"], 10, True).pack(anchor="w")
            make_label(text, f"{r['transaction_date']} · {r['note'] or '—'}", 9, False, MUTED).pack(anchor="w")
            make_label(row, money(r["amount"]), 11, True, color).pack(side="right")
            tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=20)
        tk.Frame(card, bg=CARD, height=14).pack()
        return card


# ───────────────────────────── Бюджеты и цели ─────────────────────────────
class BudgetsPage(Page):
    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, shell)
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        self.wrap = tk.Frame(scroll.inner, bg=BG)
        self.wrap.pack(fill="both", expand=True, padx=32, pady=28)
        self.render()

    def render(self) -> None:
        for child in self.wrap.winfo_children():
            child.destroy()
        month = current_month()
        self.header(self.wrap, "Бюджеты и цели",
                    f"Лимиты расходов на {month_name(month).lower()} и накопления на важные покупки.")
        grid = tk.Frame(self.wrap, bg=BG)
        grid.pack(fill="both", expand=True)
        for column in (0, 1):
            grid.grid_columnconfigure(column, weight=1, uniform="bg")
        self._budgets_card(grid, month).grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        self._goals_card(grid).grid(row=0, column=1, sticky="nsew", padx=(9, 0))

    # ---- лимиты ----
    def _budgets_card(self, parent: tk.Misc, month: str) -> tk.Frame:
        budgets = database.get_budgets(self.uid)
        spent = dict(group_by_category(database.list_transactions(self.uid, "expense", month=month), "expense"))
        card = make_card(parent)
        make_label(card, "Лимиты на месяц", 13, True).pack(anchor="w", padx=20, pady=(16, 2))
        make_label(card, "Нажми на категорию, чтобы задать или изменить лимит", 9, False, MUTED).pack(
            anchor="w", padx=20)

        total_limit = sum(budgets.values())
        total_spent = sum(spent.get(c, 0) for c in budgets)
        box = tk.Frame(card, bg=CARD_LIGHT)
        box.pack(fill="x", padx=20, pady=14)
        inner = tk.Frame(box, bg=CARD_LIGHT)
        inner.pack(fill="x", padx=14, pady=12)
        if total_limit > 0:
            ratio = total_spent / total_limit
            make_label(inner, "ВСЕГО ПО ЛИМИТАМ", 9, True, MUTED, CARD_LIGHT).pack(anchor="w")
            make_label(inner, f"{money(total_spent)} из {money(total_limit)}", 12, True,
                       meter_color(ratio), CARD_LIGHT).pack(anchor="w", pady=(2, 8))
            ProgressBar(inner, ratio, meter_color(ratio), height=8, bg=CARD_LIGHT).pack(fill="x")
        else:
            make_label(inner, "Лимиты пока не заданы", 10, True, TEXT, CARD_LIGHT).pack(anchor="w")
            make_label(inner, "Задай лимит хотя бы для одной категории — программа предупредит о перерасходе.",
                       9, False, MUTED, CARD_LIGHT, wraplength=360, justify="left").pack(anchor="w", pady=(3, 0))

        for category in EXPENSE_CATEGORIES:
            limit, used = budgets.get(category, 0), spent.get(category, 0)
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=20, pady=(0, 12))
            line = tk.Frame(row, bg=CARD)
            line.pack(fill="x")
            make_label(line, category, 10, True).pack(side="left")
            if limit > 0:
                ratio = used / limit
                make_label(line, f"{money(used)} из {money(limit)} · {ratio * 100:.0f}%", 9, True,
                           meter_color(ratio)).pack(side="right")
                ProgressBar(row, ratio, meter_color(ratio), height=7).pack(fill="x", pady=(5, 0))
            else:
                make_label(line, f"Потрачено {money(used)} · лимит не задан", 9, False, MUTED).pack(side="right")
            make_clickable(row, lambda c=category: self.edit_budget(c))
        tk.Frame(card, bg=CARD, height=6).pack()
        return card

    def edit_budget(self, category: str) -> None:
        current = database.get_budgets(self.uid).get(category, 0)

        def submit(values: dict) -> str | None:
            raw = values["limit"].replace(" ", "")
            if raw in ("", "0"):
                limit = 0.0
            else:
                parsed = parse_amount(raw)
                if parsed is None:
                    return "Введи целую сумму или 0, чтобы убрать лимит."
                limit = parsed
            database.set_budget(self.uid, category, limit)
            self.shell.toast("Лимит убран" if limit == 0 else f"Лимит «{category}» сохранён", "ok")
            self.render()
            return None

        FormDialog(self, f"Лимит: {category}",
                   [{"key": "limit", "label": "Лимит на месяц, сум", "amount": True,
                     "value": str(int(current)) if current else "",
                     "hint": "Оставь пустым или 0 — лимит будет убран."}],
                   submit, subtitle="Когда расходы подойдут к 80% лимита, появится предупреждение.")

    # ---- цели ----
    def _goals_card(self, parent: tk.Misc) -> tk.Frame:
        goals = database.list_goals(self.uid)
        card = make_card(parent)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=20, pady=(16, 2))
        make_label(top, "Цели накопления", 13, True).pack(side="left")
        make_button(top, "＋  Новая цель", self.add_goal, "primary", padx=12, pady=6,
                    font=("Segoe UI", 9, "bold")).pack(side="right")
        make_label(card, "Это отдельный учёт накоплений — на общий баланс он не влияет.", 9, False,
                   MUTED).pack(anchor="w", padx=20, pady=(0, 12))
        if not goals:
            empty_state(card, "◎", "Целей пока нет",
                        "Создай цель: ноутбук, отпуск или подушка безопасности.").pack(pady=30)
        for goal in goals:
            self._goal_block(card, goal)
        tk.Frame(card, bg=CARD, height=6).pack()
        return card

    def _goal_block(self, card: tk.Frame, goal: dict) -> None:
        target, saved = goal["target_amount"], goal["saved_amount"]
        ratio = saved / target if target else 0
        reached = saved >= target
        block = tk.Frame(card, bg=CARD_LIGHT)
        block.pack(fill="x", padx=20, pady=(0, 12))
        inner = tk.Frame(block, bg=CARD_LIGHT)
        inner.pack(fill="x", padx=14, pady=12)
        line = tk.Frame(inner, bg=CARD_LIGHT)
        line.pack(fill="x")
        make_label(line, goal["name"], 11, True, TEXT, CARD_LIGHT).pack(side="left")
        make_label(line, f"{min(ratio, 1) * 100:.0f}%", 11, True, GREEN if reached else ACCENT_HOVER,
                   CARD_LIGHT).pack(side="right")
        make_label(inner, f"{money(saved)} из {money(target)}", 9, False, SOFT, CARD_LIGHT).pack(
            anchor="w", pady=(3, 6))
        ProgressBar(inner, ratio, GREEN if reached else ACCENT, height=8, bg=CARD_LIGHT).pack(fill="x")
        info, color = self._goal_info(goal)
        make_label(inner, info, 9, False, color, CARD_LIGHT, wraplength=360, justify="left").pack(
            anchor="w", pady=(6, 0))
        buttons = tk.Frame(inner, bg=CARD_LIGHT)
        buttons.pack(fill="x", pady=(10, 0))
        small = ("Segoe UI", 9, "bold")
        make_button(buttons, "Удалить", lambda gid=goal["id"]: self.delete_goal(gid), "danger",
                    padx=10, pady=5, font=small).pack(side="right")
        make_button(buttons, "＋  Пополнить", lambda gid=goal["id"], n=goal["name"]: self.top_up(gid, n),
                    "ghost", padx=10, pady=5, font=small).pack(side="right", padx=(0, 8))

    @staticmethod
    def _goal_info(goal: dict) -> tuple[str, str]:
        remaining = goal["target_amount"] - goal["saved_amount"]
        if remaining <= 0:
            return "✓ Цель достигнута", GREEN
        fallback = (f"Осталось накопить {money(remaining)}", MUTED)
        if not goal["deadline"]:
            return fallback
        try:
            left = (date.fromisoformat(goal["deadline"]) - date.today()).days
        except ValueError:
            return fallback
        if left < 0:
            return f"Срок прошёл {-left} дн. назад · осталось {money(remaining)}", RED
        months = max(1, math.ceil(left / 30))
        return f"До {goal['deadline']}: {left} дн. · откладывай ≈ {money(remaining / months)} в месяц", MUTED

    def add_goal(self) -> None:
        fields = [
            {"key": "name", "label": "Название цели"},
            {"key": "target", "label": "Нужная сумма, сум", "amount": True},
            {"key": "saved", "label": "Уже накоплено, сум (необязательно)", "amount": True},
            {"key": "deadline", "label": "Срок (ГГГГ-ММ-ДД, необязательно)"},
        ]

        def submit(values: dict) -> str | None:
            name = values["name"]
            if len(name) < 2:
                return "Назови цель (минимум 2 символа)."
            target = parse_amount(values["target"])
            if target is None:
                return "Укажи нужную сумму — целое число больше нуля."
            saved = 0.0
            if values["saved"]:
                parsed = parse_amount(values["saved"])
                if parsed is None:
                    return "«Уже накоплено» — целое число больше нуля или пустое поле."
                saved = parsed
            deadline = None
            if values["deadline"]:
                deadline = parse_date(values["deadline"])
                if deadline is None:
                    return "Срок указывай в формате ГГГГ-ММ-ДД."
            database.add_goal(self.uid, name, target, saved, deadline)
            self.shell.toast("Цель добавлена", "ok")
            self.render()
            return None

        FormDialog(self, "Новая цель", fields, submit, "Создать")

    def top_up(self, goal_id: int, name: str) -> None:
        def submit(values: dict) -> str | None:
            amount = parse_amount(values["amount"])
            if amount is None:
                return "Введи целую сумму больше нуля."
            database.add_to_goal(self.uid, goal_id, amount)
            self.shell.toast(f"Цель «{name}» пополнена на {money(amount)}", "ok")
            self.render()
            return None

        FormDialog(self, f"Пополнить: {name}", [{"key": "amount", "label": "Сумма, сум", "amount": True}],
                   submit, "Пополнить", "green")

    def delete_goal(self, goal_id: int) -> None:
        if messagebox.askyesno("Удаление цели", "Удалить эту цель? Действие нельзя отменить."):
            database.delete_goal(self.uid, goal_id)
            self.shell.toast("Цель удалена", "ok")
            self.render()


# ───────────────────────────── Настройки ─────────────────────────────
class SettingsPage(Page):
    def __init__(self, parent: tk.Misc, shell) -> None:
        super().__init__(parent, shell)
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        wrap = tk.Frame(scroll.inner, bg=BG)
        wrap.pack(fill="both", expand=True, padx=32, pady=28)
        self.header(wrap, "Настройки", "Профиль, безопасность и управление данными.")
        self._profile(wrap)
        self._security(wrap)
        self._data(wrap)
        self._about(wrap)
        self._danger(wrap)

    @staticmethod
    def _section(parent: tk.Misc, title: str, text: str = "") -> tk.Frame:
        card = make_card(parent)
        card.pack(fill="x", pady=(0, 14))
        make_label(card, title, 13, True).pack(anchor="w", padx=22, pady=(18, 2))
        if text:
            make_label(card, text, 9, False, MUTED, wraplength=800, justify="left").pack(anchor="w", padx=22)
        body = tk.Frame(card, bg=CARD)
        body.pack(fill="x", padx=22, pady=(12, 18))
        return body

    # ---- профиль ----
    def _profile(self, wrap: tk.Misc) -> None:
        body = self._section(wrap, "Профиль", f"Логин: {self.shell.user['username']}")
        self.name_var = tk.StringVar(value=self.shell.user.get("full_name", ""))
        entry = make_entry(body, self.name_var)
        entry.pack(side="left", fill="x", expand=True, ipady=8, ipadx=8)
        entry.bind("<Return>", lambda e: self.save_name())
        make_button(body, "Сохранить имя", self.save_name, "primary").pack(side="left", padx=(10, 0))

    def save_name(self) -> None:
        name = self.name_var.get().strip()
        if len(name) < 2:
            self.shell.toast("Имя слишком короткое", "warn")
            return
        database.update_full_name(self.uid, name)
        self.shell.update_profile_name(name)
        self.shell.toast("Имя обновлено", "ok")

    # ---- безопасность ----
    def _security(self, wrap: tk.Misc) -> None:
        body = self._section(wrap, "Безопасность",
                             "Пароль хранится только в виде хеша (PBKDF2-SHA256 с солью), сам пароль нигде не записан.")
        make_button(body, "Сменить пароль", self.change_password, "ghost").pack(side="left")

    def change_password(self) -> None:
        fields = [
            {"key": "old", "label": "Текущий пароль", "kind": "password"},
            {"key": "new", "label": "Новый пароль", "kind": "password", "hint": "Не менее 6 символов."},
            {"key": "confirm", "label": "Повтори новый пароль", "kind": "password"},
        ]

        def submit(values: dict) -> str | None:
            user = database.get_user_by_username(self.shell.user["username"])
            if not user or not verify_password(values["old"], user["password_hash"], user["password_salt"]):
                return "Текущий пароль указан неверно."
            if len(values["new"]) < 6:
                return "Новый пароль должен содержать минимум 6 символов."
            if values["new"] != values["confirm"]:
                return "Пароли не совпадают."
            password_hash, salt = hash_password(values["new"])
            database.update_password(self.uid, password_hash, salt)
            self.shell.toast("Пароль изменён", "ok")
            return None

        FormDialog(self, "Смена пароля", fields, submit, "Изменить")

    # ---- данные ----
    def _data(self, wrap: tk.Misc) -> None:
        body = self._section(
            wrap, "Данные",
            "Резервная копия содержит всю базу FAMdefense на этом компьютере, включая другие профили.")
        make_button(body, "⭳  Экспорт всех операций (CSV)", self.export_all, "ghost").pack(side="left")
        make_button(body, "Резервная копия базы", self.backup, "ghost").pack(side="left", padx=10)
        make_button(body, "Удалить все мои данные", self.clear_data, "danger").pack(side="right")

    def export_all(self) -> None:
        rows = database.list_transactions(self.uid)
        if not rows:
            self.shell.toast("Пока нечего экспортировать", "warn")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"famdefense_{date.today().isoformat()}.csv")
        if not path:
            return
        try:
            database.export_transactions_csv(path, rows)
        except OSError as error:
            self.shell.toast(f"Не удалось сохранить файл: {error}", "error")
            return
        self.shell.toast(f"Экспортировано операций: {len(rows)}", "ok")

    def backup(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("База данных", "*.db")],
                                            initialfile=f"famdefense_backup_{date.today().isoformat()}.db")
        if not path:
            return
        try:
            database.backup_database(path)
        except Exception as error:  # noqa: BLE001
            self.shell.toast(f"Не удалось создать копию: {error}", "error")
            return
        self.shell.toast("Резервная копия создана", "ok")

    def clear_data(self) -> None:
        def submit(values: dict) -> str | None:
            if values["confirm"].upper() != "УДАЛИТЬ":
                return "Для подтверждения введи слово УДАЛИТЬ."
            database.clear_user_data(self.uid)
            self.shell.toast("Все операции, счета, лимиты и цели удалены", "ok")
            self.shell.show_page("Обзор")
            return None

        FormDialog(self, "Удалить все данные", [{"key": "confirm", "label": "Введи слово УДАЛИТЬ"}], submit,
                   "Удалить", "red", subtitle="Будут удалены операции, счета, лимиты и цели. Аккаунт останется.")

    # ---- о программе ----
    def _about(self, wrap: tk.Misc) -> None:
        body = self._section(wrap, "О программе")
        make_label(body, "FAMdefense 2.0 — учебная офлайн-версия менеджера личных финансов.", 10, False,
                   SOFT).pack(anchor="w")
        make_label(body, f"База данных: {database.DB_PATH}", 9, False, MUTED, wraplength=800,
                   justify="left").pack(anchor="w", pady=(4, 12))
        make_label(body, "Горячие клавиши", 10, True).pack(anchor="w")
        for keys, action in (("Ctrl+N", "новая операция"), ("Ctrl+1 … Ctrl+7", "переход по разделам"),
                             ("F5", "обновить страницу"), ("Delete", "удалить выбранное в таблице"),
                             ("Enter / Esc", "сохранить / закрыть окно")):
            row = tk.Frame(body, bg=CARD)
            row.pack(anchor="w", pady=2)
            make_label(row, keys, 9, True, ACCENT_HOVER, width=16, anchor="w").pack(side="left")
            make_label(row, action, 9, False, MUTED).pack(side="left")

    # ---- удаление аккаунта ----
    def _danger(self, wrap: tk.Misc) -> None:
        body = self._section(wrap, "Удаление аккаунта",
                             "Аккаунт и все его данные будут удалены без возможности восстановления.")
        make_button(body, "Удалить аккаунт", self.delete_account, "danger").pack(side="left")

    def delete_account(self) -> None:
        def submit(values: dict) -> str | None:
            user = database.get_user_by_username(self.shell.user["username"])
            if not user or not verify_password(values["password"], user["password_hash"], user["password_salt"]):
                return "Пароль указан неверно."
            database.delete_user(self.uid)
            self.shell.app.show_auth()
            return None

        FormDialog(self, "Удалить аккаунт", [{"key": "password", "label": "Пароль", "kind": "password"}],
                   submit, "Удалить навсегда", "red", subtitle="Для подтверждения введи пароль от аккаунта.")
