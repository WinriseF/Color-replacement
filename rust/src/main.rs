#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod image_processing;

use anyhow::{Context, Result};
use eframe::egui::{
    self, Color32, ColorImage, Context as EguiContext, Pos2, Rect, Sense, Stroke, StrokeKind,
    TextureHandle, TextureOptions, Vec2,
};
use image::RgbaImage;
use image_processing::{ProcessOptions, ProcessingMode, SelectionRect, process_image};
use rfd::FileDialog;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

fn main() -> eframe::Result<()> {
    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([951.0, 700.0])
            .with_min_inner_size([700.0, 600.0]),
        ..Default::default()
    };

    eframe::run_native(
        "图片颜色替换工具",
        native_options,
        Box::new(|cc| Ok(Box::new(ColorReplacerApp::new(cc)))),
    )
}

struct ColorReplacerApp {
    image_path: Option<PathBuf>,
    original_image: Option<RgbaImage>,
    texture: Option<TextureHandle>,
    texture_dirty: bool,
    preview: Option<PreviewState>,
    target_rgb: Option<[u8; 3]>,
    replacement_rgba: [u8; 4],
    tolerance: u8,
    feather: u8,
    mode: ProcessingMode,
    selection: Option<SelectionRect>,
    flood_fill_seeds: Vec<(u32, u32)>,
    zoom_factor: f32,
    pan_offset: Vec2,
    needs_fit: bool,
    primary_drag_start: Option<Pos2>,
    selection_drag: Option<(Pos2, Pos2)>,
    status: Option<String>,
    dialog: Option<AppDialog>,
    temp_preview_file: Option<PathBuf>,
    last_canvas_rect: Option<Rect>,
}

struct PreviewState {
    image: RgbaImage,
    texture: Option<TextureHandle>,
    transparent_replacement: bool,
}

enum AppDialog {
    Message { title: String, message: String },
    ConfirmTransparentSave { image: RgbaImage, path: PathBuf },
}

