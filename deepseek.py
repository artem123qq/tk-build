import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import copy
import os
from pathlib import Path
from datetime import datetime


# ============== КЛАСС ДЛЯ ХРАНЕНИЯ ИНФОРМАЦИИ О ВИДЖЕТЕ ==============
class WidgetInfo:
    def __init__(self, widget_type, x, y, properties=None):
        self.widget_type = widget_type
        self.x = x
        self.y = y
        self.width = properties.get('width', 100) if properties else 100
        self.height = properties.get('height', 30) if properties else 30
        self.properties = properties or {}
        self.widget_ref = None
        self.canvas_id = None
        self.widget_instance = None
        self.id = id(self)
        self.group_id = None
        self.resize_handle = None
        self.locked = False

    def to_dict(self):
        return {
            'type': self.widget_type,
            'x': self.x,
            'y': self.y,
            'properties': self.properties,
            'group_id': self.group_id,
            'locked': self.locked
        }


# ============== СИСТЕМА СОБЫТИЙ ==============
class EventSystem:
    def __init__(self):
        self.events = {}
        self.available_events = {
            'Button': ['click', 'enter', 'leave'],
            'Entry': ['focus_in', 'focus_out', 'key_press'],
            'Text': ['focus_in', 'focus_out'],
            'Listbox': ['select', 'double_click'],
            'Checkbutton': ['click'],
            'Radiobutton': ['click']
        }

    def add_event(self, widget_id, event_type, handler_code):
        if widget_id not in self.events:
            self.events[widget_id] = {}
        self.events[widget_id][event_type] = handler_code

    def remove_event(self, widget_id, event_type):
        if widget_id in self.events and event_type in self.events[widget_id]:
            del self.events[widget_id][event_type]

    def get_handler(self, widget_id, event_type):
        return self.events.get(widget_id, {}).get(event_type, '')


# ============== КЛАСС ДЛЯ ГРУППЫ ВИДЖЕТОВ ==============
class WidgetGroup:
    def __init__(self, group_id, name="Группа"):
        self.group_id = group_id
        self.name = name
        self.widgets = []

    def add_widget(self, widget):
        widget.group_id = self.group_id
        if widget not in self.widgets:
            self.widgets.append(widget)

    def remove_widget(self, widget):
        if widget in self.widgets:
            widget.group_id = None
            self.widgets.remove(widget)


# ============== МЕНЕДЖЕР КОМПОНОВКИ ==============
class LayoutManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.grid_size = 20
        self.snap_to_grid = True
        self.show_grid = False

    def set_grid_size(self, size):
        self.grid_size = size
        if self.show_grid:
            self.draw_grid()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        if self.show_grid:
            self.draw_grid()
        else:
            self.canvas.delete('grid_line')

    def draw_grid(self):
        self.canvas.delete('grid_line')
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        for x in range(0, width, self.grid_size):
            self.canvas.create_line(x, 0, x, height, fill='lightgray', tags='grid_line')
        for y in range(0, height, self.grid_size):
            self.canvas.create_line(0, y, width, y, fill='lightgray', tags='grid_line')

    def snap(self, x, y):
        if self.snap_to_grid:
            x = round(x / self.grid_size) * self.grid_size
            y = round(y / self.grid_size) * self.grid_size
        return x, y


# ============== СИСТЕМА UNDO/REDO ==============
class UndoRedoManager:
    def __init__(self, max_history=50):
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = max_history

    def add_action(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            action = self.undo_stack.pop()
            action.undo()
            self.redo_stack.append(action)
            return True
        return False

    def redo(self):
        if self.redo_stack:
            action = self.redo_stack.pop()
            action.redo()
            self.undo_stack.append(action)
            return True
        return False


class AddWidgetAction:
    def __init__(self, designer, widget_info):
        self.designer = designer
        self.widget_info = widget_info

    def undo(self):
        self.designer.delete_widget_by_info(self.widget_info)

    def redo(self):
        self.designer.restore_widget(self.widget_info)


class DeleteWidgetAction:
    def __init__(self, designer, widget_info):
        self.designer = designer
        self.widget_info = copy.deepcopy(widget_info)

    def undo(self):
        self.designer.restore_widget(self.widget_info)

    def redo(self):
        self.designer.delete_widget_by_info(self.widget_info)


class MoveWidgetAction:
    def __init__(self, designer, widget_info, old_x, old_y, new_x, new_y):
        self.designer = designer
        self.widget_info = widget_info
        self.old_x = old_x
        self.old_y = old_y
        self.new_x = new_x
        self.new_y = new_y

    def undo(self):
        self.widget_info.x = self.old_x
        self.widget_info.y = self.old_y
        self.designer.canvas.coords(self.widget_info.canvas_id, self.old_x, self.old_y)
        self.designer.update_properties_panel()

    def redo(self):
        self.widget_info.x = self.new_x
        self.widget_info.y = self.new_y
        self.designer.canvas.coords(self.widget_info.canvas_id, self.new_x, self.new_y)
        self.designer.update_properties_panel()


class GroupAction:
    def __init__(self, designer, group, action_type):
        self.designer = designer
        self.group = group
        self.action_type = action_type

    def undo(self):
        if self.action_type == 'create':
            for widget in self.group.widgets:
                widget.group_id = None
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#3498db')
            if self.group in self.designer.groups:
                self.designer.groups.remove(self.group)
        elif self.action_type == 'delete':
            self.designer.groups.append(self.group)
            for widget in self.group.widgets:
                widget.group_id = self.group.group_id
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#9b59b6')

    def redo(self):
        if self.action_type == 'create':
            self.designer.groups.append(self.group)
            for widget in self.group.widgets:
                widget.group_id = self.group.group_id
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#9b59b6')
        elif self.action_type == 'delete':
            for widget in self.group.widgets:
                widget.group_id = None
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#3498db')
            if self.group in self.designer.groups:
                self.designer.groups.remove(self.group)


# ============== DRAG & DROP MANAGER ==============
class DragDropManager:
    def __init__(self, designer):
        self.designer = designer
        self.drag_start = None
        self.dragged_widgets = []
        self.start_positions = []

    def start_drag(self, event, widget_info):
        self.drag_start = (event.x_root, event.y_root)

        selected = self.designer.get_selected_widgets()

        if len(selected) > 1:
            self.dragged_widgets = selected.copy()
        elif widget_info.group_id is not None:
            for group in self.designer.groups:
                if group.group_id == widget_info.group_id:
                    self.dragged_widgets = group.widgets.copy()
                    break
        else:
            self.dragged_widgets = [widget_info]

        self.start_positions = [(w, w.x, w.y) for w in self.dragged_widgets]

    def on_drag(self, event):
        if not self.drag_start:
            return

        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]

        for widget, start_x, start_y in self.start_positions:
            new_x = start_x + dx
            new_y = start_y + dy

            if self.designer.layout_manager.snap_to_grid:
                new_x = round(new_x / self.designer.layout_manager.grid_size) * self.designer.layout_manager.grid_size
                new_y = round(new_y / self.designer.layout_manager.grid_size) * self.designer.layout_manager.grid_size

            widget.x = new_x
            widget.y = new_y
            self.designer.canvas.coords(widget.canvas_id, new_x, new_y)

        if len(self.dragged_widgets) == 1:
            self.designer.update_properties_panel()

    def end_drag(self):
        if self.drag_start and self.start_positions:
            for widget, start_x, start_y in self.start_positions:
                if start_x != widget.x or start_y != widget.y:
                    action = MoveWidgetAction(
                        self.designer, widget,
                        start_x, start_y,
                        widget.x, widget.y
                    )
                    self.designer.undo_manager.add_action(action)

        self.drag_start = None
        self.dragged_widgets = []
        self.start_positions = []


