import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import copy
import os
from pathlib import Path


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

    def to_dict(self):
        return {
            'type': self.widget_type,
            'x': self.x,
            'y': self.y,
            'properties': self.properties,
            'group_id': self.group_id
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


# ============== ОКНО ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА (ИСПРАВЛЕННОЕ) ==============
class PreviewWindow:
    def __init__(self, parent, designer):
        self.designer = designer
        self.preview = tk.Toplevel(parent)
        self.preview.title("🔍 Предварительный просмотр (Live)")
        self.preview.geometry("900x700")
        self.preview.configure(bg='#f0f0f0')

        toolbar = tk.Frame(self.preview, bg='#2c3e50', height=40)
        toolbar.pack(fill='x')
        tk.Label(toolbar, text="LIVE PREVIEW", bg='#2c3e50', fg='white',
                 font=('Arial', 10, 'bold')).pack(side='left', padx=10)
        tk.Button(toolbar, text="🔄 Обновить", command=self.refresh,
                  bg='#27ae60', fg='white', bd=0, padx=15, pady=5).pack(side='left', padx=5)
        tk.Button(toolbar, text="✕ Закрыть", command=self.preview.destroy,
                  bg='#e74c3c', fg='white', bd=0, padx=15, pady=5).pack(side='right', padx=10)

        self.main_frame = tk.Frame(self.preview, bg='white')
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        self.widget_instances = {}
        self.refresh()
        self.update_preview()

    def refresh(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.widget_instances.clear()
        self.create_widgets()

    def create_widgets(self):
        """Создание виджетов с ВСЕМИ свойствами из дизайнера"""
        for i, w in enumerate(self.designer.widgets):
            wtype = w.widget_type
            x, y = w.x, w.y
            props = w.properties

            # Получаем свойства с значениями по умолчанию
            text = props.get('text', '')
            bg = props.get('bg', '#f0f0f0')
            fg = props.get('fg', '#000000')
            font = props.get('font', 'Arial 10')
            width = props.get('width', 100)
            height = props.get('height', 30)

            if wtype == 'Button':
                btn = tk.Button(self.main_frame, text=text,
                                font=font, bg=bg, fg=fg,
                                padx=10, pady=5)
                btn.place(x=x, y=y, width=width, height=height)
                self.widget_instances[i] = btn
                widget_id = id(w)
                if widget_id in self.designer.event_system.events:
                    if 'click' in self.designer.event_system.events[widget_id]:
                        code = self.designer.event_system.events[widget_id]['click']
                        btn.config(command=lambda c=code: self.execute_code(c))

            elif wtype == 'Label':
                lbl = tk.Label(self.main_frame, text=text,
                               font=font, bg=bg, fg=fg)
                lbl.place(x=x, y=y, width=width, height=height)

            elif wtype == 'Entry':
                entry = tk.Entry(self.main_frame, font=font, bg=bg, fg=fg)
                entry.place(x=x, y=y, width=width, height=height)
                if text:
                    entry.insert(0, text)
                self.widget_instances[i] = entry

            elif wtype == 'Text':
                text_widget = tk.Text(self.main_frame, font=font, bg=bg, fg=fg)
                text_widget.place(x=x, y=y, width=width, height=height)
                if text:
                    text_widget.insert('1.0', text)

            elif wtype == 'Listbox':
                lb = tk.Listbox(self.main_frame, font=font, bg=bg, fg=fg)
                lb.place(x=x, y=y, width=width, height=height)
                items = props.get('items', ['Элемент 1', 'Элемент 2'])
                for item in items:
                    lb.insert(tk.END, item)

            elif wtype == 'Checkbutton':
                chk = tk.Checkbutton(self.main_frame, text=text,
                                     font=font, bg=bg, fg=fg)
                chk.place(x=x, y=y)

            elif wtype == 'Radiobutton':
                rad = tk.Radiobutton(self.main_frame, text=text,
                                     font=font, bg=bg, fg=fg)
                rad.place(x=x, y=y)

            elif wtype == 'Combobox':
                cb = ttk.Combobox(self.main_frame, values=['Опция 1', 'Опция 2'])
                cb.place(x=x, y=y, width=width, height=height)

            elif wtype == 'Frame':
                fr = tk.Frame(self.main_frame, bg=bg)
                fr.place(x=x, y=y, width=width, height=height)

    def update_preview(self):
        self.refresh()
        self.preview.after(1000, self.update_preview)

    def execute_code(self, code):
        try:
            safe_globals = {
                '__builtins__': {'messagebox': __import__('tkinter.messagebox').messagebox, 'print': print},
                'messagebox': __import__('tkinter.messagebox').messagebox
            }
            exec(code, safe_globals)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка в обработчике: {str(e)}")


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

        ttk.Button(main_frame, text="✕ Закрыть", command=self.dialog.destroy).pack(pady=10)

    def login_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 80)
        self.designer.widgets[-1].properties['text'] = "🔐 Вход в систему"
        self.designer.add_widget('Label', 250, 150)
        self.designer.widgets[-1].properties['text'] = "Логин:"
        self.designer.add_widget('Entry', 320, 150)
        self.designer.add_widget('Label', 250, 200)
        self.designer.widgets[-1].properties['text'] = "Пароль:"
        self.designer.add_widget('Entry', 320, 200)
        self.designer.add_widget('Button', 280, 270)
        self.designer.widgets[-1].properties['text'] = "Войти"
        self.dialog.destroy()

    def register_template(self):
        self.designer.new_project()
        self.designer.add_widget('Label', 300, 50)
        self.designer.widgets[-1].properties['text'] = "📝 Регистрация"
        fields = [("Имя:", 250, 110), ("Email:", 250, 160), ("Пароль:", 250, 210)]
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
        settings = ["Уведомления", "Автозапуск", "Темная тема"]
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
        ttk.Button(frame3, text="🔄 По центру H", command=lambda: self.align('center_h')).pack(side='left', padx=5)
        ttk.Button(frame3, text="🔄 По центру V", command=lambda: self.align('center_v')).pack(side='left', padx=5)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        ttk.Label(main_frame, text="Распределение", font=('Arial', 11, 'bold')).pack(pady=(0, 5))
        frame4 = ttk.Frame(main_frame)
        frame4.pack(pady=5)
        ttk.Button(frame4, text="📊 По горизонтали", command=self.distribute_horizontal).pack(side='left', padx=5)
        ttk.Button(frame4, text="📈 По вертикали", command=self.distribute_vertical).pack(side='left', padx=5)

        ttk.Button(main_frame, text="Закрыть", command=self.dialog.destroy).pack(pady=15)

    def get_selected_widgets(self):
        return self.designer.get_selected_widgets()

    def align(self, direction):
        selected = self.get_selected_widgets()
        if not selected:
            messagebox.showinfo("Выравнивание", "Выберите виджеты (Ctrl+клик)")
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
        self.designer.status_bar.config(text=f"Выравнивание: {direction}")

    def distribute_horizontal(self):
        selected = self.get_selected_widgets()
        if len(selected) < 3:
            messagebox.showinfo("Распределение", "Выберите минимум 3 виджета")
            return
        selected.sort(key=lambda w: w.x)
        min_x, max_x = selected[0].x, selected[-1].x
        spacing = (max_x - min_x) / (len(selected) - 1)
        for i, w in enumerate(selected):
            w.x = min_x + spacing * i
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        self.designer.status_bar.config(text="Распределено по горизонтали")

    def distribute_vertical(self):
        selected = self.get_selected_widgets()
        if len(selected) < 3:
            messagebox.showinfo("Распределение", "Выберите минимум 3 виджета")
            return
        selected.sort(key=lambda w: w.y)
        min_y, max_y = selected[0].y, selected[-1].y
        spacing = (max_y - min_y) / (len(selected) - 1)
        for i, w in enumerate(selected):
            w.y = min_y + spacing * i
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)
        self.designer.status_bar.config(text="Распределено по вертикали")


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
        if events:
            event_combo.current(0)

        self.code_text = tk.Text(add_frame, height=5)
        self.code_text.pack(fill='x', pady=(0, 5))
        self.code_text.insert('1.0', 'messagebox.showinfo("Событие", "Виджет активирован")')
        ttk.Button(add_frame, text="➕ Добавить", command=self.add_handler).pack()

        handlers_frame = ttk.LabelFrame(main_frame, text="Обработчики", padding="5")
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
            self.designer.status_bar.config(text=f"Создана группа '{name}'")
            self.designer.undo_manager.add_action(GroupAction(self.designer, group, 'create'))
        self.dialog.destroy()


