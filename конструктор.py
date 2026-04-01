import tkinter as tk
from tkinter.colorchooser import askcolor
from tkinter import messagebox
import json

widgets = []
selected_widgets = []  # для множественного выделения
GRID_SIZE = 20
snap_to_grid = False
MAGNET_THRESHOLD = 10
AUTOSNAP_THRESHOLD = 15  # расстояние для прилипания к другим виджетам

WIDGET_WIDTH = 120
WIDGET_HEIGHT = 40
BUTTON_WIDTH = 15
BUTTON_HEIGHT = 2

# --------- Добавление виджетов ---------
def add_widget(widget_type):
    if widget_type == 'Button':
        w = tk.Button(design_area, text="Кнопка")
    elif widget_type == 'Label':
        w = tk.Label(design_area, text="Метка")
    elif widget_type == 'Entry':
        w = tk.Entry(design_area)
        w.insert(0, "Поле ввода")
    elif widget_type == 'Checkbutton':
        var = tk.IntVar()
        w = tk.Checkbutton(design_area, text="Чекбокс", variable=var)
        w.var = var
    else:
        return

    # Устанавливаем одинаковый размер при добавлении
    w.place(x=50, y=50, width=WIDGET_WIDTH, height=WIDGET_HEIGHT)
    w._drag_start_x = 0
    w._drag_start_y = 0
    make_draggable(w)
    make_resizable(w)
    w.bind("<Button-1>", lambda e, widget=w: select_widget(widget, multi=False))
    widgets.append({'type': widget_type, 'widget': w})