# ============== ОКНО ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА ==============
class PreviewWindow:
    def __init__(self, parent, designer):
        self.designer = designer
        self.preview = tk.Toplevel(parent)
        self.preview.title("🔍 Предварительный просмотр")
        self.preview.geometry("900x700")
        self.preview.configure(bg='#f0f0f0')

        toolbar = tk.Frame(self.preview, bg='#2c3e50', height=40)
        toolbar.pack(fill='x')

        tk.Label(toolbar, text="ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР",
                 bg='#2c3e50', fg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=10)

        tk.Button(toolbar, text="🔄 Обновить", command=self.refresh,
                  bg='#27ae60', fg='white', bd=0, padx=15, pady=5).pack(side='left', padx=5)
        tk.Button(toolbar, text="✕ Закрыть", command=self.preview.destroy,
                  bg='#e74c3c', fg='white', bd=0, padx=15, pady=5).pack(side='right', padx=10)

        self.main_frame = tk.Frame(self.preview, bg='white')
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        self.refresh()

    def refresh(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.create_widgets()

    def create_widgets(self):
        for w in self.designer.widgets:
            wtype = w.widget_type
            x = w.x
            y = w.y
            props = w.properties

            if wtype == 'Button':
                btn = tk.Button(self.main_frame, text=props.get('text', 'Кнопка'),
                                font=('Arial', 10), padx=10, pady=5)
                btn.place(x=x, y=y)

                widget_id = id(w)
                if widget_id in self.designer.event_system.events:
                    if 'click' in self.designer.event_system.events[widget_id]:
                        code = self.designer.event_system.events[widget_id]['click']
                        btn.config(command=lambda c=code: self.execute_code(c))

            elif wtype == 'Label':
                lbl = tk.Label(self.main_frame, text=props.get('text', 'Метка'), font=('Arial', 10))
                lbl.place(x=x, y=y)

            elif wtype == 'Entry':
                entry = tk.Entry(self.main_frame, font=('Arial', 10), width=20)
                entry.place(x=x, y=y)

            elif wtype == 'Text':
                text = tk.Text(self.main_frame, height=5, width=30, font=('Arial', 10))
                text.place(x=x, y=y)
                if props.get('text'):
                    text.insert('1.0', props['text'])

            elif wtype == 'Listbox':
                lb = tk.Listbox(self.main_frame, height=5, width=30, font=('Arial', 10))
                lb.place(x=x, y=y)
                items = props.get('items', ['Элемент 1', 'Элемент 2'])
                for item in items:
                    lb.insert(tk.END, item)

            elif wtype == 'Checkbutton':
                chk = tk.Checkbutton(self.main_frame, text=props.get('text', 'Флажок'), font=('Arial', 10))
                chk.place(x=x, y=y)

            elif wtype == 'Radiobutton':
                rad = tk.Radiobutton(self.main_frame, text=props.get('text', 'Радио'), font=('Arial', 10))
                rad.place(x=x, y=y)

    def execute_code(self, code):
        try:
            safe_globals = {
                '__builtins__': {'messagebox': __import__('tkinter.messagebox').messagebox,
                                 'print': print},
                'messagebox': __import__('tkinter.messagebox').messagebox
            }
            exec(code, safe_globals)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка в обработчике:\n{str(e)}")


# ============== LIVE PREVIEW ОКНО ==============
class LivePreviewWindow:
    def __init__(self, parent, designer):
        self.designer = designer
        self.preview = tk.Toplevel(parent)
        self.preview.title("🎬 LIVE PREVIEW - Обновляется автоматически")
        self.preview.geometry("900x700")
        self.preview.configure(bg='#f0f0f0')
        self.preview.protocol("WM_DELETE_WINDOW", self.hide)

        toolbar = tk.Frame(self.preview, bg='#2c3e50', height=40)
        toolbar.pack(fill='x')

        tk.Label(toolbar, text="LIVE PREVIEW - ОБНОВЛЯЕТСЯ АВТОМАТИЧЕСКИ",
                 bg='#2c3e50', fg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=10)

        tk.Button(toolbar, text="🔄 Обновить", command=self.refresh,
                  bg='#27ae60', fg='white', bd=0, padx=15, pady=5).pack(side='left', padx=5)
        tk.Button(toolbar, text="✕ Закрыть", command=self.hide,
                  bg='#e74c3c', fg='white', bd=0, padx=15, pady=5).pack(side='right', padx=10)

        self.main_frame = tk.Frame(self.preview, bg='white')
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        self.visible = False
        self.refresh()
        self.start_live_update()

    def hide(self):
        self.visible = False
        self.preview.withdraw()

    def show(self):
        self.visible = True
        self.preview.deiconify()
        self.refresh()

    def start_live_update(self):
        if self.visible:
            self.refresh()
        self.preview.after(1000, self.start_live_update)

    def refresh(self):
        if not self.visible:
            return
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.create_widgets()

    def create_widgets(self):
        for w in self.designer.widgets:
            wtype = w.widget_type
            x = w.x
            y = w.y
            props = w.properties

            if wtype == 'Button':
                btn = tk.Button(self.main_frame, text=props.get('text', 'Кнопка'),
                                font=('Arial', 10), padx=10, pady=5,
                                bg=props.get('bg', '#4CAF50'), fg=props.get('fg', 'white'))
                btn.place(x=x, y=y, width=w.width, height=w.height)

                widget_id = id(w)
                if widget_id in self.designer.event_system.events:
                    if 'click' in self.designer.event_system.events[widget_id]:
                        code = self.designer.event_system.events[widget_id]['click']
                        btn.config(command=lambda c=code: self.execute_code(c))

            elif wtype == 'Label':
                lbl = tk.Label(self.main_frame, text=props.get('text', 'Метка'),
                               font=('Arial', 10), bg=props.get('bg', '#2196F3'), fg=props.get('fg', 'white'))
                lbl.place(x=x, y=y, width=w.width, height=w.height)

            elif wtype == 'Entry':
                entry = tk.Entry(self.main_frame, font=('Arial', 10), width=20,
                                 bg=props.get('bg', 'white'), fg=props.get('fg', 'black'))
                entry.place(x=x, y=y, width=w.width, height=w.height)
                if props.get('text'):
                    entry.insert(0, props.get('text'))

            elif wtype == 'Text':
                text = tk.Text(self.main_frame, height=5, width=30, font=('Arial', 10),
                               bg=props.get('bg', 'white'), fg=props.get('fg', 'black'))
                text.place(x=x, y=y, width=w.width, height=w.height)
                if props.get('text'):
                    text.insert('1.0', props['text'])

            elif wtype == 'Listbox':
                lb = tk.Listbox(self.main_frame, height=5, width=30, font=('Arial', 10),
                                bg=props.get('bg', 'white'), fg=props.get('fg', 'black'))
                lb.place(x=x, y=y, width=w.width, height=w.height)
                items = props.get('items', ['Элемент 1', 'Элемент 2'])
                for item in items:
                    lb.insert(tk.END, item)

            elif wtype == 'Checkbutton':
                chk = tk.Checkbutton(self.main_frame, text=props.get('text', 'Флажок'),
                                     font=('Arial', 10), bg=props.get('bg', 'white'), fg=props.get('fg', 'black'))
                chk.place(x=x, y=y)

            elif wtype == 'Radiobutton':
                rad = tk.Radiobutton(self.main_frame, text=props.get('text', 'Радио'),
                                     font=('Arial', 10), bg=props.get('bg', 'white'), fg=props.get('fg', 'black'))
                rad.place(x=x, y=y)

            elif wtype == 'Combobox':
                cb = ttk.Combobox(self.main_frame, values=['Опция 1', 'Опция 2'])
                cb.place(x=x, y=y, width=w.width, height=w.height)

    def execute_code(self, code):
        try:
            safe_globals = {
                '__builtins__': {'messagebox': __import__('tkinter.messagebox').messagebox, 'print': print},
                'messagebox': __import__('tkinter.messagebox').messagebox
            }
            exec(code, safe_globals)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка в обработчике:\n{str(e)}")


# ============== ДИАЛОГ СНИППЕТОВ КОДА ==============
class CodeSnippetsDialog:
    SNIPPETS = {
        "📨 Показать сообщение": 'messagebox.showinfo("Информация", "Виджет активирован")',
        "⚠️ Показать предупреждение": 'messagebox.showwarning("Предупреждение", "Внимание!")',
        "❌ Показать ошибку": 'messagebox.showerror("Ошибка", "Что-то пошло не так")',
        "🖨️ Вывести в консоль": 'print("Виджет активирован")',
        "✏️ Изменить текст виджета": 'widget.config(text="Новый текст")',
        "🧹 Очистить поле ввода": 'entry.delete(0, tk.END)',
        "📥 Получить значение": 'value = entry.get()\nprint(value)',
        "📂 Открыть файл": 'filename = filedialog.askopenfilename()\nprint(filename)',
        "💾 Сохранить файл": 'filename = filedialog.asksaveasfilename()\nprint(filename)',
        "🚪 Закрыть окно": 'root.quit()',
        "🎨 Изменить цвет": 'widget.config(bg="red")',
        "👻 Скрыть виджет": 'widget.pack_forget()',
        "👀 Показать виджет": 'widget.pack()',
        "📊 Изменить значение слайдера": 'scale.set(50)',
        "📋 Скопировать в буфер": 'root.clipboard_clear()\nroot.clipboard_append("текст")',
        "🔢 Счетчик кликов": 'count = getattr(widget, "count", 0) + 1\nwidget.count = count\nwidget.config(text=f"Нажато {count} раз")'
    }

    def __init__(self, parent, text_widget):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("📋 Сниппеты кода")
        self.dialog.geometry("350x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.text_widget = text_widget
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Выберите сниппет:", font=('Arial', 11, 'bold')).pack(pady=5)

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Arial', 10))
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)

        for name in self.SNIPPETS.keys():
            self.listbox.insert(tk.END, name)

        self.listbox.bind('<Double-Button-1>', self.insert_snippet)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="📋 Вставить", command=self.insert_snippet).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="✕ Закрыть", command=self.dialog.destroy).pack(side='right', padx=5)

        ttk.Label(main_frame, text="💡 Совет: Дважды кликните для вставки",
                  font=('Arial', 8), foreground='gray').pack(pady=5)

    def insert_snippet(self, event=None):
        selection = self.listbox.curselection()
        if selection:
            name = self.listbox.get(selection[0])
            code = self.SNIPPETS[name]
            self.text_widget.insert(tk.INSERT, code)
            self.dialog.destroy()


