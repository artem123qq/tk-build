import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import os
import sys
from pathlib import Path
from datetime import datetime


class DraggableWidget:
    """Базовый класс для перетаскиваемых виджетов"""

    def __init__(self, canvas, widget_type, x=100, y=100, **kwargs):
        self.canvas = canvas
        self.type = widget_type
        self.properties = {
            'x': x,
            'y': y,
            'width': kwargs.get('width', 100),
            'height': kwargs.get('height', 30),
            'text': kwargs.get('text', widget_type),
            'bg': kwargs.get('bg', '#f0f0f0'),
            'fg': kwargs.get('fg', '#000000'),
            'font': kwargs.get('font', 'Arial 10'),
        }

        self.widget = None
        self.window_id = None
        self.resize_handles = []
        self.is_selected = False
        self.parent = None

        self.create_widget()
        self.make_draggable()

    def create_widget(self):
        """Создание конкретного виджета Tkinter"""
        wtype = self.type
        props = self.properties

        if wtype == "Button":
            self.widget = tk.Button(self.canvas, text=props['text'], bg=props['bg'], fg=props['fg'])
        elif wtype == "Label":
            self.widget = tk.Label(self.canvas, text=props['text'], bg=props['bg'], fg=props['fg'])
        elif wtype == "Entry":
            self.widget = tk.Entry(self.canvas, bg=props['bg'], fg=props['fg'])
            self.properties['height'] = 25
        elif wtype == "Text":
            self.widget = tk.Text(self.canvas, bg=props['bg'], fg=props['fg'], height=5, width=20)
            self.properties['height'] = 100
            self.properties['width'] = 150
        elif wtype == "Frame":
            self.widget = tk.Frame(self.canvas, bg=props['bg'], width=props['width'], height=props['height'])
        elif wtype == "Checkbutton":
            var = tk.BooleanVar(value=False)
            self.widget = tk.Checkbutton(self.canvas, text=props['text'], variable=var, bg=props['bg'])
            self.properties['height'] = 25
            self.var = var
        elif wtype == "Radiobutton":
            var = tk.StringVar(value="")
            self.widget = tk.Radiobutton(self.canvas, text=props['text'], variable=var, value=props['text'],
                                         bg=props['bg'])
            self.properties['height'] = 25
            self.var = var
        elif wtype == "Listbox":
            self.widget = tk.Listbox(self.canvas, bg=props['bg'], fg=props['fg'], height=5)
            self.properties['height'] = 100
            self.properties['width'] = 150
        elif wtype == "Combobox":
            self.widget = ttk.Combobox(self.canvas, values=["Item 1", "Item 2", "Item 3"])
            self.properties['height'] = 25
        elif wtype == "Scale":
            self.widget = tk.Scale(self.canvas, from_=0, to=100, orient=tk.HORIZONTAL, bg=props['bg'])
            self.properties['height'] = 50
            self.properties['width'] = 150
        elif wtype == "Progressbar":
            self.widget = ttk.Progressbar(self.canvas, length=100, mode='determinate')
            self.properties['height'] = 25
        elif wtype == "Spinbox":
            self.widget = tk.Spinbox(self.canvas, from_=0, to=100, bg=props['bg'])
            self.properties['height'] = 25
        elif wtype == "Labelframe":
            self.widget = tk.LabelFrame(self.canvas, text=props['text'], bg=props['bg'])
        elif wtype == "Notebook":
            self.widget = ttk.Notebook(self.canvas, width=props['width'], height=props['height'])
            tab1 = tk.Frame(self.widget, bg=props['bg'])
            tab2 = tk.Frame(self.widget, bg=props['bg'])
            self.widget.add(tab1, text="Tab 1")
            self.widget.add(tab2, text="Tab 2")
        elif wtype == "Treeview":
            self.widget = ttk.Treeview(self.canvas, columns=("Col1", "Col2"), show="headings")
            self.widget.heading("Col1", text="Column 1")
            self.widget.heading("Col2", text="Column 2")
            self.properties['height'] = 150
            self.properties['width'] = 200
        elif wtype == "Canvas":
            self.widget = tk.Canvas(self.canvas, bg=props['bg'], width=props['width'], height=props['height'])
        elif wtype == "Separator":
            self.widget = ttk.Separator(self.canvas, orient=tk.HORIZONTAL)
            self.properties['height'] = 5
            self.properties['width'] = 100

        if self.type not in ['Notebook', 'Treeview', 'Combobox', 'Progressbar', 'Separator']:
            if self.type in ['Frame', 'Labelframe', 'Canvas']:
                self.widget.config(width=props['width'], height=props['height'])

        self.window_id = self.canvas.create_window(
            props['x'], props['y'],
            window=self.widget,
            anchor='nw',
            width=props['width'] if self.type not in ['Entry', 'Checkbutton', 'Radiobutton', 'Spinbox'] else None,
            height=props['height'] if self.type not in ['Entry', 'Checkbutton', 'Radiobutton', 'Spinbox'] else None
        )

    def make_draggable(self):
        """Делаем виджет перетаскиваемым"""

        def on_press(event):
            self.select()
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.start_x = self.properties['x']
            self.start_y = self.properties['y']

        def on_drag(event):
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y

            new_x = self.start_x + dx
            new_y = self.start_y + dy

            new_x = round(new_x / 10) * 10
            new_y = round(new_y / 10) * 10

            self.move_to(new_x, new_y)

        self.widget.bind("<Button-1>", on_press)
        self.widget.bind("<B1-Motion>", on_drag)

    def move_to(self, x, y):
        """Перемещение виджета"""
        self.properties['x'] = x
        self.properties['y'] = y
        self.canvas.coords(self.window_id, x, y)
        if self.is_selected:
            self.show_selection()

    def resize(self, width, height):
        """Изменение размера"""
        self.properties['width'] = width
        self.properties['height'] = height

        if self.type in ['Frame', 'Labelframe', 'Canvas']:
            self.widget.config(width=width, height=height)

        self.canvas.itemconfig(self.window_id, width=width, height=height)
        if self.is_selected:
            self.show_selection()

    def select(self):
        """Выделение виджета"""
        self.canvas.event_generate("<<SelectWidget>>", data=self)

    def show_selection(self):
        """Показать рамку выделения"""
        self.hide_selection()

        x, y = self.properties['x'], self.properties['y']
        w, h = self.properties['width'], self.properties['height']

        self.selection_rect = self.canvas.create_rectangle(
            x - 2, y - 2, x + w + 2, y + h + 2,
            outline='#0078d4', width=2, tags=f"selection_{id(self)}"
        )

        if self.type in ['Frame', 'Labelframe', 'Canvas', 'Text', 'Listbox', 'Treeview', 'Notebook']:
            handle_size = 6
            handles = [
                (x + w - handle_size // 2, y + h - handle_size // 2, "se"),
                (x - handle_size // 2, y + h - handle_size // 2, "sw"),
                (x + w - handle_size // 2, y - handle_size // 2, "ne"),
                (x - handle_size // 2, y - handle_size // 2, "nw"),
            ]

            for hx, hy, direction in handles:
                handle = self.canvas.create_rectangle(
                    hx, hy, hx + handle_size, hy + handle_size,
                    fill='#0078d4', outline='white',
                    tags=(f"handle_{id(self)}", f"resize_{direction}")
                )
                self.resize_handles.append(handle)

                def make_resize_handler(d=direction):
                    return lambda e, d=d: self.start_resize(e, d)

                self.canvas.tag_bind(handle, "<Button-1>", make_resize_handler())

    def hide_selection(self):
        """Скрыть рамку выделения"""
        self.canvas.delete(f"selection_{id(self)}")
        for handle in self.resize_handles:
            self.canvas.delete(handle)
        self.resize_handles = []

    def start_resize(self, event, direction):
        """Начало ресайза"""
        self.resize_start_x = event.x
        self.resize_start_y = event.y
        self.start_w = self.properties['width']
        self.start_h = self.properties['height']
        self.start_x = self.properties['x']
        self.start_y = self.properties['y']
        self.resize_dir = direction

        def on_resize_drag(e):
            dx = e.x - self.resize_start_x
            dy = e.y - self.resize_start_y

            new_w = self.start_w
            new_h = self.start_h
            new_x = self.start_x
            new_y = self.start_y

            if 'e' in direction:
                new_w = max(20, self.start_w + dx)
            if 's' in direction:
                new_h = max(20, self.start_h + dy)
            if 'w' in direction:
                new_w = max(20, self.start_w - dx)
                new_x = self.start_x + (self.start_w - new_w)
            if 'n' in direction:
                new_h = max(20, self.start_h - dy)
                new_y = self.start_y + (self.start_h - new_h)

            new_w = round(new_w / 10) * 10
            new_h = round(new_h / 10) * 10
            new_x = round(new_x / 10) * 10
            new_y = round(new_y / 10) * 10

            self.resize(new_w, new_h)
            if new_x != self.start_x or new_y != self.start_y:
                self.move_to(new_x, new_y)

        def on_resize_end(e):
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<ButtonRelease-1>")

        self.canvas.bind("<B1-Motion>", on_resize_drag)
        self.canvas.bind("<ButtonRelease-1>", on_resize_end)

    def update_property(self, prop, value):
        """Обновление свойства"""
        self.properties[prop] = value

        if prop == 'text':
            if self.type in ['Button', 'Label', 'Checkbutton', 'Radiobutton', 'Labelframe']:
                self.widget.config(text=value)
        elif prop == 'bg':
            if self.type not in ['Combobox', 'Progressbar', 'Separator', 'Treeview', 'Notebook']:
                try:
                    self.widget.config(bg=value)
                except tk.TclError:
                    pass
        elif prop == 'fg':
            if self.type not in ['Combobox', 'Progressbar', 'Separator', 'Frame', 'Labelframe']:
                try:
                    self.widget.config(fg=value)
                except tk.TclError:
                    pass
        elif prop == 'font':
            if self.type not in ['Combobox', 'Progressbar', 'Separator', 'Scale']:
                try:
                    self.widget.config(font=value)
                except tk.TclError:
                    pass
        elif prop in ['x', 'y']:
            self.move_to(self.properties['x'], self.properties['y'])
        elif prop in ['width', 'height']:
            self.resize(self.properties['width'], self.properties['height'])

    def to_dict(self):
        """Сериализация в словарь"""
        return {
            'type': self.type,
            'properties': self.properties.copy()
        }

    @classmethod
    def from_dict(cls, canvas, data):
        """Десериализация из словаря"""
        props = data['properties']
        widget = cls(canvas, data['type'], props['x'], props['y'], **{
            k: v for k, v in props.items()
            if k not in ['x', 'y']
        })
        for k, v in props.items():
            if k not in ['x', 'y']:
                widget.update_property(k, v)
        return widget


class PropertiesPanel:
    """Панель свойств"""

    def __init__(self, parent, on_property_change):
        self.frame = ttk.Frame(parent, width=280)
        self.frame.pack_propagate(False)
        self.on_change = on_property_change
        self.current_widget = None

        self.setup_ui()

    def setup_ui(self):
        ttk.Label(self.frame, text="Свойства", font=('Segoe UI', 14, 'bold')).pack(pady=10)

        container = ttk.Frame(self.frame)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.props_frame = ttk.Frame(self.canvas)

        self.props_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.props_frame, anchor="nw", width=250)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind_all("<MouseWheel>", on_mousewheel)

        self.show_empty()

    def show_empty(self):
        """Показать пустое состояние"""
        for child in self.props_frame.winfo_children():
            child.destroy()

        ttk.Label(self.props_frame, text="Выберите виджет",
                  foreground='gray', font=('Segoe UI', 10)).pack(pady=50)
        self.current_widget = None

    def load_widget(self, widget):
        """Загрузить свойства виджета"""
        for child in self.props_frame.winfo_children():
            child.destroy()

        self.current_widget = widget
        props = widget.properties
        wtype = widget.type

        header = ttk.Frame(self.props_frame)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text=f"Тип: {wtype}",
                  font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text="🗑", width=3,
                   command=self.delete_widget).pack(side=tk.RIGHT)

        ttk.Separator(self.props_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        self.create_group("Позиция и размер")
        self.create_number_field("X", 'x', 0, 1000)
        self.create_number_field("Y", 'y', 0, 1000)
        self.create_number_field("Ширина", 'width', 10, 1000)
        self.create_number_field("Высота", 'height', 10, 1000)

        self.create_group("Внешний вид")
        if 'text' in props:
            self.create_text_field("Текст", 'text')
        if 'bg' in props or widget.type not in ['Combobox', 'Progressbar']:
            self.create_color_field("Фон", 'bg')
        if 'fg' in props or widget.type not in ['Frame', 'Labelframe', 'Combobox', 'Progressbar']:
            self.create_color_field("Цвет текста", 'fg')
        if 'font' in props:
            self.create_font_field()

        if wtype in ['Listbox', 'Combobox']:
            self.create_group("Данные")
            self.create_list_field("Элементы", 'values')

    def create_group(self, title):
        """Создать группу свойств"""
        frame = ttk.LabelFrame(self.props_frame, text=title, padding=5)
        frame.pack(fill=tk.X, pady=5, padx=2)
        self.current_group = frame

    def create_number_field(self, label, prop, min_val, max_val):
        """Числовое поле"""
        frame = ttk.Frame(self.current_group)
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text=label, width=10).pack(side=tk.LEFT)

        var = tk.IntVar(value=self.current_widget.properties[prop])

        def update(*args):
            try:
                val = var.get()
                self.current_widget.update_property(prop, val)
                self.on_change()
            except tk.TclError:
                pass

        var.trace('w', update)

        spin = ttk.Spinbox(frame, from_=min_val, to=max_val, textvariable=var, width=10)
        spin.pack(side=tk.LEFT, padx=5)

    def create_text_field(self, label, prop):
        """Текстовое поле"""
        frame = ttk.Frame(self.current_group)
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text=label, width=10).pack(side=tk.LEFT)

        var = tk.StringVar(value=self.current_widget.properties.get(prop, ''))

        def update(*args):
            self.current_widget.update_property(prop, var.get())
            self.on_change()

        var.trace('w', update)

        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def create_color_field(self, label, prop):
        """Поле выбора цвета"""
        frame = ttk.Frame(self.current_group)
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text=label, width=10).pack(side=tk.LEFT)

        var = tk.StringVar(value=self.current_widget.properties.get(prop, '#ffffff'))

        def choose_color():
            color = colorchooser.askcolor(color=var.get())[1]
            if color:
                var.set(color)
                self.current_widget.update_property(prop, color)
                color_btn.config(bg=color)
                self.on_change()

        entry = ttk.Entry(frame, textvariable=var, width=10)
        entry.pack(side=tk.LEFT, padx=5)

        color_btn = tk.Button(frame, bg=var.get(), width=3, command=choose_color)
        color_btn.pack(side=tk.LEFT)

        def on_entry_change(*args):
            try:
                color = var.get()
                self.current_widget.update_property(prop, color)
                color_btn.config(bg=color)
                self.on_change()
            except:
                pass

        var.trace('w', on_entry_change)

    def create_font_field(self):
        """Поле выбора шрифта"""
        frame = ttk.Frame(self.current_group)
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text="Шрифт", width=10).pack(side=tk.LEFT)

        fonts = ['Arial', 'Times New Roman', 'Courier New', 'Helvetica', 'Verdana', 'Segoe UI']
        sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24]

        current_font = self.current_widget.properties.get('font', 'Arial 10').split()
        current_family = current_font[0] if current_font else 'Arial'
        current_size = int(current_font[1]) if len(current_font) > 1 else 10

        family_var = tk.StringVar(value=current_family)
        size_var = tk.IntVar(value=current_size)

        def update_font(*args):
            font_str = f"{family_var.get()} {size_var.get()}"
            self.current_widget.update_property('font', font_str)
            self.on_change()

        family_combo = ttk.Combobox(frame, textvariable=family_var, values=fonts, width=12, state='readonly')
        family_combo.pack(side=tk.LEFT, padx=2)
        family_combo.bind('<<ComboboxSelected>>', update_font)

        size_combo = ttk.Combobox(frame, textvariable=size_var, values=sizes, width=5, state='readonly')
        size_combo.pack(side=tk.LEFT, padx=2)
        size_combo.bind('<<ComboboxSelected>>', update_font)

    def create_list_field(self, label, prop):
        """Поле для списка значений"""
        frame = ttk.Frame(self.current_group)
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text=label).pack(anchor='w')

        text = tk.Text(frame, height=4, width=20)
        text.pack(fill=tk.X, pady=2)

        if self.current_widget.type == 'Listbox':
            values = list(self.current_widget.widget.get(0, tk.END))
        else:
            values = list(self.current_widget.widget.cget('values') or [])

        text.insert('1.0', '\\n'.join(values))

        def update_list():
            content = text.get('1.0', tk.END).strip()
            new_values = [v.strip() for v in content.split('\\n') if v.strip()]

            if self.current_widget.type == 'Listbox':
                self.current_widget.widget.delete(0, tk.END)
                for v in new_values:
                    self.current_widget.widget.insert(tk.END, v)
            else:
                self.current_widget.widget.config(values=new_values)
            self.on_change()

        ttk.Button(frame, text="Применить", command=update_list).pack(anchor='e')

    def delete_widget(self):
        """Удалить текущий виджет"""
        if self.current_widget:
            self.on_change('delete', self.current_widget)


