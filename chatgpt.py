#!/usr/bin/env python3
# -*- coding: utf‑8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import copy
import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. КЛАСС ДЛЯ ХРАНЕНИЯ ИНФОРМАЦИИ О ВИДЖЕТЕ
# --------------------------------------------------------------------------- #
class WidgetInfo:
    def __init__(self, widget_type, x, y, properties=None):
        self.widget_type = widget_type     # имя класса виджета (Button, Label…)
        self.x = x                         # координата x
        self.y = y                         # координата y
        self.width  = properties.get('width', 100) if properties else 100
        self.height = properties.get('height', 30) if properties else 30
        self.properties = properties or {}   # словарь пользовательских свойств
        self.widget_ref = None              # frame‑обёртка
        self.canvas_id  = None              # id окна canvas
        self.widget_instance = None        # сам виджет (Button, Label…)
        self.id = id(self)                  # идентификатор объекта
        self.group_id = None                # id группы, если виджет в группе
        self.resize_handle = None          # виджет‑ручка ресайза

    def to_dict(self):
        return {
            'type': self.widget_type,
            'x': self.x,
            'y': self.y,
            'properties': self.properties,
            'group_id': self.group_id
        }

# --------------------------------------------------------------------------- #
# 2. СИСТЕМА СОБЫТИЙ
# --------------------------------------------------------------------------- #
class EventSystem:
    def __init__(self):
        self.events = {}   # {widget_id: {event: code}}
        self.available_events = {
            'Button': ['click', 'enter', 'leave'],
            'Entry': ['focus_in', 'focus_out', 'key_press'],
            'Text': ['focus_in', 'focus_out'],
            'Listbox': ['select', 'double_click'],
            'Checkbutton': ['click'],
            'Radiobutton': ['click'],
            'Combobox': ['change']
        }

    def add_event(self, widget_id, event_type, handler_code):
        self.events.setdefault(widget_id, {})[event_type] = handler_code

    def remove_event(self, widget_id, event_type):
        if widget_id in self.events and event_type in self.events[widget_id]:
            del self.events[widget_id][event_type]

    def get_handler(self, widget_id, event_type):
        return self.events.get(widget_id, {}).get(event_type, '')

# --------------------------------------------------------------------------- #
# 3. ГРУППЫ ВИДЖЕТОВ
# --------------------------------------------------------------------------- #
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

# --------------------------------------------------------------------------- #
# 4. НАВИГАЦИЯ ВЫВОДА И КУРСОР НА СЕТКЕ
# --------------------------------------------------------------------------- #
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

# --------------------------------------------------------------------------- #
# 5. ДЕРЕК КОНТРОЛЬ МАССИВОВ ОТМЕНЫ/ПОВТОРА
# --------------------------------------------------------------------------- #
class UndoRedoManager:
    def __init__(self, max_history=50):
        self.undo_stack, self.redo_stack = [], []
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


# --------------------------------------------------------------------------- #
# 6. ОПРЕДЕЛЕНИЯ ДЕЙСТВИЙ (для керонтёра UNDO/REDO)
# --------------------------------------------------------------------------- #
class AddWidgetAction:
    def __init__(self, designer, widget_info): self.designer, self.wi = designer, widget_info
    def undo(self):  self.designer.delete_widget_by_info(self.wi)
    def redo(self):  self.designer.restore_widget(self.wi)

class DeleteWidgetAction:
    def __init__(self, designer, widget_info): self.designer, self.wi = designer, copy.deepcopy(widget_info)
    def undo(self):  self.designer.restore_widget(self.wi)
    def redo(self):  self.designer.delete_widget_by_info(self.wi)

class MoveWidgetAction:
    def __init__(self, designer, widget, old_x, old_y, new_x, new_y):
        self.designer, self.wi = designer, widget
        self.old_x, self.old_y, self.new_x, self.new_y = old_x, old_y, new_x, new_y
    def undo(self):
        self.wi.x, self.wi.y = self.old_x, self.old_y
        self.designer.canvas.coords(self.wi.canvas_id, self.old_x, self.old_y)
        self.designer.update_properties_panel()
    def redo(self):
        self.wi.x, self.wi.y = self.new_x, self.new_y
        self.designer.canvas.coords(self.wi.canvas_id, self.new_x, self.new_y)
        self.designer.update_properties_panel()

class GroupAction:
    def __init__(self, designer, group, action_type):
        self.designer, self.group, self.action_type = designer, group, action_type
    def undo(self):
        if self.action_type == 'create':
            for w in self.group.widgets:
                w.group_id = None
                if w.widget_ref: w.widget_ref.config(bg='#3498db')
            if self.group in self.designer.groups:
                self.designer.groups.remove(self.group)
        else:  # delete
            self.designer.groups.append(self.group)
            for w in self.group.widgets:
                w.group_id = self.group.group_id
                if w.widget_ref: w.widget_ref.config(bg='#9b59b6')
    def redo(self):
        if self.action_type == 'create':
            self.designer.groups.append(self.group)
            for w in self.group.widgets:
                w.group_id = self.group.group_id
                if w.widget_ref: w.widget_ref.config(bg='#9b59b6')
        else:
            for w in self.group.widgets:
                w.group_id = None
                if w.widget_ref: w.widget_ref.config(bg='#3498db')
            if self.group in self.designer.groups:
                self.designer.groups.remove(self.group)

# --------------------------------------------------------------------------- #
# 7. РЕШАТЬ ДРАГ – ДРАГ
# --------------------------------------------------------------------------- #
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
            for g in self.designer.groups:
                if g.group_id == widget_info.group_id:
                    self.dragged_widgets = g.widgets.copy()
                    break
        else:
            self.dragged_widgets = [widget_info]
        self.start_positions = [(w, w.x, w.y) for w in self.dragged_widgets]

    def on_drag(self, event):
        if not self.drag_start: return
        dx, dy = event.x_root - self.drag_start[0], event.y_root - self.drag_start[1]
        for w, ox, oy in self.start_positions:
            new_x, new_y = ox+dx, oy+dy
            if self.designer.layout_manager.snap_to_grid:
                new_x, new_y = (round(new_x/self.designer.layout_manager.grid_size)*self.designer.layout_manager.grid_size,
                                round(new_y/self.designer.layout_manager.grid_size)*self.designer.layout_manager.grid_size)
            w.x, w.y = new_x, new_y
            self.designer.canvas.coords(w.canvas_id, new_x, new_y)
        if len(self.dragged_widgets)==1:
            self.designer.update_properties_panel()

    def end_drag(self):
        if self.drag_start and self.start_positions:
            for w, ox, oy in self.start_positions:
                if w.x!=ox or w.y!=oy:
                    act = MoveWidgetAction(self.designer, w, ox, oy, w.x, w.y)
                    self.designer.undo_manager.add_action(act)
        self.drag_start = None
        self.dragged_widgets = []
        self.start_positions = []