# ============== ДИАЛОГ ПАКЕТНОГО РЕДАКТИРОВАНИЯ ==============
class BatchEditDialog:
    def __init__(self, parent, designer, widgets):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("📦 Пакетное редактирование")
        self.dialog.geometry("400x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.widgets = widgets
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Пакетное редактирование", font=('Arial', 12, 'bold')).pack(pady=5)
        ttk.Label(main_frame, text=f"Выбрано виджетов: {len(self.widgets)}",
                  font=('Arial', 10)).pack(pady=5)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=10)

        # Вкладка Текст
        text_frame = ttk.Frame(notebook, padding="10")
        notebook.add(text_frame, text="📝 Текст")

        ttk.Label(text_frame, text="Новый текст (для всех):").pack(anchor='w')
        self.text_var = tk.StringVar()
        text_entry = ttk.Entry(text_frame, textvariable=self.text_var, width=30)
        text_entry.pack(fill='x', pady=5)

        ttk.Button(text_frame, text="Применить текст", command=self.apply_text).pack(pady=10)

        # Вкладка Размеры
        size_frame = ttk.Frame(notebook, padding="10")
        notebook.add(size_frame, text="📏 Размеры")

        ttk.Label(size_frame, text="Ширина:").grid(row=0, column=0, sticky='w', pady=5)
        self.width_var = tk.IntVar(value=100)
        width_spin = tk.Spinbox(size_frame, from_=20, to=500, textvariable=self.width_var, width=8)
        width_spin.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(size_frame, text="Высота:").grid(row=1, column=0, sticky='w', pady=5)
        self.height_var = tk.IntVar(value=30)
        height_spin = tk.Spinbox(size_frame, from_=20, to=500, textvariable=self.height_var, width=8)
        height_spin.grid(row=1, column=1, pady=5, padx=5)

        ttk.Button(size_frame, text="Применить размеры", command=self.apply_size).grid(row=2, column=0, columnspan=2,
                                                                                       pady=15)

        # Вкладка Цвета
        color_frame = ttk.Frame(notebook, padding="10")
        notebook.add(color_frame, text="🎨 Цвета")

        ttk.Label(color_frame, text="Цвет фона:").grid(row=0, column=0, sticky='w', pady=5)
        self.bg_color = tk.StringVar(value="#f0f0f0")
        bg_entry = ttk.Entry(color_frame, textvariable=self.bg_color, width=10)
        bg_entry.grid(row=0, column=1, pady=5)
        ttk.Button(color_frame, text="Выбрать", command=lambda: self.choose_color(self.bg_color)).grid(row=0, column=2,
                                                                                                       padx=5)

        ttk.Label(color_frame, text="Цвет текста:").grid(row=1, column=0, sticky='w', pady=5)
        self.fg_color = tk.StringVar(value="#000000")
        fg_entry = ttk.Entry(color_frame, textvariable=self.fg_color, width=10)
        fg_entry.grid(row=1, column=1, pady=5)
        ttk.Button(color_frame, text="Выбрать", command=lambda: self.choose_color(self.fg_color)).grid(row=1, column=2,
                                                                                                       padx=5)

        ttk.Button(color_frame, text="Применить цвета", command=self.apply_colors).grid(row=2, column=0, columnspan=3,
                                                                                        pady=15)

        # Вкладка Позиция
        pos_frame = ttk.Frame(notebook, padding="10")
        notebook.add(pos_frame, text="📍 Позиция")

        ttk.Label(pos_frame, text="Смещение X:").grid(row=0, column=0, sticky='w', pady=5)
        self.dx_var = tk.IntVar(value=0)
        dx_spin = tk.Spinbox(pos_frame, from_=-200, to=200, textvariable=self.dx_var, width=8)
        dx_spin.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(pos_frame, text="Смещение Y:").grid(row=1, column=0, sticky='w', pady=5)
        self.dy_var = tk.IntVar(value=0)
        dy_spin = tk.Spinbox(pos_frame, from_=-200, to=200, textvariable=self.dy_var, width=8)
        dy_spin.grid(row=1, column=1, pady=5, padx=5)

        ttk.Button(pos_frame, text="Сместить все", command=self.apply_offset).grid(row=2, column=0, columnspan=2,
                                                                                   pady=15)

        # Кнопки диалога
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Закрыть", command=self.dialog.destroy).pack(side='right', padx=5)

    def choose_color(self, var):
        color = colorchooser.askcolor(title="Выберите цвет")
        if color[1]:
            var.set(color[1])

    def apply_text(self):
        text = self.text_var.get().strip()
        if not text:
            messagebox.showinfo("Пакетное редактирование", "Введите текст")
            return

        for w in self.widgets:
            if w.widget_type in ['Button', 'Label', 'Checkbutton', 'Radiobutton']:
                try:
                    w.widget_instance.config(text=text)
                    w.properties['text'] = text
                except:
                    pass
            elif w.widget_type in ['Entry', 'Text']:
                try:
                    if isinstance(w.widget_instance, tk.Entry):
                        w.widget_instance.delete(0, tk.END)
                        w.widget_instance.insert(0, text)
                    elif isinstance(w.widget_instance, tk.Text):
                        w.widget_instance.delete('1.0', tk.END)
                        w.widget_instance.insert('1.0', text)
                    w.properties['text'] = text
                except:
                    pass

        self.designer.update_properties_panel()
        self.designer.status_bar.config(text=f"✅ Текст изменен для {len(self.widgets)} виджетов")

    def apply_size(self):
        width = self.width_var.get()
        height = self.height_var.get()

        for w in self.widgets:
            w.width = width
            w.height = height
            w.properties['width'] = width
            w.properties['height'] = height

            try:
                self.designer.canvas.itemconfigure(w.canvas_id, width=width, height=height)
                if hasattr(w.widget_instance, 'config'):
                    if w.widget_type in ['Button', 'Label', 'Entry']:
                        w.widget_instance.config(width=max(1, width // 10))
                    elif w.widget_type == 'Text':
                        w.widget_instance.config(width=max(1, width // 7), height=max(1, height // 20))
            except:
                pass

        self.designer.update_properties_panel()
        self.designer.status_bar.config(text=f"✅ Размеры изменены для {len(self.widgets)} виджетов")

    def apply_colors(self):
        bg = self.bg_color.get()
        fg = self.fg_color.get()

        for w in self.widgets:
            try:
                if hasattr(w.widget_instance, 'config'):
                    if bg:
                        w.widget_instance.config(bg=bg)
                        w.properties['bg'] = bg
                    if fg:
                        w.widget_instance.config(fg=fg)
                        w.properties['fg'] = fg
            except:
                pass

        self.designer.update_properties_panel()
        self.designer.status_bar.config(text=f"✅ Цвета изменены для {len(self.widgets)} виджетов")

    def apply_offset(self):
        dx = self.dx_var.get()
        dy = self.dy_var.get()

        for w in self.widgets:
            w.x += dx
            w.y += dy
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)

        self.designer.update_properties_panel()
        self.designer.status_bar.config(text=f"✅ Смещено {len(self.widgets)} виджетов на ({dx}, {dy})")


# ============== БИБЛИОТЕКА ШАБЛОНОВ ==============
class TemplateLibrary:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("📚 Библиотека шаблонов")
        self.dialog.geometry("650x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="📚 БИБЛИОТЕКА ШАБЛОНОВ",
                  font=('Arial', 14, 'bold')).pack(pady=10)

        templates_frame = tk.Frame(main_frame, bg='#ecf0f1')
        templates_frame.pack(fill='both', expand=True, pady=10)

        templates = [
            ("🔐 Форма входа", self.login_template, "#3498db"),
            ("📝 Регистрация", self.register_template, "#2ecc71"),
            ("🧮 Калькулятор", self.calculator_template, "#e74c3c"),
            ("💬 Чат", self.chat_template, "#9b59b6"),
            ("⚙️ Настройки", self.settings_template, "#f39c12"),
            ("📊 Дашборд", self.dashboard_template, "#1abc9c"),
            ("🔍 Поиск", self.search_template, "#3498db"),
            ("📧 Контакты", self.contacts_template, "#e67e22")
        ]

        row, col = 0, 0
        for name, func, color in templates:
            btn = tk.Button(templates_frame, text=name, command=func,
                            bg=color, fg='white', font=('Arial', 10, 'bold'),
                            width=20, height=3, bd=0, cursor='hand2')
            btn.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            col += 1
            if col > 1:
                col = 0
                row += 1

        templates_frame.grid_columnconfigure(0, weight=1)
        templates_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(main_frame, text="✕ Закрыть", command=self.dialog.destroy).pack(pady=10)

    def login_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 80)
        self.designer.widgets[-1].properties['text'] = "🔐 Вход в систему"
        self.designer.widgets[-1].widget_instance.config(text="🔐 Вход в систему", font=('Arial', 14, 'bold'))
        self.designer.add_widget('Label', 250, 150)
        self.designer.widgets[-1].properties['text'] = "Логин:"
        self.designer.add_widget('Entry', 320, 150)
        self.designer.add_widget('Label', 250, 200)
        self.designer.widgets[-1].properties['text'] = "Пароль:"
        self.designer.add_widget('Entry', 320, 200)
        self.designer.add_widget('Button', 280, 270)
        self.designer.widgets[-1].properties['text'] = "Войти"
        self.designer.add_widget('Button', 380, 270)
        self.designer.widgets[-1].properties['text'] = "Отмена"
        self.dialog.destroy()

    def register_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 50)
        self.designer.widgets[-1].properties['text'] = "📝 Регистрация"
        self.designer.widgets[-1].widget_instance.config(text="📝 Регистрация", font=('Arial', 14, 'bold'))
        fields = [("Имя:", 250, 110), ("Email:", 250, 160), ("Пароль:", 250, 210), ("Подтвердить:", 250, 260)]
        for text, x, y in fields:
            self.designer.add_widget('Label', x, y)
            self.designer.widgets[-1].properties['text'] = text
            self.designer.add_widget('Entry', x + 80, y)
        self.designer.add_widget('Button', 320, 330)
        self.designer.widgets[-1].properties['text'] = "Зарегистрироваться"
        self.dialog.destroy()

    def calculator_template(self):
        self.designer.new_project()
        self.designer.add_widget('Entry', 200, 80)
        self.designer.widgets[-1].width = 200
        buttons = [('7', 200, 130), ('8', 250, 130), ('9', 300, 130), ('/', 350, 130),
                   ('4', 200, 180), ('5', 250, 180), ('6', 300, 180), ('*', 350, 180),
                   ('1', 200, 230), ('2', 250, 230), ('3', 300, 230), ('-', 350, 230),
                   ('0', 200, 280), ('.', 250, 280), ('=', 300, 280), ('+', 350, 280)]
        for text, x, y in buttons:
            self.designer.add_widget('Button', x, y)
            self.designer.widgets[-1].properties['text'] = text
            self.designer.widgets[-1].width = 40
        self.dialog.destroy()

    def chat_template(self):
        self.designer.new_project()
        self.designer.add_widget('Text', 200, 50)
        self.designer.widgets[-1].width = 300
        self.designer.widgets[-1].height = 200
        self.designer.add_widget('Entry', 200, 270)
        self.designer.widgets[-1].width = 250
        self.designer.add_widget('Button', 460, 270)
        self.designer.widgets[-1].properties['text'] = "Отправить"
        self.dialog.destroy()

    def settings_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 50)
        self.designer.widgets[-1].properties['text'] = "⚙️ Настройки"
        self.designer.widgets[-1].widget_instance.config(text="⚙️ Настройки", font=('Arial', 14, 'bold'))
        settings = ["Уведомления", "Автозапуск", "Темная тема", "Звуки"]
        for i, text in enumerate(settings):
            self.designer.add_widget('Checkbutton', 250, 100 + i * 40)
            self.designer.widgets[-1].properties['text'] = text
        self.designer.add_widget('Button', 320, 300)
        self.designer.widgets[-1].properties['text'] = "Сохранить"
        self.dialog.destroy()

    def dashboard_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 50)
        self.designer.widgets[-1].properties['text'] = "📊 Дашборд"
        for i, text in enumerate(["Статистика", "Графики", "Отчеты"]):
            self.designer.add_widget('Button', 250, 120 + i * 60)
            self.designer.widgets[-1].properties['text'] = text
            self.designer.widgets[-1].width = 120
        self.dialog.destroy()

    def search_template(self):
        self.designer.new_project()
        self.designer.add_widget('Entry', 250, 80)
        self.designer.widgets[-1].width = 200
        self.designer.add_widget('Button', 460, 80)
        self.designer.widgets[-1].properties['text'] = "🔍 Найти"
        self.designer.add_widget('Listbox', 250, 130)
        self.designer.widgets[-1].width = 250
        self.designer.widgets[-1].height = 150
        self.dialog.destroy()

    def contacts_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 50)
        self.designer.widgets[-1].properties['text'] = "📧 Контакты"
        contacts = ["Иван Иванов", "Петр Петров", "Мария Сидорова"]
        for i, name in enumerate(contacts):
            self.designer.add_widget('Button', 250, 100 + i * 50)
            self.designer.widgets[-1].properties['text'] = name
            self.designer.widgets[-1].width = 150
        self.dialog.destroy()


# ============== ДИАЛОГ ВЫРАВНИВАНИЯ ==============
class AlignmentDialog:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Выравнивание виджетов")
        self.dialog.geometry("400x380")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Выравнивание", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        frame1 = ttk.Frame(main_frame)
        frame1.pack(pady=5)
        ttk.Button(frame1, text="⬅ По левому краю", command=lambda: self.align('left')).pack(side='left', padx=5)
        ttk.Button(frame1, text="➡ По правому краю", command=lambda: self.align('right')).pack(side='left', padx=5)

        frame2 = ttk.Frame(main_frame)
        frame2.pack(pady=5)
        ttk.Button(frame2, text="⬆ По верхнему краю", command=lambda: self.align('top')).pack(side='left', padx=5)
        ttk.Button(frame2, text="⬇ По нижнему краю", command=lambda: self.align('bottom')).pack(side='left', padx=5)

        frame3 = ttk.Frame(main_frame)
        frame3.pack(pady=5)
        ttk.Button(frame3, text="🔄 По центру (горизонтально)", command=lambda: self.align('center_h')).pack(side='left',
                                                                                                            padx=5)
        ttk.Button(frame3, text="🔄 По центру (вертикально)", command=lambda: self.align('center_v')).pack(side='left',
                                                                                                          padx=5)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        ttk.Label(main_frame, text="Распределение", font=('Arial', 11, 'bold')).pack(pady=(0, 5))

        frame4 = ttk.Frame(main_frame)
        frame4.pack(pady=5)
        ttk.Button(frame4, text="📊 Распределить по горизонтали", command=self.distribute_horizontal).pack(side='left',
                                                                                                          padx=5)
        ttk.Button(frame4, text="📈 Распределить по вертикали", command=self.distribute_vertical).pack(side='left',
                                                                                                      padx=5)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        ttk.Label(main_frame, text="Интервалы", font=('Arial', 11, 'bold')).pack(pady=(0, 5))

        frame5 = ttk.Frame(main_frame)
        frame5.pack(pady=5)
        ttk.Label(frame5, text="Отступ:").pack(side='left')
        self.spacing_var = tk.StringVar(value="20")
        ttk.Entry(frame5, textvariable=self.spacing_var, width=8).pack(side='left', padx=5)
        ttk.Button(frame5, text="Выровнять интервалы", command=self.equal_spacing).pack(side='left', padx=5)

        ttk.Button(main_frame, text="Закрыть", command=self.dialog.destroy).pack(pady=15)

    def get_selected_widgets(self):
        return self.designer.get_selected_widgets()

    def align(self, direction):
        selected = self.get_selected_widgets()
        if not selected:
            messagebox.showinfo("Выравнивание", "Выберите виджеты (Ctrl+клик для мульти-выбора)")
            return

        if direction == 'left':
            min_x = min(w.x for w in selected)
            for w in selected:
                w.x = min_x
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'right':
            max_right = max(w.x + w.width for w in selected)
            for w in selected:
                w.x = max_right - w.width
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'top':
            min_y = min(w.y for w in selected)
            for w in selected:
                w.y = min_y
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'bottom':
            max_bottom = max(w.y + w.height for w in selected)
            for w in selected:
                w.y = max_bottom - w.height
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'center_h':
            center_x = sum(w.x + w.width / 2 for w in selected) / len(selected)
            for w in selected:
                w.x = center_x - w.width / 2
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'center_v':
            center_y = sum(w.y + w.height / 2 for w in selected) / len(selected)
            for w in selected:
                w.y = center_y - w.height / 2
                self.designer.canvas.coords(w.canvas_id, w.x, w.y)

        self.designer.update_properties_panel()
        self.designer.status_bar.config(text=f"Выравнивание: {direction} ({len(selected)} виджетов)")

    def distribute_horizontal(self):
        selected = self.get_selected_widgets()
        if len(selected) < 3:
            messagebox.showinfo("Распределение", "Выберите минимум 3 виджета")
            return
        selected.sort(key=lambda w: w.x)
        min_x = selected[0].x
        max_x = selected[-1].x
        spacing = (max_x - min_x) / (len(selected) - 1)
        for i, w in enumerate(selected):
            w.x = min_x + spacing * i
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        self.designer.status_bar.config(text=f"Распределено {len(selected)} виджетов по горизонтали")

    def distribute_vertical(self):
        selected = self.get_selected_widgets()
        if len(selected) < 3:
            messagebox.showinfo("Распределение", "Выберите минимум 3 виджета")
            return
        selected.sort(key=lambda w: w.y)
        min_y = selected[0].y
        max_y = selected[-1].y
        spacing = (max_y - min_y) / (len(selected) - 1)
        for i, w in enumerate(selected):
            w.y = min_y + spacing * i
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        self.designer.status_bar.config(text=f"Распределено {len(selected)} виджетов по вертикали")

    def equal_spacing(self):
        try:
            spacing = int(self.spacing_var.get())
        except:
            spacing = 20
        selected = self.get_selected_widgets()
        if len(selected) < 2:
            messagebox.showinfo("Интервалы", "Выберите минимум 2 виджета")
            return
        selected.sort(key=lambda w: w.x)
        for i in range(1, len(selected)):
            prev_x = selected[i - 1].x + selected[i - 1].width
            selected[i].x = prev_x + spacing
            self.designer.canvas.coords(selected[i].canvas_id, selected[i].x, selected[i].y)
        self.designer.status_bar.config(text=f"Интервалы установлены: {spacing}px ({len(selected)} виджетов)")