class TkinterBuilder:
    """Главный класс приложения"""

    def __init__(self, root):
        self.root = root
        self.root.title("Tkinter Builder Pro")
        self.root.geometry("1400x900")
        self.root.configure(bg='#2b2b2b')

        self.widgets = []
        self.selected_widget = None
        self.project_name = "Untitled"
        self.project_path = None
        self.modified = False

        self.grid_size = 10
        self.show_grid = True

        self.setup_ui()
        self.setup_bindings()

    def setup_ui(self):
        self.create_menu()

        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.create_toolbar()
        self.create_canvas_area()

        self.properties_panel = PropertiesPanel(self.main_paned, self.on_property_change)
        self.main_paned.add(self.properties_panel.frame, weight=0)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новый проект", command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть...", command=self.open_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Сохранить как...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Сгенерировать код", command=self.generate_code, accelerator="F5")
        file_menu.add_command(label="Сгенерировать проект", command=self.generate_project)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Удалить", command=self.delete_selected, accelerator="Delete")
        edit_menu.add_command(label="Дублировать", command=self.duplicate_selected, accelerator="Ctrl+D")

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        self.grid_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Показывать сетку", variable=self.grid_var, command=self.toggle_grid)

        self.root.bind("<Control-n>", lambda e: self.new_project())
        self.root.bind("<Control-o>", lambda e: self.open_project())
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<F5>", lambda e: self.generate_code())
        self.root.bind("<Delete>", lambda e: self.delete_selected())
        self.root.bind("<Control-d>", lambda e: self.duplicate_selected())

    def create_toolbar(self):
        toolbar_frame = ttk.Frame(self.main_paned, width=180)
        self.main_paned.add(toolbar_frame, weight=0)

        ttk.Label(toolbar_frame, text="Виджеты",
                  font=('Segoe UI', 14, 'bold')).pack(pady=10)

        categories = {
            "Базовые": ["Button", "Label", "Entry", "Text"],
            "Контейнеры": ["Frame", "Labelframe", "Notebook"],
            "Выбор": ["Checkbutton", "Radiobutton", "Combobox", "Listbox", "Spinbox", "Scale"],
            "Данные": ["Treeview", "Progressbar"],
            "Прочее": ["Canvas", "Separator"]
        }

        for category, widgets in categories.items():
            frame = ttk.LabelFrame(toolbar_frame, text=category, padding=5)
            frame.pack(fill=tk.X, padx=5, pady=5)

            for widget_type in widgets:
                btn = ttk.Button(
                    frame,
                    text=widget_type,
                    command=lambda wt=widget_type: self.add_widget(wt)
                )
                btn.pack(fill=tk.X, pady=1)

    def create_canvas_area(self):
        canvas_container = ttk.Frame(self.main_paned)
        self.main_paned.add(canvas_container, weight=1)

        top_bar = ttk.Frame(canvas_container)
        top_bar.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(top_bar, text="Рабочая область").pack(side=tk.LEFT)
        self.coords_label = ttk.Label(top_bar, text="X: 0, Y: 0")
        self.coords_label.pack(side=tk.RIGHT)

        canvas_frame = ttk.Frame(canvas_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#ffffff',
            highlightthickness=1,
            highlightbackground='#cccccc',
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            scrollregion=(0, 0, 2000, 2000)
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)

        self.draw_grid()

    def draw_grid(self):
        """Рисуем сетку"""
        self.canvas.delete("grid")
        if not self.show_grid:
            return

        for i in range(0, 2000, self.grid_size):
            width = 2 if i % 50 == 0 else 1
            color = '#e0e0e0' if i % 50 == 0 else '#f0f0f0'

            self.canvas.create_line(i, 0, i, 2000, fill=color, width=width, tags="grid")
            self.canvas.create_line(0, i, 2000, i, fill=color, width=width, tags="grid")

    def setup_bindings(self):
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<<SelectWidget>>", self.on_widget_select)

    def on_canvas_click(self, event):
        self.deselect_all()

    def on_canvas_motion(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.coords_label.config(text=f"X: {int(x)}, Y: {int(y)}")

    def on_widget_select(self, event):
        for widget in self.widgets:
            if widget.is_selected:
                widget.is_selected = False
                widget.hide_selection()

    def add_widget(self, widget_type):
        x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
        y = self.canvas.canvasy(self.canvas.winfo_height() / 2)

        widget = DraggableWidget(self.canvas, widget_type, x, y)
        self.widgets.append(widget)

        original_select = widget.select

        def new_select():
            self.select_widget(widget)

        widget.select = new_select

        self.select_widget(widget)
        self.set_modified(True)

    def select_widget(self, widget):
        self.deselect_all()
        self.selected_widget = widget
        widget.is_selected = True
        widget.show_selection()
        self.properties_panel.load_widget(widget)

    def deselect_all(self):
        if self.selected_widget:
            self.selected_widget.is_selected = False
            self.selected_widget.hide_selection()
            self.selected_widget = None
        self.properties_panel.show_empty()

    def delete_selected(self):
        if self.selected_widget:
            self.selected_widget.hide_selection()
            self.canvas.delete(self.selected_widget.window_id)
            self.widgets.remove(self.selected_widget)
            self.selected_widget = None
            self.properties_panel.show_empty()
            self.set_modified(True)

    def duplicate_selected(self):
        if not self.selected_widget:
            return

        original = self.selected_widget
        new_widget = DraggableWidget(
            self.canvas,
            original.type,
            original.properties['x'] + 20,
            original.properties['y'] + 20,
            **{k: v for k, v in original.properties.items() if k not in ['x', 'y']}
        )

        for k, v in original.properties.items():
            if k not in ['x', 'y']:
                new_widget.update_property(k, v)

        self.widgets.append(new_widget)

        def new_select():
            self.select_widget(new_widget)

        new_widget.select = new_select

        self.select_widget(new_widget)
        self.set_modified(True)

    def on_property_change(self, action=None, widget=None):
        if action == 'delete' and widget:
            widget.hide_selection()
            self.canvas.delete(widget.window_id)
            self.widgets.remove(widget)
            if self.selected_widget == widget:
                self.selected_widget = None
                self.properties_panel.show_empty()
        self.set_modified(True)

    def set_modified(self, modified):
        self.modified = modified
        title = f"{'*' if modified else ''}{self.project_name} - Tkinter Builder Pro"
        self.root.title(title)

    def toggle_grid(self):
        self.show_grid = self.grid_var.get()
        self.draw_grid()

    def new_project(self):
        if self.modified:
            if not messagebox.askyesno("Несохранённые изменения",
                                       "Создать новый проект? Несохранённые изменения будут потеряны."):
                return

        for widget in self.widgets:
            self.canvas.delete(widget.window_id)
        self.widgets = []
        self.selected_widget = None
        self.properties_panel.show_empty()

        self.project_name = "Untitled"
        self.project_path = None
        self.set_modified(False)

    def save_project(self):
        if self.project_path:
            self._save_to_file(self.project_path)
        else:
            self.save_project_as()

    def save_project_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".tkb",
            filetypes=[("Tkinter Builder files", "*.tkb"), ("All files", "*.*")]
        )
        if path:
            self.project_path = path
            self.project_name = os.path.basename(path)
            self._save_to_file(path)

    def _save_to_file(self, path):
        data = {
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'widgets': [w.to_dict() for w in self.widgets]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.set_modified(False)
        messagebox.showinfo("Сохранено", f"Проект сохранён в:\\n{path}")

    def open_project(self):
        if self.modified:
            if not messagebox.askyesno("Несохранённые изменения",
                                       "Открыть другой проект? Текущие изменения будут потеряны."):
                return

        path = filedialog.askopenfilename(
            filetypes=[("Tkinter Builder files", "*.tkb"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for widget in self.widgets:
                self.canvas.delete(widget.window_id)
            self.widgets = []

            for w_data in data.get('widgets', []):
                widget = DraggableWidget.from_dict(self.canvas, w_data)
                self.widgets.append(widget)

                def make_select(w=widget):
                    def select():
                        self.select_widget(w)

                    return select

                widget.select = make_select()

            self.project_path = path
            self.project_name = os.path.basename(path)
            self.set_modified(False)
            self.deselect_all()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\\n{str(e)}")

    def generate_code(self):
        code = self._generate_code_string()

        top = tk.Toplevel(self.root)
        top.title("Сгенерированный код")
        top.geometry("800x600")

        text = tk.Text(top, wrap=tk.NONE, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text.insert('1.0', code)
        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Копировать",
                   command=lambda: self._copy_to_clipboard(code, top)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Сохранить в файл",
                   command=lambda: self._save_code_to_file(code)).pack(side=tk.LEFT, padx=5)

    def _generate_code_string(self):
        code = '''import tkinter as tk
from tkinter import ttk

class Application:
    def __init__(self, root):
        self.root = root
        self.root.title("Generated Application")
        self.root.geometry("800x600")

        self.setup_ui()

    def setup_ui(self):
'''

        sorted_widgets = sorted(self.widgets, key=lambda w: (w.properties['y'], w.properties['x']))

        for i, widget in enumerate(sorted_widgets):
            code += self._widget_to_code(widget, i)

        code += '''
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(root)
    app.run()
'''
        return code

    def _widget_to_code(self, widget, index):
        p = widget.properties
        wtype = widget.type
        var_name = f"{wtype.lower()}_{index}"

        lines = []
        indent = "        "

        if wtype == "Button":
            lines.append(f"self.{var_name} = tk.Button(self.root, text='{p['text']}', bg='{p['bg']}', fg='{p['fg']}')")
        elif wtype == "Label":
            lines.append(f"self.{var_name} = tk.Label(self.root, text='{p['text']}', bg='{p['bg']}', fg='{p['fg']}')")
        elif wtype == "Entry":
            lines.append(f"self.{var_name} = tk.Entry(self.root, bg='{p['bg']}', fg='{p['fg']}')")
        elif wtype == "Text":
            lines.append(
                f"self.{var_name} = tk.Text(self.root, bg='{p['bg']}', fg='{p['fg']}', width={p['width'] // 10}, height={p['height'] // 20})")
        elif wtype == "Frame":
            lines.append(
                f"self.{var_name} = tk.Frame(self.root, bg='{p['bg']}', width={p['width']}, height={p['height']})")
        elif wtype == "Checkbutton":
            lines.append(f"self.var_{var_name} = tk.BooleanVar()")
            lines.append(
                f"self.{var_name} = tk.Checkbutton(self.root, text='{p['text']}', variable=self.var_{var_name}, bg='{p['bg']}')")
        elif wtype == "Radiobutton":
            lines.append(f"self.var_{var_name} = tk.StringVar(value='{p['text']}')")
            lines.append(
                f"self.{var_name} = tk.Radiobutton(self.root, text='{p['text']}', variable=self.var_{var_name}, value='{p['text']}', bg='{p['bg']}')")
        elif wtype == "Listbox":
            lines.append(
                f"self.{var_name} = tk.Listbox(self.root, bg='{p['bg']}', fg='{p['fg']}', width={p['width'] // 10}, height={p['height'] // 20})")
        elif wtype == "Combobox":
            lines.append(f"self.{var_name} = ttk.Combobox(self.root, values=['Item 1', 'Item 2', 'Item 3'])")
        elif wtype == "Scale":
            lines.append(
                f"self.{var_name} = tk.Scale(self.root, from_=0, to=100, orient=tk.HORIZONTAL, bg='{p['bg']}')")
        elif wtype == "Progressbar":
            lines.append(f"self.{var_name} = ttk.Progressbar(self.root, length={p['width']}, mode='determinate')")
        elif wtype == "Spinbox":
            lines.append(f"self.{var_name} = tk.Spinbox(self.root, from_=0, to=100, bg='{p['bg']}')")
        elif wtype == "Labelframe":
            lines.append(f"self.{var_name} = tk.LabelFrame(self.root, text='{p['text']}', bg='{p['bg']}')")
        elif wtype == "Notebook":
            lines.append(f"self.{var_name} = ttk.Notebook(self.root)")
            lines.append(f"        self.tab1_{index} = tk.Frame(self.{var_name})")
            lines.append(f"        self.tab2_{index} = tk.Frame(self.{var_name})")
            lines.append(f"        self.{var_name}.add(self.tab1_{index}, text='Tab 1')")
            lines.append(f"        self.{var_name}.add(self.tab2_{index}, text='Tab 2')")
        elif wtype == "Treeview":
            lines.append(f"self.{var_name} = ttk.Treeview(self.root, columns=('Col1', 'Col2'), show='headings')")
            lines.append(f"        self.{var_name}.heading('Col1', text='Column 1')")
            lines.append(f"        self.{var_name}.heading('Col2', text='Column 2')")
        elif wtype == "Canvas":
            lines.append(
                f"self.{var_name} = tk.Canvas(self.root, bg='{p['bg']}', width={p['width']}, height={p['height']})")
        elif wtype == "Separator":
            lines.append(f"self.{var_name} = ttk.Separator(self.root, orient=tk.HORIZONTAL)")

        lines.append(f"        self.{var_name}.place(x={p['x']}, y={p['y']}, width={p['width']}, height={p['height']})")

        return '\\n'.join(indent + line for line in lines) + '\\n\\n'

    def _copy_to_clipboard(self, text, window):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Готово", "Код скопирован в буфер обмена!", parent=window)

    def _save_code_to_file(self, code):
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("Сохранено", f"Код сохранён в:\\n{path}")

    def generate_project(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Генерация проекта")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Настройки генерации проекта",
                  font=('Segoe UI', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(frame, text="Имя проекта:").pack(anchor='w')
        name_var = tk.StringVar(value=self.project_name.replace('.tkb', ''))
        ttk.Entry(frame, textvariable=name_var).pack(fill=tk.X, pady=2)

        ttk.Label(frame, text="Автор:").pack(anchor='w')
        author_var = tk.StringVar(value="Developer")
        ttk.Entry(frame, textvariable=author_var).pack(fill=tk.X, pady=2)

        options_frame = ttk.LabelFrame(dialog, text="Компоненты", padding=10)
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        create_main_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Создать main.py", variable=create_main_var).pack(anchor='w')

        create_requirements_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Создать requirements.txt", variable=create_requirements_var).pack(
            anchor='w')

        create_readme_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Создать README.md", variable=create_readme_var).pack(anchor='w')

        create_utils_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Создать папку utils/", variable=create_utils_var).pack(anchor='w')

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        def do_generate():
            folder = filedialog.askdirectory(title="Выберите папку для проекта")
            if not folder:
                return

            project_name = name_var.get() or "my_app"
            project_dir = os.path.join(folder, project_name)

            try:
                os.makedirs(project_dir, exist_ok=True)

                if create_main_var.get():
                    self._create_main_file(project_dir, project_name)

                if create_requirements_var.get():
                    self._create_requirements(project_dir)

                if create_readme_var.get():
                    self._create_readme(project_dir, project_name, author_var.get())

                if create_utils_var.get():
                    utils_dir = os.path.join(project_dir, "utils")
                    os.makedirs(utils_dir, exist_ok=True)
                    self._create_utils_init(utils_dir)
                    self._create_helpers(utils_dir)

                self._save_to_file(os.path.join(project_dir, f"{project_name}.tkb"))

                messagebox.showinfo("Успех", f"Проект создан в:\\n{project_dir}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(btn_frame, text="Сгенерировать", command=do_generate).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=dialog.destroy).pack(side=tk.RIGHT)

    def _create_main_file(self, project_dir, project_name):
        code = self._generate_code_string()

        enhanced_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{project_name}
Generated by Tkinter Builder Pro
"""

import tkinter as tk
from tkinter import ttk, messagebox

class {project_name.title().replace("_", "")}App:
    """Главное приложение"""

    def __init__(self, root):
        self.root = root
        self.root.title("{project_name}")
        self.root.geometry("800x600")
        self.root.minsize(400, 300)

        self.center_window()
        self.setup_ui()
        self.setup_bindings()

    def center_window(self):
        """Центрирование окна на экране"""
        self.root.update_idletasks()
        width = 800
        height = 600
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{{width}}x{{height}}+{{x}}+{{y}}')

    def setup_ui(self):
        """Настройка интерфейса"""
'''

        sorted_widgets = sorted(self.widgets, key=lambda w: (w.properties['y'], w.properties['x']))

        for i, widget in enumerate(sorted_widgets):
            enhanced_code += self._widget_to_code(widget, i)

        enhanced_code += '''
    def setup_bindings(self):
        """Привязка событий"""
        pass

    def run(self):
        """Запуск приложения"""
        self.root.mainloop()

def main():
    """Точка входа"""
    root = tk.Tk()
    app = ''' + project_name.title().replace("_", "") + '''App(root)
    app.run()

if __name__ == "__main__":
    main()
'''

        with open(os.path.join(project_dir, "main.py"), 'w', encoding='utf-8') as f:
            f.write(enhanced_code)

    def _create_requirements(self, project_dir):
        content = """# Dependencies for Tkinter application
# Note: Tkinter is usually included with Python standard library

# Uncomment if using additional packages:
# pillow>=9.0.0
# requests>=2.28.0
"""
        with open(os.path.join(project_dir, "requirements.txt"), 'w', encoding='utf-8') as f:
            f.write(content)

    def _create_readme(self, project_dir, project_name, author):
        content = \"\"\"# {project_name}


