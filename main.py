"""FAMdefense — учебный офлайн-менеджер личных финансов. Запускай этот файл: python main.py"""
from __future__ import annotations

import ctypes
import math
import os
import time
import tkinter as tk
from datetime import date

import database
from pages import (BudgetsPage, DashboardPage, SettingsPage, StatsPage, TransactionsPage,
                   UtilitiesPage, current_month)
from security import hash_password, password_strength, verify_password
from widgets import (ACCENT, ACCENT_HOVER, BG, BORDER, CARD, CARD_LIGHT, EXPENSE_CATEGORIES, FIELD,
                     FONT, GREEN, INCOME_CATEGORIES, MUTED, RED, SIDEBAR, TEXT, YELLOW, FormDialog,
                     ProgressBar, apply_styles, make_button, make_label, money, parse_amount,
                     parse_date, SOFT, FAINT)


def enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


# ───────────────────────────── Окно приложения ─────────────────────────────
class FAMdefenseApp(tk.Tk):
    def __init__(self) -> None:
        enable_windows_dpi_awareness()
        super().__init__()
        self.title("FAMdefense — личные финансы")
        self.geometry("1280x840")
        self.minsize(1100, 720)
        self.configure(bg=BG)
        apply_styles(self)
        self.current_user: dict | None = None
        self.main_screen: MainScreen | None = None
        self.failed_attempts = 0       # защита от подбора пароля живёт здесь,
        self.locked_until = 0.0        # чтобы её нельзя было сбросить переключением экранов
        self._bind_shortcuts()
        self.show_auth()

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda e: self._shortcut(lambda m: m.open_transaction(m.default_type())))
        self.bind("<F5>", lambda e: self._shortcut(lambda m: m.refresh()))
        for number, name in enumerate(MainScreen.PAGES, start=1):
            self.bind(f"<Control-Key-{number}>", lambda e, n=name: self._shortcut(lambda m: m.show_page(n)))

    def _shortcut(self, action) -> None:
        screen = self.main_screen
        if screen is not None and screen.winfo_exists():
            action(screen)

    def clear_window(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def show_auth(self) -> None:
        self.current_user = None
        self.main_screen = None
        self.clear_window()
        AuthScreen(self, self).pack(fill="both", expand=True)

    def show_dashboard(self, user: dict, welcome: bool = False) -> None:
        self.current_user = user
        self.clear_window()
        self.main_screen = MainScreen(self, self, user)
        self.main_screen.pack(fill="both", expand=True)
        if welcome:
            self.main_screen.toast("Аккаунт создан! Добро пожаловать.", "ok")


# ───────────────────────────── Вход и регистрация ─────────────────────────────
class AuthScreen(tk.Frame):
    MAX_ATTEMPTS = 5
    LOCK_SECONDS = 30

    def __init__(self, parent: tk.Misc, app: FAMdefenseApp) -> None:
        super().__init__(parent, bg=BG)
        self.app = app
        self.mode = "login"
        self.username_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self.show_var = tk.BooleanVar(value=False)
        self._lock_job: str | None = None
        self._build()

    def destroy(self) -> None:
        if self._lock_job:
            self.after_cancel(self._lock_job)
            self._lock_job = None
        super().destroy()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        center = tk.Frame(self, bg=BG)
        center.grid(row=0, column=0)

        brand = tk.Frame(center, bg=BG)
        brand.pack(pady=(0, 28))
        tk.Label(brand, text="F", bg=ACCENT, fg="white", font=(FONT, 25, "bold"),
                 width=2, height=1, padx=5, pady=4).pack(side="left", padx=(0, 13))
        brand_text = tk.Frame(brand, bg=BG)
        brand_text.pack(side="left")
        tk.Label(brand_text, text="FAMdefense", bg=BG, fg=TEXT, font=(FONT, 26, "bold")).pack(anchor="w")
        tk.Label(brand_text, text="ТВОИ ФИНАНСЫ ПОД КОНТРОЛЕМ", bg=BG, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(3, 0))

        self.card = tk.Frame(center, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        self.card.pack(ipadx=40, ipady=32)
        self.title_label = tk.Label(self.card, text="С возвращением", bg=CARD, fg=TEXT,
                                    font=(FONT, 22, "bold"))
        self.title_label.pack(anchor="w", fill="x")
        self.subtitle_label = tk.Label(self.card, text="Войди, чтобы открыть свой финансовый обзор",
                                       bg=CARD, fg=MUTED, font=(FONT, 10))
        self.subtitle_label.pack(anchor="w", pady=(8, 24))

        self.fields = tk.Frame(self.card, bg=CARD)
        self.fields.pack(fill="x")
        self.holders: dict[str, tk.Frame] = {}
        self.username_field = self._add_field("username", "Логин", self.username_var)
        self.name_field = self._add_field("name", "Как тебя зовут", self.name_var)
        self.password_entry = self._add_field("password", "Пароль", self.password_var, show="•")
        self.holders["strength"] = self._build_strength()
        self.confirm_field = self._add_field("confirm", "Повтори пароль", self.confirm_var, show="•")
        self.holders["show"] = self._build_show_toggle()

        self.message_label = tk.Label(self.card, text="", bg=CARD, fg=RED, font=(FONT, 9),
                                      wraplength=360, justify="left")
        self.message_label.pack(anchor="w", pady=(1, 10))
        self.action_button = make_button(self.card, "Войти", self.submit, "primary", pady=11)
        self.action_button.pack(fill="x", ipady=3)

        switch = tk.Frame(self.card, bg=CARD)
        switch.pack(fill="x", pady=(18, 0))
        self.switch_text = tk.Label(switch, text="Нет аккаунта?", bg=CARD, fg=MUTED, font=(FONT, 10))
        self.switch_text.pack(side="left")
        self.switch_button = tk.Button(
            switch, text="Создать аккаунт", command=self.toggle_mode, bg=CARD, fg=ACCENT_HOVER,
            activebackground=CARD, activeforeground=TEXT, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 10, "bold"))
        self.switch_button.pack(side="left", padx=(6, 0))

        tk.Label(center, text="Локальная версия • Работает без интернета", bg=BG, fg=FAINT,
                 font=(FONT, 9)).pack(pady=(20, 0))
        self.password_var.trace_add("write", lambda *_: self._update_strength())
        self._update_mode()
        self.after(100, self.username_field.focus_set)

    def _add_field(self, key: str, label: str, variable: tk.StringVar, show: str = "") -> tk.Entry:
        holder = tk.Frame(self.fields, bg=CARD)
        tk.Label(holder, text=label, bg=CARD, fg=SOFT, font=(FONT, 10, "bold")).pack(anchor="w", pady=(0, 7))
        entry = tk.Entry(holder, textvariable=variable, show=show, bg=FIELD, fg=TEXT,
                         insertbackground=TEXT, relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT, font=(FONT, 11))
        entry.pack(fill="x", ipady=11, ipadx=12)
        entry.bind("<Return>", lambda e: self.submit())
        self.holders[key] = holder
        return entry

    def _build_strength(self) -> tk.Frame:
        holder = tk.Frame(self.fields, bg=CARD)
        self.strength_bar = ProgressBar(holder, 0, MUTED, height=5)
        self.strength_bar.pack(side="left", fill="x", expand=True)
        self.strength_label = make_label(holder, "", 9, True, MUTED)
        self.strength_label.pack(side="left", padx=(10, 0))
        return holder

    def _build_show_toggle(self) -> tk.Frame:
        holder = tk.Frame(self.fields, bg=CARD)
        tk.Checkbutton(holder, text="Показать пароль", variable=self.show_var, command=self._toggle_show,
                       bg=CARD, fg=MUTED, selectcolor=FIELD, activebackground=CARD,
                       activeforeground=TEXT, font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(anchor="w")
        return holder

    def _toggle_show(self) -> None:
        char = "" if self.show_var.get() else "•"
        self.password_entry.config(show=char)
        self.confirm_field.config(show=char)

    def _update_strength(self) -> None:
        ratio, label = password_strength(self.password_var.get())
        color = RED if ratio <= 0.4 else YELLOW if ratio <= 0.6 else GREEN
        self.strength_bar.set(ratio, color)
        self.strength_label.config(text=label, fg=color)

    def toggle_mode(self) -> None:
        self.mode = "register" if self.mode == "login" else "login"
        self.message_label.config(text="")
        self._update_mode()

    def _update_mode(self) -> None:
        registering = self.mode == "register"
        self.title_label.config(text="Создать аккаунт" if registering else "С возвращением")
        self.subtitle_label.config(
            text="Создай локальный профиль для учёта своих финансов" if registering
            else "Войди, чтобы открыть свой финансовый обзор")
        order = (("username", True), ("name", registering), ("password", True),
                 ("strength", registering), ("confirm", registering), ("show", True))
        for key, _ in order:
            self.holders[key].pack_forget()
        for key, visible in order:
            if visible:
                self.holders[key].pack(fill="x", pady=(0, 6 if key == "password" and registering else 14))
        self.action_button.config(text="Зарегистрироваться" if registering else "Войти")
        self.switch_text.config(text="Уже есть аккаунт?" if registering else "Нет аккаунта?")
        self.switch_button.config(text="Войти" if registering else "Создать аккаунт")

    # ---- защита от подбора пароля ----
    def _lock_remaining(self) -> int:
        return max(0, math.ceil(self.app.locked_until - time.monotonic()))

    def _show_lock(self) -> None:
        remaining = self._lock_remaining()
        if remaining <= 0:
            self.message_label.config(text="")
            self._lock_job = None
            return
        self.message_label.config(text=f"Слишком много неверных попыток. Подожди {remaining} с.")
        self._lock_job = self.after(1000, self._show_lock)

    def submit(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self.message_label.config(text="Заполни логин и пароль.")
            return
        if self.mode == "register":
            self._register_account(username, password)
        else:
            self._login(username, password)

    def _register_account(self, username: str, password: str) -> None:
        full_name = self.name_var.get().strip()
        if not full_name:
            self.message_label.config(text="Укажи своё имя.")
        elif len(username) < 3:
            self.message_label.config(text="Логин должен содержать минимум 3 символа.")
        elif len(password) < 6:
            self.message_label.config(text="Пароль должен содержать минимум 6 символов.")
        elif password != self.confirm_var.get():
            self.message_label.config(text="Пароли не совпадают.")
        elif database.get_user_by_username(username):
            self.message_label.config(text="Такой логин уже занят. Выбери другой.")
        else:
            password_hash, salt = hash_password(password)
            try:
                user_id = database.create_user(username, full_name, password_hash, salt)
            except Exception as error:  # noqa: BLE001
                self.message_label.config(text=f"Не удалось создать аккаунт: {error}")
                return
            self.app.show_dashboard({"id": user_id, "username": username, "full_name": full_name},
                                    welcome=True)

    def _login(self, username: str, password: str) -> None:
        if self._lock_remaining() > 0:
            if self._lock_job is None:
                self._show_lock()
            return
        user = database.get_user_by_username(username)
        if user is None:
            hash_password(password)  # одинаковое время ответа для неизвестного логина
        valid = user is not None and verify_password(password, user["password_hash"], user["password_salt"])
        if not valid:
            self.app.failed_attempts += 1
            if self.app.failed_attempts >= self.MAX_ATTEMPTS:
                self.app.failed_attempts = 0
                self.app.locked_until = time.monotonic() + self.LOCK_SECONDS
                self._show_lock()
            else:
                left = self.MAX_ATTEMPTS - self.app.failed_attempts
                self.message_label.config(text=f"Неверный логин или пароль. Осталось попыток: {left}.")
            return
        self.app.failed_attempts = 0
        self.app.show_dashboard({"id": user["id"], "username": user["username"],
                                 "full_name": user["full_name"]})


# ───────────────────────────── Главный экран ─────────────────────────────
class MainScreen(tk.Frame):
    NAV_ITEMS = [("◈", "Обзор"), ("＋", "Доходы"), ("－", "Расходы"), ("▤", "Коммунальные"),
                 ("▥", "Статистика"), ("◎", "Бюджеты и цели")]
    PAGES = [name for _, name in NAV_ITEMS] + ["Настройки"]

    def __init__(self, parent: tk.Misc, app: FAMdefenseApp, user: dict) -> None:
        super().__init__(parent, bg=BG)
        self.app = app
        self.user = user
        self.active_page = "Обзор"
        self.month = current_month()   # месяц, выбранный на странице «Обзор»
        self.chart_months = 6          # сколько месяцев показывает график на «Обзоре»
        self.page: tk.Frame | None = None
        self._toast: tk.Frame | None = None
        self._toast_job: str | None = None
        self._build()

    def destroy(self) -> None:
        if self._toast_job:
            self.after_cancel(self._toast_job)
            self._toast_job = None
        super().destroy()

    # ---- каркас ----
    def _build(self) -> None:
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=244)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=22, pady=(28, 42))
        tk.Label(brand, text="F", bg=ACCENT, fg="white", font=(FONT, 18, "bold"), width=2,
                 pady=5).pack(side="left", padx=(0, 11))
        tk.Label(brand, text="FAMdefense", bg=SIDEBAR, fg=TEXT, font=(FONT, 16, "bold")).pack(side="left")

        tk.Label(self.sidebar, text="ГЛАВНОЕ МЕНЮ", bg=SIDEBAR, fg="#71839F",
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=24, pady=(0, 13))
        self.nav_buttons: dict[str, tk.Button] = {}
        for symbol, label in self.NAV_ITEMS:
            self._nav_button(self.sidebar, f"  {symbol}     {label}", label, 11, 14).pack(
                fill="x", padx=12, pady=3)

        bottom = tk.Frame(self.sidebar, bg=SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=12, pady=18)
        self._nav_button(bottom, "  ⚙     Настройки", "Настройки", 10, 12).pack(fill="x")
        tk.Frame(bottom, bg=BORDER, height=1).pack(fill="x", pady=12)
        self.name_label = tk.Label(bottom, text=self.user.get("full_name", "Пользователь"), bg=SIDEBAR,
                                   fg=TEXT, font=(FONT, 10, "bold"), anchor="w")
        self.name_label.pack(fill="x", padx=12)
        tk.Label(bottom, text=f"@{self.user.get('username', '')}", bg=SIDEBAR, fg=MUTED, font=(FONT, 9),
                 anchor="w").pack(fill="x", padx=12, pady=(3, 8))
        tk.Button(bottom, text="Выйти из аккаунта", command=self.app.show_auth, bg=SIDEBAR, fg=RED,
                  activebackground=CARD_LIGHT, activeforeground=RED, relief="flat", bd=0, cursor="hand2",
                  font=(FONT, 10), anchor="w").pack(fill="x", padx=12)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.show_page("Обзор")

    def _nav_button(self, parent: tk.Misc, text: str, page: str, size: int, pad: int) -> tk.Button:
        button = tk.Button(parent, text=text, anchor="w", command=lambda: self.show_page(page),
                           bg=SIDEBAR, fg=MUTED, activebackground=CARD_LIGHT, activeforeground=TEXT,
                           relief="flat", bd=0, cursor="hand2", font=(FONT, size), padx=18, pady=pad)
        self.nav_buttons[page] = button
        return button

    def _make_page(self, name: str) -> tk.Frame:
        factories = {
            "Обзор": lambda: DashboardPage(self.content, self),
            "Доходы": lambda: TransactionsPage(self.content, self, "income"),
            "Расходы": lambda: TransactionsPage(self.content, self, "expense"),
            "Коммунальные": lambda: UtilitiesPage(self.content, self),
            "Статистика": lambda: StatsPage(self.content, self),
            "Бюджеты и цели": lambda: BudgetsPage(self.content, self),
            "Настройки": lambda: SettingsPage(self.content, self),
        }
        return factories[name]()

    def show_page(self, name: str) -> None:
        self.active_page = name
        for label, button in self.nav_buttons.items():
            active = label == name
            button.config(bg=CARD_LIGHT if active else SIDEBAR, fg=TEXT if active else MUTED)
        for child in self.content.winfo_children():
            child.destroy()
        self.page = self._make_page(name)
        self.page.pack(fill="both", expand=True)

    def refresh(self) -> None:
        if self.page is not None and self.page.winfo_exists():
            self.page.refresh()  # type: ignore[attr-defined]

    def default_type(self) -> str:
        return "income" if self.active_page == "Доходы" else "expense"

    def update_profile_name(self, name: str) -> None:
        self.user["full_name"] = name
        self.name_label.config(text=name)

    # ---- уведомления ----
    def toast(self, text: str, kind: str = "ok") -> None:
        if self._toast_job:
            self.after_cancel(self._toast_job)
        if self._toast is not None:
            self._toast.destroy()
        color = {"ok": GREEN, "warn": YELLOW, "error": RED, "info": ACCENT}.get(kind, ACCENT)
        box = tk.Frame(self, bg=CARD_LIGHT, highlightbackground=color, highlightthickness=1)
        tk.Label(box, text="●", bg=CARD_LIGHT, fg=color, font=(FONT, 10)).pack(side="left", padx=(14, 6), pady=12)
        tk.Label(box, text=text, bg=CARD_LIGHT, fg=TEXT, font=(FONT, 10), wraplength=420,
                 justify="left").pack(side="left", padx=(0, 16))
        box.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
        box.lift()
        self._toast = box
        self._toast_job = self.after(3400, self._hide_toast)

    def _hide_toast(self) -> None:
        if self._toast is not None:
            self._toast.destroy()
        self._toast, self._toast_job = None, None

    # ---- лимиты бюджета ----
    def budget_warning(self, category: str, tx_date: str) -> str | None:
        limit = database.get_budgets(self.user["id"]).get(category)
        if not limit:
            return None
        spent = sum(r["amount"] for r in
                    database.list_transactions(self.user["id"], "expense", month=tx_date[:7])
                    if r["category"] == category)
        if spent > limit:
            return f"Расход сохранён. Лимит «{category}» превышен: {money(spent)} из {money(limit)}"
        if spent >= 0.8 * limit:
            return f"Расход сохранён. «{category}»: использовано {spent / limit * 100:.0f}% лимита"
        return None

    # ---- добавление и изменение операции (общее окно для всех страниц) ----
    def open_transaction(self, default_type: str = "expense", record: dict | None = None) -> None:
        editing = record is not None
        kind = record["transaction_type"] if editing else default_type
        categories = list(INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES)
        category = record["category"] if editing else categories[0]
        if category not in categories:
            categories.insert(0, category)

        fields: list[dict] = []
        if not editing:
            fields.append({"key": "type", "label": "Тип операции", "kind": "segment",
                           "values": [("income", "Доход"), ("expense", "Расход")], "value": kind,
                           "on_change": self._type_changed})
        fields += [
            {"key": "category", "label": "Категория", "kind": "combo", "values": categories, "value": category},
            {"key": "amount", "label": "Сумма, сум", "amount": True, "hint": "Целое число, например 150000",
             "value": str(int(record["amount"])) if editing else ""},
            {"key": "date", "label": "Дата (ГГГГ-ММ-ДД)",
             "value": record["transaction_date"] if editing else date.today().isoformat()},
            {"key": "note", "label": "Комментарий (необязательно)",
             "value": (record["note"] or "") if editing else ""},
        ]

        def submit(values: dict) -> str | None:
            tx_type = kind if editing else values["type"]
            amount = parse_amount(values["amount"])
            if amount is None:
                return "Введи целую сумму в сумах, больше нуля."
            tx_date = parse_date(values["date"])
            if tx_date is None:
                return "Проверь дату. Используй формат ГГГГ-ММ-ДД."
            try:
                if editing:
                    database.update_transaction(self.user["id"], record["id"], values["category"], amount,
                                                values["note"], tx_date)
                else:
                    database.add_transaction(self.user["id"], tx_type, values["category"], amount,
                                             values["note"], tx_date)
            except Exception as error:  # noqa: BLE001
                return f"Не удалось сохранить операцию: {error}"
            warning = self.budget_warning(values["category"], tx_date) if tx_type == "expense" else None
            if warning:
                self.toast(warning, "warn")
            elif editing:
                self.toast("Изменения сохранены", "ok")
            else:
                self.toast("Доход сохранён" if tx_type == "income" else "Расход сохранён", "ok")
            self.refresh()
            return None

        FormDialog(self, "Изменить операцию" if editing else "Новая операция", fields, submit,
                   "Сохранить", "primary")

    @staticmethod
    def _type_changed(dialog: FormDialog, value: str) -> None:
        dialog.set_choices("category", INCOME_CATEGORIES if value == "income" else EXPENSE_CATEGORIES)


def main() -> None:
    database.initialize_database()
    app = FAMdefenseApp()
    app.mainloop()


if __name__ == "__main__":
    main()
