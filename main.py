import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, colorchooser
from PIL import Image, ImageTk
import os
import platform
import subprocess
import tempfile
import math

class ColorReplacerApp:
    def __init__(self, master):
        self.master = master
        master.title("图片颜色替换工具")
        default_font = ("微软雅黑", 9)
        master.option_add("*Font", default_font)

        # 使用 ttk 主题
        self.style = ttk.Style()

        # Image and Path
        self.image_path = None
        self.original_pil_image = None
        self.display_pil_image = None
        self.tk_image = None

        # ROI
        self.roi_rect_original = None
        self.roi_rect_canvas_id = None
        self.drag_start_canvas_coords = None
        self.is_defining_roi = False

        # Zoom and Pan
        self.zoom_factor = 1.0
        self.pan_offset_orig = (0.0, 0.0)
        self.base_zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.last_pan_mouse_canvas = None
        self.is_panning = False
        
        self.temp_preview_file = None

        # --- UI 元素 ---
        self.frame_top_controls = ttk.Frame(master, padding=(10, 5))
        self.frame_top_controls.pack(fill="x")

        self.frame_file = ttk.LabelFrame(self.frame_top_controls, text="文件操作", padding=(10, 5))
        self.frame_file.pack(side=tk.LEFT, padx=(0,10), fill="y")
        self.btn_load = ttk.Button(self.frame_file, text="加载图片", command=self.load_image)
        self.btn_load.pack(pady=5, padx=5, fill="x")
        self.lbl_image_path = ttk.Label(self.frame_file, text="未选择图片", width=20, wraplength=130, anchor="center")
        self.lbl_image_path.pack(pady=5, padx=5)

        self.frame_zoom_controls = ttk.LabelFrame(self.frame_top_controls, text="视图控制", padding=(10, 5))
        self.frame_zoom_controls.pack(side=tk.LEFT, fill="y")
        self.btn_zoom_in = ttk.Button(self.frame_zoom_controls, text="+", command=self.zoom_in_center, width=3)
        self.btn_zoom_in.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_zoom_out = ttk.Button(self.frame_zoom_controls, text="-", command=self.zoom_out_center, width=3)
        self.btn_zoom_out.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.lbl_zoom_factor = ttk.Label(self.frame_zoom_controls, text="缩放: 100.0%", anchor="center")
        self.lbl_zoom_factor.grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        self.btn_reset_view = ttk.Button(self.frame_zoom_controls, text="重置视图", command=self.reset_view)
        self.btn_reset_view.grid(row=1, column=0, columnspan=3, padx=2, pady=5, sticky="ew")


        self.frame_colors = ttk.LabelFrame(master, text="颜色与参数设置", padding=(10, 10))
        self.frame_colors.pack(padx=10, pady=5, fill="x")
        
        self.frame_colors.columnconfigure(1, weight=1)
        self.frame_colors.columnconfigure(3, weight=1)


        ttk.Label(self.frame_colors, text="目标颜色:").grid(row=0, column=0, sticky="w", pady=3, padx=5)
        self.lbl_target_color_preview = tk.Label(self.frame_colors, text="  ", bg="white", width=3, relief="sunken", borderwidth=1)
        self.lbl_target_color_preview.grid(row=0, column=1, sticky="w", padx=5)
        self.lbl_target_color_rgb = ttk.Label(self.frame_colors, text="RGB: (尚未选择)")
        self.lbl_target_color_rgb.grid(row=0, column=2, columnspan=2, sticky="w", padx=5)

        ttk.Label(self.frame_colors, text="替换颜色:").grid(row=1, column=0, sticky="w", pady=3, padx=5)
        self.btn_pick_replacement_color = ttk.Button(self.frame_colors, text="选择", command=self.pick_replacement_color)
        self.btn_pick_replacement_color.grid(row=1, column=1, sticky="ew", padx=5)
        self.lbl_replacement_color_preview = tk.Label(self.frame_colors, text="  ", bg="white", width=3, relief="sunken", borderwidth=1)
        self.lbl_replacement_color_preview.grid(row=1, column=2, sticky="w", padx=5)

        ttk.Label(self.frame_colors, text="R:").grid(row=2, column=0, sticky="e", pady=3, padx=5)
        self.entry_replace_r = ttk.Entry(self.frame_colors, width=5)
        self.entry_replace_r.grid(row=2, column=1, sticky="ew", padx=5)
        self.entry_replace_r.insert(0, "0")
        ttk.Label(self.frame_colors, text="G:").grid(row=2, column=2, sticky="e", pady=3, padx=5)
        self.entry_replace_g = ttk.Entry(self.frame_colors, width=5)
        self.entry_replace_g.grid(row=2, column=3, sticky="ew", padx=5)
        self.entry_replace_g.insert(0, "0")
        
        ttk.Label(self.frame_colors, text="B:").grid(row=3, column=0, sticky="e", pady=3, padx=5)
        self.entry_replace_b = ttk.Entry(self.frame_colors, width=5)
        self.entry_replace_b.grid(row=3, column=1, sticky="ew", padx=5)
        self.entry_replace_b.insert(0, "0")
        ttk.Label(self.frame_colors, text="透明度 (A):").grid(row=3, column=2, sticky="e", pady=3, padx=5)
        self.entry_replace_a = ttk.Entry(self.frame_colors, width=5)
        self.entry_replace_a.grid(row=3, column=3, sticky="ew", padx=5)
        self.entry_replace_a.insert(0, "255")
        self.update_replacement_color_preview()

        ttk.Label(self.frame_colors, text="颜色容差:").grid(row=4, column=0, sticky="w", pady=3, padx=5)
        self.entry_tolerance = ttk.Entry(self.frame_colors, width=5)
        self.entry_tolerance.grid(row=4, column=1, sticky="ew", padx=5)
        self.entry_tolerance.insert(0, "20")
        
        # --- 新增：边缘平滑设置 ---
        ttk.Label(self.frame_colors, text="边缘平滑:").grid(row=5, column=0, sticky="w", pady=3, padx=5)
        self.entry_feather = ttk.Entry(self.frame_colors, width=5)
        self.entry_feather.grid(row=5, column=1, sticky="ew", padx=5)
        self.entry_feather.insert(0, "10")

        self.frame_roi_mode = ttk.LabelFrame(master, text="处理模式", padding=(10, 10))
        self.frame_roi_mode.pack(padx=10, pady=5, fill="x")
        self.roi_mode_var = tk.StringVar(value="none")
        modes = [("替换整张图片", "none"), ("仅替换选区内颜色", "inside"), ("替换选区外颜色", "outside")]
        for i, (text, mode) in enumerate(modes):
            rb = ttk.Radiobutton(self.frame_roi_mode, text=text, variable=self.roi_mode_var, value=mode, command=self.update_roi_mode_buttons_state)
            rb.pack(side=tk.LEFT, padx=10, pady=5, expand=True)
            if mode in ["inside", "outside"]: rb.config(state=tk.DISABLED)

        self.frame_image_display = ttk.LabelFrame(master, text="图片预览 (左键拾色/拖拽选区, 右键拖拽移动, 滚轮缩放)", padding=(5,5))
        self.frame_image_display.pack(padx=10, pady=5, fill="both", expand=True)
        self.btn_clear_roi = ttk.Button(self.frame_image_display, text="清除选区", command=self.clear_roi_and_update, state=tk.DISABLED)
        self.btn_clear_roi.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=2)

        self.canvas_image = tk.Canvas(self.frame_image_display, bg="lightgrey", width=500, height=400, relief="sunken", borderwidth=1)
        self.canvas_image.pack(fill="both", expand=True, padx=5, pady=(25,5))
        
        self.canvas_image.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas_image.bind("<B1-Motion>", self.on_left_drag)
        self.canvas_image.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas_image.bind("<ButtonPress-3>", self.on_middle_press)
        self.canvas_image.bind("<B3-Motion>", self.on_middle_drag)
        self.canvas_image.bind("<ButtonRelease-3>", self.on_middle_release)
        self.canvas_image.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas_image.bind("<Button-4>", self.on_mouse_wheel_linux)
        self.canvas_image.bind("<Button-5>", self.on_mouse_wheel_linux)

        self.frame_actions = ttk.Frame(master, padding=(10,10))
        self.frame_actions.pack(fill="x")
        self.btn_process = ttk.Button(self.frame_actions, text="处理并预览", command=self.process_image, state=tk.DISABLED)
        self.btn_process.pack(side=tk.RIGHT, padx=5, pady=5)
        
        for entry in [self.entry_replace_r, self.entry_replace_g, self.entry_replace_b, self.entry_replace_a, self.entry_tolerance]:
            entry.bind("<KeyRelease>", self.update_replacement_color_preview)
        
        self.master.bind("<Configure>", self.on_window_resize)
        self.master.minsize(650, 700)

    def on_window_resize(self, event=None):
        if self.original_pil_image and (event is None or event.widget == self.master or event.widget == self.canvas_image):
            self.master.after(50, self.update_display_image_and_roi) # 延迟一点点以获取正确的winfo

    def update_zoom_label(self):
        self.lbl_zoom_factor.config(text=f"缩放: {self.zoom_factor*100:.1f}%")

    def zoom_at_canvas_point(self, factor_change, canvas_x, canvas_y):
        if not self.original_pil_image: return
        orig_x_at_mouse, orig_y_at_mouse = self.canvas_to_original_coords(canvas_x, canvas_y)
        self.zoom_factor *= factor_change
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, self.zoom_factor))
        self.pan_offset_orig = (
            orig_x_at_mouse - (canvas_x / self.zoom_factor),
            orig_y_at_mouse - (canvas_y / self.zoom_factor)
        )
        self.clamp_pan_offset()
        self.update_display_image_and_roi()
        self.update_zoom_label()

    def zoom_in_center(self):
        if not self.original_pil_image: return
        canvas_center_x = self.canvas_image.winfo_width() / 2
        canvas_center_y = self.canvas_image.winfo_height() / 2
        self.zoom_at_canvas_point(1.2, canvas_center_x, canvas_center_y)

    def zoom_out_center(self):
        if not self.original_pil_image: return
        canvas_center_x = self.canvas_image.winfo_width() / 2
        canvas_center_y = self.canvas_image.winfo_height() / 2
        self.zoom_at_canvas_point(1 / 1.2, canvas_center_x, canvas_center_y)

    def on_mouse_wheel(self, event):
        if not self.original_pil_image: return
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self.zoom_at_canvas_point(factor, event.x, event.y)
        return "break"

    def on_mouse_wheel_linux(self, event):
        if not self.original_pil_image: return
        factor = 1.1 if event.num == 4 else (1 / 1.1 if event.num == 5 else 1.0)
        self.zoom_at_canvas_point(factor, event.x, event.y)
        return "break"

    def reset_view(self):
        if not self.original_pil_image: return
        self.load_image(self.image_path)

    def clamp_pan_offset(self):
        if not self.original_pil_image: return
        canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
        if canvas_w == 0 or canvas_h == 0: return
        orig_w, orig_h = self.original_pil_image.size
        viewport_w_orig, viewport_h_orig = canvas_w / self.zoom_factor, canvas_h / self.zoom_factor
        current_pan_x, current_pan_y = self.pan_offset_orig
        new_pan_x = (orig_w - viewport_w_orig) / 2.0 if viewport_w_orig >= orig_w else max(0.0, min(current_pan_x, orig_w - viewport_w_orig))
        new_pan_y = (orig_h - viewport_h_orig) / 2.0 if viewport_h_orig >= orig_h else max(0.0, min(current_pan_y, orig_h - viewport_h_orig))
        self.pan_offset_orig = (new_pan_x, new_pan_y)

    def update_display_image_and_roi(self):
        if not self.original_pil_image:
            self.canvas_image.delete("all")
            return
        canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            self.master.after(50, self.update_display_image_and_roi)
            return
        bg_color = "lightgray"
        self.display_pil_image = Image.new('RGBA', (canvas_w, canvas_h), bg_color)
        src_x1_orig, src_y1_orig = self.pan_offset_orig
        src_w_orig, src_h_orig = canvas_w / self.zoom_factor, canvas_h / self.zoom_factor
        src_x2_orig, src_y2_orig = src_x1_orig + src_w_orig, src_y1_orig + src_h_orig
        crop_x1, crop_y1 = max(0, src_x1_orig), max(0, src_y1_orig)
        crop_x2, crop_y2 = min(self.original_pil_image.width, src_x2_orig), min(self.original_pil_image.height, src_y2_orig)
        if crop_x1 < crop_x2 and crop_y1 < crop_y2:
            cropped_from_original = self.original_pil_image.crop((int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)))
            paste_x_canvas, paste_y_canvas = (crop_x1 - src_x1_orig) * self.zoom_factor, (crop_y1 - src_y1_orig) * self.zoom_factor
            display_cropped_w, display_cropped_h = int(cropped_from_original.width * self.zoom_factor), int(cropped_from_original.height * self.zoom_factor)
            if display_cropped_w > 0 and display_cropped_h > 0:
                resized_cropped_image = cropped_from_original.resize((display_cropped_w, display_cropped_h), Image.Resampling.LANCZOS)
                self.display_pil_image.paste(resized_cropped_image, (int(paste_x_canvas), int(paste_y_canvas)), resized_cropped_image if resized_cropped_image.mode == 'RGBA' else None)
        self.canvas_image.delete("all")
        self.tk_image = ImageTk.PhotoImage(self.display_pil_image)
        self.canvas_image.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.draw_roi_on_canvas()
        self.update_zoom_label()

    def draw_roi_on_canvas(self):
        if self.roi_rect_canvas_id: self.canvas_image.delete(self.roi_rect_canvas_id); self.roi_rect_canvas_id = None
        if self.roi_rect_original:
            ox1, oy1, ox2, oy2 = self.roi_rect_original
            cx1, cy1 = self.original_to_canvas_coords(ox1, oy1)
            cx2, cy2 = self.original_to_canvas_coords(ox2, oy2)
            self.roi_rect_canvas_id = self.canvas_image.create_rectangle(cx1, cy1, cx2, cy2, outline="red", dash=(4,2), width=1.5) 

    def canvas_to_original_coords(self, canvas_x, canvas_y):
        if not self.original_pil_image: return (0,0)
        return (self.pan_offset_orig[0] + (canvas_x / self.zoom_factor), self.pan_offset_orig[1] + (canvas_y / self.zoom_factor))

    def original_to_canvas_coords(self, orig_x, orig_y):
        if not self.original_pil_image: return (0,0)
        return ((orig_x - self.pan_offset_orig[0]) * self.zoom_factor, (orig_y - self.pan_offset_orig[1]) * self.zoom_factor)

    def update_roi_mode_buttons_state(self, event=None):
        has_roi = self.roi_rect_original is not None
        for child in self.frame_roi_mode.winfo_children():
            if isinstance(child, ttk.Radiobutton): 
                mode_value = child.cget("value")
                if mode_value in ["inside", "outside"]: child.config(state=tk.NORMAL if has_roi else tk.DISABLED)
        if not has_roi and self.roi_mode_var.get() != "none": self.roi_mode_var.set("none")
        self.btn_clear_roi.config(state=tk.NORMAL if has_roi else tk.DISABLED)

    def pick_replacement_color(self):
        color_code = colorchooser.askcolor(title="选择替换颜色")
        if color_code and color_code[0]:
            r, g, b = color_code[0]
            self.entry_replace_r.delete(0, tk.END); self.entry_replace_r.insert(0, str(int(r)))
            self.entry_replace_g.delete(0, tk.END); self.entry_replace_g.insert(0, str(int(g)))
            self.entry_replace_b.delete(0, tk.END); self.entry_replace_b.insert(0, str(int(b)))
            if not self.entry_replace_a.get(): self.entry_replace_a.insert(0, "255")
            self.update_replacement_color_preview()

    def update_replacement_color_preview(self, event=None):
        try:
            r,g,b = int(self.entry_replace_r.get()), int(self.entry_replace_g.get()), int(self.entry_replace_b.get())
            self.lbl_replacement_color_preview.config(bg=f"#{r:02x}{g:02x}{b:02x}" if all(0 <= val <= 255 for val in [r,g,b]) else "white")
        except ValueError: self.lbl_replacement_color_preview.config(bg="white")

    def load_image(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(title="选择图片文件", filetypes=(("常用图片格式", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.tiff;*.tif;*.webp"),("所有文件", "*.*")))
        if path:
            self.image_path = path
            self.lbl_image_path.config(text=path.split('/')[-1])
            try:
                self.original_pil_image = Image.open(path)
                canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
                if canvas_w <=1: canvas_w = self.canvas_image.cget("width") 
                if canvas_h <=1: canvas_h = self.canvas_image.cget("height") 
                orig_w, orig_h = self.original_pil_image.size
                if orig_w == 0 or orig_h == 0: raise ValueError("图片尺寸为零")
                ratio_w, ratio_h = canvas_w / orig_w, canvas_h / orig_h
                self.base_zoom = min(ratio_w, ratio_h, 1.0) 
                self.zoom_factor = self.base_zoom
                viewport_w_orig, viewport_h_orig = canvas_w / self.zoom_factor, canvas_h / self.zoom_factor
                self.pan_offset_orig = ((orig_w - viewport_w_orig) / 2.0, (orig_h - viewport_h_orig) / 2.0)
                self.clamp_pan_offset()
                self.btn_process.config(state=tk.NORMAL)
                self.target_color_rgb = None
                self.lbl_target_color_preview.config(bg="white"); self.lbl_target_color_rgb.config(text="RGB: (尚未选择)")
                self.clear_roi_and_update()
                self.update_display_image_and_roi()
            except Exception as e:
                messagebox.showerror("错误", f"无法加载图片: {e}")
                self.image_path=None; self.original_pil_image=None; self.display_pil_image=None; self.tk_image=None
                self.lbl_image_path.config(text="加载失败"); self.btn_process.config(state=tk.DISABLED)
                self.clear_roi_and_update(); self.update_display_image_and_roi()

    def on_left_press(self, event):
        if not self.original_pil_image: return
        self.drag_start_canvas_coords = (event.x, event.y)
        self.is_defining_roi = False
        if self.roi_rect_canvas_id: self.canvas_image.delete(self.roi_rect_canvas_id); self.roi_rect_canvas_id = None

    def on_left_drag(self, event):
        if not self.drag_start_canvas_coords or not self.original_pil_image: return
        self.is_defining_roi = True
        x1_c, y1_c = self.drag_start_canvas_coords; x2_c, y2_c = event.x, event.y
        if self.roi_rect_canvas_id: self.canvas_image.coords(self.roi_rect_canvas_id, x1_c, y1_c, x2_c, y2_c)
        else: self.roi_rect_canvas_id = self.canvas_image.create_rectangle(x1_c, y1_c, x2_c, y2_c, outline="red", dash=(4,2), width=1.5)

    def on_left_release(self, event):
        if not self.original_pil_image: return
        if self.is_defining_roi and self.drag_start_canvas_coords:
            c_x1, c_y1 = self.drag_start_canvas_coords; c_x2, c_y2 = event.x, event.y
            orig_x1, orig_y1 = self.canvas_to_original_coords(min(c_x1, c_x2), min(c_y1, c_y2))
            orig_x2, orig_y2 = self.canvas_to_original_coords(max(c_x1, c_x2), max(c_y1, c_y2))
            img_w, img_h = self.original_pil_image.size
            orig_x1,orig_y1 = max(0,min(orig_x1,img_w)), max(0,min(orig_y1,img_h))
            orig_x2,orig_y2 = max(0,min(orig_x2,img_w)), max(0,min(orig_y2,img_h))
            self.roi_rect_original = (orig_x1, orig_y1, orig_x2, orig_y2) if orig_x2 > orig_x1 and orig_y2 > orig_y1 else None
            self.draw_roi_on_canvas()
        elif not self.is_defining_roi and self.drag_start_canvas_coords:
            self.pick_color_at_canvas_coords(self.drag_start_canvas_coords[0], self.drag_start_canvas_coords[1])
        self.drag_start_canvas_coords = None; self.is_defining_roi = False
        self.update_roi_mode_buttons_state()

    def on_middle_press(self, event): # 右键按下
        if not self.original_pil_image: return
        self.last_pan_mouse_canvas = (event.x, event.y)
        self.is_panning = True
        self.canvas_image.config(cursor="fleur")

    def on_middle_drag(self, event): # 右键拖动
        if not self.is_panning or not self.last_pan_mouse_canvas or not self.original_pil_image: return
        dx_canvas, dy_canvas = event.x - self.last_pan_mouse_canvas[0], event.y - self.last_pan_mouse_canvas[1]
        dx_orig, dy_orig = dx_canvas / self.zoom_factor, dy_canvas / self.zoom_factor
        self.pan_offset_orig = (self.pan_offset_orig[0] - dx_orig, self.pan_offset_orig[1] - dy_orig)
        self.clamp_pan_offset(); self.update_display_image_and_roi()
        self.last_pan_mouse_canvas = (event.x, event.y)

    def on_middle_release(self, event): # 右键释放
        self.is_panning = False; self.last_pan_mouse_canvas = None
        self.canvas_image.config(cursor="")

    def pick_color_at_canvas_coords(self, canvas_x, canvas_y):
        if self.original_pil_image:
            orig_x, orig_y = self.canvas_to_original_coords(canvas_x, canvas_y)
            img_w, img_h = self.original_pil_image.size
            if 0 <= orig_x < img_w and 0 <= orig_y < img_h:
                try:
                    img_pick = self.original_pil_image.convert("RGBA")
                    r,g,b,_ = img_pick.getpixel((int(orig_x), int(orig_y)))
                    self.target_color_rgb = (r,g,b)
                    self.lbl_target_color_preview.config(bg=f"#{r:02x}{g:02x}{b:02x}")
                    self.lbl_target_color_rgb.config(text=f"RGB: {(r,g,b)}")
                except Exception as e: messagebox.showerror("错误", f"无法获取像素颜色: {e}")

    def clear_roi_and_update(self):
        if self.roi_rect_canvas_id: self.canvas_image.delete(self.roi_rect_canvas_id); self.roi_rect_canvas_id = None
        self.roi_rect_original = None
        self.update_roi_mode_buttons_state()
        self.update_display_image_and_roi()

    # --- 函数已重写 ---
    def process_image(self):
        if not self.image_path: messagebox.showerror("错误", "请先加载一张图片。"); return
        if not self.target_color_rgb: messagebox.showerror("错误", "请先点击图片选择要替换的目标颜色。"); return
        
        current_roi_mode = self.roi_mode_var.get()
        if current_roi_mode != "none" and not self.roi_rect_original:
            messagebox.showerror("错误", "选择了选区处理模式，但未定义选区。"); return

        try:
            r_rep,g_rep,b_rep,a_rep = int(self.entry_replace_r.get()),int(self.entry_replace_g.get()),int(self.entry_replace_b.get()),int(self.entry_replace_a.get())
            if not all(0 <= v <= 255 for v in [r_rep,g_rep,b_rep,a_rep]): raise ValueError("RGBA值需在0-255间")
            replacement_rgba = (r_rep,g_rep,b_rep,a_rep)
            
            tolerance = int(self.entry_tolerance.get())
            if not (0 <= tolerance <= 442): raise ValueError("容差值建议在0-442之间") # sqrt(255^2*3) is ~441.7

            feather = int(self.entry_feather.get())
            if not (0 <= feather): raise ValueError("平滑值必须为正数")

        except ValueError as e: 
            messagebox.showerror("输入错误", f"输入参数无效: {e}"); return

        try:
            img_to_process_copy = self.original_pil_image.convert("RGBA")
            datas = list(img_to_process_copy.getdata())
            width, height = img_to_process_copy.size
            
            r_target, g_target, b_target = self.target_color_rgb

            for i in range(len(datas)):
                px, py = i % width, i // width
                item_r, item_g, item_b, item_a = datas[i]

                # 检查像素是否在需要处理的区域内 (ROI)
                is_in_processing_area = False
                if current_roi_mode == "none":
                    is_in_processing_area = True
                elif self.roi_rect_original:
                    r_x1, r_y1, r_x2, r_y2 = self.roi_rect_original
                    is_inside_roi = (r_x1 <= px < r_x2 and r_y1 <= py < r_y2)
                    if current_roi_mode == "inside" and is_inside_roi:
                        is_in_processing_area = True
                    elif current_roi_mode == "outside" and not is_inside_roi:
                        is_in_processing_area = True
                
                if not is_in_processing_area:
                    continue

                # --- 核心平滑替换逻辑 ---
                # 计算颜色距离 (Euclidean distance in RGB space)
                dist = math.sqrt((item_r - r_target)**2 + (item_g - g_target)**2 + (item_b - b_target)**2)
                
                blend_ratio = 0.0 # 混合比例，0.0表示不混合，1.0表示完全替换

                if dist < tolerance:
                    blend_ratio = 1.0
                elif feather > 0 and tolerance <= dist < tolerance + feather:
                    # 在羽化区域内，计算混合比例，实现平滑过渡
                    blend_ratio = 1.0 - ((dist - tolerance) / feather)
                
                if blend_ratio > 0:
                    # 根据混合比例，混合原始颜色和替换颜色
                    # C_final = C_replace * ratio + C_original * (1 - ratio)
                    final_r = replacement_rgba[0] * blend_ratio + item_r * (1.0 - blend_ratio)
                    final_g = replacement_rgba[1] * blend_ratio + item_g * (1.0 - blend_ratio)
                    final_b = replacement_rgba[2] * blend_ratio + item_b * (1.0 - blend_ratio)
                    
                    # 同时混合透明度
                    final_a = replacement_rgba[3] * blend_ratio + item_a * (1.0 - blend_ratio)
                    
                    datas[i] = (int(final_r), int(final_g), int(final_b), int(final_a))

            processed_pil_image = Image.new("RGBA", (width, height))
            processed_pil_image.putdata(datas)
            self.show_preview_window(processed_pil_image, replacement_rgba[3] < 255)

        except Exception as e:
            messagebox.showerror("处理错误", f"处理图片时发生错误: {e}")


    def _open_with_system_viewer(self, image_to_view): # 新增辅助方法
        try:
            # 创建一个带特定后缀的临时文件，以便系统知道如何打开它
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                image_to_view.save(tmp_file.name, "PNG")
                self.temp_preview_file = tmp_file.name # 保存路径以备后用

            if self.temp_preview_file:
                system = platform.system()
                if system == "Windows":
                    os.startfile(self.temp_preview_file)
                elif system == "Darwin": # macOS
                    subprocess.call(["open", self.temp_preview_file])
                else: # Linux and other UNIX-like
                    subprocess.call(["xdg-open", self.temp_preview_file])
        except Exception as e:
            messagebox.showerror("打开错误", f"无法使用系统查看器打开图片: {e}", parent=self.master) # parent 设为主窗口

    def _cleanup_temp_file(self): # 新增辅助方法
        if self.temp_preview_file and os.path.exists(self.temp_preview_file):
            try:
                os.remove(self.temp_preview_file)
                self.temp_preview_file = None
            except Exception as e:
                print(f"无法删除临时文件 {self.temp_preview_file}: {e}")
        self.temp_preview_file = None # 确保即使删除失败也重置

    def show_preview_window(self, processed_image, is_transparent_replacement):
        preview_window = tk.Toplevel(self.master)
        preview_window.title("预览处理结果")
        preview_window.grab_set()
        
        # 绑定关闭事件以清理临时文件
        preview_window.protocol("WM_DELETE_WINDOW", lambda: (self._cleanup_temp_file(), preview_window.destroy()))


        max_preview_w, max_preview_h = 600, 500
        img_w, img_h = processed_image.size
        ratio = min(max_preview_w / img_w, max_preview_h / img_h) if img_w > 0 and img_h > 0 else 1
        display_image_for_preview = processed_image
        if ratio < 1: 
            pw, ph = int(img_w * ratio), int(img_h * ratio)
            if pw > 0 and ph > 0:
                 display_image_for_preview = processed_image.resize((pw, ph), Image.Resampling.LANCZOS)
            else: 
                display_image_for_preview = processed_image.resize((100,100), Image.Resampling.LANCZOS)
        
        final_disp_w = max(1, display_image_for_preview.width)
        final_disp_h = max(1, display_image_for_preview.height)

        tk_preview_image = ImageTk.PhotoImage(display_image_for_preview.resize((final_disp_w, final_disp_h), Image.Resampling.LANCZOS))

        canvas_preview = tk.Canvas(preview_window, width=final_disp_w, height=final_disp_h, bg="lightgray")
        canvas_preview.create_image(final_disp_w//2, final_disp_h//2, anchor=tk.CENTER, image=tk_preview_image)
        canvas_preview.image = tk_preview_image 
        canvas_preview.pack(padx=10, pady=10)
        
        frame_preview_buttons = ttk.Frame(preview_window, padding=(0,5,0,10)) 
        frame_preview_buttons.pack()

        # “用系统查看器打开”按钮
        btn_open_system = ttk.Button(frame_preview_buttons, text="用系统查看器打开",
                                     command=lambda: self._open_with_system_viewer(processed_image))
        btn_open_system.pack(side=tk.LEFT, padx=5)

        btn_save = ttk.Button(frame_preview_buttons, text="保存图片", 
                              command=lambda: self.finalize_save(processed_image, preview_window, is_transparent_replacement))
        btn_save.pack(side=tk.LEFT, padx=10)
        btn_cancel = ttk.Button(frame_preview_buttons, text="取消", 
                                command=lambda: (self._cleanup_temp_file(), preview_window.destroy()))
        btn_cancel.pack(side=tk.LEFT, padx=10)
        preview_window.resizable(False, False)

    def finalize_save(self, image_to_save, preview_window_instance, is_transparent_replacement):
        # 在 finalize_save 开始时也尝试清理，以防用户直接点保存而没点系统查看器
        self._cleanup_temp_file() 
        
        output_path = filedialog.asksaveasfilename(title="保存处理后的图片", defaultextension=".png", filetypes=(("PNG 文件", "*.png"), ("所有文件", "*.*")))
        if not output_path: preview_window_instance.focus_set(); return
        if not output_path.lower().endswith(".png") and is_transparent_replacement:
            if not messagebox.askyesno("警告", "您选择了透明替换，但输出文件名不是 .png。\n为保证透明效果，建议使用 .png 格式。\n是否仍要继续？", parent=preview_window_instance):
                preview_window_instance.focus_set(); return
        try:
            image_to_save.save(output_path, "PNG")
            messagebox.showinfo("成功", f"图片已成功处理并保存到:\n{output_path}")
            preview_window_instance.destroy() # 关闭预览窗口
        except Exception as e:
            messagebox.showerror("保存错误", f"保存图片时发生错误: {e}", parent=preview_window_instance)
            preview_window_instance.focus_set()

if __name__ == "__main__":
    root = tk.Tk()
    app = ColorReplacerApp(root)
    root.mainloop()