impl ColorReplacerApp {
    fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        Self {
            image_path: None,
            original_image: None,
            texture: None,
            texture_dirty: false,
            preview: None,
            target_rgb: None,
            replacement_rgba: [0, 0, 0, 255],
            tolerance: 20,
            feather: 30,
            mode: ProcessingMode::All,
            selection: None,
            flood_fill_seeds: Vec::new(),
            zoom_factor: 1.0,
            pan_offset: Vec2::ZERO,
            needs_fit: true,
            primary_drag_start: None,
            selection_drag: None,
            status: None,
            dialog: None,
            temp_preview_file: None,
            last_canvas_rect: None,
        }
    }

    fn load_image(&mut self, ctx: &EguiContext, path: &Path) -> Result<()> {
        let image = image::open(path)
            .with_context(|| format!("无法打开图片: {}", path.display()))?
            .to_rgba8();

        self.image_path = Some(path.to_path_buf());
        self.original_image = Some(image);
        self.texture_dirty = true;
        self.texture = None;
        self.preview = None;
        self.clear_all_selections();
        self.needs_fit = true;
        self.status = Some(format!("已加载: {}", display_name(path)));
        ctx.request_repaint();
        Ok(())
    }

    fn clear_all_selections(&mut self) {
        self.selection = None;
        self.flood_fill_seeds.clear();
        self.target_rgb = None;
        self.mode = ProcessingMode::All;
        self.primary_drag_start = None;
        self.selection_drag = None;
    }

    fn ensure_texture(&mut self, ctx: &EguiContext) {
        if !self.texture_dirty {
            return;
        }

        if let Some(image) = &self.original_image {
            let color_image = rgba_to_color_image(image);
            if let Some(texture) = &mut self.texture {
                texture.set(color_image, TextureOptions::LINEAR);
            } else {
                self.texture =
                    Some(ctx.load_texture("loaded-image", color_image, TextureOptions::LINEAR));
            }
        }

        self.texture_dirty = false;
    }

    fn process_current_image(&mut self, ctx: &EguiContext) {
        let Some(source) = &self.original_image else {
            self.show_message("错误", "请先加载一张图片。");
            return;
        };
        let Some(target_rgb) = self.target_rgb else {
            self.show_message("错误", "请先点击图片选择要替换的目标颜色。");
            return;
        };

        if matches!(
            self.mode,
            ProcessingMode::InsideSelection | ProcessingMode::OutsideSelection
        ) && self.selection.is_none()
        {
            self.show_message("错误", "当前处理模式需要先框选区域。");
            return;
        }

        if self.mode == ProcessingMode::FloodFill && self.flood_fill_seeds.is_empty() {
            self.show_message("错误", "扩散填充模式需要至少一个起始点。");
            return;
        }

        let options = ProcessOptions {
            target_rgb,
            replacement_rgba: self.replacement_rgba,
            tolerance: self.tolerance,
            feather: self.feather,
            mode: self.mode,
            selection: self.selection,
            flood_fill_seeds: self.flood_fill_seeds.clone(),
        };

        let processed = process_image(source, &options);
        self.preview = Some(PreviewState {
            image: processed,
            texture: None,
            transparent_replacement: self.replacement_rgba[3] < 255,
        });
        self.status = Some("处理完成，请在预览窗口确认。".to_owned());
        ctx.request_repaint();
    }

    fn apply_preview_as_current(&mut self, ctx: &EguiContext) {
        let Some(preview) = self.preview.take() else {
            return;
        };

        self.original_image = Some(preview.image);
        self.texture_dirty = true;
        self.clear_all_selections();
        self.needs_fit = true;
        self.status = Some("已将处理结果应用到主画布，可以继续编辑。".to_owned());
        ctx.request_repaint();
    }

    fn save_image(&mut self, image: &RgbaImage, transparent_replacement: bool) {
        let Some(path) = FileDialog::new()
            .set_title("保存处理后的图片")
            .add_filter("PNG 文件", &["png"])
            .set_file_name("processed_image.png")
            .save_file()
        else {
            return;
        };

        if transparent_replacement && !path_has_png_extension(&path) {
            self.dialog = Some(AppDialog::ConfirmTransparentSave {
                image: image.clone(),
                path,
            });
            return;
        }

        self.save_image_to_path(image, &path);
    }

    fn save_image_to_path(&mut self, image: &RgbaImage, path: &Path) {
        match image.save_with_format(path, image::ImageFormat::Png) {
            Ok(()) => {
                let message = format!("图片已成功处理并保存到:\n{}", path.display());
                self.status = Some(message.clone());
                self.show_message("成功", &message);
            }
            Err(err) => self.show_message("保存错误", &format!("保存图片时发生错误: {err}")),
        }
    }

    fn open_preview_with_system_viewer(&mut self, image: &RgbaImage) {
        self.cleanup_temp_file();

        let mut path = std::env::temp_dir();
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or_default();
        path.push(format!("color_replacement_preview_{stamp}.png"));

        match image
            .save_with_format(&path, image::ImageFormat::Png)
            .with_context(|| format!("无法写入临时文件: {}", path.display()))
            .and_then(|_| open::that(&path).context("无法打开系统查看器"))
        {
            Ok(()) => {
                self.temp_preview_file = Some(path);
                self.status = Some("已用系统查看器打开预览图。".to_owned());
            }
            Err(err) => self.show_message("打开错误", &format!("{err:#}")),
        }
    }

    fn show_message(&mut self, title: impl Into<String>, message: impl Into<String>) {
        let message = message.into();
        self.status = Some(message.clone());
        self.dialog = Some(AppDialog::Message {
            title: title.into(),
            message,
        });
    }

    fn cleanup_temp_file(&mut self) {
        if let Some(path) = self.temp_preview_file.take() {
            let _ = fs::remove_file(path);
        }
    }

    fn fit_image_to_canvas(&mut self, canvas_size: Vec2) {
        let Some(image) = &self.original_image else {
            return;
        };
        if canvas_size.x <= 1.0 || canvas_size.y <= 1.0 || image.width() == 0 || image.height() == 0
        {
            return;
        }

        let ratio_w = canvas_size.x / image.width() as f32;
        let ratio_h = canvas_size.y / image.height() as f32;
        self.zoom_factor = ratio_w.min(ratio_h).min(1.0).max(0.1);
        self.pan_offset = Vec2::new(
            (image.width() as f32 - canvas_size.x / self.zoom_factor) / 2.0,
            (image.height() as f32 - canvas_size.y / self.zoom_factor) / 2.0,
        );
        self.clamp_pan(canvas_size);
    }

    fn clamp_pan(&mut self, canvas_size: Vec2) {
        let Some(image) = &self.original_image else {
            return;
        };

        let viewport_w = canvas_size.x / self.zoom_factor;
        let viewport_h = canvas_size.y / self.zoom_factor;
        let image_w = image.width() as f32;
        let image_h = image.height() as f32;

        self.pan_offset.x = if viewport_w >= image_w {
            (image_w - viewport_w) / 2.0
        } else {
            self.pan_offset.x.clamp(0.0, image_w - viewport_w)
        };
        self.pan_offset.y = if viewport_h >= image_h {
            (image_h - viewport_h) / 2.0
        } else {
            self.pan_offset.y.clamp(0.0, image_h - viewport_h)
        };
    }

    fn zoom_at(&mut self, canvas_rect: Rect, point: Pos2, factor: f32) {
        if self.original_image.is_none() {
            return;
        }

        let before = self.canvas_to_image_float(canvas_rect, point);
        self.zoom_factor = (self.zoom_factor * factor).clamp(0.1, 10.0);
        self.pan_offset = Vec2::new(
            before.x - (point.x - canvas_rect.left()) / self.zoom_factor,
            before.y - (point.y - canvas_rect.top()) / self.zoom_factor,
        );
        self.clamp_pan(canvas_rect.size());
    }

    fn zoom_canvas_center(&mut self, factor: f32) {
        if let Some(rect) = self.last_canvas_rect {
            self.zoom_at(rect, rect.center(), factor);
        } else {
            self.zoom_factor = (self.zoom_factor * factor).clamp(0.1, 10.0);
        }
    }

    fn canvas_to_image_float(&self, canvas_rect: Rect, point: Pos2) -> Vec2 {
        Vec2::new(
            self.pan_offset.x + (point.x - canvas_rect.left()) / self.zoom_factor,
            self.pan_offset.y + (point.y - canvas_rect.top()) / self.zoom_factor,
        )
    }

    fn canvas_to_image_pixel(&self, canvas_rect: Rect, point: Pos2) -> Option<(u32, u32)> {
        let image = self.original_image.as_ref()?;
        let pos = self.canvas_to_image_float(canvas_rect, point);
        let x = pos.x.floor();
        let y = pos.y.floor();
        if x >= 0.0 && y >= 0.0 && x < image.width() as f32 && y < image.height() as f32 {
            Some((x as u32, y as u32))
        } else {
            None
        }
    }

    fn image_to_canvas(&self, canvas_rect: Rect, x: f32, y: f32) -> Pos2 {
        Pos2::new(
            canvas_rect.left() + (x - self.pan_offset.x) * self.zoom_factor,
            canvas_rect.top() + (y - self.pan_offset.y) * self.zoom_factor,
        )
    }

    fn pick_or_seed(&mut self, canvas_rect: Rect, point: Pos2) {
        let Some((x, y)) = self.canvas_to_image_pixel(canvas_rect, point) else {
            return;
        };
        let Some(image) = &self.original_image else {
            return;
        };

        let pixel = image.get_pixel(x, y).0;
        if self.mode == ProcessingMode::FloodFill && self.target_rgb.is_some() {
            if !self.flood_fill_seeds.contains(&(x, y)) {
                self.flood_fill_seeds.push((x, y));
            }
        } else {
            self.target_rgb = Some([pixel[0], pixel[1], pixel[2]]);
            self.selection = None;
            self.flood_fill_seeds.clear();
            self.flood_fill_seeds.push((x, y));
        }
    }

    fn finish_selection(&mut self, canvas_rect: Rect, start: Pos2, end: Pos2) {
        let Some(image) = &self.original_image else {
            return;
        };

        let a = self.canvas_to_image_float(canvas_rect, start);
        let b = self.canvas_to_image_float(canvas_rect, end);
        let rect = SelectionRect {
            x1: a.x.floor().max(0.0) as u32,
            y1: a.y.floor().max(0.0) as u32,
            x2: b.x.ceil().max(0.0) as u32,
            y2: b.y.ceil().max(0.0) as u32,
        };

        if let Some(rect) = rect.normalized(image.width(), image.height()) {
            self.selection = Some(rect);
            self.flood_fill_seeds.clear();
            self.mode = ProcessingMode::InsideSelection;
        }
    }
}

