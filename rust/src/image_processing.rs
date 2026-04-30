use image::{Rgba, RgbaImage};
use std::collections::VecDeque;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProcessingMode {
    All,
    InsideSelection,
    OutsideSelection,
    FloodFill,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SelectionRect {
    pub x1: u32,
    pub y1: u32,
    pub x2: u32,
    pub y2: u32,
}

impl SelectionRect {
    pub fn normalized(mut self, width: u32, height: u32) -> Option<Self> {
        if self.x1 > self.x2 {
            std::mem::swap(&mut self.x1, &mut self.x2);
        }
        if self.y1 > self.y2 {
            std::mem::swap(&mut self.y1, &mut self.y2);
        }

        self.x1 = self.x1.min(width);
        self.x2 = self.x2.min(width);
        self.y1 = self.y1.min(height);
        self.y2 = self.y2.min(height);

        (self.x2 > self.x1 + 1 && self.y2 > self.y1 + 1).then_some(self)
    }

    pub fn contains(self, x: u32, y: u32) -> bool {
        self.x1 <= x && x < self.x2 && self.y1 <= y && y < self.y2
    }
}

#[derive(Clone, Debug)]
pub struct ProcessOptions {
    pub target_rgb: [u8; 3],
    pub replacement_rgba: [u8; 4],
    pub tolerance: u8,
    pub feather: u8,
    pub mode: ProcessingMode,
    pub selection: Option<SelectionRect>,
    pub flood_fill_seeds: Vec<(u32, u32)>,
}

pub fn process_image(source: &RgbaImage, options: &ProcessOptions) -> RgbaImage {
    let (width, height) = source.dimensions();
    let mut output = source.clone();
    let max_dist = f32::from(options.tolerance) + f32::from(options.feather);

    match options.mode {
        ProcessingMode::FloodFill => {
            for index in flood_fill_indices(source, options, max_dist) {
                blend_pixel(index, source, &mut output, options, max_dist);
            }
        }
        ProcessingMode::All
        | ProcessingMode::InsideSelection
        | ProcessingMode::OutsideSelection => {
            for y in 0..height {
                for x in 0..width {
                    if should_process_position(x, y, options) {
                        let index = (y * width + x) as usize;
                        blend_pixel(index, source, &mut output, options, max_dist);
                    }
                }
            }
        }
    }

    output
}

fn should_process_position(x: u32, y: u32, options: &ProcessOptions) -> bool {
    match options.mode {
        ProcessingMode::All => true,
        ProcessingMode::InsideSelection => {
            options.selection.is_some_and(|rect| rect.contains(x, y))
        }
        ProcessingMode::OutsideSelection => {
            options.selection.is_some_and(|rect| !rect.contains(x, y))
        }
        ProcessingMode::FloodFill => false,
    }
}

fn flood_fill_indices(source: &RgbaImage, options: &ProcessOptions, max_dist: f32) -> Vec<usize> {
    let (width, height) = source.dimensions();
    let mut visited = vec![false; (width * height) as usize];
    let mut queue = VecDeque::new();
    let mut indices = Vec::new();

    for &(x, y) in &options.flood_fill_seeds {
        if x < width && y < height {
            let index = (y * width + x) as usize;
            if !visited[index] {
                visited[index] = true;
                queue.push_back((x, y));
            }
        }
    }

    while let Some((x, y)) = queue.pop_front() {
        indices.push((y * width + x) as usize);

        for (nx, ny) in neighbors4(x, y, width, height) {
            let next_index = (ny * width + nx) as usize;
            if visited[next_index] {
                continue;
            }

            visited[next_index] = true;
            let pixel = source.get_pixel(nx, ny).0;
            if rgb_distance(pixel, options.target_rgb) < max_dist {
                queue.push_back((nx, ny));
            }
        }
    }

    indices
}

fn neighbors4(x: u32, y: u32, width: u32, height: u32) -> impl Iterator<Item = (u32, u32)> {
    let mut neighbors = [(u32::MAX, u32::MAX); 4];
    let mut count = 0;

    if y + 1 < height {
        neighbors[count] = (x, y + 1);
        count += 1;
    }
    if y > 0 {
        neighbors[count] = (x, y - 1);
        count += 1;
    }
    if x + 1 < width {
        neighbors[count] = (x + 1, y);
        count += 1;
    }
    if x > 0 {
        neighbors[count] = (x - 1, y);
        count += 1;
    }

    neighbors.into_iter().take(count)
}

fn blend_pixel(
    index: usize,
    source: &RgbaImage,
    output: &mut RgbaImage,
    options: &ProcessOptions,
    max_dist: f32,
) {
    let pixel = source.as_raw()[index * 4..index * 4 + 4]
        .try_into()
        .unwrap();
    let dist = rgb_distance(pixel, options.target_rgb);
    if dist >= max_dist {
        return;
    }

    let blend_ratio = if dist < f32::from(options.tolerance) {
        1.0
    } else if options.feather > 0 {
        1.0 - ((dist - f32::from(options.tolerance)) / f32::from(options.feather))
    } else {
        0.0
    };

    if blend_ratio <= 0.0 {
        return;
    }

    let replacement = options.replacement_rgba;
    let blended = [
        blend_channel(replacement[0], pixel[0], blend_ratio),
        blend_channel(replacement[1], pixel[1], blend_ratio),
        blend_channel(replacement[2], pixel[2], blend_ratio),
        blend_channel(replacement[3], pixel[3], blend_ratio),
    ];
    let width = source.width() as usize;
    let x = (index % width) as u32;
    let y = (index / width) as u32;
    output.put_pixel(x, y, Rgba(blended));
}

fn blend_channel(replacement: u8, original: u8, ratio: f32) -> u8 {
    ((f32::from(replacement) * ratio) + (f32::from(original) * (1.0 - ratio))) as u8
}

fn rgb_distance(pixel: [u8; 4], target: [u8; 3]) -> f32 {
    let dr = f32::from(pixel[0]) - f32::from(target[0]);
    let dg = f32::from(pixel[1]) - f32::from(target[1]);
    let db = f32::from(pixel[2]) - f32::from(target[2]);
    (dr * dr + dg * dg + db * db).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn options(mode: ProcessingMode) -> ProcessOptions {
        ProcessOptions {
            target_rgb: [10, 10, 10],
            replacement_rgba: [110, 120, 130, 0],
            tolerance: 5,
            feather: 0,
            mode,
            selection: None,
            flood_fill_seeds: Vec::new(),
        }
    }

    #[test]
    fn replaces_matching_pixels_across_whole_image() {
        let image = RgbaImage::from_vec(2, 1, vec![10, 10, 10, 255, 80, 80, 80, 255]).unwrap();

        let result = process_image(&image, &options(ProcessingMode::All));

        assert_eq!(result.get_pixel(0, 0).0, [110, 120, 130, 0]);
        assert_eq!(result.get_pixel(1, 0).0, [80, 80, 80, 255]);
    }

    #[test]
    fn feather_blends_pixels_in_falloff_range() {
        let image = RgbaImage::from_vec(1, 1, vec![20, 10, 10, 200]).unwrap();
        let mut opts = options(ProcessingMode::All);
        opts.tolerance = 5;
        opts.feather = 10;

        let result = process_image(&image, &opts);

        assert_eq!(result.get_pixel(0, 0).0, [65, 65, 70, 100]);
    }

    #[test]
    fn limits_processing_to_selection_inside() {
        let image = RgbaImage::from_vec(
            3,
            1,
            vec![10, 10, 10, 255, 10, 10, 10, 255, 10, 10, 10, 255],
        )
        .unwrap();
        let mut opts = options(ProcessingMode::InsideSelection);
        opts.selection = Some(SelectionRect {
            x1: 1,
            y1: 0,
            x2: 3,
            y2: 1,
        });

        let result = process_image(&image, &opts);

        assert_eq!(result.get_pixel(0, 0).0, [10, 10, 10, 255]);
        assert_eq!(result.get_pixel(1, 0).0, [110, 120, 130, 0]);
        assert_eq!(result.get_pixel(2, 0).0, [110, 120, 130, 0]);
    }

    #[test]
    fn flood_fill_stops_at_non_matching_barrier() {
        let image = RgbaImage::from_vec(
            3,
            1,
            vec![10, 10, 10, 255, 80, 80, 80, 255, 10, 10, 10, 255],
        )
        .unwrap();
        let mut opts = options(ProcessingMode::FloodFill);
        opts.flood_fill_seeds = vec![(0, 0)];

        let result = process_image(&image, &opts);

        assert_eq!(result.get_pixel(0, 0).0, [110, 120, 130, 0]);
        assert_eq!(result.get_pixel(1, 0).0, [80, 80, 80, 255]);
        assert_eq!(result.get_pixel(2, 0).0, [10, 10, 10, 255]);
    }
}