# --------- Drag, snap и магнит к сетке и другим виджетам ---------
def make_draggable(widget):
    def on_press(event):
        widget._drag_start_x = event.x
        widget._drag_start_y = event.y

    def on_drag(event):
        dx = event.x_root - design_area.winfo_rootx() - widget._drag_start_x
        dy = event.y_root - design_area.winfo_rooty() - widget._drag_start_y

        if snap_to_grid:
            dx = (dx // GRID_SIZE) * GRID_SIZE
            dy = (dy // GRID_SIZE) * GRID_SIZE

        # Автоснап к другим виджетам
        for other in widgets:
            ow = other['widget']
            if ow == widget:
                continue
            ox, oy = ow.winfo_x(), ow.winfo_y()
            if abs(dx - ox) <= AUTOSNAP_THRESHOLD:
                dx = ox
            if abs(dy - oy) <= AUTOSNAP_THRESHOLD:
                dy = oy

        widget.place(x=dx, y=dy, width=widget.winfo_width(), height=widget.winfo_height())
        if hasattr(widget, "_handle"):
            update_handle(widget)

        # Перемещение выделенных виджетов группой
        if widget in selected_widgets:
            for w in selected_widgets:
                if w != widget:
                    w.place(x=w.winfo_x() + (dx - widget.winfo_x()),
                            y=w.winfo_y() + (dy - widget.winfo_y()),
                            width=w.winfo_width(), height=w.winfo_height())
                    if hasattr(w, "_handle"):
                        update_handle(w)

    widget.bind("<Button-1>", on_press)
    widget.bind("<B1-Motion>", on_drag)

# --------- Resize ---------
def make_resizable(widget):
    try:
        handle = tk.Frame(design_area, bg="black", width=6, height=6, cursor="bottom_right_corner")
    except tk.TclError:
        handle = tk.Frame(design_area, bg="black", width=6, height=6)

    def update():
        x, y = widget.winfo_x(), widget.winfo_y()
        w, h = widget.winfo_width(), widget.winfo_height()
        handle.place(x=x+w-3, y=y+h-3)

    def start_resize(event):
        handle._start_width = widget.winfo_width()
        handle._start_height = widget.winfo_height()
        handle._start_x = event.x_root
        handle._start_y = event.y_root

    def do_resize(event):
        dx = event.x_root - handle._start_x
        dy = event.y_root - handle._start_y
        new_w = max(10, handle._start_width + dx)
        new_h = max(10, handle._start_height + dy)
        if snap_to_grid:
            new_w = (new_w // GRID_SIZE) * GRID_SIZE
            new_h = (new_h // GRID_SIZE) * GRID_SIZE
        widget.place(width=new_w, height=new_h)
        update()

    handle.bind("<Button-1>", start_resize)
    handle.bind("<B1-Motion>", do_resize)
    widget._handle = handle
    update_handle(widget)

def update_handle(widget):
    if hasattr(widget, "_handle"):
        x, y = widget.winfo_x(), widget.winfo_y()
        w, h = widget.winfo_width(), widget.winfo_height()
        widget._handle.place(x=x+w-3, y=y+h-3)

# --------- Выбор виджетов ---------
def select_widget(widget, multi=False):
    global selected_widgets
    if not multi:
        selected_widgets.clear()
    if widget not in selected_widgets:
        selected_widgets.append(widget)
    update_settings_panel(widget)

# --------- Настройки ---------
def update_settings_panel(widget):
    for child in settings_panel.winfo_children():
        child.destroy()
    tk.Label(settings_panel, text="Настройки виджета", bg="lightgray").pack(pady=10)

    if isinstance(widget, (tk.Button, tk.Label, tk.Checkbutton, tk.Entry)):
        tk.Label(settings_panel, text="Текст/значение:", bg="lightgray").pack(pady=5)
        text_entry = tk.Entry(settings_panel)
        text_val = widget.get() if isinstance(widget, tk.Entry) else widget['text']
        text_entry.insert(0, text_val)
        text_entry.pack(pady=5)
        tk.Button(settings_panel, text="Применить текст", command=lambda: apply_text(widget, text_entry.get())).pack(pady=5)

    tk.Label(settings_panel, text="Размер шрифта:", bg="lightgray").pack(pady=5)
    font_entry = tk.Entry(settings_panel)
    font_entry.insert(0, get_font_size(widget))
    font_entry.pack(pady=5)
    tk.Button(settings_panel, text="Применить шрифт", command=lambda: widget.config(font=("Arial", int(font_entry.get())))).pack(pady=5)
    tk.Button(settings_panel, text="Цвет текста", command=lambda: change_fg(widget)).pack(pady=5)
    tk.Button(settings_panel, text="Цвет фона", command=lambda: change_bg(widget)).pack(pady=5)

def apply_text(widget, val):
    if isinstance(widget, tk.Entry):
        widget.delete(0, tk.END)
        widget.insert(0, val)
    else:
        widget['text'] = val

def change_fg(widget):
    color = askcolor(title="Цвет текста")[1]
    if color:
        widget.config(fg=color)

def change_bg(widget):
    color = askcolor(title="Цвет фона")[1]
    if color:
        widget.config(bg=color)

def get_font_size(widget):
    f = widget.cget("font")
    if isinstance(f, tuple) and len(f) > 1:
        return f[1]
    elif isinstance(f, str):
        parts = f.split()
        for p in parts:
            if p.isdigit():
                return int(p)
    return 12

# --------- Сохранение и загрузка ---------
def generate_code(file_name="project.py"):
    code = "import tkinter as tk\n\nroot = tk.Tk()\nroot.geometry('800x500')\n\n"
    for item in widgets:
        w_type = item['type']
        w = item['widget']
        x, y = w.winfo_x(), w.winfo_y()
        font_size = get_font_size(w)
        fg = w.cget("fg") if 'fg' in w.keys() else "black"
        bg = w.cget("bg") if 'bg' in w.keys() else "SystemButtonFace"
        text_val = w.get() if isinstance(w, tk.Entry) else w['text']
        code += f"{w_type.lower()} = tk.{w_type}(root, text='{text_val}', fg='{fg}', bg='{bg}', font=('Arial',{font_size}))\n"
        code += f"{w_type.lower()}.place(x={x}, y={y}, width={w.winfo_width()}, height={w.winfo_height()})\n"
    with open(file_name, "w", encoding='utf-8') as f:
        f.write(code)
    messagebox.showinfo("Сохранение", f"Python-файл сохранён как {file_name}")

def save_json():
    data = []
    for item in widgets:
        w_type = item['type']
        w = item['widget']
        x, y = w.winfo_x(), w.winfo_y()
        font_size = get_font_size(w)
        fg = w.cget("fg") if 'fg' in w.keys() else "black"
        bg = w.cget("bg") if 'bg' in w.keys() else "SystemButtonFace"
        text_val = w.get() if isinstance(w, tk.Entry) else w['text']
        data.append({
            'type': w_type,
            'x': x,
            'y': y,
            'width': w.winfo_width(),
            'height': w.winfo_height(),
            'text': text_val,
            'font': font_size,
            'fg': fg,
            'bg': bg
        })
    with open("project.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    messagebox.showinfo("Сохранение", "JSON-проект сохранён как project.json")

def load_project():
    try:
        with open("project.json", "r", encoding='utf-8') as f:
            data = json.load(f)
        for item in widgets:
            item['widget'].destroy()
            if hasattr(item['widget'], '_handle'):
                item['widget']._handle.destroy()
        widgets.clear()
        for item in data:
            add_widget(item['type'])
            w = widgets[-1]['widget']
            w.place(x=item['x'], y=item['y'], width=item['width'], height=item['height'])
            if isinstance(w, tk.Entry):
                w.delete(0, tk.END)
                w.insert(0, item['text'])
            else:
                w['text'] = item['text']
            w.config(font=("Arial", item['font']), fg=item['fg'], bg=item['bg'])
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить проект:\n{e}")

# --------- Предпросмотр ---------
def preview():
    win = tk.Toplevel()
    win.title("Предпросмотр проекта")
    win.geometry('800x500')
    for item in widgets:
        w_type = item['type']
        w = item['widget']
        x, y = w.winfo_x(), w.winfo_y()
        font_size = get_font_size(w)
        fg = w.cget("fg") if 'fg' in w.keys() else "black"
        bg = w.cget("bg") if 'bg' in w.keys() else "SystemButtonFace"
        text_val = w.get() if isinstance(w, tk.Entry) else w['text']
        if w_type == 'Button':
            widget_new = tk.Button(win, text=text_val, fg=fg, bg=bg, font=("Arial", font_size))
        elif w_type == 'Label':
            widget_new = tk.Label(win, text=text_val, fg=fg, bg=bg, font=("Arial", font_size))
        elif w_type == 'Entry':
            widget_new = tk.Entry(win, fg=fg, bg=bg, font=("Arial", font_size))
            widget_new.insert(0, text_val)
        elif w_type == 'Checkbutton':
            var = tk.IntVar()
            widget_new = tk.Checkbutton(win, text=text_val, variable=var, fg=fg, bg=bg, font=("Arial", font_size))
        widget_new.place(x=x, y=y, width=w.winfo_width(), height=w.winfo_height())

# --------- Сетка ---------
def toggle_grid():
    global snap_to_grid
    snap_to_grid = not snap_to_grid
    design_area.delete("grid_line")
    if snap_to_grid:
        width = design_area.winfo_width()
        height = design_area.winfo_height()
        for i in range(0, width, GRID_SIZE):
            design_area.create_line(i, 0, i, height, fill="lightgray", tags="grid_line")
        for j in range(0, height, GRID_SIZE):
            design_area.create_line(0, j, width, j, fill="lightgray", tags="grid_line")

# --------- Изменение размера холста ---------
def resize_canvas():
    try:
        new_width = int(width_entry.get())
        new_height = int(height_entry.get())
        design_area.config(width=new_width, height=new_height)
        if snap_to_grid:
            root.after(10, lambda: (toggle_grid(), toggle_grid()))
    except ValueError:
        messagebox.showerror("Ошибка", "Введите корректные числа для ширины и высоты")

# --------- Очистка холста ---------
def clear_canvas():
    for item in widgets:
        item['widget'].destroy()
        if hasattr(item['widget'], '_handle'):
            item['widget']._handle.destroy()
    widgets.clear()

# --------- Главное окно ---------
root = tk.Tk()
root.title("Профи-конструктор Tkinter")
root.geometry("1200x600")

toolbar = tk.Frame(root, width=200, bg="lightgray")
toolbar.pack(side='left', fill='y')

tk.Label(toolbar, text="Добавить виджет:", bg="lightgray").pack(pady=10)
tk.Button(toolbar, text="Кнопка", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=lambda: add_widget('Button')).pack(pady=5)
tk.Button(toolbar, text="Метка", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=lambda: add_widget('Label')).pack(pady=5)
tk.Button(toolbar, text="Поле ввода", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=lambda: add_widget('Entry')).pack(pady=5)
tk.Button(toolbar, text="Чекбокс", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=lambda: add_widget('Checkbutton')).pack(pady=5)

tk.Button(toolbar, text="Сохранить как JSON", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=save_json, bg="lightgreen").pack(pady=10)
tk.Button(toolbar, text="Сохранить как PY", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=lambda: generate_code("project.py"), bg="lightblue").pack(pady=10)
tk.Button(toolbar, text="Загрузить проект", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=load_project, bg="lightyellow").pack(pady=5)
tk.Button(toolbar, text="Сетка On/Off", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=toggle_grid, bg="orange").pack(pady=10)
tk.Button(toolbar, text="Предпросмотр", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=preview, bg="pink").pack(pady=10)
tk.Button(toolbar, text="Очистить холст", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=clear_canvas, bg="red").pack(pady=10)

# Панель изменения размера холста
tk.Label(toolbar, text="Размер холста:", bg="lightgray").pack(pady=10)
tk.Label(toolbar, text="Ширина:", bg="lightgray").pack()
width_entry = tk.Entry(toolbar)
width_entry.insert(0, "800")
width_entry.pack(pady=2)
tk.Label(toolbar, text="Высота:", bg="lightgray").pack()
height_entry = tk.Entry(toolbar)
height_entry.insert(0, "500")
height_entry.pack(pady=2)
tk.Button(toolbar, text="Применить размер", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
          command=resize_canvas, bg="lightblue").pack(pady=5)

design_area = tk.Canvas(root, bg="white", width=800, height=500)
design_area.pack(side='left', expand=True, fill='both')

settings_panel = tk.Frame(root, width=250, bg="lightgray")
settings_panel.pack(side='right', fill='y')

root.mainloop()