impl eframe::App for ColorReplacerApp {
    fn update(&mut self, ctx: &EguiContext, _frame: &mut eframe::Frame) {
        self.ensure_texture(ctx);

        egui::TopBottomPanel::top("top_controls").show(ctx, |ui| {
            self.show_top_controls(ui, ctx);
        });

        egui::SidePanel::left("settings")
            .resizable(false)
            .default_width(280.0)
            .show(ctx, |ui| self.show_settings(ui, ctx));

        egui::CentralPanel::default().show(ctx, |ui| {
            self.show_canvas(ui, ctx);
        });

        self.show_preview_window(ctx);
        self.show_dialog_window(ctx);
    }
}

impl ColorReplacerApp {
    fn show_top_controls(&mut self, ui: &mut egui::Ui, ctx: &EguiContext) {
        ui.horizontal_wrapped(|ui| {
            if ui.button("加载图片").clicked() {
                if let Some(path) = FileDialog::new()
                    .set_title("选择图片文件")
                    .add_filter(
                        "常用图片格式",
                        &["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp"],
                    )
                    .pick_file()
                {
                    if let Err(err) = self.load_image(ctx, &path) {
                        self.show_message("错误", format!("{err:#}"));
                    }
                }
            }

            if ui.button("+").clicked() {
                self.zoom_canvas_center(1.2);
            }
            if ui.button("-").clicked() {
                self.zoom_canvas_center(1.0 / 1.2);
            }
            if ui.button("重置视图").clicked() {
                self.needs_fit = true;
            }
            ui.label(format!("缩放: {:.1}%", self.zoom_factor * 100.0));

            if let Some(path) = &self.image_path {
                ui.separator();
                ui.label(display_name(path));
            } else {
                ui.separator();
                ui.label("未选择图片");
            }
        });
    }

