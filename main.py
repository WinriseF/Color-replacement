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

        self.style = ttk.Style()

        # State Variables
        self.image_path = None
        self.original_pil_image = None
        self.display_pil_image = None
        self.tk_image = None
        self.roi_rect_original = None
        self.roi_rect_canvas_id = None
        self.drag_start_canvas_coords = None
        self.is_defining_roi = False
        self.flood_fill_seeds = []
        self.seed_marker_ids = []
        self.target_color_rgb = None
        self.zoom_factor = 1.0
        self.pan_offset_orig = (0.0, 0.0)
        self.base_zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.last_pan_mouse_canvas = None
        self.is_panning = False
        self.temp_preview_file = None
        self.layout_mode = ""
        self._after_id = None
        self.drag_warning_shown = False

        # --- UI Element Creation ---
        self.frame_top_controls = ttk.Frame(master)
        self.frame_file = ttk.LabelFrame(self.frame_top_controls, text="文件操作", padding=(10, 5))
        self.btn_load = ttk.Button(self.frame_file, text="加载图片", command=self.load_image)
        self.lbl_image_path = ttk.Label(self.frame_file, text="未选择图片", width=20, wraplength=130, anchor="center")
        self.frame_zoom_controls = ttk.LabelFrame(self.frame_top_controls, text="视图控制", padding=(10, 5))
        self.btn_zoom_in = ttk.Button(self.frame_zoom_controls, text="+", command=self.zoom_in_center, width=3)
        self.btn_zoom_out = ttk.Button(self.frame_zoom_controls, text="-", command=self.zoom_out_center, width=3)
        self.lbl_zoom_factor = ttk.Label(self.frame_zoom_controls, text="缩放: 100.0%", anchor="center")
        self.btn_reset_view = ttk.Button(self.frame_zoom_controls, text="重置视图", command=self.reset_view)
        
        self.frame_colors = ttk.LabelFrame(master, text="颜色与参数设置", padding=(10, 10))
        self.frame_roi_mode = ttk.LabelFrame(master, text="处理模式", padding=(10, 10))
        self.roi_mode_var = tk.StringVar(value="none")
        
        self.frame_image_display = ttk.LabelFrame(master, text="图片预览 (左键拾色/拖拽选区, 右键拖拽移动, 滚轮缩放)", padding=(5,5))
        self.btn_clear_roi = ttk.Button(self.frame_image_display, text="清除选区", command=self.clear_all_selections, state=tk.DISABLED)
        self.canvas_image = tk.Canvas(self.frame_image_display, bg="lightgrey", width=500, height=400, relief="sunken", borderwidth=1)
        
        self.frame_actions = ttk.Frame(master, padding=(10,10))
        self.btn_process = ttk.Button(self.frame_actions, text="处理并预览", command=self.process_image, state=tk.DISABLED)

        # --- Place Widgets within their respective frames ---
        self.frame_file.pack(side=tk.LEFT, padx=(0,10), fill="y")
        self.btn_load.pack(pady=5, padx=5, fill="x")
        self.lbl_image_path.pack(pady=5, padx=5)
        self.frame_zoom_controls.pack(side=tk.LEFT, fill="y")
        self.btn_zoom_in.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_zoom_out.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.lbl_zoom_factor.grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        self.btn_reset_view.grid(row=1, column=0, columnspan=3, padx=2, pady=5, sticky="ew")
        
        self.frame_colors.columnconfigure(1, weight=1); self.frame_colors.columnconfigure(3, weight=1)
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
        self.entry_replace_r = ttk.Entry(self.frame_colors, width=5); self.entry_replace_r.grid(row=2, column=1, sticky="ew", padx=5); self.entry_replace_r.insert(0, "0")
        ttk.Label(self.frame_colors, text="G:").grid(row=2, column=2, sticky="e", pady=3, padx=5)
        self.entry_replace_g = ttk.Entry(self.frame_colors, width=5); self.entry_replace_g.grid(row=2, column=3, sticky="ew", padx=5); self.entry_replace_g.insert(0, "0")
        ttk.Label(self.frame_colors, text="B:").grid(row=3, column=0, sticky="e", pady=3, padx=5)
        self.entry_replace_b = ttk.Entry(self.frame_colors, width=5); self.entry_replace_b.grid(row=3, column=1, sticky="ew", padx=5); self.entry_replace_b.insert(0, "0")
        ttk.Label(self.frame_colors, text="透明度 (A):").grid(row=3, column=2, sticky="e", pady=3, padx=5)
        self.entry_replace_a = ttk.Entry(self.frame_colors, width=5); self.entry_replace_a.grid(row=3, column=3, sticky="ew", padx=5); self.entry_replace_a.insert(0, "255")
        self.update_replacement_color_preview()
        ttk.Label(self.frame_colors, text="颜色容差:").grid(row=4, column=0, sticky="w", pady=3, padx=5)
        self.entry_tolerance = ttk.Entry(self.frame_colors, width=5); self.entry_tolerance.grid(row=4, column=1, sticky="ew", padx=5); self.entry_tolerance.insert(0, "20")
        ttk.Label(self.frame_colors, text="边缘平滑:").grid(row=5, column=0, sticky="w", pady=3, padx=5)
        self.entry_feather = ttk.Entry(self.frame_colors, width=5); self.entry_feather.grid(row=5, column=1, sticky="ew", padx=5); self.entry_feather.insert(0, "30")

        modes = [("替换整张图片", "none"), ("仅替换选区内颜色", "inside"), ("替换选区外颜色", "outside"), ("扩散填充", "floodfill")]
        for i, (text, mode) in enumerate(modes):
            rb = ttk.Radiobutton(self.frame_roi_mode, text=text, variable=self.roi_mode_var, value=mode, command=self.update_roi_mode_buttons_state)
            rb.pack(side=tk.LEFT, padx=10, pady=5, expand=True)
            if mode in ["inside", "outside", "floodfill"]: rb.config(state=tk.DISABLED)

        self.btn_clear_roi.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=2)
        self.canvas_image.pack(fill="both", expand=True, padx=5, pady=(25,5))
        self.btn_process.pack(side=tk.RIGHT, padx=5, pady=5)
        
        self.master.columnconfigure(1, weight=1)

        self.canvas_image.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas_image.bind("<B1-Motion>", self.on_left_drag)
        self.canvas_image.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas_image.bind("<ButtonPress-3>", self.on_middle_press)
        self.canvas_image.bind("<B3-Motion>", self.on_middle_drag)
        self.canvas_image.bind("<ButtonRelease-3>", self.on_middle_release)
        self.canvas_image.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas_image.bind("<Button-4>", self.on_mouse_wheel_linux)
        self.canvas_image.bind("<Button-5>", self.on_mouse_wheel_linux)
        self.master.bind("<Configure>", self.on_window_resize)
        
        self.master.geometry("951x700")
        self.master.minsize(700, 600)
        
        self.master.after(50, lambda: self.update_layout(self.master.winfo_width()))

    def update_layout(self, width):
        threshold = 950
        new_mode = "wide" if width >= threshold else "narrow"
        if new_mode == self.layout_mode:
            return
        self.layout_mode = new_mode
        for widget in self.master.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.grid_forget()

        if self.layout_mode == "wide":
            self.master.columnconfigure(0, weight=0); self.master.columnconfigure(1, weight=1)
            self.master.rowconfigure(0, weight=0); self.master.rowconfigure(1, weight=0)
            self.master.rowconfigure(2, weight=1); self.master.rowconfigure(3, weight=0)
            self.frame_top_controls.grid(row=0, column=0, sticky="nwe", padx=10, pady=(5,0))
            self.frame_roi_mode.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
            self.frame_colors.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 10), pady=5)
            self.frame_image_display.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
            self.frame_actions.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10)
        else:
            self.master.columnconfigure(0, weight=1); self.master.columnconfigure(1, weight=0)
            self.master.rowconfigure(0, weight=0); self.master.rowconfigure(1, weight=0)
            self.master.rowconfigure(2, weight=0); self.master.rowconfigure(3, weight=1)
            self.master.rowconfigure(4, weight=0)
            self.frame_top_controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            self.frame_colors.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            self.frame_roi_mode.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            self.frame_image_display.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
            self.frame_actions.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10)

    def update_display_image_and_roi(self):
        if not self.original_pil_image:
            self.canvas_image.delete("all"); return
        canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            self.master.after(50, self.update_display_image_and_roi); return
        
        bg_color = "lightgray"
        self.display_pil_image = Image.new('RGBA', (canvas_w, canvas_h), bg_color)
        src_x1, src_y1 = self.pan_offset_orig
        src_w, src_h = canvas_w / self.zoom_factor, canvas_h / self.zoom_factor
        src_x2, src_y2 = src_x1 + src_w, src_y1 + src_h
        crop_x1, crop_y1 = max(0, src_x1), max(0, src_y1)
        crop_x2, crop_y2 = min(self.original_pil_image.width, src_x2), min(self.original_pil_image.height, src_y2)

        if crop_x1 < crop_x2 and crop_y1 < crop_y2:
            cropped = self.original_pil_image.crop((int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)))
            paste_x = (crop_x1 - src_x1) * self.zoom_factor
            paste_y = (crop_y1 - src_y1) * self.zoom_factor
            disp_w, disp_h = int(cropped.width * self.zoom_factor), int(cropped.height * self.zoom_factor)
            if disp_w > 0 and disp_h > 0:
                resized = cropped.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
                self.display_pil_image.paste(resized, (int(paste_x), int(paste_y)), resized if resized.mode == 'RGBA' else None)
        
        self.canvas_image.delete("all")
        self.tk_image = ImageTk.PhotoImage(self.display_pil_image)
        self.canvas_image.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
        self.draw_roi_on_canvas()
        self.draw_seed_markers()
        self.update_zoom_label()

    def on_window_resize(self, event=None):
        if event and event.widget == self.master:
            self.update_layout(event.width)
        if self.original_pil_image:
            if self._after_id:
                self.master.after_cancel(self._after_id)
            self._after_id = self.master.after(50, self.update_display_image_and_roi)

    def on_left_press(self, event):
        if not self.original_pil_image: return
        self.drag_start_canvas_coords = (event.x, event.y)
        self.is_defining_roi = False

    def on_left_drag(self, event):
        if not self.drag_start_canvas_coords or not self.original_pil_image: return
        distance = math.hypot(event.x - self.drag_start_canvas_coords[0], event.y - self.drag_start_canvas_coords[1])
        drag_threshold = 3
        if distance < drag_threshold:
            return
            
        if self.roi_mode_var.get() == "floodfill":
            if not self.drag_warning_shown:
                messagebox.showwarning(
                    "操作受限",
                    "您当前处于“扩散填充”模式。如需框选，请先点击“清除选区”切换回默认模式。",
                    parent=self.master
                )
                self.drag_warning_shown = True
            return

        if not self.is_defining_roi:
            if self.flood_fill_seeds:
                self.flood_fill_seeds.clear()
                self.update_roi_mode_buttons_state()
                self.update_display_image_and_roi()

        self.is_defining_roi = True
        
        x1_c, y1_c = self.drag_start_canvas_coords
        x2_c, y2_c = event.x, event.y
        if self.roi_rect_canvas_id:
            self.canvas_image.coords(self.roi_rect_canvas_id, x1_c, y1_c, x2_c, y2_c)
        else:
            self.roi_rect_canvas_id = self.canvas_image.create_rectangle(x1_c, y1_c, x2_c, y2_c, outline="red", dash=(4, 2), width=1.5)

    def clear_all_selections(self):
        self.roi_rect_original = None
        self.flood_fill_seeds.clear()
        self.target_color_rgb = None
        self.lbl_target_color_preview.config(bg="white")
        self.lbl_target_color_rgb.config(text="RGB: (尚未选择)")
        self.roi_mode_var.set("none")
        self.drag_warning_shown = False  # 在这里重置警告标志
        self.update_roi_mode_buttons_state()
        self.update_display_image_and_roi()

    def on_left_release(self, event):
        if not self.original_pil_image: return
        if self.is_defining_roi and self.drag_start_canvas_coords:
            c_x1, c_y1 = self.drag_start_canvas_coords; c_x2, y2_c = event.x, event.y
            orig_x1, orig_y1 = self.canvas_to_original_coords(min(c_x1, c_x2), min(c_y1, y2_c))
            orig_x2, orig_y2 = self.canvas_to_original_coords(max(c_x1, c_x2), max(c_y1, y2_c))
            img_w, img_h = self.original_pil_image.size
            orig_x1,orig_y1 = max(0,min(orig_x1,img_w)), max(0,min(orig_y1,img_h))
            orig_x2,orig_y2 = max(0,min(orig_x2,img_w)), max(0,min(orig_y2,img_h))
            if orig_x2 > orig_x1 + 1 and orig_y2 > orig_y1 + 1:
                self.roi_rect_original = (orig_x1, orig_y1, orig_x2, orig_y2)
                self.roi_mode_var.set("inside")
            else:
                if self.roi_rect_canvas_id:
                    self.canvas_image.delete(self.roi_rect_canvas_id)
                    self.roi_rect_canvas_id = None
            self.update_display_image_and_roi()
        elif not self.is_defining_roi and self.drag_start_canvas_coords:
            click_data = self._get_data_at_canvas_coords(self.drag_start_canvas_coords[0], self.drag_start_canvas_coords[1])
            if click_data:
                if self.roi_rect_original: self.roi_rect_original = None
                (r, g, b), (orig_x, orig_y) = click_data
                new_seed = (int(orig_x), int(orig_y))
                current_mode = self.roi_mode_var.get()
                if current_mode == "floodfill" and self.target_color_rgb is not None:
                    if new_seed not in self.flood_fill_seeds: self.flood_fill_seeds.append(new_seed)
                else:
                    self.target_color_rgb = (r, g, b)
                    self.flood_fill_seeds.clear()
                    self.flood_fill_seeds.append(new_seed)
                    self.lbl_target_color_preview.config(bg=f"#{r:02x}{g:02x}{b:02x}")
                    self.lbl_target_color_rgb.config(text=f"RGB: {(r,g,b)}")
                self.update_display_image_and_roi()
        self.drag_start_canvas_coords = None
        self.is_defining_roi = False
        self.update_roi_mode_buttons_state()

    def clear_all_selections(self):
        self.roi_rect_original = None
        self.flood_fill_seeds.clear()
        self.target_color_rgb = None
        self.lbl_target_color_preview.config(bg="white")
        self.lbl_target_color_rgb.config(text="RGB: (尚未选择)")
        self.roi_mode_var.set("none")
        self.update_roi_mode_buttons_state()
        self.update_display_image_and_roi()

    def update_roi_mode_buttons_state(self, event=None):
        has_roi = self.roi_rect_original is not None
        has_target_color = self.target_color_rgb is not None
        for child in self.frame_roi_mode.winfo_children():
            if isinstance(child, ttk.Radiobutton): 
                mode_value = child.cget("value")
                if mode_value in ["inside", "outside"]: child.config(state=tk.NORMAL if has_roi else tk.DISABLED)
                elif mode_value == "floodfill": child.config(state=tk.NORMAL if has_target_color else tk.DISABLED)
        current_mode = self.roi_mode_var.get()
        if not has_roi and current_mode in ["inside", "outside"]: self.roi_mode_var.set("none")
        if not has_target_color and current_mode == "floodfill": self.roi_mode_var.set("none")
        self.btn_clear_roi.config(state=tk.NORMAL if has_roi or self.flood_fill_seeds else tk.DISABLED)

    def draw_seed_markers(self):
        for marker_id in self.seed_marker_ids: self.canvas_image.delete(marker_id)
        self.seed_marker_ids.clear()
        for seed_orig_x, seed_orig_y in self.flood_fill_seeds:
            cx, cy = self.original_to_canvas_coords(seed_orig_x, seed_orig_y)
            marker1 = self.canvas_image.create_line(cx - 5, cy, cx + 5, cy, fill="blue", width=1.5)
            marker2 = self.canvas_image.create_line(cx, cy - 5, cx, cy + 5, fill="blue", width=1.5)
            self.seed_marker_ids.extend([marker1, marker2])

    def draw_roi_on_canvas(self):
        if self.roi_rect_canvas_id: self.canvas_image.delete(self.roi_rect_canvas_id); self.roi_rect_canvas_id = None
        if self.roi_rect_original:
            ox1, oy1, ox2, oy2 = self.roi_rect_original
            cx1, cy1 = self.original_to_canvas_coords(ox1, oy1); cx2, cy2 = self.original_to_canvas_coords(ox2, oy2)
            self.roi_rect_canvas_id = self.canvas_image.create_rectangle(cx1, cy1, cx2, cy2, outline="red", dash=(4,2), width=1.5) 
    
    def process_image(self):
        if not self.image_path: messagebox.showerror("错误", "请先加载一张图片。"); return
        if not self.target_color_rgb: messagebox.showerror("错误", "请先点击图片选择要替换的目标颜色。"); return
        current_roi_mode = self.roi_mode_var.get()
        if current_roi_mode in ["inside", "outside"] and not self.roi_rect_original: messagebox.showerror("错误", "选择了选区处理模式，但未定义选区。"); return
        if current_roi_mode == "floodfill" and not self.flood_fill_seeds: messagebox.showerror("错误", "使用扩散填充模式前，请至少点击一个起始点。"); return
        try:
            r_rep,g_rep,b_rep,a_rep = int(self.entry_replace_r.get()),int(self.entry_replace_g.get()),int(self.entry_replace_b.get()),int(self.entry_replace_a.get())
            if not all(0 <= v <= 255 for v in [r_rep,g_rep,b_rep,a_rep]): raise ValueError("RGBA值需在0-255间")
            replacement_rgba = (r_rep,g_rep,b_rep,a_rep)
            tolerance = int(self.entry_tolerance.get()); feather = int(self.entry_feather.get())
            if not (0 <= tolerance <=255 and 0 <= feather <=200): raise ValueError("容差和平滑值过大或过小")
        except ValueError as e: messagebox.showerror("输入错误", f"输入参数无效: {e}"); return
        try:
            img_to_process_copy = self.original_pil_image.convert("RGBA")
            datas = list(img_to_process_copy.getdata())
            original_pixel_data = list(datas)
            width, height = img_to_process_copy.size
            r_target, g_target, b_target = self.target_color_rgb
            pixels_to_process_indices = []
            max_dist = tolerance + feather
            if current_roi_mode == "floodfill":
                q = list(self.flood_fill_seeds)
                visited = set(self.flood_fill_seeds)
                head = 0
                while head < len(q):
                    px, py = q[head]; head+=1
                    pixels_to_process_indices.append(py * width + px)
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                            visited.add((nx, ny))
                            nr, ng, nb, _ = original_pixel_data[ny * width + nx]
                            dist = math.hypot(nr - r_target, ng - g_target, nb - b_target)
                            if dist < max_dist: q.append((nx, ny))
            else:
                for i in range(len(datas)):
                    px, py = i % width, i // width
                    should_check = False
                    if current_roi_mode == "none": should_check = True
                    elif self.roi_rect_original:
                        r_x1, r_y1, r_x2, r_y2 = self.roi_rect_original
                        is_inside_roi = (r_x1 <= px < r_x2 and r_y1 <= py < r_y2)
                        if current_roi_mode == "inside" and is_inside_roi: should_check = True
                        elif current_roi_mode == "outside" and not is_inside_roi: should_check = True
                    if should_check: pixels_to_process_indices.append(i)
            for i in pixels_to_process_indices:
                item_r, item_g, item_b, item_a = original_pixel_data[i]
                dist = math.hypot(item_r - r_target, item_g - g_target, item_b - b_target)
                if dist >= max_dist: continue
                blend_ratio = 1.0 if dist < tolerance else (1.0 - ((dist - tolerance) / feather)) if feather > 0 else 0.0
                if blend_ratio > 0:
                    final_r = replacement_rgba[0] * blend_ratio + item_r * (1.0 - blend_ratio)
                    final_g = replacement_rgba[1] * blend_ratio + item_g * (1.0 - blend_ratio)
                    final_b = replacement_rgba[2] * blend_ratio + item_b * (1.0 - blend_ratio)
                    final_a = replacement_rgba[3] * blend_ratio + item_a * (1.0 - blend_ratio)
                    datas[i] = (int(final_r), int(final_g), int(final_b), int(final_a))
            processed_pil_image = Image.new("RGBA", (width, height)); processed_pil_image.putdata(datas)
            self.show_preview_window(processed_pil_image, replacement_rgba[3] < 255)
        except Exception as e:
            messagebox.showerror("处理错误", f"处理图片时发生错误: {e}")

    def _get_data_at_canvas_coords(self, canvas_x, canvas_y):
        if self.original_pil_image:
            orig_x, orig_y = self.canvas_to_original_coords(canvas_x, canvas_y)
            img_w, img_h = self.original_pil_image.size
            if 0 <= orig_x < img_w and 0 <= orig_y < img_h:
                try:
                    img_pick = self.original_pil_image.convert("RGBA")
                    r,g,b,_ = img_pick.getpixel((int(orig_x), int(orig_y)))
                    return (r, g, b), (orig_x, orig_y)
                except Exception as e: messagebox.showerror("错误", f"无法获取像素颜色: {e}")
        return None
        
    def load_image(self, path=None):
        if path is None: path = filedialog.askopenfilename(title="选择图片文件", filetypes=(("常用图片格式", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.tiff;*.tif;*.webp"),("所有文件", "*.*")))
        if path:
            self.image_path = path; self.lbl_image_path.config(text=path.split('/')[-1])
            try:
                self.original_pil_image = Image.open(path)
                canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
                if canvas_w <=1: canvas_w = 500
                if canvas_h <=1: canvas_h = 400 
                orig_w, orig_h = self.original_pil_image.size
                if orig_w == 0 or orig_h == 0: raise ValueError("图片尺寸为零")
                ratio_w, ratio_h = canvas_w / orig_w, canvas_h / orig_h
                self.base_zoom = min(ratio_w, ratio_h, 1.0); self.zoom_factor = self.base_zoom
                self.pan_offset_orig = ((orig_w - (canvas_w / self.zoom_factor)) / 2.0, (orig_h - (canvas_h / self.zoom_factor)) / 2.0)
                self.clamp_pan_offset()
                self.btn_process.config(state=tk.NORMAL)
                self.clear_all_selections()
                self.update_display_image_and_roi()
            except Exception as e:
                messagebox.showerror("错误", f"无法加载图片: {e}")
                self.image_path=None; self.original_pil_image=None; self.clear_all_selections()
                self.lbl_image_path.config(text="加载失败"); self.btn_process.config(state=tk.DISABLED)
                self.update_display_image_and_roi()
    
    def on_middle_press(self, event):
        if not self.original_pil_image: return
        self.last_pan_mouse_canvas = (event.x, event.y); self.is_panning = True; self.canvas_image.config(cursor="fleur")
    
    def on_middle_drag(self, event):
        if not self.is_panning or not self.last_pan_mouse_canvas or not self.original_pil_image: return
        dx_canvas, dy_canvas = event.x - self.last_pan_mouse_canvas[0], event.y - self.last_pan_mouse_canvas[1]
        dx_orig, dy_orig = dx_canvas / self.zoom_factor, dy_canvas / self.zoom_factor
        self.pan_offset_orig = (self.pan_offset_orig[0] - dx_orig, self.pan_offset_orig[1] - dy_orig)
        self.clamp_pan_offset(); self.update_display_image_and_roi()
        self.last_pan_mouse_canvas = (event.x, event.y)
    
    def on_middle_release(self, event):
        self.is_panning = False; self.last_pan_mouse_canvas = None; self.canvas_image.config(cursor="")
    
    def canvas_to_original_coords(self, canvas_x, canvas_y):
        if not self.original_pil_image: return (0,0)
        return (self.pan_offset_orig[0] + (canvas_x / self.zoom_factor), self.pan_offset_orig[1] + (canvas_y / self.zoom_factor))

    def original_to_canvas_coords(self, orig_x, orig_y):
        if not self.original_pil_image: return (0,0)
        return ((orig_x - self.pan_offset_orig[0]) * self.zoom_factor, (orig_y - self.pan_offset_orig[1]) * self.zoom_factor)

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
    
    def update_zoom_label(self):
        self.lbl_zoom_factor.config(text=f"缩放: {self.zoom_factor*100:.1f}%")

    def zoom_at_canvas_point(self, factor_change, canvas_x, canvas_y):
        if not self.original_pil_image: return
        orig_x_at_mouse, orig_y_at_mouse = self.canvas_to_original_coords(canvas_x, canvas_y)
        self.zoom_factor *= factor_change
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, self.zoom_factor))
        self.pan_offset_orig = (orig_x_at_mouse - (canvas_x/self.zoom_factor), orig_y_at_mouse - (canvas_y/self.zoom_factor))
        self.clamp_pan_offset(); self.update_display_image_and_roi(); self.update_zoom_label()

    def zoom_in_center(self):
        if not self.original_pil_image: return
        self.zoom_at_canvas_point(1.2, self.canvas_image.winfo_width()/2, self.canvas_image.winfo_height()/2)

    def zoom_out_center(self):
        if not self.original_pil_image: return
        self.zoom_at_canvas_point(1 / 1.2, self.canvas_image.winfo_width()/2, self.canvas_image.winfo_height()/2)

    def on_mouse_wheel(self, event):
        if not self.original_pil_image: return
        self.zoom_at_canvas_point(1.1 if event.delta > 0 else 1/1.1, event.x, event.y); return "break"

    def on_mouse_wheel_linux(self, event):
        if not self.original_pil_image: return
        self.zoom_at_canvas_point(1.1 if event.num == 4 else 1/1.1, event.x, event.y); return "break"

    def reset_view(self):
        if self.image_path: self.load_image(self.image_path)
    
    def clamp_pan_offset(self):
        if not self.original_pil_image: return
        canvas_w, canvas_h = self.canvas_image.winfo_width(), self.canvas_image.winfo_height()
        if canvas_w == 0 or canvas_h == 0: return
        orig_w, orig_h = self.original_pil_image.size
        viewport_w_orig, viewport_h_orig = canvas_w / self.zoom_factor, canvas_h / self.zoom_factor
        current_pan_x, current_pan_y = self.pan_offset_orig
        new_pan_x = (orig_w-viewport_w_orig)/2.0 if viewport_w_orig >= orig_w else max(0.0, min(current_pan_x, orig_w-viewport_w_orig))
        new_pan_y = (orig_h-viewport_h_orig)/2.0 if viewport_h_orig >= orig_h else max(0.0, min(current_pan_y, orig_h-viewport_h_orig))
        self.pan_offset_orig = (new_pan_x, new_pan_y)

    def _open_with_system_viewer(self, image_to_view):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                image_to_view.save(tmp_file.name, "PNG"); self.temp_preview_file = tmp_file.name
            if self.temp_preview_file:
                system = platform.system()
                if system == "Windows": os.startfile(self.temp_preview_file)
                elif system == "Darwin": subprocess.call(["open", self.temp_preview_file])
                else: subprocess.call(["xdg-open", self.temp_preview_file])
        except Exception as e: messagebox.showerror("打开错误", f"无法使用系统查看器打开图片: {e}", parent=self.master)

    def _cleanup_temp_file(self):
        if self.temp_preview_file and os.path.exists(self.temp_preview_file):
            try: os.remove(self.temp_preview_file); self.temp_preview_file = None
            except Exception as e: print(f"无法删除临时文件 {self.temp_preview_file}: {e}")
        self.temp_preview_file = None

    def show_preview_window(self, processed_image, is_transparent_replacement):
        preview_window = tk.Toplevel(self.master)
        preview_window.title("预览处理结果")
        preview_window.grab_set()
        preview_window.protocol("WM_DELETE_WINDOW", lambda: (self._cleanup_temp_file(), preview_window.destroy()))
        max_preview_w, max_preview_h = 600, 500
        img_w, img_h = processed_image.size
        ratio = min(max_preview_w / img_w, max_preview_h / img_h) if img_w > 0 and img_h > 0 else 1
        display_image_for_preview = processed_image
        if ratio < 1: 
            pw, ph = int(img_w * ratio), int(img_h * ratio)
            if pw > 0 and ph > 0: display_image_for_preview = processed_image.resize((pw, ph), Image.Resampling.LANCZOS)
        final_disp_w, final_disp_h = max(1, display_image_for_preview.width), max(1, display_image_for_preview.height)
        tk_preview_image = ImageTk.PhotoImage(display_image_for_preview)
        canvas_preview = tk.Canvas(preview_window, width=final_disp_w, height=final_disp_h, bg="lightgray")
        canvas_preview.create_image(final_disp_w//2, final_disp_h//2, anchor=tk.CENTER, image=tk_preview_image)
        canvas_preview.image = tk_preview_image 
        canvas_preview.pack(padx=10, pady=10)
        frame_preview_buttons = ttk.Frame(preview_window, padding=(0,5,0,10)); frame_preview_buttons.pack()
        ttk.Button(frame_preview_buttons, text="用系统查看器打开", command=lambda: self._open_with_system_viewer(processed_image)).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_preview_buttons, text="保存图片", command=lambda: self.finalize_save(processed_image, preview_window, is_transparent_replacement)).pack(side=tk.LEFT, padx=10)
        ttk.Button(frame_preview_buttons, text="取消", command=lambda: (self._cleanup_temp_file(), preview_window.destroy())).pack(side=tk.LEFT, padx=10)
        preview_window.resizable(False, False)

    def finalize_save(self, image_to_save, preview_window_instance, is_transparent_replacement):
        self._cleanup_temp_file() 
        output_path = filedialog.asksaveasfilename(title="保存处理后的图片", defaultextension=".png", filetypes=(("PNG 文件", "*.png"), ("所有文件", "*.*")))
        if not output_path: preview_window_instance.focus_set(); return
        if not output_path.lower().endswith(".png") and is_transparent_replacement:
            if not messagebox.askyesno("警告", "您选择了透明替换，但输出文件名不是 .png。\n为保证透明效果，建议使用 .png 格式。\n是否仍要继续？", parent=preview_window_instance):
                preview_window_instance.focus_set(); return
        try:
            image_to_save.save(output_path, "PNG")
            messagebox.showinfo("成功", f"图片已成功处理并保存到:\n{output_path}")
            preview_window_instance.destroy()
        except Exception as e: messagebox.showerror("保存错误", f"保存图片时发生错误: {e}", parent=preview_window_instance)

if __name__ == "__main__":
    root = tk.Tk()
    app = ColorReplacerApp(root)
    root.mainloop()