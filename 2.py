import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from PIL import Image, ImageTk

class ColorReplacerApp:
    def __init__(self, master):
        self.master = master
        master.title("图片颜色替换工具")

        self.image_path = None
        self.output_path = None
        self.original_pil_image = None # 用于获取像素颜色
        self.display_pil_image = None  # 用于在Tkinter中显示的图片，可能被缩放
        self.tk_image = None

        # --- UI 元素 ---
        # 文件选择
        self.frame_file = tk.LabelFrame(master, text="文件操作", padx=10, pady=10)
        self.frame_file.pack(padx=10, pady=5, fill="x")

        self.btn_load = tk.Button(self.frame_file, text="加载图片", command=self.load_image)
        self.btn_load.pack(side=tk.LEFT, padx=5)

        self.lbl_image_path = tk.Label(self.frame_file, text="未选择图片")
        self.lbl_image_path.pack(side=tk.LEFT, padx=5)

        # 颜色选择与参数设置
        self.frame_colors = tk.LabelFrame(master, text="颜色设置", padx=10, pady=10)
        self.frame_colors.pack(padx=10, pady=5, fill="x")

        # 目标颜色 (通过点击图片选择)
        tk.Label(self.frame_colors, text="目标颜色 (点击图片选择):").grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_target_color_preview = tk.Label(self.frame_colors, text="  ", bg="white", width=3, relief="sunken")
        self.lbl_target_color_preview.grid(row=0, column=1, sticky="w", padx=5)
        self.lbl_target_color_rgb = tk.Label(self.frame_colors, text="RGB: (尚未选择)")
        self.lbl_target_color_rgb.grid(row=0, column=2, sticky="w", padx=5)
        self.target_color_rgb = None

        # 替换颜色 (通过颜色选择器或手动输入)
        tk.Label(self.frame_colors, text="替换颜色:").grid(row=1, column=0, sticky="w", pady=2)
        self.btn_pick_replacement_color = tk.Button(self.frame_colors, text="选择颜色", command=self.pick_replacement_color)
        self.btn_pick_replacement_color.grid(row=1, column=1, sticky="ew", padx=5)
        
        self.lbl_replacement_color_preview = tk.Label(self.frame_colors, text="  ", bg="white", width=3, relief="sunken")
        self.lbl_replacement_color_preview.grid(row=1, column=2, sticky="w", padx=5)

        tk.Label(self.frame_colors, text="R:").grid(row=2, column=0, sticky="e", pady=1)
        self.entry_replace_r = tk.Entry(self.frame_colors, width=5)
        self.entry_replace_r.grid(row=2, column=1, sticky="w", padx=5)
        self.entry_replace_r.insert(0, "0")
        tk.Label(self.frame_colors, text="G:").grid(row=2, column=2, sticky="e", pady=1)
        self.entry_replace_g = tk.Entry(self.frame_colors, width=5)
        self.entry_replace_g.grid(row=2, column=3, sticky="w", padx=5)
        self.entry_replace_g.insert(0, "0")
        tk.Label(self.frame_colors, text="B:").grid(row=3, column=0, sticky="e", pady=1)
        self.entry_replace_b = tk.Entry(self.frame_colors, width=5)
        self.entry_replace_b.grid(row=3, column=1, sticky="w", padx=5)
        self.entry_replace_b.insert(0, "0")
        tk.Label(self.frame_colors, text="透明度 (0-255):").grid(row=3, column=2, sticky="e", pady=1)
        self.entry_replace_a = tk.Entry(self.frame_colors, width=5)
        self.entry_replace_a.grid(row=3, column=3, sticky="w", padx=5)
        self.entry_replace_a.insert(0, "255") # 默认不透明

        self.update_replacement_color_preview() # 初始化预览

        # 容差
        tk.Label(self.frame_colors, text="颜色容差 (0-255):").grid(row=4, column=0, sticky="w", pady=2)
        self.entry_tolerance = tk.Entry(self.frame_colors, width=5)
        self.entry_tolerance.grid(row=4, column=1, sticky="w", padx=5)
        self.entry_tolerance.insert(0, "20") # 默认容差

        # 图片显示区域
        self.frame_image_display = tk.LabelFrame(master, text="图片预览 (点击选择目标颜色)", padx=10, pady=10)
        self.frame_image_display.pack(padx=10, pady=5, fill="both", expand=True)

        self.canvas_image = tk.Canvas(self.frame_image_display, bg="lightgray", width=400, height=300)
        self.canvas_image.pack(fill="both", expand=True)
        self.canvas_image.bind("<Button-1>", self.on_image_click)

        # 操作按钮
        self.frame_actions = tk.Frame(master, padx=10, pady=10)
        self.frame_actions.pack(fill="x")

        self.btn_process = tk.Button(self.frame_actions, text="开始替换并保存", command=self.process_image, state=tk.DISABLED)
        self.btn_process.pack(side=tk.RIGHT, padx=5)
        
        # 绑定Entry变化事件来更新替换颜色预览
        self.entry_replace_r.bind("<KeyRelease>", self.update_replacement_color_preview)
        self.entry_replace_g.bind("<KeyRelease>", self.update_replacement_color_preview)
        self.entry_replace_b.bind("<KeyRelease>", self.update_replacement_color_preview)
        self.entry_replace_a.bind("<KeyRelease>", self.update_replacement_color_preview)


    def pick_replacement_color(self):
        # 打开颜色选择器
        color_code = colorchooser.askcolor(title="选择替换颜色")
        if color_code and color_code[0]: # color_code[0] 是RGB元组, color_code[1] 是十六进制颜色字符串
            r, g, b = color_code[0]
            self.entry_replace_r.delete(0, tk.END)
            self.entry_replace_r.insert(0, str(int(r)))
            self.entry_replace_g.delete(0, tk.END)
            self.entry_replace_g.insert(0, str(int(g)))
            self.entry_replace_b.delete(0, tk.END)
            self.entry_replace_b.insert(0, str(int(b)))
            # Alpha值保持用户输入，或默认为255
            if not self.entry_replace_a.get():
                self.entry_replace_a.insert(0, "255")
            self.update_replacement_color_preview()

    def update_replacement_color_preview(self, event=None):
        try:
            r = int(self.entry_replace_r.get())
            g = int(self.entry_replace_g.get())
            b = int(self.entry_replace_b.get())
            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                self.lbl_replacement_color_preview.config(bg=hex_color)
            else:
                self.lbl_replacement_color_preview.config(bg="white") # 无效则白色
        except ValueError:
            self.lbl_replacement_color_preview.config(bg="white") # 输入非数字则白色


    def load_image(self):
        path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=(("常用图片格式", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.tiff;*.tif;*.webp"),
                       ("JPEG 文件", "*.jpg;*.jpeg"),
                       ("PNG 文件", "*.png"),
                       ("GIF 文件", "*.gif"),
                       ("BMP 文件", "*.bmp"),
                       ("TIFF 文件", "*.tiff;*.tif"),
                       ("WebP 文件", "*.webp"),
                       ("所有文件", "*.*"))
        )
        if path:
            self.image_path = path
            self.lbl_image_path.config(text=path.split('/')[-1]) # 显示文件名
            try:
                self.original_pil_image = Image.open(path)
                
                # --- 调整图片大小以适应Canvas ---
                canvas_width = self.canvas_image.winfo_width()
                canvas_height = self.canvas_image.winfo_height()
                
                # 如果Canvas还未实际绘制，需要给个默认值或更好的处理
                if canvas_width <= 1 or canvas_height <= 1:
                    canvas_width = 400 # 默认值
                    canvas_height = 300 # 默认值

                img_w, img_h = self.original_pil_image.size
                
                # 计算缩放比例，保持宽高比
                ratio = min(canvas_width / img_w, canvas_height / img_h)
                new_w = int(img_w * ratio)
                new_h = int(img_h * ratio)

                # 使用 Image.Resampling.LANCZOS (替代旧的 ANTIALIAS) 进行高质量缩放
                self.display_pil_image = self.original_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self.tk_image = ImageTk.PhotoImage(self.display_pil_image)
                
                self.canvas_image.delete("all") # 清除旧图片
                self.canvas_image.config(width=new_w, height=new_h) # 调整canvas大小
                self.canvas_image.create_image(new_w//2, new_h//2, anchor=tk.CENTER, image=self.tk_image)
                
                self.btn_process.config(state=tk.NORMAL)
                self.target_color_rgb = None # 重置已选目标颜色
                self.lbl_target_color_preview.config(bg="white")
                self.lbl_target_color_rgb.config(text="RGB: (尚未选择)")

            except Exception as e:
                messagebox.showerror("错误", f"无法加载图片: {e}")
                self.image_path = None
                self.original_pil_image = None
                self.display_pil_image = None
                self.tk_image = None
                self.lbl_image_path.config(text="加载失败")
                self.btn_process.config(state=tk.DISABLED)


    def on_image_click(self, event):
        if self.display_pil_image and self.original_pil_image:
            disp_w, disp_h = self.display_pil_image.size
            
            # 点击坐标相对于显示的图片 (因为Canvas已调整为图片大小)
            click_x_on_disp_img = float(event.x)
            click_y_on_disp_img = float(event.y)

            # 确保点击在显示的图片范围内
            if 0 <= click_x_on_disp_img < disp_w and 0 <= click_y_on_disp_img < disp_h:
                original_w, original_h = self.original_pil_image.size
                
                # 计算缩放比例
                scale_x = float(original_w) / disp_w
                scale_y = float(original_h) / disp_h
                
                # 将显示图片的点击坐标转换为原始图片的坐标
                original_x = int(click_x_on_disp_img * scale_x)
                original_y = int(click_y_on_disp_img * scale_y)

                # 再次确保计算出的原始坐标在有效范围内
                original_x = max(0, min(original_x, original_w - 1))
                original_y = max(0, min(original_y, original_h - 1))

                try:
                    # 将原始图片转换为RGBA格式以准确获取像素的R,G,B值，
                    # 这样可以避免因原图是调色板模式(P)或带有Alpha通道时直接转换RGB导致的颜色偏差。
                    img_for_pixel_picking = self.original_pil_image.convert("RGBA")
                    
                    # getpixel 在 RGBA 图片上返回 (R, G, B, A)
                    r, g, b, a_val = img_for_pixel_picking.getpixel((original_x, original_y)) # a_val 存储alpha值，但目标颜色只取RGB
                    
                    # 我们需要的是RGB分量作为目标颜色
                    pixel_color_rgb = (r, g, b)
                    
                    self.target_color_rgb = pixel_color_rgb
                    hex_color = f"#{pixel_color_rgb[0]:02x}{pixel_color_rgb[1]:02x}{pixel_color_rgb[2]:02x}"
                    self.lbl_target_color_preview.config(bg=hex_color)
                    self.lbl_target_color_rgb.config(text=f"RGB: {pixel_color_rgb}")
                except Exception as e:
                    messagebox.showerror("错误", f"无法获取像素颜色: {e}")


    def process_image(self):
        if not self.image_path:
            messagebox.showerror("错误", "请先加载一张图片。")
            return
        if not self.target_color_rgb:
            messagebox.showerror("错误", "请先点击图片选择要替换的目标颜色。")
            return

        try:
            r_replace = int(self.entry_replace_r.get())
            g_replace = int(self.entry_replace_g.get())
            b_replace = int(self.entry_replace_b.get())
            a_replace = int(self.entry_replace_a.get())
            if not all(0 <= val <= 255 for val in [r_replace, g_replace, b_replace, a_replace]):
                raise ValueError("替换颜色的 RGBA 值必须在 0 到 255 之间。")
            replacement_rgba = (r_replace, g_replace, b_replace, a_replace)
        except ValueError as e:
            messagebox.showerror("输入错误", f"替换颜色值无效: {e}")
            return

        try:
            tolerance = int(self.entry_tolerance.get())
            if not (0 <= tolerance <= 255):
                raise ValueError("容差值必须在 0 到 255 之间。")
        except ValueError as e:
            messagebox.showerror("输入错误", f"容差值无效: {e}")
            return

        self.output_path = filedialog.asksaveasfilename(
            title="保存处理后的图片",
            defaultextension=".png",
            filetypes=(("PNG 文件", "*.png"), ("所有文件", "*.*"))
        )

        if not self.output_path:
            return # 用户取消保存

        if not self.output_path.lower().endswith(".png") and replacement_rgba[3] < 255: # replacement_rgba[3] is alpha
            if not messagebox.askyesno("警告", "您选择了透明替换，但输出文件名不是 .png。\n为了保证透明效果，建议使用 .png 格式。\n是否仍要继续？"):
                return

        try:
            img_to_process = Image.open(self.image_path) 
            img_to_process = img_to_process.convert("RGBA") 

            datas = img_to_process.getdata()
            newData = []

            r_target, g_target, b_target = self.target_color_rgb
            
            for item_r, item_g, item_b, item_a in datas: # RGBA
                if (abs(item_r - r_target) <= tolerance and
                    abs(item_g - g_target) <= tolerance and
                    abs(item_b - b_target) <= tolerance):
                    newData.append(replacement_rgba)
                else:
                    newData.append((item_r, item_g, item_b, item_a)) #保留原像素，包括Alpha
            
            img_to_process.putdata(newData)
            img_to_process.save(self.output_path, "PNG")
            messagebox.showinfo("成功", f"图片已成功处理并保存到:\n{self.output_path}")

        except Exception as e:
            messagebox.showerror("处理错误", f"处理图片时发生错误: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ColorReplacerApp(root)
    root.mainloop()