# ============== ДИАЛОГ СВОЙСТВ ==============
class PropertiesDialog:
    def __init__(self, parent, widget_info, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Свойства - {widget_info.widget_type}")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.widget_info = widget_info
        self.callback = callback
        self.properties = widget_info.properties.copy()
        self.setup_ui()

    def setup_ui(self):
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Основные")

        row = 0
        self.entries = {}

        if self.widget_info.widget_type in ['Button', 'Label']:
            ttk.Label(main_frame, text="Текст:").grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Entry(main_frame)
            entry.insert(0, self.properties.get('text', ''))
            entry.grid(row=row, column=1, sticky='ew', pady=5, padx=5)
            self.entries['text'] = entry
            row += 1

        ttk.Label(main_frame, text="Ширина:").grid(row=row, column=0, sticky='w', pady=5)
        entry_w = ttk.Entry(main_frame)
        entry_w.insert(0, self.properties.get('width', '100'))
        entry_w.grid(row=row, column=1, sticky='ew', pady=5, padx=5)
        self.entries['width'] = entry_w
        row += 1

        ttk.Label(main_frame, text="Высота:").grid(row=row, column=0, sticky='w', pady=5)
        entry_h = ttk.Entry(main_frame)
        entry_h.insert(0, self.properties.get('height', '30'))
        entry_h.grid(row=row, column=1, sticky='ew', pady=5, padx=5)
        self.entries['height'] = entry_h
        row += 1

        style_frame = ttk.Frame(notebook)
        notebook.add(style_frame, text="Внешний вид")

        ttk.Label(style_frame, text="Цвет фона:").grid(row=0, column=0, pady=5)
        self.bg_color = tk.StringVar(value=self.properties.get('bg', '#f0f0f0'))
        ttk.Entry(style_frame, textvariable=self.bg_color, width=10).grid(row=0, column=1, pady=5)
        ttk.Button(style_frame, text="Выбрать", command=lambda: self.choose_color(self.bg_color)).grid(row=0, column=2,
                                                                                                       padx=5)

        ttk.Label(style_frame, text="Цвет текста:").grid(row=1, column=0, pady=5)
        self.fg_color = tk.StringVar(value=self.properties.get('fg', '#000000'))
        ttk.Entry(style_frame, textvariable=self.fg_color, width=10).grid(row=1, column=1, pady=5)
        ttk.Button(style_frame, text="Выбрать", command=lambda: self.choose_color(self.fg_color)).grid(row=1, column=2,
                                                                                                       padx=5)

        ttk.Label(style_frame, text="Шрифт:").grid(row=2, column=0, pady=5)
        self.font_entry = ttk.Entry(style_frame, width=20)
        self.font_entry.insert(0, self.properties.get('font', 'Arial 10'))
        self.font_entry.grid(row=2, column=1, columnspan=2, pady=5)

        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Применить", command=self.apply).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.dialog.destroy).pack(side='left', padx=5)

    def choose_color(self, var):
        color = colorchooser.askcolor(title="Выберите цвет")
        if color[1]:
            var.set(color[1])

    def apply(self):
        for prop, entry in self.entries.items():
            self.properties[prop] = entry.get()
        self.properties['bg'] = self.bg_color.get()
        self.properties['fg'] = self.fg_color.get()
        self.properties['font'] = self.font_entry.get()
        self.widget_info.properties = self.properties
        self.callback(self.widget_info)
        self.dialog.destroy()


# ============== ДИАЛОГ СОБЫТИЙ ==============
class EventDialog:
    def __init__(self, parent, widget_info, event_system, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"События - {widget_info.widget_type}")
        self.dialog.geometry("550x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.widget_info = widget_info
        self.event_system = event_system
        self.callback = callback
        self.widget_id = id(widget_info)
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        info_frame = ttk.LabelFrame(main_frame, text="Виджет", padding="5")
        info_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(info_frame, text=f"Тип: {self.widget_info.widget_type}").pack(anchor='w')

        add_frame = ttk.LabelFrame(main_frame, text="Добавить обработчик", padding="5")
        add_frame.pack(fill='x', pady=(0, 10))

        events = self.event_system.available_events.get(self.widget_info.widget_type, ['click'])
        self.event_var = tk.StringVar()
        event_combo = ttk.Combobox(add_frame, textvariable=self.event_var, values=events, state='readonly')
        event_combo.pack(fill='x', pady=(0, 5))
        if events: event_combo.current(0)

        self.code_text = tk.Text(add_frame, height=5)
        self.code_text.pack(fill='x', pady=(0, 5))
        self.code_text.insert('1.0', 'messagebox.showinfo("Событие", "Виджет активирован")')

        ttk.Button(add_frame, text="➕ Добавить", command=self.add_handler).pack()

        handlers_frame = ttk.LabelFrame(main_frame, text="Существующие обработчики", padding="5")
        handlers_frame.pack(fill='both', expand=True)

        self.handlers_list = tk.Listbox(handlers_frame, height=5)
        self.handlers_list.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(handlers_frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_frame, text="✖ Удалить", command=self.delete_handler).pack(side='left', padx=2)

        self.refresh_list()

        dialog_btn = ttk.Frame(main_frame)
        dialog_btn.pack(fill='x', pady=(10, 0))
        ttk.Button(dialog_btn, text="Сохранить", command=self.save).pack(side='right', padx=2)
        ttk.Button(dialog_btn, text="Отмена", command=self.dialog.destroy).pack(side='right', padx=2)

    def add_handler(self):
        event = self.event_var.get()
        code = self.code_text.get('1.0', 'end-1c')
        if event and code:
            self.event_system.add_event(self.widget_id, event, code)
            self.refresh_list()
            self.code_text.delete('1.0', 'end')

    def delete_handler(self):
        selection = self.handlers_list.curselection()
        if selection:
            text = self.handlers_list.get(selection[0])
            event = text.split(':')[0]
            self.event_system.remove_event(self.widget_id, event)
            self.refresh_list()

    def refresh_list(self):
        self.handlers_list.delete(0, tk.END)
        if self.widget_id in self.event_system.events:
            for event, code in self.event_system.events[self.widget_id].items():
                self.handlers_list.insert(tk.END, f"{event}: {code[:40]}...")

    def save(self):
        self.callback(self.event_system)
        self.dialog.destroy()


# ============== ДИАЛОГ ГРУППИРОВКИ ==============
class GroupDialog:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Управление группами")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        create_frame = ttk.LabelFrame(main_frame, text="Создать группу", padding="5")
        create_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(create_frame, text="Название группы:").pack(anchor='w')
        self.group_name = ttk.Entry(create_frame)
        self.group_name.pack(fill='x', pady=5)

        ttk.Button(create_frame, text="Создать группу", command=self.create_group).pack(pady=5)

        widgets_frame = ttk.LabelFrame(main_frame, text="Выберите виджеты", padding="5")
        widgets_frame.pack(fill='both', expand=True, pady=(0, 10))

        scrollbar = ttk.Scrollbar(widgets_frame)
        scrollbar.pack(side='right', fill='y')

        self.widgets_list = tk.Listbox(widgets_frame, selectmode='multiple', yscrollcommand=scrollbar.set)
        self.widgets_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.widgets_list.yview)

        for i, w in enumerate(self.designer.widgets):
            self.widgets_list.insert(tk.END, f"{i + 1}. {w.widget_type} (x={w.x}, y={w.y})")

        ttk.Button(main_frame, text="Закрыть", command=self.dialog.destroy).pack(pady=10)

    def create_group(self):
        name = self.group_name.get().strip()
        if not name:
            name = f"Группа {len(self.designer.groups) + 1}"

        selected = self.widgets_list.curselection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите виджеты для группировки")
            return

        group = WidgetGroup(len(self.designer.groups) + 1, name)

        for idx in selected:
            if idx < len(self.designer.widgets):
                widget = self.designer.widgets[idx]
                group.add_widget(widget)
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#9b59b6')

        if group.widgets:
            self.designer.groups.append(group)
            self.designer.status_bar.config(text=f"Создана группа '{name}' с {len(group.widgets)} виджетами")
            self.designer.undo_manager.add_action(GroupAction(self.designer, group, 'create'))
            self.dialog.destroy()


# ============== ДИАЛОГ ТЕМ ==============
class ThemeDialog:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Темы оформления")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="🎨 ВЫБЕРИТЕ ТЕМУ", font=('Arial', 14, 'bold')).pack(pady=10)

        themes = [
            ("🌞 Светлая", self.light_theme, "#ecf0f1"),
            ("🌙 Темная", self.dark_theme, "#2c3e50"),
            ("💙 Синяя", self.blue_theme, "#3498db"),
            ("💚 Зеленая", self.green_theme, "#27ae60"),
            ("🧡 Оранжевая", self.orange_theme, "#e67e22"),
            ("💜 Фиолетовая", self.purple_theme, "#9b59b6")
        ]

        for name, func, color in themes:
            btn = tk.Button(main_frame, text=name, command=func,
                            bg=color, fg='white', font=('Arial', 10),
                            width=20, height=2, bd=0)
            btn.pack(pady=5)

        ttk.Button(main_frame, text="Закрыть", command=self.dialog.destroy).pack(pady=15)

    def light_theme(self):
        self.designer.apply_theme('light')
        self.dialog.destroy()

    def dark_theme(self):
        self.designer.apply_theme('dark')
        self.dialog.destroy()

    def blue_theme(self):
        self.designer.apply_theme('blue')
        self.dialog.destroy()

    def green_theme(self):
        self.designer.apply_theme('green')
        self.dialog.destroy()

    def orange_theme(self):
        self.designer.apply_theme('orange')
        self.dialog.destroy()

    def purple_theme(self):
        self.designer.apply_theme('purple')
        self.dialog.destroy()


# ============== МЕНЕДЖЕР БУФЕРА ОБМЕНА ==============
class ClipboardManager:
    def __init__(self):
        self.clipboard = []
        self.max_items = 10

    def copy(self, widgets_data):
        self.clipboard.insert(0, copy.deepcopy(widgets_data))
        if len(self.clipboard) > self.max_items:
            self.clipboard.pop()
        return True

    def paste(self):
        if self.clipboard:
            return copy.deepcopy(self.clipboard[0])
        return None

    def clear(self):
        self.clipboard.clear()


# ============== МЕНЕДЖЕР АВТОСОХРАНЕНИЯ ==============
class AutoSaveManager:
    def __init__(self, designer, interval=300000):
        self.designer = designer
        self.interval = interval
        self.enabled = True
        self.autosave_dir = Path.home() / '.tkinter_designer' / 'autosave'
        self.autosave_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        self.auto_save()

    def auto_save(self):
        if self.enabled and self.designer.widgets:
            try:
                filename = self.autosave_dir / f'autosave_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tkdesign'
                data = {
                    'widgets': [w.to_dict() for w in self.designer.widgets],
                    'events': self.designer.event_system.events,
                    'timestamp': datetime.now().isoformat()
                }
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                self.designer.status_bar.config(text=f"💾 Автосохранение: {filename.name}")
            except Exception as e:
                print(f"Auto-save error: {e}")
        self.designer.root.after(self.interval, self.auto_save)

    def get_last_autosave(self):
        files = sorted(self.autosave_dir.glob("autosave_*.tkdesign"), reverse=True)
        return files[0] if files else None

    def restore_last_autosave(self):
        last = self.get_last_autosave()
        if last:
            try:
                with open(last, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.designer.load_project_data(data)
                self.designer.status_bar.config(text=f"✅ Восстановлено из: {last.name}")
                return True
            except Exception as e:
                print(f"Restore error: {e}")
        return False


# ============== МИНИ-КАРТА ==============
class MiniMap:
    def __init__(self, designer):
        self.designer = designer
        self.window = None
        self.canvas = None

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        self.window = tk.Toplevel(self.designer.root)
        self.window.title("🗺️ Мини-карта")
        self.window.geometry("250x250")
        self.window.configure(bg="#2b2b2b")
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        self.canvas = tk.Canvas(self.window, bg="#1e1e1e", width=250, height=250, highlightthickness=0)
        self.canvas.pack(padx=5, pady=5)

        self.canvas.bind("<Button-1>", self.on_click)
        self.update()

    def hide(self):
        if self.window:
            self.window.withdraw()

    def on_click(self, event):
        x = event.x * 2000 / 250
        y = event.y * 2000 / 250
        self.designer.canvas.xview_moveto(x / 2000)
        self.designer.canvas.yview_moveto(y / 2000)

    def update(self):
        if not self.window or not self.window.winfo_exists():
            return

        self.canvas.delete("all")

        for w in self.designer.widgets:
            x = w.x * 250 / 2000
            y = w.y * 250 / 2000
            wd = w.width * 250 / 2000
            ht = w.height * 250 / 2000

            color = "#4CAF50"
            if w == self.designer.selected_widget:
                color = "#FFC107"
            elif w.group_id:
                color = "#9B59B6"

            self.canvas.create_rectangle(x, y, x + wd, y + ht, fill=color, outline="#fff", width=1)

        x1 = self.designer.canvas.canvasx(0) * 250 / 2000
        y1 = self.designer.canvas.canvasy(0) * 250 / 2000
        x2 = self.designer.canvas.canvasx(self.designer.canvas.winfo_width()) * 250 / 2000
        y2 = self.designer.canvas.canvasy(self.designer.canvas.winfo_height()) * 250 / 2000

        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff88", width=2, dash=(4, 2))

        self.window.after(1000, self.update)


# ============== ДИАЛОГ ПОИСКА ==============
class SearchDialog:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🔍 Поиск виджетов")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Поиск:", font=('Arial', 10, 'bold')).pack(anchor='w')
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(main_frame, textvariable=self.search_var)
        self.search_entry.pack(fill='x', pady=5)
        self.search_entry.bind('<KeyRelease>', lambda e: self.search())

        ttk.Label(main_frame, text="Результаты:").pack(anchor='w', pady=(10, 0))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.results_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.results_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.results_list.yview)

        self.results_list.bind('<Double-Button-1>', self.select_widget)

        ttk.Button(main_frame, text="Выделить", command=self.select_widget).pack(pady=5)
        ttk.Button(main_frame, text="Закрыть", command=self.dialog.destroy).pack()

    def search(self):
        self.results_list.delete(0, tk.END)
        search_text = self.search_var.get().lower()
        if not search_text:
            return

        for i, w in enumerate(self.designer.widgets):
            text = w.properties.get('text', '').lower()
            wtype = w.widget_type.lower()
            if search_text in text or search_text in wtype:
                self.results_list.insert(tk.END, f"{i + 1}. {w.widget_type}: {w.properties.get('text', '')[:30]}")

    def select_widget(self, event=None):
        selection = self.results_list.curselection()
        if selection:
            idx = int(self.results_list.get(selection[0]).split('.')[0]) - 1
            if idx < len(self.designer.widgets):
                widget = self.designer.widgets[idx]
                self.designer.select_widget_by_info(widget)
                self.dialog.destroy()