    fn show_settings(&mut self, ui: &mut egui::Ui, ctx: &EguiContext) {
        ui.heading("颜色与参数");
        ui.add_space(8.0);

        ui.horizontal(|ui| {
            ui.label("目标颜色:");
            color_swatch(ui, self.target_rgb.map(|rgb| [rgb[0], rgb[1], rgb[2], 255]));
        });
        if let Some(rgb) = self.target_rgb {
            ui.label(format!("RGB: ({}, {}, {})", rgb[0], rgb[1], rgb[2]));
        } else {
            ui.label("RGB: 尚未选择");
        }

        ui.separator();
        ui.label("替换颜色:");
        ui.horizontal(|ui| {
            let mut color = Color32::from_rgba_unmultiplied(
                self.replacement_rgba[0],
                self.replacement_rgba[1],
                self.replacement_rgba[2],
                self.replacement_rgba[3],
            );
            if ui.color_edit_button_srgba(&mut color).changed() {
                self.replacement_rgba = [color.r(), color.g(), color.b(), color.a()];
            }
            ui.label("选择");
        });
        ui.horizontal(|ui| {
            ui.label("R");
            ui.add(egui::DragValue::new(&mut self.replacement_rgba[0]).range(0..=255));
            ui.label("G");
            ui.add(egui::DragValue::new(&mut self.replacement_rgba[1]).range(0..=255));
        });
        ui.horizontal(|ui| {
            ui.label("B");
            ui.add(egui::DragValue::new(&mut self.replacement_rgba[2]).range(0..=255));
            ui.label("A");
            ui.add(egui::DragValue::new(&mut self.replacement_rgba[3]).range(0..=255));
            color_swatch(ui, Some(self.replacement_rgba));
        });

        ui.add_space(6.0);
        ui.horizontal(|ui| {
            ui.label("颜色容差");
            ui.add(egui::DragValue::new(&mut self.tolerance).range(0..=255));
        });
        ui.horizontal(|ui| {
            ui.label("边缘平滑");
            ui.add(egui::DragValue::new(&mut self.feather).range(0..=200));
        });

        ui.separator();
        ui.heading("处理模式");
        ui.radio_value(&mut self.mode, ProcessingMode::All, "替换整张图片");
        ui.add_enabled_ui(self.selection.is_some(), |ui| {
            ui.radio_value(
                &mut self.mode,
                ProcessingMode::InsideSelection,
                "仅替换选区内颜色",
            );
            ui.radio_value(
                &mut self.mode,
                ProcessingMode::OutsideSelection,
                "替换选区外颜色",
            );
        });
        ui.add_enabled_ui(self.target_rgb.is_some(), |ui| {
            ui.radio_value(&mut self.mode, ProcessingMode::FloodFill, "扩散填充");
        });

        if ui.button("清除选区/种子/目标色").clicked() {
            self.clear_all_selections();
        }

        ui.separator();
        if ui
            .add_enabled(
                self.original_image.is_some(),
                egui::Button::new("处理并预览"),
            )
            .clicked()
        {
            self.process_current_image(ctx);
        }

        if let Some(status) = &self.status {
            ui.separator();
            ui.label(status);
        }
    }