# --------------------------------------------------------------------------- #
# 8. ПРИМЕР ПЕРЕСМОТРА (LIVE)
# --------------------------------------------------------------------------- #
class PreviewWindow:
    def __init__(self, parent, designer):
        self.designer = designer
        self.win = tk.Toplevel(parent)
        self.win.title("🔍 LIVE–PREVIEW")
        self.win.geometry("900x700")
        self.win.configure(bg="#f0f0f0")
        toolbar = tk.Frame(self.win, bg="#2c3e50", height=40)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="LIVE PREVIEW - ОБНОВЛЯЕТСЯ АВТОМАТИЧЕСКИ",
                 bg="#2c3e50", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        tk.Button(toolbar, text="🔄 Обновить", command=self.refresh,
                 bg="#27ae60", fg="white").pack(side="left", padx=5)
        tk.Button(toolbar, text="✕ Закрыть", command=self.win.destroy,
                 bg="#e74c3c", fg="white").pack(side="right", padx=10)

        self.main = tk.Frame(self.win, bg="white")
        self.main.pack(fill="both", expand=True, padx=20, pady=20)
        self.refresh()
        self.update_preview()

    def refresh(self):
        for w in self.main.winfo_children():
            w.destroy()
        self.create_widgets()

    def create_widgets(self):
        for i, w in enumerate(self.designer.widgets):
            props = w.properties
            if w.widget_type=="Button":
                btn = tk.Button(self.main, text=props.get("text","Кнопка"), font=("Arial",10),
                                padx=10, pady=5)
                btn.place(x=w.x, y=w.y)
                wid = id(w)
                if wid in self.designer.event_system.events and \
                   "click" in self.designer.event_system.events[wid]:
                    code = self.designer.event_system.events[wid]["click"]
                    btn.config(command=lambda c=code: self.exec_code(c))
            elif w.widget_type=="Label":
                tk.Label(self.main, text=props.get("text","Метка"), font=("Arial",10)
                       ).place(x=w.x, y=w.y)
            elif w.widget_type=="Entry":
                ent = tk.Entry(self.main, font=("Arial",10), width=20)
                ent.place(x=w.x, y=w.y)
            elif w.widget_type=="Text":
                txt = tk.Text(self.main, height=5, width=30, font=("Arial",10))
                txt.place(x=w.x, y=w.y)
                txt.insert("1.0","")  # пустой текст уже в проперти
            elif w.widget_type=="Listbox":
                lb = tk.Listbox(self.main, height=5, width=30, font=("Arial",10))
                lb.place(x=w.x, y=w.y)
            elif w.widget_type=="Checkbutton":
                cb = tk.Checkbutton(self.main, text=props.get("text","Флажок"),
                                    font=("Arial",10))
                cb.place(x=w.x, y=w.y)
            elif w.widget_type=="Radiobutton":
                rb = tk.Radiobutton(self.main, text=props.get("text","Радио"),
                                    font=("Arial",10))
                rb.place(x=w.x, y=w.y)

    def update_preview(self):
        self.refresh()
        self.win.after(1000, self.update_preview)

    def exec_code(self, code):
        # ограниченный набор глобальных функций
        globs = {"messagebox": __import__("tkinter.messagebox").messagebox,
                 "print": print}
        try:
            exec(code, globs)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка в обработчике: {e}")

# --------------------------------------------------------------------------- #
# 9. БИБЛИОТЕКА ШАБЛОНОВ (8 готовых)
# --------------------------------------------------------------------------- #
class TemplateLibrary:
    def __init__(self, parent, designer):
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("📚 Библиотека шаблонов")
        self.dlg.geometry("650x550")
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        frm = ttk.Frame(self.dlg, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="📚 БАЗИОН ШАБЛОНОВ", font=("Arial",14,"bold")).pack(pady=10)
        tf = ttk.Frame(frm)
        tf.pack(fill="both", expand=True, pady=10)
        templates = [("🔐 Форма входа", self.login),
                     ("📝 Регистрация", self.register),
                     ("🧮 Калькулятор", self.calculator),
                     ("💬 Чат", self.chat),
                     ("⚙️ Настройки", self.settings),
                     ("📊 Дашборд", self.dashboard),
                     ("🔍 Поиск", self.search),
                     ("📧 Контакты", self.contacts)]
        r,c=0,0
        for name, func in templates:
            btn = tk.Button(tf, text=name, command=func,
                           bg="#3498db", fg="white", font=("Arial",10,"bold"),
                           width=20, height=3, bd=0, cursor="hand2")
            btn.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
            c+=1
            if c>1:
                c=0; r+=1
        tf.grid_columnconfigure(0, weight=1)
        tf.grid_columnconfigure(1, weight=1)
        ttk.Button(frm, text="✕ Закрыть", command=self.dlg.destroy).pack(pady=10)

    def login(self):   self.designer.new_project(); self.designer.add_widgets_by_script([("Label",300,80,"🔐 Вход в систему"),
                                      ("Label",250,150,"Логин:"),("Entry",320,150),
                                      ("Label",250,200,"Пароль:"),("Entry",320,200),
                                      ("Button",280,270,"Войти"),("Button",380,270,"Отмена")])

    def register(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Label",300,50,"📝 Регистрация"),
                                      ("Label",250,110,"Имя:"),("Entry",330,110),
                                      ("Label",250,160,"Email:"),("Entry",330,160),
                                      ("Label",250,210,"Пароль:"),("Entry",330,210),
                                      ("Label",250,260,"Подтвердить:"),("Entry",330,260),
                                      ("Button",320,330,"Зарегистрироваться")])

    def calculator(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Entry",200,80,{"width":200}),
                                      ("Button",200,130,"7"),("Button",250,130,"8"),
                                      ("Button",300,130,"9"),("Button",350,130,"/"),
                                      ("Button",200,180,"4"),("Button",250,180,"5"),
                                      ("Button",300,180,"6"),("Button",350,180,"*"),
                                      ("Button",200,230,"1"),("Button",250,230,"2"),
                                      ("Button",300,230,"3"),("Button",350,230,"-"),
                                      ("Button",200,280,"0"),("Button",250,280,"."),("Button",300,280,"="),
                                      ("Button",350,280,"+")])
    def chat(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Text",200,50,{"width":300,"height":200}),
                           ("Entry",200,270,{"width":250}),
                           ("Button",460,270,"Отправить")])
    def settings(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Label",300,50,"⚙️ Настройки"),
                      ("Checkbutton",250,100,"Уведомления"),("Checkbutton",250,140,"Автозапуск"),
                      ("Checkbutton",250,180,"Темная тема"),("Checkbutton",250,220,"Звуки"),
                      ("Button",320,260,"Сохранить")])
    def dashboard(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Label",300,50,"📊 Дашборд"),
                      ("Button",250,120,"Статистика"),("Button",250,180,"Графики"),
                      ("Button",250,240,"Отчеты")])
    def search(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Entry",250,80,{"width":200}),
                      ("Button",460,80,"🔍 Найти"),("Listbox",250,130,{"width":250,"height":150})])
    def contacts(self): self.designer.new_project(); self.designer.add_widgets_by_script([("Label",300,50,"📧 Контакты"),
                      ("Button",250,100,"Иван Иванов"),("Button",250,150,"Петр Петров"),
                      ("Button",250,200,"Мария Сидорова")])