# ============== ГЕНЕРАТОР КОДА ==============
class CodeGenerator:
    @staticmethod
    def generate_python_code(designer, filename):
        widgets_data = designer.widgets

        code = []
        code.append('import tkinter as tk')
        code.append('from tkinter import ttk, messagebox')
        code.append('')
        code.append('')
        code.append('class MainApplication:')
        code.append('    """Главное приложение"""')
        code.append('    def __init__(self):')
        code.append('        self.root = tk.Tk()')
        code.append('        self.root.title("Мое приложение")')
        code.append('        self.root.geometry("800x600")')
        code.append('        self.setup_ui()')
        code.append('')
        code.append('    def setup_ui(self):')
        code.append('        """Настройка интерфейса"""')

        for i, w in enumerate(widgets_data):
            wtype = w.widget_type
            x, y = w.x, w.y
            props = w.properties
            var_name = f"widget_{i}"

            if wtype == 'Button':
                code.append(f'        self.{var_name} = tk.Button(self.root, text="{props.get("text", "Кнопка")}")')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Label':
                code.append(f'        self.{var_name} = tk.Label(self.root, text="{props.get("text", "Метка")}")')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Entry':
                code.append(f'        self.{var_name} = tk.Entry(self.root)')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Text':
                code.append(f'        self.{var_name} = tk.Text(self.root, height=5, width=30)')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Listbox':
                code.append(f'        self.{var_name} = tk.Listbox(self.root, height=5, width=30)')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Checkbutton':
                code.append(
                    f'        self.{var_name} = tk.Checkbutton(self.root, text="{props.get("text", "Флажок")}")')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Radiobutton':
                code.append(f'        self.{var_name} = tk.Radiobutton(self.root, text="{props.get("text", "Радио")}")')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Combobox':
                code.append(f'        self.{var_name} = ttk.Combobox(self.root, values=["Опция 1", "Опция 2"])')
                code.append(f'        self.{var_name}.place(x={x}, y={y})')
            elif wtype == 'Frame':
                code.append(f'        self.{var_name} = tk.Frame(self.root, bg="#f0f0f0")')
                code.append(f'        self.{var_name}.place(x={x}, y={y}, width={w.width}, height={w.height})')

        code.append('')
        code.append('    def run(self):')
        code.append('        """Запуск приложения"""')
        code.append('        self.root.mainloop()')
        code.append('')
        code.append('')
        code.append('if __name__ == "__main__":')
        code.append('    app = MainApplication()')
        code.append('    app.run()')

        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(code))

        return filename


# ============== ГЕНЕРАТОР HTML ==============
class HTMLGenerator:
    @staticmethod
    def generate_html(designer, filename):
        widgets_data = designer.widgets

        html = []
        html.append('<!DOCTYPE html>')
        html.append('<html>')
        html.append('<head>')
        html.append('<title>Generated Interface</title>')
        html.append('<meta charset="utf-8">')
        html.append('<style>')
        html.append('body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }')
        html.append('.widget { position: absolute; }')
        html.append(
            'button { background: #4CAF50; color: white; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; }')
        html.append('button:hover { background: #45a049; }')
        html.append('label { display: inline-block; }')
        html.append('input { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }')
        html.append('textarea { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }')
        html.append('select { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }')
        html.append('</style>')
        html.append('</head>')
        html.append('<body>')

        for w in widgets_data:
            wtype = w.widget_type
            x, y = w.x, w.y
            props = w.properties

            style = f"left: {x}px; top: {y}px;"

            if wtype == 'Button':
                html.append(f'<button class="widget" style="{style}">{props.get("text", "Кнопка")}</button>')
            elif wtype == 'Label':
                html.append(f'<label class="widget" style="{style}">{props.get("text", "Метка")}</label>')
            elif wtype == 'Entry':
                html.append(f'<input class="widget" type="text" style="{style}" value="{props.get("text", "")}">')
            elif wtype == 'Text':
                html.append(
                    f'<textarea class="widget" style="{style} width:{w.width}px; height:{w.height}px;">{props.get("text", "")}</textarea>')
            elif wtype == 'Checkbutton':
                html.append(
                    f'<label class="widget" style="{style}"><input type="checkbox"> {props.get("text", "Флажок")}</label>')
            elif wtype == 'Radiobutton':
                html.append(
                    f'<label class="widget" style="{style}"><input type="radio" name="radio"> {props.get("text", "Радио")}</label>')

        html.append('</body>')
        html.append('</html>')

        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))

        return filename