# ============== ДИАЛОГ ТЕМ ==============
class ThemeDialog:
    def __init__(self, parent, designer):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Темы оформления")
        self.dialog.geometry("400x300")
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

        self.setup_ui()
        self.create_menu()

    def setup_ui(self):
        # Левая панель
        self.toolbar = tk.Frame(self.root, bg='#2c3e50', width=280)
        self.toolbar.pack(side='left', fill='y')
        self.toolbar.pack_propagate(False)

        title = tk.Label(self.toolbar, text="🎨 TKINTER DESIGNER PRO",
                         bg='#2c3e50', fg='white', font=('Arial', 12, 'bold'))
        title.pack(pady=10)

        self.notebook = ttk.Notebook(self.toolbar)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Вкладка виджетов
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

        # Вкладка групп
        groups_frame = ttk.Frame(self.notebook)
        self.notebook.add(groups_frame, text="📦 Группы")
        tk.Button(groups_frame, text="📦 Управление группами", command=self.show_group_dialog,
                  bg='#9b59b6', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)
        tk.Button(groups_frame, text="🔲 Создать группу", command=self.create_group_from_selected,
                  bg='#3498db', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)
        tk.Button(groups_frame, text="🔓 Разгруппировать", command=self.ungroup_selected,
                  bg='#e67e22', fg='white', bd=0, pady=8).pack(fill='x', padx=5, pady=3)

        # Вкладка действий
        actions_frame = ttk.Frame(self.notebook)
        self.notebook.add(actions_frame, text="⚡ Действия")
        actions = [
            ("↩️ Отменить", self.undo_action), ("↪️ Повторить", self.redo_action),
            ("🗑️ Удалить", self.delete_widget), ("⚙️ Свойства", self.edit_properties),
            ("🎯 События", self.edit_events), ("📋 Копировать", self.copy_widget),
            ("📐 Выравнивание", self.show_alignment), ("🎨 Темы", self.show_themes),
            ("📚 Шаблоны", self.show_templates)
        ]
        for text, cmd in actions:
            btn = tk.Button(actions_frame, text=text, bg='#34495e', fg='white',
                            font=('Arial', 10), bd=0, pady=5, command=cmd)
            btn.pack(fill='x', padx=5, pady=2)

        self.info_label = tk.Label(self.toolbar, text="Виджетов: 0 | Групп: 0",
                                   bg='#2c3e50', fg='#95a5a6')
        self.info_label.pack(side='bottom', pady=10)

        # Правая панель
        self.right_panel = tk.Frame(self.root, bg='#ecf0f1', width=300)
        self.right_panel.pack(side='right', fill='y')
        self.right_panel.pack_propagate(False)
        tk.Label(self.right_panel, text="📋 СВОЙСТВА", bg='#ecf0f1',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.properties_frame = tk.Frame(self.right_panel, bg='#ecf0f1')
        self.properties_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Центральная область
        canvas_container = tk.Frame(self.root, bg='white')
        canvas_container.pack(side='left', fill='both', expand=True)

        self.canvas_toolbar = tk.Frame(canvas_container, bg='#bdc3c7', height=40)
        self.canvas_toolbar.pack(fill='x')
        tk.Label(self.canvas_toolbar, text="Рабочая область:", bg='#bdc3c7',
                 font=('Arial', 9, 'bold')).pack(side='left', padx=10)

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
        tk.Button(self.canvas_toolbar, text="🎬 Предпросмотр", command=self.preview,
                  bg='#27ae60', fg='white', bd=0, padx=10).pack(side='left', padx=5)
        tk.Button(self.canvas_toolbar, text="📐 Выравнивание", command=self.show_alignment,
                  bg='#f39c12', fg='white', bd=0, padx=10).pack(side='left', padx=5)

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
        self.canvas.bind('<Control-MouseWheel>', self.on_zoom_wheel)

        self.status_bar = tk.Label(self.root,
                                   text="✅ Готов | Ctrl+колесо - масштаб | Ctrl+клик - мульти-выбор",
                                   bd=1, relief='sunken', bg='#ecf0f1', anchor='w')
        self.status_bar.pack(side='bottom', fill='x')

        self.layout_manager = LayoutManager(self.canvas)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Файл', menu=file_menu)
        file_menu.add_command(label='Новый проект', command=self.new_project, accelerator='Ctrl+N')
        file_menu.add_command(label='Сохранить проект', command=self.save_project, accelerator='Ctrl+S')
        file_menu.add_command(label='Загрузить проект', command=self.load_project, accelerator='Ctrl+O')
        file_menu.add_separator()
        file_menu.add_command(label='Выход', command=self.root.quit, accelerator='Ctrl+Q')

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Правка', menu=edit_menu)
        edit_menu.add_command(label='Отменить', command=self.undo_action, accelerator='Ctrl+Z')
        edit_menu.add_command(label='Повторить', command=self.redo_action, accelerator='Ctrl+Y')
        edit_menu.add_separator()
        edit_menu.add_command(label='Удалить', command=self.delete_widget, accelerator='Del')
        edit_menu.add_command(label='Свойства', command=self.edit_properties, accelerator='F4')
        edit_menu.add_command(label='События', command=self.edit_events, accelerator='F5')
        edit_menu.add_command(label='Копировать', command=self.copy_widget, accelerator='Ctrl+C')
        edit_menu.add_command(label='Выделить все', command=self.select_all, accelerator='Ctrl+A')

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Вид', menu=view_menu)
        view_menu.add_command(label='Выравнивание', command=self.show_alignment)
        view_menu.add_command(label='Сетка', command=self.toggle_grid)
        view_menu.add_command(label='Темы', command=self.show_themes)

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
        self.root.bind('<Control-Shift-L>', lambda e: self.align_selected('left'))
        self.root.bind('<Control-Shift-R>', lambda e: self.align_selected('right'))
        self.root.bind('<Control-Shift-T>', lambda e: self.align_selected('top'))
        self.root.bind('<Control-Shift-B>', lambda e: self.align_selected('bottom'))
        self.root.bind('<Control-Shift-C>', lambda e: self.align_selected('center_h'))

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

    # Зум функции
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

    def on_zoom_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    # Функции тем
    def apply_theme(self, theme):
        self.current_theme = theme
        themes = {
            'light': {'bg': '#ecf0f1', 'fg': '#2c3e50', 'toolbar': '#34495e'},
            'dark': {'bg': '#2c3e50', 'fg': '#ecf0f1', 'toolbar': '#1a2632'},
            'blue': {'bg': '#3498db', 'fg': '#ffffff', 'toolbar': '#2980b9'},
            'green': {'bg': '#27ae60', 'fg': '#ffffff', 'toolbar': '#229954'},
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

    def preview(self):
        if self.widgets:
            PreviewWindow(self.root, self)
            self.status_bar.config(text="🔍 Открыт LIVE предпросмотр")
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
            'height': height,
            'bg': '#f0f0f0',
            'fg': '#000000',
            'font': 'Arial 10'
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

        # Хэндл для изменения размера
        resize_handle = tk.Label(frame, text="◢", bg='#3498db', fg='white', cursor='sizing')
        resize_handle.place(relx=1.0, rely=1.0, anchor='se')
        resize_handle.bind('<Button-1>', lambda e, wi=widget_info: self.start_resize(e, wi))
        resize_handle.bind('<B1-Motion>', lambda e, wi=widget_info: self.on_resize(e, wi))
        resize_handle.bind('<ButtonRelease-1>', lambda e, wi=widget_info: self.end_resize(e, wi))
        widget_info.resize_handle = resize_handle

        action = AddWidgetAction(self, widget_info)
        self.undo_manager.add_action(action)
        self.update_info()
        self.update_properties_panel()

    def start_resize(self, event, widget_info):
        self.resizing_widget = widget_info
        self.resize_start = (event.x_root, event.y_root)
        self.original_size = (widget_info.width, widget_info.height)

    def on_resize(self, event, widget_info):
        if self.resizing_widget == widget_info:
            dx = event.x_root - self.resize_start[0]
            dy = event.y_root - self.resize_start[1]
            new_width = max(50, self.original_size[0] + dx)
            new_height = max(30, self.original_size[1] + dy)
            widget_info.width = new_width
            widget_info.height = new_height
            widget_info.properties['width'] = new_width
            widget_info.properties['height'] = new_height

            # ИСПРАВЛЕНИЕ: Разные виджеты по-разному реагируют на размер
            if hasattr(widget_info.widget_instance, 'config'):
                try:
                    if widget_info.widget_type in ['Entry', 'Text', 'Listbox']:
                        # Для текстовых виджетов используем символы
                        widget_info.widget_instance.config(width=int(new_width / 8), height=int(new_height / 20))
                    else:
                        # Для кнопок и меток
                        widget_info.widget_instance.config(width=int(new_width / 10))
                except:
                    pass

    def end_resize(self, event, widget_info):
        self.resizing_widget = None
        self.resize_start = None

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
            tk.Label(self.properties_frame, text="Используйте выравнивание\nCtrl+Shift+L/R/T/B/C",
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
        if widget_info.widget_instance:
            if 'text' in widget_info.properties:
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
        self.update_properties_panel()
        self.status_bar.config(text="⚙️ Свойства обновлены")

    def on_events_changed(self, event_system):
        self.event_system = event_system
        self.status_bar.config(text="🎯 События обновлены")

    def show_group_dialog(self):
        GroupDialog(self.root, self)

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
            self.status_bar.config(text=f"📦 Создана группа '{group_name}'")
            self.undo_manager.add_action(GroupAction(self, group, 'create'))
            self.update_info()
        elif len(selected) == 1:
            messagebox.showinfo("Группировка", "Выделите минимум 2 виджета (Ctrl+клик)")
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

    def show_alignment(self):
        AlignmentDialog(self.root, self)

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
            self.new_project()
            for wdata in data['widgets']:
                self.add_widget(wdata['type'], wdata['x'], wdata['y'])
            for widget in self.widgets:
                if widget.x == wdata['x'] and widget.y == wdata['y']:
                    widget.properties = wdata.get('properties', {})
            if 'events' in data:
                self.event_system.events = data['events']
            self.update_info()
            messagebox.showinfo("Загрузка", "✅ Проект загружен!")
            self.status_bar.config(text=f"📂 Проект загружен: {filename}")

    def update_info(self):
        self.info_label.config(text=f"Виджетов: {len(self.widgets)} | Групп: {len(self.groups)}")

    def run(self):
        self.root.mainloop()


# ============== ЗАПУСК ==============
if __name__ == "__main__":
    app = TkinterDesigner()
    app.run()