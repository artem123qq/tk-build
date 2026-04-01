# tk_builder_pro_max_rus_v2.py
"""
Продвинутая и исправленная версия конструктора GUI на Tkinter (русский).
- Клики по кнопкам/чекбоксам работают в режиме редактирования.
- Перетаскивание начинается только после движения (порог).
- Canvas управляет позициями/размерами через create_window/coords/itemconfigure.
- Новые виджеты: Radio, Listbox, Text, Scale, Combobox (ttk).
- Меню, тулбар, свойства, сохранение/загрузка JSON, экспорт в .py, предпросмотр.
"""

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
import json

GRID_SIZE = 20
AUTOSNAP_THRESHOLD = 12
DRAG_THRESHOLD = 6  # пикселей движения, чтобы начать drag

class WidgetMeta:
    def __init__(self, wtype, widget, win_id, props):
        self.wtype = wtype
        self.widget = widget
        self.win_id = win_id
        self.props = props  # text, width, height, x, y, font_size, fg, bg, extra
        self.handle = None

class TkBuilderPro:
    def __init__(self, root):
        self.root = root
        root.title("Конструктор GUI — PRO (rus) — v2")
        root.geometry("1280x780")

        # state
        self.widgets = {}          # id(widget) -> WidgetMeta
        self.selected = []         # list of widget objects (primary is last)
        self.canvas_w = 900
        self.canvas_h = 600
        self.grid_on = False

        # counters for exporting readable names
        self.name_counters = {}

        # --- Menu ---
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Сохранить проект (JSON)...", command=self.save_json)
        filemenu.add_command(label="Загрузить проект (JSON)...", command=self.load_json)
        filemenu.add_separator()
        filemenu.add_command(label="Экспорт в Python (.py)...", command=self.export_python)
        filemenu.add_separator()
        filemenu.add_command(label="Выход", command=root.quit)
        menubar.add_cascade(label="Файл", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Предпросмотр", command=self.preview)
        viewmenu.add_checkbutton(label="Сетка (snap)", command=self.toggle_grid, onvalue=True, offvalue=False,
                                 variable=tk.BooleanVar(value=False), )
        menubar.add_cascade(label="Вид", menu=viewmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="О программе", command=lambda: messagebox.showinfo("О программе",
                                                                                       "PRO TkBuilder v2 — редактор GUI на Tkinter"))
        menubar.add_cascade(label="Справка", menu=helpmenu)

        root.config(menu=menubar)

        # --- Layout: toolbar | canvas | props ---
        self.toolbar = tk.Frame(root, width=220, bg="#f3f3f3")
        self.toolbar.pack(side="left", fill="y")

        main = tk.Frame(root)
        main.pack(side="left", expand=True, fill="both")

        self.canvas_frame = tk.Frame(main)
        self.canvas_frame.pack(side="left", expand=True, fill="both", padx=6, pady=6)

        self.prop_frame = tk.Frame(root, width=260, bg="#fafafa")
        self.prop_frame.pack(side="right", fill="y")

        # --- Toolbar (compact, clean) ---
        tk.Label(self.toolbar, text="Добавить", bg="#f3f3f3", font=("Arial", 11, "bold")).pack(pady=8)

        # Основные виджеты
        main_widgets = [
            ("Кнопка", "Button"),
            ("Метка", "Label"),
            ("Поле ввода", "Entry"),
            ("Флажок", "Checkbutton"),
            ("Радио", "Radiobutton"),
        ]

        for text, wtype in main_widgets:
            tk.Button(
                self.toolbar,
                text=text,
                width=18,
                command=lambda t=wtype: self.add_widget_from_toolbar(t)
            ).pack(pady=4)

        # Дополнительные виджеты (в выпадающем блоке)
        extra_widgets = [
            ("Список", "Listbox"),
            ("Текст", "Text"),
            ("Ползунок", "Scale"),
            ("Combobox", "Combobox"),
        ]

        self.extra_frame = None

        def toggle_extra():
            if self.extra_frame and self.extra_frame.winfo_ismapped():
                self.extra_frame.pack_forget()
                extra_btn.config(text="Дополнительно ▼")
            else:
                if not self.extra_frame:
                    self.extra_frame = tk.Frame(self.toolbar, bg="#e9e9e9")
                    for text, wtype in extra_widgets:
                        tk.Button(
                            self.extra_frame,
                            text=text,
                            width=18,
                            command=lambda t=wtype: self.add_widget_from_toolbar(t)
                        ).pack(pady=3)

                # вот тут фикс → вставляем сразу ПОД extra_btn
                self.extra_frame.pack(after=extra_btn, pady=5)
                extra_btn.config(text="Дополнительно ▲")

        extra_btn = tk.Button(self.toolbar, text="Дополнительно ▼", width=18, command=toggle_extra)
        extra_btn.pack(pady=6)

        ttk.Separator(self.toolbar, orient="horizontal").pack(fill="x", pady=8)
        tk.Button(self.toolbar, text="Сохранить проект (JSON)...", width=20, command=self.save_json, bg="#cfeecd").pack(pady=4)
        tk.Button(self.toolbar, text="Загрузить проект (JSON)...", width=20, command=self.load_json, bg="#fff2b2").pack(pady=4)
        tk.Button(self.toolbar, text="Экспорт .py...", width=20, command=self.export_python, bg="#cfe0ff").pack(pady=4)
        tk.Button(self.toolbar, text="Предпросмотр", width=20, command=self.preview, bg="#ffd7b2").pack(pady=4)
        tk.Button(self.toolbar, text="Очистить холст", width=20, command=self.clear_canvas, bg="#ffcfcf").pack(pady=6)

        ttk.Separator(self.toolbar, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(self.toolbar, text="Холст (px):", bg="#f3f3f3").pack(pady=(6,2))
        sizef = tk.Frame(self.toolbar, bg="#f3f3f3")
        sizef.pack()
        tk.Label(sizef, text="W:", bg="#f3f3f3").grid(row=0, column=0)
        self.width_e = tk.Entry(sizef, width=6)
        self.width_e.insert(0, str(self.canvas_w)); self.width_e.grid(row=0, column=1, padx=6)
        tk.Label(sizef, text="H:", bg="#f3f3f3").grid(row=1, column=0)
        self.height_e = tk.Entry(sizef, width=6)
        self.height_e.insert(0, str(self.canvas_h)); self.height_e.grid(row=1, column=1, padx=6)
        tk.Button(self.toolbar, text="Применить", command=self.resize_canvas).pack(pady=6)

        # --- Canvas ---
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", width=self.canvas_w, height=self.canvas_h)
        self.canvas.pack(expand=True, fill="both")
        self.canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e))
        # click on empty canvas could add widget if you want — currently toolbar adds

        # --- Properties panel (right) ---
        tk.Label(self.prop_frame, text="Свойства", bg="#fafafa", font=("Arial", 11, "bold")).pack(pady=8)
        self.prop_label = tk.Label(self.prop_frame, text="Нет выделения", bg="#fafafa", fg="#666")
        self.prop_label.pack()

        frame = tk.Frame(self.prop_frame, bg="#fafafa")
        frame.pack(padx=8, pady=8, fill="x")

        tk.Label(frame, text="Текст:", bg="#fafafa").grid(row=0, column=0, sticky="w")
        self.text_var = tk.StringVar()
        self.text_entry = tk.Entry(frame, textvariable=self.text_var, width=22)
        self.text_entry.grid(row=0, column=1, pady=4)

        tk.Label(frame, text="Ширина:", bg="#fafafa").grid(row=1, column=0, sticky="w")
        self.width_var = tk.IntVar()
        self.width_spin = tk.Spinbox(frame, from_=10, to=2000, textvariable=self.width_var, width=8, command=self.apply_props)
        self.width_spin.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(frame, text="Высота:", bg="#fafafa").grid(row=2, column=0, sticky="w")
        self.height_var = tk.IntVar()
        self.height_spin = tk.Spinbox(frame, from_=10, to=2000, textvariable=self.height_var, width=8, command=self.apply_props)
        self.height_spin.grid(row=2, column=1, sticky="w", pady=2)

        tk.Label(frame, text="Размер шрифта:", bg="#fafafa").grid(row=3, column=0, sticky="w")
        self.font_var = tk.IntVar(value=12)
        self.font_spin = tk.Spinbox(frame, from_=6, to=72, textvariable=self.font_var, width=8, command=self.apply_props)
        self.font_spin.grid(row=3, column=1, sticky="w", pady=2)

        tk.Button(self.prop_frame, text="Цвет текста", command=lambda: self.choose_color("fg")).pack(fill="x", padx=8, pady=6)
        tk.Button(self.prop_frame, text="Цвет фона", command=lambda: self.choose_color("bg")).pack(fill="x", padx=8, pady=2)
        tk.Button(self.prop_frame, text="Удалить выделенные", command=self.delete_selected).pack(fill="x", padx=8, pady=8)

        # keyboard binds
        root.bind("<Delete>", lambda e: self.delete_selected())
        root.bind("<Escape>", lambda e: self.clear_selection())

    # ------------------- Canvas / Grid -------------------
    def _on_canvas_configure(self, event):
        self.canvas_w, self.canvas_h = event.width, event.height
        if self.grid_on:
            self.draw_grid()

    def draw_grid(self):
        self.canvas.delete("grid_line")
        w = self.canvas.winfo_width(); h = self.canvas.winfo_height()
        for i in range(0, w, GRID_SIZE):
            self.canvas.create_line(i, 0, i, h, fill="#eee", tags="grid_line")
        for j in range(0, h, GRID_SIZE):
            self.canvas.create_line(0, j, w, j, fill="#eee", tags="grid_line")
        self.grid_on = True

    def toggle_grid(self):
        self.grid_on = not self.grid_on
        if self.grid_on:
            self.draw_grid()
        else:
            self.canvas.delete("grid_line")

    def resize_canvas(self):
        try:
            w = int(self.width_e.get()); h = int(self.height_e.get())
            self.canvas.config(width=w, height=h)
            self.canvas_w, self.canvas_h = w, h
            if self.grid_on:
                self.draw_grid()
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные целые размеры")

    # ------------------- Add / Create widgets -------------------
    def add_widget_from_toolbar(self, wtype):
        # default position with offset to avoid stacking
        x, y = 30, 30
        occupied = {(m.props.get("x", 0), m.props.get("y", 0)) for m in self.widgets.values()}
        while (x, y) in occupied:
            x += 30; y += 20
        self.create_widget(wtype, x, y)

    def create_widget(self, wtype, x, y, props=None):
        if props is None:
            props = {}
        defaults = {
            "Button": {"text": "Кнопка", "bg": "#4A90E2", "fg": "white", "width": 140, "height": 34, "font_size": 12},
            "Label": {"text": "Метка", "bg": "#E0E0E0", "fg": "#222", "width": 140, "height": 30, "font_size": 12},
            "Entry": {"text": "Поле ввода", "bg": "white", "fg": "black", "width": 180, "height": 28, "font_size": 12},
            "Checkbutton": {"text": "Флажок", "bg": "#f8f8f8", "fg": "black", "width": 140, "height": 30,
                            "font_size": 12},
            "Radiobutton": {"text": "Радио", "bg": "#f8f8f8", "fg": "black", "width": 140, "height": 30,
                            "font_size": 12},
            "Listbox": {"text": "", "bg": "white", "fg": "black", "width": 180, "height": 80, "font_size": 12},
            "Text": {"text": "", "bg": "white", "fg": "black", "width": 240, "height": 120, "font_size": 12},
            "Scale": {"text": "", "bg": "white", "fg": "black", "width": 160, "height": 30, "font_size": 12},
            "Combobox": {"text": "", "bg": "white", "fg": "black", "width": 140, "height": 30, "font_size": 12},
        }
        d = defaults.get(wtype, {})
        text = props.get("text", d.get("text", ""))
        width = props.get("width", d.get("width", 140))
        height = props.get("height", d.get("height", 30))
        font_size = props.get("font_size", d.get("font_size", 12))
        fg = props.get("fg", d.get("fg", "black"))
        bg = props.get("bg", d.get("bg", "SystemButtonFace"))

        # создание виджета
        if wtype == "Button":
            w = tk.Button(self.canvas, text=text, bg=bg, fg=fg)
        elif wtype == "Label":
            w = tk.Label(self.canvas, text=text, bg=bg, fg=fg, anchor="w")
        elif wtype == "Entry":
            w = tk.Entry(self.canvas, bg=bg, fg=fg)
            if text: w.insert(0, text)
        elif wtype == "Checkbutton":
            var = tk.IntVar(value=props.get("value", 0))
            w = tk.Checkbutton(self.canvas, text=text, variable=var, bg=bg, fg=fg)
            w._var = var
        elif wtype == "Radiobutton":
            var = tk.IntVar(value=props.get("value", 0))
            w = tk.Radiobutton(self.canvas, text=text, variable=var, value=1, bg=bg, fg=fg)
            w._var = var
        elif wtype == "Listbox":
            w = tk.Listbox(self.canvas)
        elif wtype == "Text":
            w = tk.Text(self.canvas, wrap="word")
            if text: w.insert("1.0", text)
        elif wtype == "Scale":
            w = tk.Scale(self.canvas, orient="horizontal", from_=0, to=100)
        elif wtype == "Combobox":
            w = ttk.Combobox(self.canvas, values=props.get("values", []))
            if text: w.set(text)
        else:
            return

        try:
            w.config(font=("Arial", font_size))
        except Exception:
            pass

        win_id = self.canvas.create_window(x, y, window=w, anchor="nw", width=width, height=height)
        meta = WidgetMeta(wtype, w, win_id, {"text": text, "width": width, "height": height,
                                             "x": x, "y": y, "font_size": font_size, "fg": fg, "bg": bg})
        self.widgets[id(w)] = meta

        # Бинды для перетаскивания (исправленные!)
        w.bind("<Button-1>", lambda e, widget=w: self._on_press(e, widget))
        w.bind("<B1-Motion>", lambda e, widget=w: self._on_motion(e, widget))
        w.bind("<ButtonRelease-1>", lambda e, widget=w: self._on_release(e, widget))
        w.bind("<Button-3>", lambda e, widget=w: self._on_right_click(e, widget))
        w.bind("<Double-Button-1>", lambda e, widget=w: self.edit_text_quick(widget))

        self._make_resizable(meta)
        self.canvas.tag_raise(win_id)
        w.lift()
        self.clear_selection()
        self.select_widget(w)
        return w

    def _on_press(self, event, widget):
        meta = self.widgets.get(id(widget))
        if not meta: return
        widget._press_x, widget._press_y = event.x_root, event.y_root
        widget._dragging = False
        widget._orig_coords = {}
        for w in self.selected:
            m = self.widgets.get(id(w))
            if m:
                coords = self.canvas.coords(m.win_id)
                if coords:
                    widget._orig_coords[id(w)] = (int(coords[0]), int(coords[1]))

    def _on_motion(self, event, widget):
        meta = self.widgets.get(id(widget))
        if not meta: return "break"
        dx = event.x_root - getattr(widget, "_press_x", event.x_root)
        dy = event.y_root - getattr(widget, "_press_y", event.y_root)

        if not getattr(widget, "_dragging", False):
            if abs(dx) < DRAG_THRESHOLD and abs(dy) < DRAG_THRESHOLD:
                return
            widget._dragging = True

        coords = self.canvas.coords(meta.win_id)
        base_x, base_y = (int(coords[0]), int(coords[1])) if coords else (meta.props["x"], meta.props["y"])
        nx, ny = max(0, base_x + dx), max(0, base_y + dy)

        if self.grid_on:
            nx = (nx // GRID_SIZE) * GRID_SIZE
            ny = (ny // GRID_SIZE) * GRID_SIZE

        if widget in self.selected and len(self.selected) > 1:
            prim_orig = widget._orig_coords.get(id(widget), (base_x, base_y))
            dx_rel, dy_rel = nx - prim_orig[0], ny - prim_orig[1]
            for w in self.selected:
                m = self.widgets.get(id(w))
                if not m: continue
                orig = widget._orig_coords.get(id(w))
                if not orig: continue
                tx, ty = max(0, orig[0] + dx_rel), max(0, orig[1] + dy_rel)
                if self.grid_on:
                    tx = (tx // GRID_SIZE) * GRID_SIZE
                    ty = (ty // GRID_SIZE) * GRID_SIZE
                self.canvas.coords(m.win_id, tx, ty)
                m.props["x"], m.props["y"] = tx, ty
                if m.handle: self._update_handle(m)
        else:
            self.canvas.coords(meta.win_id, nx, ny)
            meta.props["x"], meta.props["y"] = nx, ny
            if meta.handle: self._update_handle(meta)

        widget._press_x, widget._press_y = event.x_root, event.y_root
        return "break"

    def _on_release(self, event, widget):
        meta = self.widgets.get(id(widget))
        if not meta: return
        was_dragging = getattr(widget, "_dragging", False)
        widget._dragging = False
        widget._orig_coords = {}

        if was_dragging:
            return "break"  # не даём кнопкам/чекбоксам случайно срабатывать при перетаскивании
        else:
            state = event.state
            shift = (state & 0x0001) != 0
            if shift:
                self.select_widget(widget, multi=True)
            else:
                self.clear_selection()
                self.select_widget(widget, multi=False)
            return  # оставляем стандартное поведение (клик по кнопке, галочка и т.д.)

    def _on_right_click(self, event, widget):
        # right click selects without triggering default action
        self.clear_selection()
        self.select_widget(widget)
        return "break"

    # ---------------- selection / properties ----------------
    def select_widget(self, widget, multi=False):
        if not multi:
            self.clear_selection()
        if widget not in self.selected:
            self.selected.append(widget)
            # visual cue
            try:
                widget.config(relief="solid", bd=1)
            except Exception:
                pass
        self._update_props(widget)

    def clear_selection(self):
        for w in list(self.selected):
            try:
                w.config(relief="flat", bd=0)
            except Exception:
                pass
        self.selected.clear()
        self._update_props(None)

    def _update_props(self, widget):
        if widget is None:
            self.prop_label.config(text="Нет выделения")
            self.text_var.set("")
            self.width_var.set(0); self.height_var.set(0); self.font_var.set(12)
            return
        meta = self.widgets.get(id(widget))
        if not meta:
            return
        self.prop_label.config(text=f"Выделено: {meta.wtype}")
        # text
        txt = ""
        try:
            if meta.wtype == "Text":
                txt = widget.get("1.0", "1.0 + 40 chars")
            elif meta.wtype == "Entry":
                txt = widget.get()
            elif meta.wtype == "Combobox":
                txt = widget.get()
            elif meta.wtype == "Listbox":
                # show nothing editable for listbox here
                txt = ""
            else:
                txt = widget.cget("text") if 'text' in widget.keys() else meta.props.get("text","")
        except Exception:
            txt = meta.props.get("text","")
        self.text_var.set(txt)
        # sizes (read actual widget sizes for accuracy)
        self.root.update_idletasks()
        self.width_var.set(widget.winfo_width())
        self.height_var.set(widget.winfo_height())
        self.font_var.set(meta.props.get("font_size", 12))

    def apply_props(self):
        if not self.selected:
            return
        primary = self.selected[-1]
        meta = self.widgets.get(id(primary))
        if not meta:
            return
        txt = self.text_var.get()
        try:
            if meta.wtype == "Text":
                primary.delete("1.0", "end")
                primary.insert("1.0", txt)
            elif meta.wtype == "Entry":
                primary.delete(0, "end")
                primary.insert(0, txt)
            elif meta.wtype == "Combobox":
                primary.set(txt)
            elif meta.wtype == "Listbox":
                # not editing items here
                pass
            else:
                primary.config(text=txt)
            meta.props["text"] = txt
        except Exception:
            pass

        # sizes via canvas.itemconfigure (no flicker)
        try:
            w = int(self.width_var.get()); h = int(self.height_var.get())
            self.canvas.itemconfigure(meta.win_id, width=w, height=h)
            meta.props["width"], meta.props["height"] = w, h
            self.root.update_idletasks()
            if meta.handle:
                self._update_handle(meta)
        except Exception:
            pass

        try:
            fs = int(self.font_var.get())
            primary.config(font=("Arial", fs))
            meta.props["font_size"] = fs
            self.root.update_idletasks()
            if meta.handle:
                self._update_handle(meta)
        except Exception:
            pass

    def choose_color(self, which):
        if not self.selected:
            messagebox.showinfo("Инфо", "Сначала выберите элемент.")
            return
        col = colorchooser.askcolor(title="Выберите цвет")[1]
        if not col:
            return
        for w in list(self.selected):
            meta = self.widgets.get(id(w))
            if not meta:
                continue
            try:
                if which == "fg":
                    w.config(fg=col)
                    meta.props["fg"] = col
                else:
                    w.config(bg=col)
                    meta.props["bg"] = col
            except Exception:
                pass

    # ---------------- resize handle ----------------
    def _make_resizable(self, meta):
        w = meta.widget
        handle = tk.Frame(self.canvas, width=9, height=9, bg="#222", cursor="bottom_right_corner")
        meta.handle = handle

        def place_handle():
            coords = self.canvas.coords(meta.win_id)
            if not coords:
                return
            x, y = int(coords[0]), int(coords[1])
            self.root.update_idletasks()
            try:
                ww = w.winfo_width(); hh = w.winfo_height()
            except Exception:
                ww = meta.props.get("width", 100); hh = meta.props.get("height", 30)
            handle.place(x=x + ww - 6, y=y + hh - 6)

        def start_resize(e):
            handle._start_w = w.winfo_width()
            handle._start_h = w.winfo_height()
            handle._start_x = e.x_root
            handle._start_y = e.y_root

        def do_resize(e):
            dx = e.x_root - handle._start_x
            dy = e.y_root - handle._start_y
            new_w = max(10, handle._start_w + dx)
            new_h = max(10, handle._start_h + dy)
            if self.grid_on:
                new_w = (new_w // GRID_SIZE) * GRID_SIZE
                new_h = (new_h // GRID_SIZE) * GRID_SIZE
            try:
                self.canvas.itemconfigure(meta.win_id, width=new_w, height=new_h)
            except Exception:
                pass
            meta.props["width"], meta.props["height"] = new_w, new_h
            self.root.update_idletasks()
            place_handle()

        handle.bind("<Button-1>", start_resize)
        handle.bind("<B1-Motion>", do_resize)
        # initial placement after widget is created
        self.root.after(30, place_handle)

    def _update_handle(self, meta):
        if not meta or not meta.handle:
            return
        coords = self.canvas.coords(meta.win_id)
        if not coords:
            return
        x, y = int(coords[0]), int(coords[1])
        self.root.update_idletasks()
        try:
            w = meta.widget.winfo_width(); h = meta.widget.winfo_height()
        except Exception:
            w = meta.props.get("width", 100); h = meta.props.get("height", 30)
        try:
            meta.handle.place(x=x + w - 6, y=y + h - 6)
        except Exception:
            pass

    # ---------------- delete / clear ----------------
    def delete_selected(self):
        if not self.selected:
            return
        if not messagebox.askyesno("Удаление", "Удалить выделенные элементы?"):
            return
        for w in list(self.selected):
            meta = self.widgets.pop(id(w), None)
            try:
                if meta:
                    if meta.handle:
                        meta.handle.destroy()
                    try:
                        self.canvas.delete(meta.win_id)
                    except Exception:
                        pass
                    w.destroy()
            except Exception:
                pass
        self.selected.clear()
        self._update_props(None)

    def clear_canvas(self):
        if not self.widgets:
            return
        if not messagebox.askyesno("Очистка", "Очистить холст?"):
            return
        for meta in list(self.widgets.values()):
            try:
                if meta.handle:
                    meta.handle.destroy()
                try:
                    self.canvas.delete(meta.win_id)
                except Exception:
                    pass
                meta.widget.destroy()
            except Exception:
                pass
        self.widgets.clear()
        self.selected.clear()
        self.canvas.delete("all")
        if self.grid_on:
            self.draw_grid()

    # ---------------- save / load (JSON) ----------------
    def save_json(self):
        data = []
        for meta in self.widgets.values():
            coords = self.canvas.coords(meta.win_id) or (meta.props.get("x",0), meta.props.get("y",0))
            x, y = int(coords[0]), int(coords[1])
            # gather type-specific details
            extra = {}
            try:
                if meta.wtype == "Listbox":
                    extra["items"] = list(meta.widget.get(0, "end"))
                elif meta.wtype == "Text":
                    extra["text"] = meta.widget.get("1.0", "end")
                elif meta.wtype == "Combobox":
                    extra["values"] = list(meta.widget["values"])
            except Exception:
                pass
            rec = {
                "type": meta.wtype,
                "x": x, "y": y,
                "width": meta.widget.winfo_width(),
                "height": meta.widget.winfo_height(),
                "text": meta.props.get("text",""),
                "font_size": meta.props.get("font_size",12),
                "fg": meta.props.get("fg","black"),
                "bg": meta.props.get("bg","SystemButtonFace"),
                "extra": extra
            }
            data.append(rec)
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], title="Сохранить проект как")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Сохранено", f"Проект сохранён: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")], title="Загрузить проект")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить JSON:\n{e}")
            return
        # clear first
        self.clear_canvas()
        for item in data:
            props = {
                "text": item.get("text",""),
                "width": item.get("width",140),
                "height": item.get("height",30),
                "font_size": item.get("font_size",12),
                "fg": item.get("fg","black"),
                "bg": item.get("bg","SystemButtonFace"),
            }
            w = self.create_widget(item.get("type","Label"), item.get("x",10), item.get("y",10), props=props)
            if w:
                meta = self.widgets.get(id(w))
                # apply extras
                extra = item.get("extra", {})
                try:
                    if meta.wtype == "Listbox":
                        meta.widget.delete(0, "end")
                        for it in extra.get("items", []):
                            meta.widget.insert("end", it)
                    elif meta.wtype == "Text":
                        meta.widget.delete("1.0","end")
                        meta.widget.insert("1.0", extra.get("text",""))
                    elif meta.wtype == "Combobox":
                        meta.widget["values"] = extra.get("values", [])
                    self.canvas.itemconfigure(meta.win_id, width=props["width"], height=props["height"])
                    meta.widget.config(font=("Arial", props["font_size"]), fg=props["fg"], bg=props["bg"])
                    self.root.update_idletasks()
                    self._update_handle(meta)
                except Exception:
                    pass
        messagebox.showinfo("Загружено", "Проект загружен.")

    # ---------------- export to .py ----------------
    def export_python(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python", "*.py")],
            title="Экспорт в Python"
        )
        if not path:
            return

        self.name_counters.clear()

        def make_name(t):
            base = t.lower()
            n = self.name_counters.get(base, 0) + 1
            self.name_counters[base] = n
            return f"{base}_{n}"

        lines = [
            "import tkinter as tk",
            "from tkinter import ttk",
            "",
            "root = tk.Tk()",
            f"root.geometry('{self.canvas_w}x{self.canvas_h}')",
            "",
            "# TODO: добавьте обработчики событий и назначьте их кнопкам",
            ""
        ]

        for meta in self.widgets.values():
            name = make_name(meta.wtype)
            t = meta.wtype

            # свойства
            txt = meta.props.get("text", "").replace("'", "\\'")
            fg = meta.props.get("fg", "black")
            bg = meta.props.get("bg", "SystemButtonFace")
            fs = meta.props.get("font_size", 12)
            w = meta.widget.winfo_width()
            h = meta.widget.winfo_height()

            coords = self.canvas.coords(meta.win_id) or (
                meta.props.get("x", 0),
                meta.props.get("y", 0)
            )
            x, y = int(coords[0]), int(coords[1])

            # --- генерация виджетов ---
            if t == "Entry":
                lines.append(f"{name} = tk.Entry(root, fg='{fg}', bg='{bg}', font=('Arial', {fs}))")
                if txt:
                    lines.append(f"{name}.insert(0, '{txt}')")

            elif t == "Text":
                lines.append(f"{name} = tk.Text(root, fg='{fg}', bg='{bg}', font=('Arial', {fs}))")
                if txt:
                    safe_txt = txt[:100].replace("'", "\\'").replace("\n", "\\n")
                    lines.append(f"{name}.insert('1.0', '{safe_txt}')")

            elif t == "Listbox":
                lines.append(f"{name} = tk.Listbox(root)")

            elif t == "Combobox":
                lines.append(f"{name} = ttk.Combobox(root)")
                if meta.props.get("values"):
                    lines.append(f"{name}['values'] = {meta.props['values']!r}")

            elif t == "Scale":
                lines.append(f"{name} = tk.Scale(root, orient='horizontal')")

            elif t == "Checkbutton":
                lines.append(f"{name}_var = tk.IntVar()")
                lines.append(
                    f"{name} = tk.Checkbutton(root, text='{txt}', variable={name}_var, "
                    f"fg='{fg}', bg='{bg}', font=('Arial', {fs}))"
                )

            elif t == "Radiobutton":
                lines.append(f"{name}_var = tk.IntVar()")
                lines.append(
                    f"{name} = tk.Radiobutton(root, text='{txt}', variable={name}_var, value=1, "
                    f"fg='{fg}', bg='{bg}', font=('Arial', {fs}))"
                )

            else:  # Button, Label и прочее
                lines.append(
                    f"{name} = tk.{t}(root, text='{txt}', fg='{fg}', bg='{bg}', font=('Arial', {fs}))"
                )

            # размещение
            lines.append(f"{name}.place(x={x}, y={y}, width={w}, height={h})")
            lines.append("")

        lines.append("root.mainloop()")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Экспорт", f"Файл сохранён: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать:\n{e}")

    # ---------------- preview ----------------
    def preview(self):
        win = tk.Toplevel(self.root)
        win.title("Предпросмотр")
        win.geometry(f"{self.canvas_w}x{self.canvas_h}")
        for meta in self.widgets.values():
            t = meta.wtype
            w = meta.widget
            coords = self.canvas.coords(meta.win_id) or (meta.props.get("x",0), meta.props.get("y",0))
            x, y = int(coords[0]), int(coords[1])
            w_w, w_h = w.winfo_width(), w.winfo_height()
            txt = meta.props.get("text","")
            fg = meta.props.get("fg","black"); bg = meta.props.get("bg","SystemButtonFace"); fs = meta.props.get("font_size",12)
            if t == "Label":
                nw = tk.Label(win, text=txt, fg=fg, bg=bg, font=("Arial",fs))
            elif t == "Button":
                nw = tk.Button(win, text=txt, fg=fg, bg=bg, font=("Arial",fs), command=lambda: messagebox.showinfo("Нажата", f"Кнопка '{txt}' нажата"))
            elif t == "Entry":
                nw = tk.Entry(win, fg=fg, bg=bg, font=("Arial",fs)); nw.insert(0, txt)
            elif t == "Checkbutton":
                v = tk.IntVar(); nw = tk.Checkbutton(win, text=txt, variable=v, fg=fg, bg=bg, font=("Arial",fs))
            elif t == "Radiobutton":
                v = tk.IntVar(); nw = tk.Radiobutton(win, text=txt, variable=v, value=1, fg=fg, bg=bg, font=("Arial",fs))
            elif t == "Listbox":
                nw = tk.Listbox(win);  # items lost unless saved in JSON
            elif t == "Text":
                nw = tk.Text(win); nw.insert("1.0", txt)
            elif t == "Scale":
                nw = tk.Scale(win, orient="horizontal")
            elif t == "Combobox":
                nw = ttk.Combobox(win, values=meta.widget["values"] if "values" in meta.widget.keys() else [])
                if txt: nw.set(txt)
            else:
                continue
            nw.place(x=x, y=y, width=w_w, height=w_h)

    # ---------------- small utilities ----------------
    def edit_text_quick(self, widget):
        meta = self.widgets.get(id(widget))
        if not meta: return
        if meta.wtype == "Text":
            initial = widget.get("1.0", "end")
        elif meta.wtype == "Entry":
            initial = widget.get()
        else:
            initial = widget.cget("text") if 'text' in widget.keys() else meta.props.get("text","")
        dlg = tk.Toplevel(self.root)
        dlg.title("Редактирование текста")
        txt = tk.Text(dlg, width=50, height=10)
        txt.pack(padx=8, pady=8)
        txt.insert("1.0", initial)
        def ok():
            val = txt.get("1.0","end").rstrip("\n")
            if meta.wtype == "Text":
                widget.delete("1.0","end"); widget.insert("1.0", val)
            elif meta.wtype == "Entry":
                widget.delete(0,"end"); widget.insert(0,val)
            else:
                try: widget.config(text=val)
                except: pass
            meta.props["text"] = val
            self._update_props_for_widget(widget)
            dlg.destroy()
        tk.Button(dlg, text="OK", command=ok).pack(pady=(0,8))

    def _update_props_for_widget(self, widget):
        if widget in self.selected:
            self._update_props(widget)
    # ---------------- AI Chat Assistant ----------------
    def open_ai_chat(self):
        chat_win = tk.Toplevel(self.root)
        chat_win.title("AI Chat")
        chat_win.geometry("400x500")

        txt_area = tk.Text(chat_win, wrap="word", state="disabled")
        txt_area.pack(fill="both", expand=True, padx=5, pady=5)

        entry = tk.Entry(chat_win)
        entry.pack(fill="x", padx=5, pady=5)

        def send_message():
            user_msg = entry.get().strip()
            if not user_msg:
                return
            entry.delete(0, "end")
            self._append_chat(txt_area, "Вы", user_msg)

            # сюда добавим GPT API
            response = self.ask_ai(user_msg)
            self._append_chat(txt_area, "ИИ", response)

        tk.Button(chat_win, text="Отправить", command=send_message).pack(pady=5)

    def _append_chat(self, widget, sender, message):
        widget.config(state="normal")
        widget.insert("end", f"{sender}: {message}\n\n")
        widget.config(state="disabled")
        widget.see("end")

def ask_ai(self, prompt: str) -> str:
    try:
        import openai, os
        openai.api_key = os.getenv("TOGETHER_API_KEY")
        openai.api_base = "https://api.together.xyz/v1"

        response = openai.ChatCompletion.create(
            model="meta-llama/Meta-Llama-3-8B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Ошибка: {e}"




# ---------------- run ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = TkBuilderPro(root)
    root.mainloop()