# ============== ГЛАВНЫЙ КЛАСС КОНСТРУКТОРА ==============
class TkinterDesigner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Tkinter Designer Pro - Визуальный конструктор")
        self.root.geometry("1500x850")

        self.widgets = []
        self.selected_widget = None
        self.placing_widget = None
        self.event_system = EventSystem()
        self.groups = []
        self.current_theme = 'light'

        self.zoom_level = 1.0
        self.resizing_widget = None
        self.resize_start = None

        self.undo_manager = UndoRedoManager()
        self.drag_drop = DragDropManager(self)

        self.clipboard_manager = ClipboardManager()
        self.autosave_manager = AutoSaveManager(self)
        self.minimap = MiniMap(self)
        self.live_preview = LivePreviewWindow(self.root, self)
        self.live_preview.hide()

        self.setup_ui()
        self.create_menu()

        self.autosave_manager.start()

    def setup_ui(self):
        self.toolbar = tk.Frame(self.root, bg='#2c3e50', width=280)
        self.toolbar.pack(side='left', fill='y')
        self.toolbar.pack_propagate(False)

        title = tk.Label(self.toolbar, text="🎨 TKINTER DESIGNER PRO", bg='#2c3e50', fg='white',
                         font=('Arial', 12, 'bold'))
        title.pack(pady=10)

        self.notebook = ttk.Notebook(self.toolbar)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        widgets_frame = ttk.Frame(self.notebook)
        self.notebook.add(widgets_frame, text="🔘 Виджеты")

        widgets = [
            ("🔘 Кнопка", "Button"), ("📝 Метка", "Label"), ("✏️ Поле ввода", "Entry"),
            ("📄 Текст", "Text"), ("📋 Список", "Listbox"), ("✅ Флажок", "Checkbutton"),
            ("🔘 Радио", "Radiobutton"), ("📊 Комбобокс", "Combobox"), ("📦 Фрейм", "Frame")
        ]

        for text, wtype in widgets:
            btn = tk.Button(widgets_frame, text=text, bg='#34495e', fg='white',
                            font=('Arial', 10), bd=0, pady=8,
                            command=lambda t=wtype: self.start_place_widget(t))
            btn.pack(fill='x', padx=5, pady=3)

        groups_frame = ttk.Frame(self.notebook)
        self.notebook.add(groups_frame, text="📦 Группы")

        tk.Button(groups_frame, text="📦 Управление группами", command=self.show_group_dialog,
                  bg='#9b59b6', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)
        tk.Button(groups_frame, text="🔲 Создать группу", command=self.create_group_from_selected,
                  bg='#3498db', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)
        tk.Button(groups_frame, text="🔓 Разгруппировать", command=self.ungroup_selected,
                  bg='#e67e22', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)

        actions_frame = ttk.Frame(self.notebook)
        self.notebook.add(actions_frame, text="⚡ Действия")

        actions = [
            ("↩️ Отменить", self.undo_action), ("↪️ Повторить", self.redo_action),
            ("🗑️ Удалить", self.delete_widget), ("⚙️ Свойства", self.edit_properties),
            ("🎯 События", self.edit_events), ("📋 Сниппеты", self.show_snippets),
            ("📦 Пакетное редактирование", self.show_batch_edit), ("📐 Выравнивание", self.show_alignment),
            ("🎨 Темы", self.show_themes), ("📚 Шаблоны", self.show_templates),
            ("🗺️ Мини-карта", self.show_minimap), ("🔍 Поиск", self.show_search),
            ("🎬 Live Preview", self.show_live_preview), ("📄 Экспорт в Python", self.export_python),
            ("🌐 Экспорт в HTML", self.export_html)
        ]

        for text, cmd in actions:
            btn = tk.Button(actions_frame, text=text, bg='#34495e', fg='white',
                            font=('Arial', 10), bd=0, pady=5, command=cmd)
            btn.pack(fill='x', padx=5, pady=2)

        self.info_label = tk.Label(self.toolbar, text="Виджетов: 0 | Групп: 0",
                                   bg='#2c3e50', fg='#95a5a6')
        self.info_label.pack(side='bottom', pady=10)

        self.right_panel = tk.Frame(self.root, bg='#ecf0f1', width=300)
        self.right_panel.pack(side='right', fill='y')
        self.right_panel.pack_propagate(False)

        tk.Label(self.right_panel, text="📋 СВОЙСТВА", bg='#ecf0f1',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.properties_frame = tk.Frame(self.right_panel, bg='#ecf0f1')
        self.properties_frame.pack(fill='both', expand=True, padx=10, pady=5)

        canvas_container = tk.Frame(self.root, bg='white')
        canvas_container.pack(side='left', fill='both', expand=True)

        self.canvas_toolbar = tk.Frame(canvas_container, bg='#bdc3c7', height=40)
        self.canvas_toolbar.pack(fill='x')

        tk.Label(self.canvas_toolbar, text="Рабочая область:", bg='#bdc3c7',
                 font=('Arial', 9, 'bold')).pack(side='left', padx=10)

        tk.Label(self.canvas_toolbar, text="Сетка:", bg='#bdc3c7').pack(side='left', padx=(10, 2))
        self.grid_size_var = tk.StringVar(value="20")
        grid_entry = tk.Entry(self.canvas_toolbar, textvariable=self.grid_size_var, width=5)
        grid_entry.pack(side='left', padx=2)
        tk.Button(self.canvas_toolbar, text="Уст.", command=self.set_grid_size,
                  bg='#95a5a6', bd=0, padx=5).pack(side='left', padx=2)

        tk.Button(self.canvas_toolbar, text="🔍 +", command=self.zoom_in,
                  bg='#95a5a6', bd=0, padx=10).pack(side='left', padx=2)
        tk.Button(self.canvas_toolbar, text="🔍 -", command=self.zoom_out,
                  bg='#95a5a6', bd=0, padx=10).pack(side='left', padx=2)
        tk.Button(self.canvas_toolbar, text="🔍 1:1", command=self.zoom_reset,
                  bg='#95a5a6', bd=0, padx=10).pack(side='left', padx=2)

        self.zoom_label = tk.Label(self.canvas_toolbar, text="100%", bg='#bdc3c7')
        self.zoom_label.pack(side='left', padx=5)

        tk.Button(self.canvas_toolbar, text="📐 Сетка", command=self.toggle_grid,
                  bg='#95a5a6', bd=0, padx=10).pack(side='left', padx=5)
        tk.Button(self.canvas_toolbar, text="🎬 Live Preview", command=self.show_live_preview,
                  bg='#27ae60', fg='white', bd=0, padx=10).pack(side='left', padx=5)
        tk.Button(self.canvas_toolbar, text="📐 Выравнивание", command=self.show_alignment,
                  bg='#f39c12', fg='white', bd=0, padx=10).pack(side='left', padx=5)
        tk.Button(self.canvas_toolbar, text="🎨 Темы", command=self.show_themes,
                  bg='#9b59b6', fg='white', bd=0, padx=10).pack(side='left', padx=5)
        tk.Button(self.canvas_toolbar, text="🗺️ Карта", command=self.show_minimap,
                  bg='#1abc9c', fg='white', bd=0, padx=10).pack(side='left', padx=5)

        v_scroll = tk.Scrollbar(canvas_container, orient='vertical')
        v_scroll.pack(side='right', fill='y')
        h_scroll = tk.Scrollbar(canvas_container, orient='horizontal')
        h_scroll.pack(side='bottom', fill='x')

        self.canvas = tk.Canvas(canvas_container, bg='white',
                                yscrollcommand=v_scroll.set,
                                xscrollcommand=h_scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)

        v_scroll.config(command=self.canvas.yview)
        h_scroll.config(command=self.canvas.xview)
        self.canvas.config(scrollregion=(0, 0, 2000, 2000))

        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.canvas.bind('<Motion>', self.on_mouse_move)

        self.status_bar = tk.Label(self.root,
                                   text="✅ Готов | Ctrl+клик - мульти-выбор | Ctrl+Z - отменить | Координаты: X=0, Y=0",
                                   bd=1, relief='sunken', bg='#ecf0f1', anchor='w')
        self.status_bar.pack(side='bottom', fill='x')

        self.layout_manager = LayoutManager(self.canvas)

    def on_mouse_move(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.status_bar.config(
            text=f"✅ Готов | Ctrl+клик - мульти-выбор | Ctrl+Z - отменить | Координаты: X={int(x)}, Y={int(y)}")

    def show_snippets(self):
        if self.selected_widget:
            event_dialog = EventDialog(self.root, self.selected_widget, self.event_system, self.on_events_changed)
            CodeSnippetsDialog(self.root, event_dialog.code_text)
        else:
            messagebox.showinfo("Сниппеты", "Сначала выберите виджет для добавления события")

    def show_batch_edit(self):
        selected = self.get_selected_widgets()
        if len(selected) < 2:
            messagebox.showinfo("Пакетное редактирование", "Выделите минимум 2 виджета для пакетного редактирования")
            return
        BatchEditDialog(self.root, self, selected)

    def show_live_preview(self):
        if self.live_preview.visible:
            self.live_preview.hide()
            self.status_bar.config(text="🎬 Live Preview скрыт")
        else:
            self.live_preview.show()
            self.status_bar.config(text="🎬 Live Preview открыт - обновляется автоматически")

    def set_grid_size(self):
        try:
            size = int(self.grid_size_var.get())
            if size >= 5:
                self.layout_manager.set_grid_size(size)
                self.status_bar.config(text=f"📐 Размер сетки: {size}px")
        except:
            pass

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Файл', menu=file_menu)
        file_menu.add_command(label='Новый проект', command=self.new_project, accelerator='Ctrl+N')
        file_menu.add_command(label='Сохранить проект', command=self.save_project, accelerator='Ctrl+S')
        file_menu.add_command(label='Загрузить проект', command=self.load_project, accelerator='Ctrl+O')
        file_menu.add_separator()
        file_menu.add_command(label='Экспорт в Python', command=self.export_python)
        file_menu.add_command(label='Экспорт в HTML', command=self.export_html)
        file_menu.add_separator()
        file_menu.add_command(label='Восстановить автосохранение', command=self.restore_autosave)
        file_menu.add_separator()
        file_menu.add_command(label='Выход', command=self.root.quit, accelerator='Ctrl+Q')

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Правка', menu=edit_menu)
        edit_menu.add_command(label='Отменить', command=self.undo_action, accelerator='Ctrl+Z')
        edit_menu.add_command(label='Повторить', command=self.redo_action, accelerator='Ctrl+Y')
        edit_menu.add_separator()
        edit_menu.add_command(label='Копировать виджеты', command=self.copy_widgets_to_clipboard,
                              accelerator='Ctrl+Shift+C')
        edit_menu.add_command(label='Вставить виджеты', command=self.paste_widgets, accelerator='Ctrl+Shift+V')
        edit_menu.add_separator()
        edit_menu.add_command(label='Удалить', command=self.delete_widget, accelerator='Del')
        edit_menu.add_command(label='Свойства', command=self.edit_properties, accelerator='F4')
        edit_menu.add_command(label='События', command=self.edit_events, accelerator='F5')
        edit_menu.add_command(label='Выделить все', command=self.select_all, accelerator='Ctrl+A')

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Вид', menu=view_menu)
        view_menu.add_command(label='Выравнивание', command=self.show_alignment)
        view_menu.add_command(label='Сетка', command=self.toggle_grid)
        view_menu.add_command(label='Темы', command=self.show_themes)
        view_menu.add_command(label='Мини-карта', command=self.show_minimap)
        view_menu.add_command(label='Поиск', command=self.show_search)
        view_menu.add_command(label='Live Preview', command=self.show_live_preview)

        template_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Шаблоны', menu=template_menu)
        template_menu.add_command(label='📚 Библиотека шаблонов', command=self.show_templates)

        self.root.bind('<Control-n>', lambda e: self.new_project())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-o>', lambda e: self.load_project())
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-y>', lambda e: self.redo_action())
        self.root.bind('<Delete>', lambda e: self.delete_widget())
        self.root.bind('<F4>', lambda e: self.edit_properties())
        self.root.bind('<F5>', lambda e: self.edit_events())
        self.root.bind('<Control-c>', lambda e: self.copy_widget())
        self.root.bind('<Control-a>', lambda e: self.select_all())
        self.root.bind('<Control-Shift-C>', lambda e: self.copy_widgets_to_clipboard())
        self.root.bind('<Control-Shift-V>', lambda e: self.paste_widgets())
        self.root.bind('<Control-Shift-L>', lambda e: self.align_selected('left'))
        self.root.bind('<Control-Shift-R>', lambda e: self.align_selected('right'))
        self.root.bind('<Control-Shift-T>', lambda e: self.align_selected('top'))
        self.root.bind('<Control-Shift-B>', lambda e: self.align_selected('bottom'))
        self.root.bind('<Control-Shift-C>', lambda e: self.align_selected('center_h'))
        self.root.bind('<Control-f>', lambda e: self.show_search())

    def align_selected(self, direction):
        selected = self.get_selected_widgets()
        if not selected:
            return
        if direction == 'left':
            min_x = min(w.x for w in selected)
            for w in selected:
                w.x = min_x
                self.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'right':
            max_right = max(w.x + w.width for w in selected)
            for w in selected:
                w.x = max_right - w.width
                self.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'top':
            min_y = min(w.y for w in selected)
            for w in selected:
                w.y = min_y
                self.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'bottom':
            max_bottom = max(w.y + w.height for w in selected)
            for w in selected:
                w.y = max_bottom - w.height
                self.canvas.coords(w.canvas_id, w.x, w.y)
        elif direction == 'center_h':
            center_x = sum(w.x + w.width / 2 for w in selected) / len(selected)
            for w in selected:
                w.x = center_x - w.width / 2
                self.canvas.coords(w.canvas_id, w.x, w.y)
        self.update_properties_panel()

    def zoom_in(self):
        if self.zoom_level < 3.0:
            self.zoom_level += 0.1
            self.canvas.scale('all', 0, 0, 1.1, 1.1)
            self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")

    def zoom_out(self):
        if self.zoom_level > 0.3:
            self.zoom_level -= 0.1
            self.canvas.scale('all', 0, 0, 0.9, 0.9)
            self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")

    def zoom_reset(self):
        factor = 1.0 / self.zoom_level
        self.canvas.scale('all', 0, 0, factor, factor)
        self.zoom_level = 1.0
        self.zoom_label.config(text="100%")

    def apply_theme(self, theme):
        self.current_theme = theme
        themes = {
            'light': {'bg': '#ecf0f1', 'fg': '#2c3e50', 'toolbar': '#34495e', 'accent': '#3498db'},
            'dark': {'bg': '#2c3e50', 'fg': '#ecf0f1', 'toolbar': '#1a2632', 'accent': '#3498db'},
            'blue': {'bg': '#3498db', 'fg': '#ffffff', 'toolbar': '#2980b9', 'accent': '#f1c40f'},
            'green': {'bg': '#27ae60', 'fg': '#ffffff', 'toolbar': '#229954', 'accent': '#f1c40f'},
            'orange': {'bg': '#e67e22', 'fg': '#ffffff', 'toolbar': '#d35400', 'accent': '#f1c40f'},
            'purple': {'bg': '#9b59b6', 'fg': '#ffffff', 'toolbar': '#8e44ad', 'accent': '#f1c40f'}
        }

        if theme in themes:
            t = themes[theme]
            self.root.configure(bg=t['bg'])
            self.right_panel.configure(bg=t['bg'])
            self.properties_frame.configure(bg=t['bg'])
            self.status_bar.configure(bg=t['bg'], fg=t['fg'])

    def show_themes(self):
        ThemeDialog(self.root, self)

    def show_templates(self):
        TemplateLibrary(self.root, self)

    def show_alignment(self):
        AlignmentDialog(self.root, self)

    def show_group_dialog(self):
        GroupDialog(self.root, self)

    def show_minimap(self):
        self.minimap.show()

    def show_search(self):
        SearchDialog(self.root, self)

    def export_python(self):
        filename = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python files", "*.py")])
        if filename:
            CodeGenerator.generate_python_code(self, filename)
            messagebox.showinfo("Экспорт", f"✅ Python код сохранен в:\n{filename}")
            self.status_bar.config(text=f"📄 Экспортирован Python код: {filename}")

    def export_html(self):
        filename = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML files", "*.html")])
        if filename:
            HTMLGenerator.generate_html(self, filename)
            messagebox.showinfo("Экспорт", f"✅ HTML сохранен в:\n{filename}")
            self.status_bar.config(text=f"🌐 Экспортирован HTML: {filename}")

    def copy_widgets_to_clipboard(self):
        selected = self.get_selected_widgets()
        if selected:
            widgets_data = [w.to_dict() for w in selected]
            self.clipboard_manager.copy(widgets_data)
            self.status_bar.config(text=f"📋 Скопировано {len(selected)} виджетов в буфер")

    def paste_widgets(self):
        widgets_data = self.clipboard_manager.paste()
        if widgets_data:
            offset_x = 30
            offset_y = 30
            for wdata in widgets_data:
                self.add_widget(wdata['type'], wdata['x'] + offset_x, wdata['y'] + offset_y)
                for widget in self.widgets:
                    if widget.x == wdata['x'] + offset_x and widget.y == wdata['y'] + offset_y:
                        widget.properties = wdata.get('properties', {})
                        if 'text' in widget.properties and widget.widget_instance:
                            try:
                                widget.widget_instance.config(text=widget.properties['text'])
                            except:
                                pass
            self.status_bar.config(text=f"📋 Вставлено {len(widgets_data)} виджетов")

    def restore_autosave(self):
        if self.autosave_manager.restore_last_autosave():
            messagebox.showinfo("Восстановление", "✅ Проект восстановлен из автосохранения")
        else:
            messagebox.showinfo("Восстановление", "❌ Нет автосохранений")

    def preview(self):
        if self.widgets:
            PreviewWindow(self.root, self)
            self.status_bar.config(text="🔍 Открыт предварительный просмотр")
        else:
            messagebox.showinfo("Предпросмотр", "Нет виджетов для просмотра")

    def start_place_widget(self, widget_type):
        self.placing_widget = widget_type
        self.canvas.config(cursor='cross')
        self.status_bar.config(text=f"📍 Размещение: {widget_type} - кликните на холст")

    def on_canvas_click(self, event):
        if self.placing_widget:
            x, y = self.layout_manager.snap(event.x, event.y)
            self.add_widget(self.placing_widget, x, y)
            self.placing_widget = None
            self.canvas.config(cursor='arrow')
            self.status_bar.config(text="✅ Виджет размещен")
        else:
            self.clear_selection()

    def add_widget(self, widget_type, x, y):
        frame = tk.Frame(self.canvas, bg='#3498db', relief='solid', borderwidth=2)

        if widget_type == 'Button':
            w = tk.Button(frame, text='Кнопка', width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 35
        elif widget_type == 'Label':
            w = tk.Label(frame, text='Метка', width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif widget_type == 'Entry':
            w = tk.Entry(frame, width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif widget_type == 'Text':
            w = tk.Text(frame, height=3, width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 70
        elif widget_type == 'Listbox':
            w = tk.Listbox(frame, height=3, width=12)
            w.insert(1, 'Элемент 1')
            w.insert(2, 'Элемент 2')
            w.pack(padx=8, pady=5)
            width, height = 100, 70
        elif widget_type == 'Checkbutton':
            w = tk.Checkbutton(frame, text='Флажок')
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif widget_type == 'Radiobutton':
            w = tk.Radiobutton(frame, text='Радио')
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif widget_type == 'Combobox':
            w = ttk.Combobox(frame, values=['Опция 1', 'Опция 2'])
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif widget_type == 'Frame':
            w = tk.Frame(frame, bg='#95a5a6', width=100, height=100)
            w.pack()
            width, height = 100, 100
        else:
            return

        properties = {
            'text': w.cget('text') if hasattr(w, 'cget') and 'text' in w.keys() else '',
            'width': width,
            'height': height
        }

        widget_info = WidgetInfo(widget_type, x, y, properties)
        widget_info.widget_ref = frame
        widget_info.widget_instance = w
        widget_info.width = width
        widget_info.height = height

        canvas_id = self.canvas.create_window(x, y, window=frame, anchor='nw')
        widget_info.canvas_id = canvas_id

        self.widgets.append(widget_info)

        frame.bind('<Button-1>', lambda e, wi=widget_info: self.on_widget_click(e, wi))
        frame.bind('<B1-Motion>', lambda e, wi=widget_info: self.on_widget_drag(e, wi))
        frame.bind('<ButtonRelease-1>', lambda e, wi=widget_info: self.on_widget_release(e, wi))
        frame.bind('<Double-Button-1>', lambda e, wi=widget_info: self.edit_properties())

        action = AddWidgetAction(self, widget_info)
        self.undo_manager.add_action(action)

        self.update_info()
        self.update_properties_panel()

    def on_widget_click(self, event, widget_info):
        ctrl_pressed = (event.state & 0x0004) != 0

        if ctrl_pressed:
            self.toggle_widget_selection(widget_info)
        else:
            self.clear_selection()
            self.select_widget_by_info(widget_info)

        self.drag_drop.start_drag(event, widget_info)

    def on_widget_drag(self, event, widget_info):
        self.drag_drop.on_drag(event)

    def on_widget_release(self, event, widget_info):
        self.drag_drop.end_drag()

    def toggle_widget_selection(self, widget_info):
        is_selected = (widget_info.widget_ref.cget('bg') == '#f1c40f')
        if is_selected:
            widget_info.widget_ref.config(bg='#3498db')
            if self.selected_widget == widget_info:
                self.selected_widget = None
        else:
            widget_info.widget_ref.config(bg='#f1c40f')
            self.selected_widget = widget_info
        self.update_properties_panel()
        self.update_status_with_selection_count()

    def clear_selection(self):
        for w in self.widgets:
            if w.widget_ref:
                w.widget_ref.config(bg='#3498db')
        self.selected_widget = None
        self.update_properties_panel()
        self.update_status_with_selection_count()

    def get_selected_count(self):
        count = 0
        for w in self.widgets:
            if w.widget_ref and w.widget_ref.cget('bg') == '#f1c40f':
                count += 1
        return count

    def get_selected_widgets(self):
        selected = []
        for w in self.widgets:
            if w.widget_ref and w.widget_ref.cget('bg') == '#f1c40f':
                selected.append(w)
        return selected

    def update_status_with_selection_count(self):
        count = self.get_selected_count()
        if count == 0:
            self.status_bar.config(text="✅ Готов")
        elif count == 1:
            self.status_bar.config(text=f"✨ Выбран 1 виджет")
        else:
            self.status_bar.config(text=f"✨ Выбрано {count} виджетов")

    def select_widget_by_info(self, widget_info):
        if self.selected_widget:
            if self.selected_widget.group_id:
                for group in self.groups:
                    if group.group_id == self.selected_widget.group_id:
                        for w in group.widgets:
                            if w.widget_ref:
                                w.widget_ref.config(bg='#3498db')
                        break
            else:
                self.selected_widget.widget_ref.config(bg='#3498db')

        self.selected_widget = widget_info

        if widget_info.group_id:
            for group in self.groups:
                if group.group_id == widget_info.group_id:
                    for w in group.widgets:
                        if w.widget_ref:
                            w.widget_ref.config(bg='#f1c40f')
                    self.status_bar.config(text=f"✨ Выбрана группа: {group.name}")
                    break
        else:
            widget_info.widget_ref.config(bg='#f1c40f')
            self.status_bar.config(text=f"✨ Выбран: {widget_info.widget_type}")

        self.update_properties_panel()

    def update_properties_panel(self):
        for w in self.properties_frame.winfo_children():
            w.destroy()

        selected_count = self.get_selected_count()

        if selected_count == 0:
            tk.Label(self.properties_frame, text="Виджет не выбран",
                     bg='#ecf0f1', font=('Arial', 10)).pack(pady=20)
            return
        elif selected_count > 1:
            tk.Label(self.properties_frame, text=f"🎯 Выбрано {selected_count} виджетов",
                     bg='#ecf0f1', font=('Arial', 10, 'bold')).pack(pady=10)
            tk.Label(self.properties_frame,
                     text="Используйте выравнивание\nдля работы с группой\n\nГорячие клавиши:\nCtrl+Shift+L/R/T/B/C",
                     bg='#ecf0f1', justify='center').pack(pady=5)
            return

        w = self.selected_widget
        if not w:
            return

        tk.Label(self.properties_frame, text=f"📌 {w.widget_type}",
                 bg='#ecf0f1', font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        tk.Label(self.properties_frame, text=f"Позиция: X={w.x}, Y={w.y}",
                 bg='#ecf0f1').pack(anchor='w', pady=2)
        tk.Label(self.properties_frame, text=f"Размер: {w.width}x{w.height}",
                 bg='#ecf0f1').pack(anchor='w', pady=2)

        tk.Frame(self.properties_frame, height=1, bg='#bdc3c7').pack(fill='x', pady=5)

        if w.widget_type in ['Button', 'Label']:
            tk.Label(self.properties_frame, text="Текст:", bg='#ecf0f1').pack(anchor='w', pady=(5, 0))
            text_var = tk.StringVar(value=w.properties.get('text', ''))
            entry = tk.Entry(self.properties_frame, textvariable=text_var)
            entry.pack(fill='x', pady=(0, 5))

            def update_text():
                if w.widget_instance:
                    w.widget_instance.config(text=text_var.get())
                    w.properties['text'] = text_var.get()

            tk.Button(self.properties_frame, text="Применить",
                      command=update_text, bg='#3498db', fg='white', bd=0).pack(fill='x', pady=2)

        tk.Frame(self.properties_frame, height=1, bg='#bdc3c7').pack(fill='x', pady=5)

        btn_frame = tk.Frame(self.properties_frame, bg='#ecf0f1')
        btn_frame.pack(fill='x', pady=5)

        tk.Button(btn_frame, text="⚙️ Свойства", command=self.edit_properties,
                  bg='#9b59b6', fg='white', bd=0).pack(side='left', padx=2, expand=True, fill='x')
        tk.Button(btn_frame, text="🎯 События", command=self.edit_events,
                  bg='#e67e22', fg='white', bd=0).pack(side='left', padx=2, expand=True, fill='x')
        tk.Button(btn_frame, text="🗑️ Удалить", command=self.delete_widget,
                  bg='#e74c3c', fg='white', bd=0).pack(side='left', padx=2, expand=True, fill='x')

    def delete_widget(self):
        selected = self.get_selected_widgets()
        if selected:
            for widget in selected:
                action = DeleteWidgetAction(self, widget)
                self.undo_manager.add_action(action)
                self.delete_widget_by_info(widget)
            self.status_bar.config(text=f"🗑️ Удалено {len(selected)} виджетов")

    def delete_widget_by_info(self, widget_info):
        if widget_info in self.widgets:
            if widget_info.group_id:
                for group in self.groups:
                    if group.group_id == widget_info.group_id:
                        group.remove_widget(widget_info)
                        if not group.widgets:
                            self.groups.remove(group)
                        break
            self.canvas.delete(widget_info.canvas_id)
            self.widgets.remove(widget_info)
            if self.selected_widget == widget_info:
                self.selected_widget = None
            self.update_info()
            self.update_properties_panel()

    def restore_widget(self, widget_info):
        frame = tk.Frame(self.canvas, bg='#3498db', relief='solid', borderwidth=2)

        if widget_info.widget_type == 'Button':
            w = tk.Button(frame, text=widget_info.properties.get('text', 'Кнопка'), width=12)
            w.pack(padx=8, pady=5)
        elif widget_info.widget_type == 'Label':
            w = tk.Label(frame, text=widget_info.properties.get('text', 'Метка'), width=12)
            w.pack(padx=8, pady=5)
        elif widget_info.widget_type == 'Entry':
            w = tk.Entry(frame, width=12)
            w.pack(padx=8, pady=5)
        else:
            return

        widget_info.widget_ref = frame
        widget_info.widget_instance = w
        canvas_id = self.canvas.create_window(widget_info.x, widget_info.y, window=frame, anchor='nw')
        widget_info.canvas_id = canvas_id
        self.widgets.append(widget_info)

        frame.bind('<Button-1>', lambda e, wi=widget_info: self.on_widget_click(e, wi))
        frame.bind('<B1-Motion>', lambda e, wi=widget_info: self.on_widget_drag(e, wi))
        frame.bind('<ButtonRelease-1>', lambda e, wi=widget_info: self.on_widget_release(e, wi))

        if widget_info.group_id:
            for group in self.groups:
                if group.group_id == widget_info.group_id:
                    group.add_widget(widget_info)
                    break
        self.update_info()

    def copy_widget(self):
        selected = self.get_selected_widgets()
        if selected:
            for widget in selected:
                self.add_widget(widget.widget_type, widget.x + 30, widget.y + 30)
            self.status_bar.config(text=f"📋 Скопировано {len(selected)} виджетов")

    def edit_properties(self):
        if self.selected_widget:
            PropertiesDialog(self.root, self.selected_widget, self.on_properties_changed)

    def edit_events(self):
        if self.selected_widget:
            EventDialog(self.root, self.selected_widget, self.event_system, self.on_events_changed)

    def on_properties_changed(self, widget_info):
        if widget_info.widget_instance and 'text' in widget_info.properties:
            try:
                widget_info.widget_instance.config(text=widget_info.properties['text'])
            except:
                pass
        if 'width' in widget_info.properties:
            try:
                widget_info.width = int(widget_info.properties['width'])
            except:
                pass
        if 'height' in widget_info.properties:
            try:
                widget_info.height = int(widget_info.properties['height'])
            except:
                pass
        if 'bg' in widget_info.properties:
            try:
                widget_info.widget_instance.config(bg=widget_info.properties['bg'])
                widget_info.widget_ref.config(bg=widget_info.properties['bg'])
            except:
                pass
        if 'fg' in widget_info.properties:
            try:
                widget_info.widget_instance.config(fg=widget_info.properties['fg'])
            except:
                pass
        if 'font' in widget_info.properties:
            try:
                widget_info.widget_instance.config(font=widget_info.properties['font'])
            except:
                pass
        self.update_properties_panel()
        self.status_bar.config(text="⚙️ Свойства обновлены")

    def on_events_changed(self, event_system):
        self.event_system = event_system
        self.status_bar.config(text="🎯 События обновлены")

    def create_group_from_selected(self):
        selected = self.get_selected_widgets()
        if len(selected) >= 2:
            group_name = f"Группа {len(self.groups) + 1}"
            group = WidgetGroup(len(self.groups) + 1, group_name)
            for widget in selected:
                group.add_widget(widget)
                if widget.widget_ref:
                    widget.widget_ref.config(bg='#9b59b6')
            self.groups.append(group)
            self.status_bar.config(text=f"📦 Создана группа '{group_name}' с {len(selected)} виджетами")
            self.undo_manager.add_action(GroupAction(self, group, 'create'))
            self.update_info()
        elif len(selected) == 1:
            messagebox.showinfo("Группировка",
                                "Выделите минимум 2 виджета для группировки\n(Ctrl+клик для мульти-выбора)")
        else:
            messagebox.showinfo("Группировка", "Нет выделенных виджетов")

    def ungroup_selected(self):
        if self.selected_widget and self.selected_widget.group_id:
            for group in self.groups:
                if group.group_id == self.selected_widget.group_id:
                    for w in group.widgets:
                        w.group_id = None
                        if w.widget_ref:
                            w.widget_ref.config(bg='#3498db')
                    self.groups.remove(group)
                    self.status_bar.config(text=f"🔓 Группа '{group.name}' разгруппирована")
                    self.undo_manager.add_action(GroupAction(self, group, 'delete'))
                    self.update_info()
                    break

    def select_all(self):
        if self.widgets:
            for w in self.widgets:
                if w.widget_ref:
                    w.widget_ref.config(bg='#f1c40f')
            self.selected_widget = self.widgets[-1] if self.widgets else None
            self.status_bar.config(text=f"✅ Выделено {len(self.widgets)} виджетов")
            self.update_properties_panel()

    def undo_action(self):
        if self.undo_manager.undo():
            self.status_bar.config(text="↩️ Действие отменено")
            self.update_info()
            self.update_properties_panel()
        else:
            self.status_bar.config(text="❌ Нет действий для отмены")

    def redo_action(self):
        if self.undo_manager.redo():
            self.status_bar.config(text="↪️ Действие повторено")
            self.update_info()
            self.update_properties_panel()
        else:
            self.status_bar.config(text="❌ Нет действий для повтора")

    def toggle_grid(self):
        self.layout_manager.toggle_grid()
        self.status_bar.config(text="📐 Сетка: " + ("включена" if self.layout_manager.show_grid else "выключена"))

    def on_drag(self, event):
        pass

    def on_mousewheel(self, event):
        pass

    def new_project(self):
        if messagebox.askyesno("Новый проект", "Очистить рабочую область?"):
            for widget in self.widgets:
                self.canvas.delete(widget.canvas_id)
            self.widgets.clear()
            self.groups.clear()
            self.selected_widget = None
            self.event_system = EventSystem()
            self.update_info()
            self.update_properties_panel()
            self.status_bar.config(text="✅ Создан новый проект")

    def save_project(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".tkdesign",
            filetypes=[("TkDesign files", "*.tkdesign")]
        )
        if filename:
            data = {
                'widgets': [w.to_dict() for w in self.widgets],
                'events': self.event_system.events
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Сохранение", "✅ Проект сохранен!")
            self.status_bar.config(text=f"💾 Проект сохранен: {filename}")

    def load_project(self):
        filename = filedialog.askopenfilename(
            filetypes=[("TkDesign files", "*.tkdesign")]
        )
        if filename:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.load_project_data(data)
            self.update_info()
            messagebox.showinfo("Загрузка", "✅ Проект загружен!")
            self.status_bar.config(text=f"📂 Проект загружен: {filename}")

    def load_project_data(self, data):
        self.new_project()
        for wdata in data['widgets']:
            self.add_widget(wdata['type'], wdata['x'], wdata['y'])
            for widget in self.widgets:
                if widget.x == wdata['x'] and widget.y == wdata['y']:
                    widget.properties = wdata.get('properties', {})
        if 'events' in data:
            self.event_system.events = data['events']

    def update_info(self):
        self.info_label.config(text=f"Виджетов: {len(self.widgets)} | Групп: {len(self.groups)}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TkinterDesigner()
    app.run()