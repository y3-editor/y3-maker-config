#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在图片上绘制坐标网格，帮助精确定位像素位置。

用法:
    py -3.13 draw_grid.py <input_image> [options]

选项:
    --output, -o     输出文件路径（默认覆盖原图）
    --grid-size, -g  网格间距（默认100像素）
    --offset-x       X轴偏移（用于多显示器，如 -1920）
    --offset-y       Y轴偏移
    --color          网格颜色（默认 red）
    --no-labels      不显示坐标标签
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("错误: 需要安装 Pillow 库")
    print("运行: pip install Pillow")
    sys.exit(1)


def draw_grid(
    input_path: str,
    output_path: str = None,
    grid_size: int = 100,
    offset_x: int = 0,
    offset_y: int = 0,
    color: str = "red",
    show_labels: bool = True,
    label_interval: int = 1,  # 每隔几条线显示标签
):
    """在图片上绘制坐标网格"""
    
    # 加载图片
    img = Image.open(input_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # 尝试加载字体
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        font_candidates = [
            Path(win_dir) / "Fonts" / "msyh.ttc",
            Path(win_dir) / "Fonts" / "arial.ttf",
        ]
        font = None
        for candidate in font_candidates:
            if candidate.exists():
                try:
                    font = ImageFont.truetype(str(candidate), 14)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()
    
    # 网格颜色（半透明效果用不同亮度模拟）
    grid_color = color
    label_color = "white"
    label_bg_color = (0, 0, 0, 180)  # 半透明黑色背景
    
    # 绘制垂直线（X轴）
    line_count = 0
    for pixel_x in range(0, width, grid_size):
        screen_x = pixel_x + offset_x
        
        # 绘制网格线
        draw.line([(pixel_x, 0), (pixel_x, height)], fill=grid_color, width=1)
        
        # 绘制坐标标签
        if show_labels and line_count % label_interval == 0:
            label = str(screen_x)
            # 获取文本边界框
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 绘制标签背景
            label_x = pixel_x + 2
            label_y = 5
            draw.rectangle(
                [label_x - 1, label_y - 1, label_x + text_width + 2, label_y + text_height + 2],
                fill=(0, 0, 0)
            )
            draw.text((label_x, label_y), label, fill=label_color, font=font)
        
        line_count += 1
    
    # 绘制水平线（Y轴）
    line_count = 0
    for pixel_y in range(0, height, grid_size):
        screen_y = pixel_y + offset_y
        
        # 绘制网格线
        draw.line([(0, pixel_y), (width, pixel_y)], fill=grid_color, width=1)
        
        # 绘制坐标标签
        if show_labels and line_count % label_interval == 0 and pixel_y > 20:
            label = str(screen_y)
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 绘制标签背景
            label_x = 5
            label_y = pixel_y + 2
            draw.rectangle(
                [label_x - 1, label_y - 1, label_x + text_width + 2, label_y + text_height + 2],
                fill=(0, 0, 0)
            )
            draw.text((label_x, label_y), label, fill=label_color, font=font)
        
        line_count += 1
    
    # 在原点绘制特殊标记（如果可见）
    origin_pixel_x = -offset_x
    origin_pixel_y = -offset_y
    if 0 <= origin_pixel_x < width and 0 <= origin_pixel_y < height:
        # 绘制原点十字
        cross_size = 20
        draw.line(
            [(origin_pixel_x - cross_size, origin_pixel_y), 
             (origin_pixel_x + cross_size, origin_pixel_y)],
            fill="yellow", width=3
        )
        draw.line(
            [(origin_pixel_x, origin_pixel_y - cross_size), 
             (origin_pixel_x, origin_pixel_y + cross_size)],
            fill="yellow", width=3
        )
        draw.text((origin_pixel_x + 5, origin_pixel_y + 5), "(0,0)", fill="yellow", font=font)
    
    # 保存图片
    if output_path is None:
        output_path = input_path
    
    img.save(output_path)
    print(f"网格已绘制: {output_path}")
    print(f"图片尺寸: {width} x {height}")
    print(f"网格间距: {grid_size}px")
    print(f"坐标偏移: X={offset_x}, Y={offset_y}")
    print(f"屏幕坐标范围: X=[{offset_x}, {offset_x + width}], Y=[{offset_y}, {offset_y + height}]")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="在图片上绘制坐标网格")
    parser.add_argument("input", help="输入图片路径")
    parser.add_argument("-o", "--output", help="输出图片路径（默认覆盖原图）")
    parser.add_argument("-g", "--grid-size", type=int, default=100, help="网格间距（默认100像素）")
    parser.add_argument("--offset-x", type=int, default=0, help="X轴坐标偏移（如 -1920）")
    parser.add_argument("--offset-y", type=int, default=0, help="Y轴坐标偏移")
    parser.add_argument("--color", default="red", help="网格颜色（默认 red）")
    parser.add_argument("--no-labels", action="store_true", help="不显示坐标标签")
    parser.add_argument("--label-interval", type=int, default=1, help="标签显示间隔（默认每条线都显示）")
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"错误: 文件不存在 - {args.input}")
        sys.exit(1)
    
    draw_grid(
        input_path=args.input,
        output_path=args.output,
        grid_size=args.grid_size,
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        color=args.color,
        show_labels=not args.no_labels,
        label_interval=args.label_interval,
    )


if __name__ == "__main__":
    main()
