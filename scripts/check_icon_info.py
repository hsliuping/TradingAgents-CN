#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 .ico 文件的尺寸信息
"""

import struct
import sys
from pathlib import Path

def check_ico_file(ico_path: str):
    """检查 .ico 文件包含的图标尺寸"""
    ico_file = Path(ico_path)
    
    if not ico_file.exists():
        print(f"❌ 文件不存在: {ico_path}")
        return
    
    print(f"📁 文件路径: {ico_path}")
    print(f"📦 文件大小: {ico_file.stat().st_size} 字节")
    print()
    
    try:
        with open(ico_file, 'rb') as f:
            # 读取 ICO 文件头
            # ICO 文件格式：
            # - 2 bytes: Reserved (must be 0)
            # - 2 bytes: Type (1 = ICO, 2 = CUR)
            # - 2 bytes: Number of images
            
            reserved = struct.unpack('<H', f.read(2))[0]
            image_type = struct.unpack('<H', f.read(2))[0]
            num_images = struct.unpack('<H', f.read(2))[0]
            
            print(f"🔍 ICO 文件头信息:")
            print(f"   Reserved: {reserved}")
            print(f"   Type: {image_type} ({'ICO' if image_type == 1 else 'CUR' if image_type == 2 else 'Unknown'})")
            print(f"   图标数量: {num_images}")
            print()
            
            if num_images == 0:
                print("⚠️  警告: 文件中没有图标")
                return
            
            print(f"📐 包含的图标尺寸:")
            print(f"   {'序号':<6} {'宽度':<8} {'高度':<8} {'颜色数':<10} {'数据大小':<12} {'偏移量':<10}")
            print(f"   {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*12} {'-'*10}")
            
            sizes = []
            for i in range(num_images):
                # ICO 目录项格式（16 bytes）:
                # - 1 byte: Width (0 = 256)
                # - 1 byte: Height (0 = 256)
                # - 1 byte: Color palette (0 if no palette)
                # - 1 byte: Reserved (must be 0)
                # - 2 bytes: Color planes (usually 0 or 1)
                # - 2 bytes: Bits per pixel
                # - 4 bytes: Size of image data
                # - 4 bytes: Offset of image data
                
                width = struct.unpack('<B', f.read(1))[0]
                height = struct.unpack('<B', f.read(1))[0]
                color_palette = struct.unpack('<B', f.read(1))[0]
                reserved = struct.unpack('<B', f.read(1))[0]
                color_planes = struct.unpack('<H', f.read(2))[0]
                bits_per_pixel = struct.unpack('<H', f.read(2))[0]
                data_size = struct.unpack('<I', f.read(4))[0]
                data_offset = struct.unpack('<I', f.read(4))[0]
                
                # 处理 0 = 256 的特殊情况
                actual_width = 256 if width == 0 else width
                actual_height = 256 if height == 0 else height
                
                sizes.append({
                    'width': actual_width,
                    'height': actual_height,
                    'bits_per_pixel': bits_per_pixel,
                    'data_size': data_size
                })
                
                print(f"   {i+1:<6} {actual_width:<8} {actual_height:<8} {bits_per_pixel:<10} {data_size:<12} {data_offset:<10}")
            
            print()
            print(f"✅ Icon size summary:")
            unique_sizes = {}
            for size in sizes:
                key = f"{size['width']}x{size['height']}"
                if key not in unique_sizes:
                    unique_sizes[key] = []
                unique_sizes[key].append(size['bits_per_pixel'])
            
            for size_key, bpp_list in sorted(unique_sizes.items()):
                bpp_str = ', '.join(set(str(bpp) for bpp in bpp_list))
                size_key_parts = size_key.split('x')
                matching_count = len([s for s in sizes if s['width'] == int(size_key_parts[0]) and s['height'] == int(size_key_parts[1])])
                print(f"   {size_key} ({matching_count} icon(s), {bpp_str} bpp)")
            
            print()
            print(f"💡 Recommendations:")
            recommended_sizes = [16, 32, 48, 64, 128, 256]
            missing_sizes = []
            for size in recommended_sizes:
                if not any(s['width'] == size and s['height'] == size for s in sizes):
                    missing_sizes.append(size)
            
            if missing_sizes:
                missing_str = ', '.join(f'{s}x{s}' for s in missing_sizes)
                print(f"   ⚠️  Missing recommended sizes: {missing_str}")
                print(f"   💡 Windows shortcuts recommend: 16x16, 32x32, 48x48, 256x256")
            else:
                print(f"   ✅ Contains all recommended sizes")
                
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ico_path = sys.argv[1]
    else:
        # 默认检查便携版目录中的图标
        script_dir = Path(__file__).parent.parent
        ico_path = script_dir / "release" / "TradingAgentsCN-portable" / "frontend" / "dist" / "favicon.ico"
        if not ico_path.exists():
            # 尝试项目根目录
            ico_path = script_dir / "frontend" / "dist" / "favicon.ico"
        if not ico_path.exists():
            # 尝试 public 目录
            ico_path = script_dir / "frontend" / "public" / "favicon.ico"
    
    check_ico_file(str(ico_path))