# --------------------------------------------------------------------------- #
# 10. ДИАЛОГ ВЫРАВНИВАНИЯ
# --------------------------------------------------------------------------- #
class AlignmentDialog:
    def __init__(self, parent, designer):
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("Выравнивание виджетов")
        self.dlg.geometry("400x380")
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.designer = designer
        self.setup_ui()

    def setup_ui(self):
        frm = ttk.Frame(self.dlg, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Выравнивание", font=("Arial",12,"bold")).pack(pady=5)
        tb1 = ttk.Frame(frm); tb1.pack(pady=5)
        ttk.Button(tb1, text="⬅ По левому краю", command=lambda: self.align("left")).pack(side="left", padx=3)
        ttk.Button(tb1, text="➡ По правому краю", command=lambda: self.align("right")).pack(side="left", padx=3)
        tb2 = ttk.Frame(frm); tb2.pack(pady=5)
        ttk.Button(tb2, text="⬆ По верхнему краю", command=lambda: self.align("top")).pack(side="left", padx=3)
        ttk.Button(tb2, text="⬇ По нижнему краю", command=lambda: self.align("bottom")).pack(side="left", padx=3)
        tb3 = ttk.Frame(frm); tb3.pack(pady=5)
        ttk.Button(tb3, text="🔄 По центру (гориз.)", command=lambda: self.align("center_h")).pack(side="left", padx=3)
        ttk.Button(tb3, text="🔄 По центру (верт.)", command=lambda: self.align("center_v")).pack(side="left", padx=3)
        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(frm, text="Распределение", font=("Arial",11,"bold")).pack(pady=5)
        tb4 = ttk.Frame(frm); tb4.pack(pady=5)
        ttk.Button(tb4, text="📊 По горизонтали", command=self.distribute_h).pack(side="left", padx=3)
        ttk.Button(tb4, text="📈 По вертикали", command=self.distribute_v).pack(side="left", padx=3)
        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(frm, text="Интервалы", font=("Arial",11,"bold")).pack(pady=5)
        ic = ttk.Frame(frm); ic.pack(pady=5)
        ttk.Label(ic, text="Отступ:").pack(side="left")
        self.sp = tk.StringVar(value="20")
        ttk.Entry(ic, textvariable=self.sp, width=5).pack(side="left", padx=3)
        ttk.Button(ic, text="Выровнять", command=self.spacing).pack(side="left", padx=3)
        ttk.Button(frm, text="Закрыть", command=self.dlg.destroy).pack(pady=10)

    def get_selected(self): return self.designer.get_selected_widgets()
    def align(self, dir):
        sel = self.get_selected_widgets()
        if not sel:
            messagebox.showinfo("Выравнивание", "Выберите виджеты (Ctrl+клик)")
            return

        if dir == "left":
            minx = min(w.x for w in sel)
            for w in sel:
                w.x = minx
        elif dir == "right":
            maxx = max(w.x + w.width for w in sel)
            for w in sel:
                w.x = maxx - w.width
        elif dir == "top":
            mint = min(w.y for w in sel)
            for w in sel:
                w.y = mint
        elif dir == "bottom":
            maxy = max(w.y + w.height for w in sel)
            for w in sel:
                w.y = maxy - w.height
        elif dir == "center_h":
            cx = sum(w.x + w.width / 2 for w in sel) / len(sel)
            for w in sel:
                w.x = cx - w.width / 2
        elif dir == "center_v":
            cy = sum(w.y + w.height / 2 for w in sel) / len(sel)
            for w in sel:
                w.y = cy - w.height / 2

        for w in sel:
            self.designer.canvas.coords(w.canvas_id, w.x, w.y)

        self.designer.update_properties_panel()
        self.designer.status_bar.config(
            text=f"Выравнивание: {dir} ({len(sel)} виджетов)"
        )


    def distribute_h(self):
        sel=self.get_selected(); N=len(sel)
        if N<3: return messagebox.showinfo("Распределение","Мин. 3 виджета")
        sel.sort(key=lambda w:w.x); mn, mx=sel[0].x, sel[-1].x
        step=(mx-mn)/(N-1)
        [setattr(w,"x",mn+i*step); self.designer.canvas.coords(w.canvas_id,w.x,w.y) for i,w in enumerate(sel)]
        self.designer.status_bar.config(text=f"Гориз. разметка {N}")

    def distribute_v(self):
        sel=self.get_selected(); N=len(sel)
        if N<3: return messagebox.showinfo("Распределение","Мин. 3 виджета")
        sel.sort(key=lambda w:w.y); mn, mx=sel[0].y, sel[-1].y
        step=(mx-mn)/(N-1)
        [setattr(w,"y",mn+i*step); self.designer.canvas.coords(w.canvas_id,w.x,w.y) for i,w in enumerate(sel)]
        self.designer.status_bar.config(text=f"Вертик. разметка {N}")

    def spacing(self):
        try: s=int(self.sp.get())
        except: s=20
        sel=self.get_selected(); sel.sort(key=lambda w:w.x)
        if len(sel)<2: return messagebox.showinfo("Интервалы","Мин. 2 виджета")
        [setattr(sel[i], "x", sel[i-1].x + sel[i-1].width + s) for i in range(1,len(sel))]
        [self.designer.canvas.coords(w.canvas_id,w.x,w.y) for w in sel]
        self.designer.status_bar.config(text=f"Интервалы {s}px")

# --------------------------------------------------------------------------- #
# 11. ДИАЛОГ СВОЙСТВ
# --------------------------------------------------------------------------- #
class PropertiesDialog:
    def __init__(self, parent, widget, callback):
        self.win = tk.Toplevel(parent)
        self.win.title(f"Свойства - {widget.widget_type}")
        self.win.geometry("450x420")
        self.win.transient(parent)
        self.win.grab_set()
        self.widget = widget
        self.callback = callback
        self.props = dict(widget.properties)  # клонируем
        self.create_ui()

    def create_ui(self):
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ----- основной блок -----
        main = ttk.Frame(nb)
        nb.add(main, text="Основное")
        r=0
        if self.widget.widget_type in ["Button","Label"]:
            ttk.Label(main, text="Текст:").grid(row=r, column=0, sticky="w", pady=4)
            self.tvar=ttk.Entry(main); self.tvar.insert(0,self.props.get("text","")); self.tvar.grid(row=r,column=1,columnspan=2,sticky="ew",pady=4); r+=1
        ttk.Label(main, text="Ширина:").grid(row=r,column=0,sticky="w",pady=4)
        self.wvar=ttk.Entry(main); self.wvar.insert(0,self.props.get("width","100")); self.wvar.grid(row=r,column=1,sticky="ew",pady=4); r+=1
        ttk.Label(main, text="Высота:").grid(row=r,column=0,sticky="w",pady=4)
        self.hvar=ttk.Entry(main); self.hvar.insert(0,self.props.get("height","30")); self.hvar.grid(row=r,column=1,sticky="ew",pady=4); r+=1

        # ----- внешний вид -----
        vis = ttk.Frame(nb)
        nb.add(vis, text="Внешний вид")
        ttk.Label(vis, text="Цвет фона:").grid(row=0, column=0, sticky="w", pady=4)
        self.bgvar=tk.StringVar(self.props.get("bg","#f0f0f0"))
        ttk.Entry(vis, textvariable=self.bgvar, width=8).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Button(vis, text="Выбрать", command=lambda:self.pick_color(self.bgvar)).grid(row=0, column=2, padx=3)
        ttk.Label(vis, text="Цвет текста:").grid(row=1, column=0, sticky="w", pady=4)
        self.fgvar=tk.StringVar(self.props.get("fg","black"))
        ttk.Entry(vis, textvariable=self.fgvar, width=8).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Button(vis, text="Выбрать", command=lambda:self.pick_color(self.fgvar)).grid(row=1, column=2, padx=3)
        ttk.Label(vis, text="Шрифт:").grid(row=2, column=0, sticky="w", pady=4)
        self.fvar=tk.StringVar(self.props.get("font","Arial 10"))
        ttk.Entry(vis, textvariable=self.fvar, width=15).grid(row=2, column=1, columnspan=2, sticky="w", padx=2)

        # ---- кнопки ----
        btns = ttk.Frame(self.win)
        btns.pack(pady=10)
        ttk.Button(btns, text="Применить", command=self.apply).pack(side="left", padx=3)
        ttk.Button(btns, text="Отмена", command=self.win.destroy).pack(side="left", padx=3)

    def pick_color(self, var):
        clr = colorchooser.askcolor(color=var.get())[1]
        if clr: var.set(clr)

    def apply(self):
        self.props["text"]=self.tvar.get() if self.widget.widget_type in ["Button","Label"] else ""
        self.props["width"]=int(self.wvar.get())
        self.props["height"]=int(self.hvar.get())
        self.props["bg"]=self.bgvar.get()
        self.props["fg"]=self.fgvar.get()
        self.props["font"]=self.fvar.get()
        self.widget.properties=self.props
        # обновляем виджет
        if self.widget.widget_instance:
            self.widget.widget_instance.config(text=self.props.get("text",""),
                                               width=int(self.props.get("width",100)/10 if hasattr(self.widget.widget_instance,"config") else None),
                                               height=int(self.props.get("height",30)/10 if hasattr(self.widget.widget_instance,"config") else None),
                                               bg=self.props.get("bg","#f0f0f0"),
                                               fg=self.props.get("fg","black"),
                                               font=self.props.get("font","Arial 10"))
        self.callback(self.widget)
        self.win.destroy()

# --------------------------------------------------------------------------- #
# 12. ДИАЛОГ СОБЫТИЙ
# --------------------------------------------------------------------------- #
class EventDialog:
    def __init__(self, parent, widget, evt_syst, callback):
        self.win = tk.Toplevel(parent)
        self.win.title(f"События - {widget.widget_type}")
        self.win.geometry("550x460")
        self.win.transient(parent)
        self.win.grab_set()
        self.widget, self.evt_syst, self.callback = widget, evt_syst, callback
        self.wid = id(widget)
        self.create_ui()

    def create_ui(self):
        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Тип: {self.widget.widget_type}").pack(anchor="w")
        ttk.Label(frm, text="Добавление обработчика").pack(anchor="w", pady=2)

        self.event_combo = ttk.Combobox(frm, state="readonly",
                                        values=self.evt_syst.available_events.get(self.widget.widget_type, ["click"]))
        self.event_combo.pack(fill="x", pady=2); self.event_combo.current(0)

        ttk.Label(frm, text="Код:").pack(anchor="w")
        self.code_txt = tk.Text(frm, height=6)
        self.code_txt.pack(fill="x", pady=2)
        self.code_txt.insert("1.0", 'messagebox.showinfo("Событие", "Виджет активирован")')
        ttk.Button(frm, text="Добавить", command=self.add_handler).pack(pady=2)

        # список существующих обработчиков
        tk.Label(frm, text="Обработчики:").pack(anchor="w", pady=2)
        self.listbox = tk.Listbox(frm, height=4)
        self.listbox.pack(fill="x", pady=2)
        self.refresh_handlers()
        ttk.Button(frm, text="Удалить", command=self.del_handler).pack(pady=2)

        ttk.Button(frm, text="Сохранить", command=self.save).pack(side="right", padx=5)

    def refresh_handlers(self):
        self.listbox.delete(0, tk.END)
        if self.wid in self.evt_syst.events:
            for ev, code in self.evt_syst.events[self.wid].items():
                self.listbox.insert(tk.END, f"{ev}: {code[:40]}...")

    def add_handler(self):
        ev = self.event_combo.get()
        code = self.code_txt.get("1.0", "end-1c")
        if ev and code:
            self.evt_syst.add_event(self.wid, ev, code)
            self.refresh_handlers()
            self.code_txt.delete("1.0", "end")

    def del_handler(self):
        sel = self.listbox.curselection()
        if sel:
            item=self.listbox.get(sel[0])
            ev=item.split(":")[0]
            self.evt_syst.remove_event(self.wid, ev)
            self.refresh_handlers()

    def save(self):
        self.callback(self.evt_syst)
        self.win.destroy()

# --------------------------------------------------------------------------- #
# 13. ДИАЛОГ ГРОППИРОВКИ
# --------------------------------------------------------------------------- #
class GroupDialog:
    def __init__(self, parent, designer):
        self.win = tk.Toplevel(parent)
        self.win.title("Управление группами")
        self.win.geometry("500x400")
        self.win.transient(parent)
        self.win.grab_set()
        self.designer = designer
        self.create_ui()

    def create_ui(self):
        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Создать группу").pack(anchor="w")
        self.gname = ttk.Entry(frm); self.gname.pack(fill="x", pady=3)
        ttk.Button(frm, text="Создать", command=self.create).pack(pady=3)
        ttk.Label(frm, text="Выделите виджеты").pack(anchor="w", pady=5)
        self.lst = tk.Listbox(frm, selectmode="multiple")
        self.lst.pack(fill="both", expand=True)
        for i,w in enumerate(self.designer.widgets):
            self.lst.insert(tk.END, f"{i+1}. {w.widget_type} ({w.x},{w.y})")
        ttk.Button(frm, text="Закрыть", command=self.win.destroy).pack(pady=5)

    def create(self):
        name=self.gname.get() or f"Группа {len(self.designer.groups)+1}"
        idx=self.lst.curselection()
        if not idx: messagebox.showwarning("Ошибка", "Нет выбранных виджетов")
        else:
            g=WidgetGroup(len(self.designer.groups)+1, name)
            for i in idx:
                w=self.designer.widgets[i]
                g.add_widget(w)
                w.widget_ref.config(bg="#9b59b6")
            self.designer.groups.append(g)
            self.designer.undo_manager.add_action(GroupAction(self.designer,g,'create'))
            self.win.destroy()

# --------------------------------------------------------------------------- #
# 14. ДИАЛОГ ТЕМ
# --------------------------------------------------------------------------- #
class ThemeDialog:
    def __init__(self, parent, designer):
        self.win = tk.Toplevel(parent)
        self.win.title("Темы оформления")
        self.win.geometry("400x300")
        self.win.transient(parent)
        self.win.grab_set()
        self.designer = designer
        self.create_ui()

    def create_ui(self):
        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Выберите тему").pack(pady=5)
        themes=[("Светлая","light"),("Темная","dark"),("Синяя","blue"),
                ("Зеленая","green"),("Оранжевая","orange"),("Фиолетовая","purple")]
        for name, key in themes:
            ttk.Button(frm,text=name,command=lambda k=key:self.apply(k)).pack(fill="x", pady=2)
        ttk.Button(frm,text="Закрыть",command=self.win.destroy).pack(pady=10)

    def apply(self, key):
        self.designer.apply_theme(key)
        self.win.destroy()

# --------------------------------------------------------------------------- #
# 15. ОСНОВНОЙ КЛАСС КОНСТРУКТОРА
# --------------------------------------------------------------------------- #
class TkinterDesigner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Tkinter Designer Pro")
        self.root.geometry("1500x850")
        self.widgets = []
        self.selected_widget = None
        self.placing_widget = None
        self.event_system = EventSystem()
        self.groups = []
        self.zoom_level = 1.0
        self.resizing = None
        self.res_start = None
        self.undo_manager = UndoRedoManager()
        self.drag_drop = DragDropManager(self)
        self.current_theme = "light"

        self.setup_ui()
        self.create_menu()

    # ---------- UI ---------- #
    def setup_ui(self):
        # 1. Левая панель с иконками‑кнопками
        toolbar = tk.Frame(self.root, bg="#2c3e50", width=260)
        toolbar.pack(side="left", fill="y")
        toolbar.pack_propagate(False)
        ttk.Label(toolbar, text="🎨 TKINTER DESIGNER PRO",
                  bg="#2c3e50", fg="white", font=("Arial", 12, "bold")).pack(pady=10)

        notebook = ttk.Notebook(toolbar)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # виджеты
        wframe = ttk.Frame(notebook); notebook.add(wframe, text="🔘 Виджеты")
        btns=[("🔘 Кнопка", "Button"),("📝 Метка","Label"),("✏️ Поле","Entry"),
              ("📄 Текст","Text"),("📋 Список","Listbox"),
              ("✅ Флажок","Checkbutton"),("🔘 Радио","Radiobutton"),
              ("📊 Комбо","Combobox"),("📦 Фрейм","Frame")]
        for lab, typ in btns:
            btn=tk.Button(wframe, text=lab, bg="#34495e", fg="white",
                           font=("Arial",10), bd=0, pady=8,
                           command=lambda t=typ:self.start_place_widget(t))
            btn.pack(fill="x", padx=5, pady=3)

        # группы
        gframe=ttk.Frame(notebook); notebook.add(gframe, text="📦 Группы")
        ttk.Button(gframe, text="📦 Управление группами", command=self.show_group_dialog,
                  bg="#9b59b6", fg="white", bd=0, pady=8).pack(fill="x", padx=5, pady=3)
        ttk.Button(gframe, text="🔲 Создать группу", command=self.create_group_from_selected,
                  bg="#3498db", fg="white", bd=0, pady=8).pack(fill="x", padx=5, pady=3)
        ttk.Button(gframe, text="🔓 Разгруппировать", command=self.ungroup_selected,
                  bg="#e67e22", fg="white", bd=0, pady=8).pack(fill="x", padx=5, pady=3)

        # действия
        aframe = ttk.Frame(notebook); notebook.add(aframe, text="⚡ Действия")
        actions = [("↩️ Отменить", self.undo_action), ("↪️ Повторить", self.redo_action),
                   ("🗑️ Удалить", self.delete_widget), ("⚙️ Свойства", self.edit_properties),
                   ("🎯 События", self.edit_events), ("📋 Копировать", self.copy_widget),
                   ("📐 Выравнивание", self.show_alignment), ("🎨 Темы", self.show_themes),
                   ("📚 Шаблоны", self.show_templates)]
        for txt, cmd in actions:
            tk.Button(aframe, text=txt, bg="#34495e", fg="white",
                      font=("Arial",10), bd=0, pady=5, command=cmd).pack(fill="x", padx=5, pady=2)

        self.infobar = tk.Label(toolbar, text="Виджетов: 0 | Групп: 0",
                                bg="#2c3e50", fg="#95a5a6")
        self.infobar.pack(side="bottom", pady=10)

        # правая панель
        right = tk.Frame(self.root, bg="#ecf0f1", width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        ttk.Label(right, text="📋 СВОЙСТВА",
                  bg="#ecf0f1", font=("Arial",10,"bold")).pack(pady=5)
        self.prop_frame = tk.Frame(right, bg="#ecf0f1")
        self.prop_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # центральная область
        canvas_container = tk.Frame(self.root, bg="white")
        canvas_container.pack(side="left", fill="both", expand=True)
        self.canvas_toolbar = tk.Frame(canvas_container, bg="#bdc3c7", height=40)
        self.canvas_toolbar.pack(fill="x")

        tk.Label(self.canvas_toolbar, text="Рабочая область:", bg="#bdc3c7",
                 font=("Arial",9,"bold")).pack(side="left", padx=10)

        # зум
        tk.Button(self.canvas_toolbar, text="🔍 +", command=self.zoom_in,
                  bg="#95a5a6", bd=0, padx=10).pack(side="left", padx=2)
        tk.Button(self.canvas_toolbar, text="🔍 -", command=self.zoom_out,
                  bg="#95a5a6", bd=0, padx=10).pack(side="left", padx=2)
        tk.Button(self.canvas_toolbar, text="🔍 1:1", command=self.zoom_reset,
                  bg="#95a5a6", bd=0, padx=10).pack(side="left", padx=2)

        self.zoom_lbl = tk.Label(self.canvas_toolbar, text="100%", bg="#bdc3c7")
        self.zoom_lbl.pack(side="left", padx=3)

        # сетка, preview, alignment, themes
        tk.Button(self.canvas_toolbar, text="📐 Сетка", command=self.toggle_grid,
                  bg="#95a5a6", bd=0, padx=10).pack(side="left", padx=5)
        tk.Button(self.canvas_toolbar, text="🎬 Предпросмотр", command=self.preview,
                  bg="#27ae60", fg="white", bd=0, padx=10).pack(side="left", padx=5)
        tk.Button(self.canvas_toolbar, text="📐 Выравнивание", command=self.show_alignment,
                  bg="#f39c12", fg="white", bd=0, padx=10).pack(side="left", padx=5)
        tk.Button(self.canvas_toolbar, text="🎨 Темы", command=self.show_themes,
                  bg="#9b59b6", fg="white", bd=0, padx=10).pack(side="left", padx=5)

        # canvas
        vsb = tk.Scrollbar(canvas_container, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = tk.Scrollbar(canvas_container, orient="horizontal")
        hsb.pack(side="bottom", fill="x")
        self.canvas = tk.Canvas(canvas_container, bg="white",
                                yscrollcommand=vsb.set,
                                xscrollcommand=hsb.set)
        self.canvas.pack(fill="both", expand=True)
        vsb.config(command=self.canvas.yview)
        hsb.config(command=self.canvas.xview)
        self.canvas.config(scrollregion=(0,0,2000,2000))

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom_wheel)

        self.status_bar = tk.Label(self.root,
            text="✅ Готов | Ctrl+колесо – масштаб | Ctrl+клик – мульти‑выбор | Перетаскивание файлов",
            bd=1, relief="sunken", bg="#ecf0f1", anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

        self.layout_manager = LayoutManager(self.canvas)

    # ---------- меню ---------- #
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        fmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=fmenu)
        fmenu.add_command(label="Новый проект", command=self.new_project, accelerator="Ctrl+N")
        fmenu.add_command(label="Сохранить проект", command=self.save_project, accelerator="Ctrl+S")
        fmenu.add_command(label="Загрузить проект", command=self.load_project, accelerator="Ctrl+O")
        fmenu.add_separator()
        fmenu.add_command(label="Выход", command=self.root.quit, accelerator="Ctrl+Q")

        emenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=emenu)
        emenu.add_command(label="Отменить", command=self.undo_action, accelerator="Ctrl+Z")
        emenu.add_command(label="Повторить", command=self.redo_action, accelerator="Ctrl+Y")
        emenu.add_separator()
        emenu.add_command(label="Удалить", command=self.delete_widget, accelerator="Del")
        emenu.add_command(label="Свойства", command=self.edit_properties, accelerator="F4")
        emenu.add_command(label="События", command=self.edit_events, accelerator="F5")
        emenu.add_command(label="Копировать", command=self.copy_widget, accelerator="Ctrl+C")
        emenu.add_command(label="Выделить все", command=self.select_all, accelerator="Ctrl+A")

        vmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=vmenu)
        vmenu.add_command(label="Выравнивание", command=self.show_alignment)
        vmenu.add_command(label="Сетка", command=self.toggle_grid)
        vmenu.add_command(label="Темы", command=self.show_themes)

        tmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Шаблоны", menu=tmenu)
        tmenu.add_command(label="📚 Библиотека", command=self.show_templates)

        # горячие клавиши
        self.root.bind("<Control-n>", lambda e: self.new_project())
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<Control-o>", lambda e: self.load_project())
        self.root.bind("<Control-z>", lambda e: self.undo_action())
        self.root.bind("<Control-y>", lambda e: self.redo_action())
        self.root.bind("<Delete>", lambda e: self.delete_widget())
        self.root.bind("<F4>", lambda e: self.edit_properties())
        self.root.bind("<F5>", lambda e: self.edit_events())
        self.root.bind("<Control-c>", lambda e: self.copy_widget())
        self.root.bind("<Control-a>", lambda e: self.select_all())

        # горячие клавиши выравнивания
        self.root.bind("<Control-Shift-L>", lambda e: self.align_selected("left"))
        self.root.bind("<Control-Shift-R>", lambda e: self.align_selected("right"))
        self.root.bind("<Control-Shift-T>", lambda e: self.align_selected("top"))
        self.root.bind("<Control-Shift-B>", lambda e: self.align_selected("bottom"))
        self.root.bind("<Control-Shift-C>", lambda e: self.align_selected("center_h"))

    # ---------- размещение ---------- #
    def start_place_widget(self, typ):
        self.placing_widget = typ
        self.canvas.config(cursor="cross")
        self.status_bar.config(text=f"📍 Размещение: {typ} – кликните на холст")

    def on_canvas_click(self, e):
        if self.placing_widget:
            x, y = self.layout_manager.snap(e.x, e.y)
            self.add_widget(self.placing_widget, x, y)
            self.placing_widget = None
            self.canvas.config(cursor="arrow")
            self.status_bar.config(text="✅ Виджет размещен")
        else:
            self.clear_selection()

    def add_widget(self, typ, x, y):
        """Добавление конкретного виджета на canvas"""
        # главное обернутое поле (frame)
        frame = tk.Frame(self.canvas, bg="#3498db", relief="solid", borderwidth=2)

        # конечный виджет
        if typ=="Button":
            w = tk.Button(frame, text="Кнопка", width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 35
        elif typ=="Label":
            w = tk.Label(frame, text="Метка", width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif typ=="Entry":
            w = tk.Entry(frame, width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif typ=="Text":
            w = tk.Text(frame, height=3, width=12)
            w.pack(padx=8, pady=5)
            width, height = 100, 70
        elif typ=="Listbox":
            w = tk.Listbox(frame, height=3, width=12)
            w.insert(1,"Элемент 1"); w.insert(2,"Элемент 2")
            w.pack(padx=8, pady=5)
            width, height = 100, 70
        elif typ=="Checkbutton":
            w = tk.Checkbutton(frame, text="Флажок")
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif typ=="Radiobutton":
            w = tk.Radiobutton(frame, text="Радио")
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif typ=="Combobox":
            w = ttk.Combobox(frame, values=["Опция 1","Опция 2"])
            w.pack(padx=8, pady=5)
            width, height = 100, 30
        elif typ=="Frame":
            w = tk.Frame(frame, bg="#95a5a6", width=100, height=100)
            w.pack()
            width, height = 100, 100
        else:
            return

        props = {"text": w.cget("text") if hasattr(w,"cget") and "text" in w.keys() else "",
                 "width": width, "height": height}
        winfo = WidgetInfo(typ, x, y, props)
        winfo.widget_ref = frame
        winfo.widget_instance = w
        winfo.width, winfo.height = width, height

        cid = self.canvas.create_window(x, y, window=frame, anchor="nw")
        winfo.canvas_id = cid
        self.widgets.append(winfo)

        # обработчики графических событий
        frame.bind("<Button-1>", lambda e, wi=winfo: self.on_widget_click(e, wi))
        frame.bind("<B1-Motion>", lambda e, wi=winfo: self.on_widget_drag(e, wi))
        frame.bind("<ButtonRelease-1>", lambda e, wi=winfo: self.on_widget_release(e, wi))
        frame.bind("<Double-Button-1>", lambda e, wi=winfo: self.edit_properties())

        # ручка ресайза
        handle = tk.Label(frame, text="◢", bg="#3498db", fg="white", cursor="sizing")
        handle.place(relx=1.0, rely=1.0, anchor="se")
        handle.bind("<Button-1>", lambda e, wi=winfo: self.start_resize(e, wi))
        handle.bind("<B1-Motion>", lambda e, wi=winfo: self.on_resize(e, wi))
        handle.bind("<ButtonRelease-1>", lambda e, wi=winfo: self.end_resize(e, wi))
        winfo.resize_handle = handle

        # действие для Undo
        self.undo_manager.add_action(AddWidgetAction(self, winfo))

        self.update_info()
        self.update_properties_panel()

    # ---------- пользователя взаимодействие ---------- #
    def on_widget_click(self, e, winfo):
        ctrl = (e.state & 0x0004) != 0
        if ctrl:
            self.toggle_selection(winfo)
        else:
            self.clear_selection()
            self.select_blender(winfo)
        self.drag_drop.start_drag(e, winfo)

    def on_widget_drag(self, e, winfo):  # called from DragDropManager
        self.drag_drop.on_drag(e)

    def on_widget_release(self, e, winfo):
        self.drag_drop.end_drag()

    # скалировка, ресайз
    def start_resize(self, e, winfo):
        self.resizing = winfo
        self.res_start = (e.x_root, e.y_root)
        self.orig_size = (winfo.width, winfo.height)

    def on_resize(self, e, winfo):
        if self.resizing != winfo: return
        dx, dy = e.x_root - self.res_start[0], e.y_root - self.res_start[1]
        new_w, new_h = max(50, self.orig_size[0]+dx), max(30, self.orig_size[1]+dy)
        winfo.width, winfo.height = new_w, new_h
        winfo.properties["width"], winfo.properties["height"] = new_w, new_h
        # обновляем виджет (иногда только width/height смысла)
        if hasattr(winfo.widget_instance, "config"):
            try:
                winfo.widget_instance.config(width=int(new_w/8), height=int(new_h/10))
            except: pass

    def end_resize(self, e, winfo):
        self.resizing = None
        self.res_start = None

    # --------------------- мульти‑выбор --------------------- #
    def toggle_selection(self, winfo):
        sel = winfo.widget_ref.cget("bg") == "#f1c40f"
        if sel:
            winfo.widget_ref.config(bg="#3498db")
            if self.selected_widget==winfo: self.selected_widget=None
        else:
            winfo.widget_ref.config(bg="#f1c40f")
            self.selected_widget=winfo
        self.update_properties_panel()
        self.update_status_count()

    def clear_selection(self):
        for w in self.widgets:
            w.widget_ref.config(bg="#3498db")
        self.selected_widget = None
        self.update_properties_panel()
        self.update_status_count()

    def get_selected_widgets(self): return [w for w in self.widgets if w.widget_ref.cget("bg")=="#f1c40f"]

    def get_selected_count(self): return len(self.get_selected_widgets())

    def update_status_count(self):
        c=self.get_selected_count()
        if c==0: self.status_bar.config(text="✅ Готов")
        elif c==1: self.status_bar.config(text="✨ Выбран 1 виджет")
        else:    self.status_bar.config(text=f"✨ Выбрано {c} виджетов")

    def select_blender(self, winfo):
        if self.selected_widget:
            if self.selected_widget.group_id:
                for g in self.groups:
                    if g.group_id==self.selected_widget.group_id:
                        for s in g.widgets:
                            if s.widget_ref: s.widget_ref.config(bg="#3498db")
                        break
            else:
                self.selected_widget.widget_ref.config(bg="#3498db")
        self.selected_widget=winfo
        if winfo.group_id:
            for g in self.groups:
                if g.group_id==winfo.group_id:
                    for s in g.widgets:
                        if s.widget_ref: s.widget_ref.config(bg="#f1c40f")
                    self.status_bar.config(text=f"✨ Выбрана группа: {g.name}")
                    break
        else:
            winfo.widget_ref.config(bg="#f1c40f")
            self.status_bar.config(text=f"✨ Выбран: {winfo.widget_type}")
        self.update_properties_panel()

    # ---------- действия интерфейса ---------- #
    def update_info(self):
        self.infobar.config(text=f"Виджетов: {len(self.widgets)} | Групп: {len(self.groups)}")

    def update_properties_panel(self):
        for w in self.prop_frame.winfo_children(): w.destroy()
        count=self.get_selected_count()
        if count==0:
            tk.Label(self.prop_frame,text="Виджет не выбран",bg="#ecf0f1",font=("Arial",10)).pack(pady=20)
            return
        if count>1:
            tk.Label(self.prop_frame,text=f"🎯 Выбрано {count} виджетов",bg="#ecf0f1",
                     font=("Arial",10,"bold")).pack(pady=10)
            tk.Label(self.prop_frame,text="Используйте выравнивание\nдля работы с группой",
                     bg="#ecf0f1",justify="center").pack(pady=5)
            return
        w=self.selected_widget
        tk.Label(self.prop_frame, text=f"📌 {w.widget_type}",bg="#ecf0f1",
                 font=("Arial",10,"bold")).pack(anchor="w",pady=5)
        tk.Label(self.prop_frame, text=f"Позиция X={w.x} Y={w.y}",bg="#ecf0f1").pack(anchor="w",pady=2)
        tk.Label(self.prop_frame, text=f"Размер: {w.width}x{w.height}",bg="#ecf0f1").pack(anchor="w",pady=2)
        tk.Frame(self.prop_frame,height=1,bg="#bdc3c7").pack(fill="x",pady=5)
        if w.widget_type in ["Button","Label"]:
            tk.Label(self.prop_frame,text="Текст:",bg="#ecf0f1").pack(anchor="w",pady=0)
            entry=tk.Entry(self.prop_frame); entry.insert(0,w.properties.get("text","")); entry.pack(fill="x",pady=3)
            def upd():
                w.properties["text"]=entry.get()
                if w.widget_instance:
                    w.widget_instance.config(text=entry.get())
            tk.Button(self.prop_frame,text="Применить",command=upd).pack(fill="x",pady=2)
        tk.Frame(self.prop_frame,height=1,bg="#bdc3c7").pack(fill="x",pady=5)
        btns=ttk.Frame(self.prop_frame); btns.pack(fill="x", pady=5)
        ttk.Button(btns,text="⚙️ Свойства", command=self.edit_properties, style="Accent.TButton").pack(side="left",expand=True,fill="x",padx=2)
        ttk.Button(btns,text="🎯 События", command=self.edit_events, style="Accent.TButton").pack(side="left",expand=True,fill="x",padx=2)
        ttk.Button(btns,text="🗑️ Удалить", command=self.delete_widget, style="Accent.TButton").pack(side="left",expand=True,fill="x",padx=2)

    # --- действия ----- #
    def delete_widget(self):
        sel=self.get_selected_widgets()
        if sel:
            for w in sel:
                self.undo_manager.add_action(DeleteWidgetAction(self,w))
                self.delete_widget_by_info(w)
            self.status_bar.config(text=f"🗑️ Удалено {len(sel)} виджетов")

    def delete_widget_by_info(self, wi):
        if wi in self.widgets:
            if wi.group_id:
                for g in self.groups:
                    if g.group_id==wi.group_id:
                        g.remove_widget(wi)
                        if not g.widgets:
                            self.groups.remove(g)
                        break
            self.canvas.delete(wi.canvas_id)
            self.widgets.remove(wi)
            if self.selected_widget==wi: self.selected_widget=None
            self.update_info()
            self.update_properties_panel()

    def restore_widget(self, wi):
        frame=tk.Frame(self.canvas, bg="#3498db", relief="solid", borderwidth=2)
        if wi.widget_type=="Button":
            w=tk.Button(frame,text=wi.properties.get("text","Кнопка"),width=12); w.pack(padx=8,pady=5)
        elif wi.widget_type=="Label":
            w=tk.Label(frame,text=wi.properties.get("text","Метка"),width=12); w.pack(padx=8,pady=5)
        elif wi.widget_type=="Entry":
            w=tk.Entry(frame,width=12); w.pack(padx=8,pady=5)
        else:
            return
        wi.widget_ref, wi.widget_instance = frame, w
        cid=self.canvas.create_window(wi.x,wi.y,window=frame,anchor="nw")
        wi.canvas_id=cid
        self.widgets.append(wi)
        self.update_info()
        # привязки
        frame.bind("<Button-1>", lambda e, wi=wi: self.on_widget_click(e, wi))
        frame.bind("<B1-Motion>", lambda e, wi=wi: self.on_widget_drag(e, wi))
        frame.bind("<ButtonRelease-1>", lambda e, wi=wi: self.on_widget_release(e, wi))
        frame.bind("<Double-Button-1>", lambda e, wi=wi: self.edit_properties())
        if wi.group_id:
            for g in self.groups:
                if g.group_id==wi.group_id: g.add_widget(wi)
                break

    def copy_widget(self):
        sel=self.get_selected_widgets()
        if sel:
            for w in sel:
                self.add_widget(w.widget_type, w.x+30, w.y+30)
            self.status_bar.config(text=f"📋 Скопировано {len(sel)} виджетов")

    def edit_properties(self):
        if self.selected_widget:
            PropertiesDialog(self.root, self.selected_widget, self.on_prop_changed)

    def edit_events(self):
        if self.selected_widget:
            EventDialog(self.root, self.selected_widget, self.event_system, self.on_event_changed)

    def on_prop_changed(self, wi):
        if wi.widget_instance and "text" in wi.properties:
            wi.widget_instance.config(text=wi.properties["text"])
        if "width" in wi.properties: wi.width=int(wi.properties["width"])
        if "height" in wi.properties: wi.height=int(wi.properties["height"])
        self.update_properties_panel()
        self.status_bar.config(text="⚙️ Свойства обновлены")

    def on_event_changed(self, esyst):
        self.event_system=esyst
        self.status_bar.config(text="🎯 События обновлены")

    # ---------- группировка ---------- #
    def show_group_dialog(self): GroupDialog(self.root, self).win.mainloop()
    def create_group_from_selected(self):
        sel=self.get_selected_widgets()
        if len(sel)>=2:
            name=f"Группа {len(self.groups)+1}"
            g=WidgetGroup(len(self.groups)+1,name)
            for w in sel:
                g.add_widget(w); w.widget_ref.config(bg="#9b59b6")
            self.groups.append(g)
            self.undo_manager.add_action(GroupAction(self,g,"create"))
            self.status_bar.config(text=f"📦 Создана {name}")
            self.update_info()
        else:
            messagebox.showinfo("Группировка","Выбрать минимум 2 виджета (Ctrl+клик)")

    def ungroup_selected(self):
        if self.selected_widget and self.selected_widget.group_id:
            for g in self.groups:
                if g.group_id==self.selected_widget.group_id:
                    for w in g.widgets:
                        w.group_id=None; w.widget_ref.config(bg="#3498db")
                    self.groups.remove(g)
                    self.undo_manager.add_action(GroupAction(self,g,"delete"))
                    self.status_bar.config(text=f"🔓 Группа разгруппирована")
                    break

    # ---------- выравнивание ---------- #
    def show_alignment(self): AlignmentDialog(self.root, self).win.mainloop()
    def align_selected(self, dir):   # горячая функция
        sel=self.get_selected_widgets()
        if not sel: return
        if dir=="left":
            minx=min(w.x for w in sel); [w.x=minx for w in sel]
        elif dir=="right":
            maxx=max(w.x+w.width for w in sel); [w.x=maxx-w.width for w in sel]
        elif dir=="top":
            mint=min(w.y for w in sel); [w.y=mint for w in sel]
        elif dir=="bottom":
            maxy=max(w.y+w.height for w in sel); [w.y=maxy-w.height for w in sel]
        elif dir=="center_h":
            cx=sum(w.x+w.width/2 for w in sel)/len(sel); [w.x=cx-w.width/2 for w in sel]
        for w in sel:
            self.canvas.coords(w.canvas_id,w.x,w.y)
        self.update_properties_panel()
        self.status_bar.config(text=f"Выравнивание {dir}")

    # ---------- зум ---------- #
    def zoom_in(self):
        if self.zoom_level<3.0:
            self.zoom_level+=0.1; self.canvas.scale("all",0,0,1.1,1.1); self.zoom_lbl.config(text=f"{int(self.zoom_level*100)}%")

    def zoom_out(self):
        if self.zoom_level>0.3:
            self.zoom_level-=0.1; self.canvas.scale("all",0,0,0.9,0.9); self.zoom_lbl.config(text=f"{int(self.zoom_level*100)}%")

    def zoom_reset(self):
        fac=1.0/self.zoom_level; self.canvas.scale("all",0,0,fac,fac); self.zoom_level=1.0; self.zoom_lbl.config(text="100%")

    def on_zoom_wheel(self, e):
        if e.delta>0: self.zoom_in()
        else:           self.zoom_out()

    # ---------- preview ---------- #
    def preview(self):
        if self.widgets: PreviewWindow(self.root, self).win.mainloop()
        else: messagebox.showinfo("Предпросмотр","Нет виджетов")

    # ---------- темы ---------- #
    def apply_theme(self, key):
        m={ "light":{"bg":"#ecf0f1","fg":"#2c3e50","toolbar":"#34495e"},
            "dark":{"bg":"#2c3e50","fg":"#ecf0f1","toolbar":"#1a2632"},
            "blue":{"bg":"#3498db","fg":"#ffffff","toolbar":"#2980b9"},
            "green":{"bg":"#27ae60","fg":"#ffffff","toolbar":"#229954"},
            "orange":{"bg":"#e67e22","fg":"#ffffff","toolbar":"#d35400"},
            "purple":{"bg":"#9b59b6","fg":"#ffffff","toolbar":"#8e44ad"}}
        t=m[key]
        self.root.configure(bg=t["bg"])
        self.right_panel.configure(bg=t["bg"])
        self.prop_frame.configure(bg=t["bg"])
        self.status_bar.configure(bg=t["bg"],fg=t["fg"])
        self.status_bar.config(text=f"✅ Тема: {key.upper()}")
        self.current_theme=key

    def show_themes(self): ThemeDialog(self.root,self).win.mainloop()
    def show_templates(self): TemplateLibrary(self.root,self).win.mainloop()

    # ---------- удаление/создание проекта ---------- #
    def new_project(self):
        if messagebox.askyesno("Новый проект","Очистить рабочую область?"):
            for w in self.widgets: self.canvas.delete(w.canvas_id)
            self.widgets.clear(); self.groups.clear(); self.selected_widget=None
            self.event_system=EventSystem()
            self.update_info(); self.update_properties_panel()
            self.status_bar.config(text="✅ Новый проект")

    def save_project(self):
        f = filedialog.asksaveasfilename(defaultextension=".tkdesign",
                filetypes=[("TkDesign files","*.tkdesign")])
        if f:
            data={"widgets":[w.to_dict() for w in self.widgets],
                  "events":self.event_system.events}
            with open(f,"w",encoding="utf8") as O: json.dump(data,O,indent=4,ensure_ascii=False)
            messagebox.showinfo("Сохранить","✅ Проект сохранен")
            self.status_bar.config(text=f"💾 {f}")

    def load_project(self):
        f = filedialog.askopenfilename(filetypes=[("TkDesign files","*.tkdesign")])
        if f:
            with open(f,"r",encoding="utf8") as F: data=json.load(F)
            self.new_project()
            for w in data["widgets"]:
                typ,wx,wy,props = w["type"],w["x"],w["y"],w["properties"]; group_id=w.get("group_id")
                self.add_widget(typ, wx, wy); sel=self.widgets[-1]
                sel.properties=props
                if group_id: sel.group_id=group_id
            self.event_system.events=data.get("events",{})
            self.update_info()
            messagebox.showinfo("Загрузить","✅ Проект загружен")

    # ---------- неопределённые события ---------- #
    def on_drag(self, e): pass
    def on_mousewheel(self, e): pass

    def run(self): self.root.mainloop()

# --------------------------------------------------------------------------- #
# Основной запуск
# --------------------------------------------------------------------------- #
if __name__=="__main__":
    TkinterDesigner().run()