    fn show_canvas(&mut self, ui: &mut egui::Ui, ctx: &EguiContext) {
        let available = ui.available_size().max(Vec2::new(300.0, 260.0));
        let (rect, response) = ui.allocate_exact_size(available, Sense::click_and_drag());
        self.last_canvas_rect = Some(rect);
        let painter = ui.painter_at(rect);
        painter.rect_filled(rect, 0.0, Color32::from_gray(214));

        if self.needs_fit {
            self.fit_image_to_canvas(rect.size());
            self.needs_fit = false;
        }

        let Some(texture_id) = self.texture.as_ref().map(|texture| texture.id()) else {
            painter.text(
                rect.center(),
                egui::Align2::CENTER_CENTER,
                "加载图片后开始编辑",
                egui::FontId::proportional(18.0),
                Color32::from_gray(80),
            );
            return;
        };

        if response.hovered() {
            let scroll = ui.input(|input| input.raw_scroll_delta.y);
            if scroll.abs() > 0.0 {
                let pointer = ui
                    .input(|input| input.pointer.hover_pos())
                    .unwrap_or(rect.center());
                self.zoom_at(rect, pointer, if scroll > 0.0 { 1.1 } else { 1.0 / 1.1 });
                ctx.request_repaint();
            }
        }

        if response.dragged_by(egui::PointerButton::Secondary)
            || response.dragged_by(egui::PointerButton::Middle)
        {
            let delta = ui.input(|input| input.pointer.delta());
            self.pan_offset -= delta / self.zoom_factor;
            self.clamp_pan(rect.size());
            ctx.request_repaint();
        }

        if response.drag_started_by(egui::PointerButton::Primary) {
            self.primary_drag_start = response.interact_pointer_pos();
            self.selection_drag = None;
        }

        if response.dragged_by(egui::PointerButton::Primary) {
            if let (Some(start), Some(current)) =
                (self.primary_drag_start, response.interact_pointer_pos())
            {
                if start.distance(current) > 3.0 {
                    if self.mode == ProcessingMode::FloodFill {
                        self.status = Some(
                            "扩散填充模式下点击添加种子点；如需框选请先切换处理模式。".to_owned(),
                        );
                    } else {
                        self.selection_drag = Some((start, current));
                    }
                }
            }
        }

        if response.drag_stopped_by(egui::PointerButton::Primary) {
            if let (Some(start), Some(end)) = (
                self.primary_drag_start.take(),
                response.interact_pointer_pos(),
            ) {
                if start.distance(end) > 3.0 && self.mode != ProcessingMode::FloodFill {
                    self.finish_selection(rect, start, end);
                } else {
                    self.pick_or_seed(rect, start);
                }
            }
            self.selection_drag = None;
        } else if response.clicked_by(egui::PointerButton::Primary) {
            if let Some(pos) = response.interact_pointer_pos() {
                self.pick_or_seed(rect, pos);
            }
        }

        let Some(image) = &self.original_image else {
            return;
        };

        let image_min = Pos2::new(
            rect.left() - self.pan_offset.x * self.zoom_factor,
            rect.top() - self.pan_offset.y * self.zoom_factor,
        );
        let image_size = Vec2::new(
            image.width() as f32 * self.zoom_factor,
            image.height() as f32 * self.zoom_factor,
        );
        let image_rect = Rect::from_min_size(image_min, image_size);
        painter.image(
            texture_id,
            image_rect,
            Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)),
            Color32::WHITE,
        );

        if let Some(selection) = self.selection {
            let min = self.image_to_canvas(rect, selection.x1 as f32, selection.y1 as f32);
            let max = self.image_to_canvas(rect, selection.x2 as f32, selection.y2 as f32);
            painter.rect_stroke(
                Rect::from_min_max(min, max),
                0.0,
                Stroke::new(1.5, Color32::RED),
                StrokeKind::Inside,
            );
        }

        if let Some((start, current)) = self.selection_drag {
            painter.rect_stroke(
                Rect::from_two_pos(start, current),
                0.0,
                Stroke::new(1.5, Color32::RED),
                StrokeKind::Inside,
            );
        }

        for &(x, y) in &self.flood_fill_seeds {
            let center = self.image_to_canvas(rect, x as f32, y as f32);
            painter.line_segment(
                [center + Vec2::new(-5.0, 0.0), center + Vec2::new(5.0, 0.0)],
                Stroke::new(1.5, Color32::BLUE),
            );
            painter.line_segment(
                [center + Vec2::new(0.0, -5.0), center + Vec2::new(0.0, 5.0)],
                Stroke::new(1.5, Color32::BLUE),
            );
        }
    }

    fn show_preview_window(&mut self, ctx: &EguiContext) {
        let Some(preview) = &mut self.preview else {
            return;
        };

        if preview.texture.is_none() {
            preview.texture = Some(ctx.load_texture(
                "processed-preview",
                rgba_to_color_image(&preview.image),
                TextureOptions::LINEAR,
            ));
        }

        let mut action = PreviewAction::None;
        let mut open_window = true;
        egui::Window::new("预览处理结果")
            .open(&mut open_window)
            .collapsible(false)
            .show(ctx, |ui| {
                let Some(texture) = &preview.texture else {
                    return;
                };

                let max_size = Vec2::new(600.0, 500.0);
                let image_size =
                    Vec2::new(preview.image.width() as f32, preview.image.height() as f32);
                let scale = (max_size.x / image_size.x)
                    .min(max_size.y / image_size.y)
                    .min(1.0)
                    .max(0.01);
                ui.image((texture.id(), image_size * scale));

                ui.horizontal(|ui| {
                    if ui.button("以此图继续编辑").clicked() {
                        action = PreviewAction::Apply;
                    }
                    if ui.button("用系统查看器打开").clicked() {
                        action = PreviewAction::OpenExternal;
                    }
                    if ui.button("保存图片").clicked() {
                        action = PreviewAction::Save;
                    }
                    if ui.button("取消").clicked() {
                        action = PreviewAction::Close;
                    }
                });
            });

        if !open_window {
            action = PreviewAction::Close;
        }

        match action {
            PreviewAction::None => {}
            PreviewAction::Apply => self.apply_preview_as_current(ctx),
            PreviewAction::OpenExternal => {
                if let Some(image) = self.preview.as_ref().map(|preview| preview.image.clone()) {
                    self.open_preview_with_system_viewer(&image);
                }
            }
            PreviewAction::Save => {
                if let Some((image, transparent)) = self
                    .preview
                    .as_ref()
                    .map(|preview| (preview.image.clone(), preview.transparent_replacement))
                {
                    self.save_image(&image, transparent);
                }
            }
            PreviewAction::Close => {
                self.cleanup_temp_file();
                self.preview = None;
            }
        }
    }

    fn show_dialog_window(&mut self, ctx: &EguiContext) {
        let Some(dialog) = self.dialog.take() else {
            return;
        };

        match dialog {
            AppDialog::Message { title, message } => {
                let mut keep_open = true;
                let mut close = false;
                egui::Window::new(&title)
                    .open(&mut keep_open)
                    .collapsible(false)
                    .resizable(false)
                    .show(ctx, |ui| {
                        ui.label(message.as_str());
                        ui.add_space(8.0);
                        ui.horizontal(|ui| {
                            if ui.button("确定").clicked() {
                                close = true;
                            }
                        });
                    });

                if keep_open && !close {
                    self.dialog = Some(AppDialog::Message { title, message });
                }
            }
            AppDialog::ConfirmTransparentSave { image, path } => {
                let mut keep_open = true;
                let mut decision = SaveDecision::Wait;
                egui::Window::new("警告")
                    .open(&mut keep_open)
                    .collapsible(false)
                    .resizable(false)
                    .show(ctx, |ui| {
                        ui.label(
                            "您选择了透明替换，但输出文件名不是 .png。\n为保证透明效果，建议使用 .png 格式。\n是否仍要继续？",
                        );
                        ui.add_space(8.0);
                        ui.horizontal(|ui| {
                            if ui.button("继续").clicked() {
                                decision = SaveDecision::Continue;
                            }
                            if ui.button("取消").clicked() {
                                decision = SaveDecision::Cancel;
                            }
                        });
                    });

                match decision {
                    SaveDecision::Wait if keep_open => {
                        self.dialog = Some(AppDialog::ConfirmTransparentSave { image, path });
                    }
                    SaveDecision::Continue => self.save_image_to_path(&image, &path),
                    SaveDecision::Cancel | SaveDecision::Wait => {}
                }
            }
        }
    }
}

enum PreviewAction {
    None,
    Apply,
    OpenExternal,
    Save,
    Close,
}

enum SaveDecision {
    Wait,
    Continue,
    Cancel,
}

fn rgba_to_color_image(image: &RgbaImage) -> ColorImage {
    ColorImage::from_rgba_unmultiplied(
        [image.width() as usize, image.height() as usize],
        image.as_raw(),
    )
}

fn color_swatch(ui: &mut egui::Ui, color: Option<[u8; 4]>) {
    let (rect, _) = ui.allocate_exact_size(Vec2::new(32.0, 18.0), Sense::hover());
    let fill = color
        .map(|rgba| Color32::from_rgba_unmultiplied(rgba[0], rgba[1], rgba[2], rgba[3]))
        .unwrap_or(Color32::WHITE);
    ui.painter().rect_filled(rect, 2.0, fill);
    ui.painter().rect_stroke(
        rect,
        2.0,
        Stroke::new(1.0, Color32::from_gray(80)),
        StrokeKind::Inside,
    );
}

fn display_name(path: &Path) -> String {
    path.file_name()
        .and_then(|name| name.to_str())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| path.display().to_string())
}

fn path_has_png_extension(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .is_some_and(|extension| extension.eq_ignore_ascii_case("png"))
}
