# -*- coding: utf-8 -*-
"""
Screenshot with Cursor - Capture screen with the actual mouse cursor rendered.
Usage: python screenshot_with_cursor.py [output_path]
"""
import ctypes
import ctypes.wintypes
import sys
from datetime import datetime

from PIL import Image, ImageDraw
try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import mss
except ImportError:
    mss = None

try:
    integer_handle = long
except NameError:
    integer_handle = int


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
HCURSOR = getattr(ctypes.wintypes, "HCURSOR", ctypes.wintypes.HANDLE)
HBITMAP = getattr(ctypes.wintypes, "HBITMAP", ctypes.wintypes.HANDLE)

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
CURSOR_SHOWING = 0x00000001
DI_NORMAL = 0x0003
BI_RGB = 0
DIB_RGB_COLORS = 0


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


_set_dpi_awareness()


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("hCursor", HCURSOR),
        ("ptScreenPos", POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", ctypes.wintypes.BOOL),
        ("xHotspot", ctypes.wintypes.DWORD),
        ("yHotspot", ctypes.wintypes.DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", ctypes.c_ushort),
        ("bmBitsPixel", ctypes.c_ushort),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.wintypes.DWORD * 3),
    ]


def _get_virtual_screen():
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return left, top, width, height


def _delete_gdi_object(handle):
    if handle:
        gdi32.DeleteObject(ctypes.c_void_p(integer_handle(handle)))


def _handle_value(handle):
    return ctypes.c_void_p(integer_handle(handle))


def _get_cursor_info():
    cursor_info = CURSORINFO()
    cursor_info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(cursor_info)):
        raise ctypes.WinError()
    return cursor_info


def _get_bitmap_size(hbitmap):
    bitmap = BITMAP()
    result = gdi32.GetObjectW(_handle_value(hbitmap), ctypes.sizeof(bitmap), ctypes.byref(bitmap))
    if not result:
        raise ctypes.WinError()
    return bitmap.bmWidth, bitmap.bmHeight


def _hbitmap_to_image(hdc, hbitmap, width, height):
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    buffer_len = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_len)
    rows = gdi32.GetDIBits(
        hdc,
        _handle_value(hbitmap),
        0,
        height,
        buffer,
        ctypes.byref(bmi),
        DIB_RGB_COLORS
    )
    if rows != height:
        raise ctypes.WinError()

    return Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)


def _hbitmap_to_mask(hdc, hbitmap, width, height):
    image = _hbitmap_to_image(hdc, hbitmap, width, height)
    return image.split()[0]


def _apply_monochrome_cursor(base_image, mask_image, cursor_x, cursor_y, hotspot_x, hotspot_y, screen_left, screen_top):
    width, full_height = mask_image.size
    height = full_height // 2
    and_mask = mask_image.crop((0, 0, width, height))
    xor_mask = mask_image.crop((0, height, width, full_height))

    base_x = cursor_x - hotspot_x - screen_left
    base_y = cursor_y - hotspot_y - screen_top
    pixels = base_image.load()
    and_pixels = and_mask.load()
    xor_pixels = xor_mask.load()

    for y in range(height):
        target_y = int(base_y + y)
        if target_y < 0 or target_y >= base_image.size[1]:
            continue
        for x in range(width):
            target_x = int(base_x + x)
            if target_x < 0 or target_x >= base_image.size[0]:
                continue

            and_on = and_pixels[x, y] > 127
            xor_on = xor_pixels[x, y] > 127
            r, g, b, a = pixels[target_x, target_y]

            if and_on and not xor_on:
                continue
            if (not and_on) and (not xor_on):
                pixels[target_x, target_y] = (0, 0, 0, 255)
                continue
            if (not and_on) and xor_on:
                pixels[target_x, target_y] = (255, 255, 255, 255)
                continue

            pixels[target_x, target_y] = (255 - r, 255 - g, 255 - b, a)


def _get_cursor_image():
    cursor_info = _get_cursor_info()
    if not (cursor_info.flags & CURSOR_SHOWING):
        return None, None, None

    icon_info = ICONINFO()
    if not user32.GetIconInfo(cursor_info.hCursor, ctypes.byref(icon_info)):
        raise ctypes.WinError()

    hdc = user32.GetDC(None)
    memdc = gdi32.CreateCompatibleDC(hdc)

    try:
        if icon_info.hbmColor:
            width, height = _get_bitmap_size(icon_info.hbmColor)
        else:
            width, height = _get_bitmap_size(icon_info.hbmMask)

        hbitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
        if not hbitmap:
            raise ctypes.WinError()

        old_bitmap = gdi32.SelectObject(memdc, hbitmap)
        try:
            if icon_info.hbmColor:
                if not user32.DrawIconEx(memdc, 0, 0, cursor_info.hCursor, width, height, 0, None, DI_NORMAL):
                    raise ctypes.WinError()
                image = _hbitmap_to_image(memdc, hbitmap, width, height)
                payload = ("color", image)
            else:
                mask_image = _hbitmap_to_mask(hdc, icon_info.hbmMask, width, height)
                payload = ("monochrome", mask_image)
        finally:
            gdi32.SelectObject(memdc, old_bitmap)
            gdi32.DeleteObject(hbitmap)
    finally:
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, hdc)
        if icon_info.hbmColor:
            _delete_gdi_object(icon_info.hbmColor)
        if icon_info.hbmMask:
            _delete_gdi_object(icon_info.hbmMask)

    return payload, cursor_info.ptScreenPos.x, cursor_info.ptScreenPos.y, icon_info.xHotspot, icon_info.yHotspot


def _capture_screen():
    left, top, width, height = _get_virtual_screen()
    if mss is not None:
        with mss.mss() as sct:
            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
            screenshot = sct.grab(monitor)
            image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return image.convert("RGBA"), left, top

    if ImageGrab is not None:
        bbox = (left, top, left + width, top + height)
        return ImageGrab.grab(bbox).convert("RGBA"), left, top

    raise RuntimeError("Missing screenshot backend. Install with 'pip install pillow mss'.")


def _draw_cursor_highlight(image, cursor_x, cursor_y, screen_left, screen_top):
    draw = ImageDraw.Draw(image)
    x = cursor_x - screen_left
    y = cursor_y - screen_top
    outer = 11
    inner = 9
    draw.ellipse((x - outer, y - outer, x + outer, y + outer), outline=(255, 48, 48, 255), width=2)
    draw.ellipse((x - inner, y - inner, x + inner, y + inner), outline=(255, 255, 255, 255), width=1)
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(255, 48, 48, 255))


def screenshot_with_cursor(output_path=None, highlight=True):
    image, screen_left, screen_top = _capture_screen()
    cursor = _get_cursor_image()

    if cursor[0] is not None:
        cursor_payload, cursor_x, cursor_y, hotspot_x, hotspot_y = cursor
        cursor_kind, cursor_data = cursor_payload
        if cursor_kind == "color":
            paste_x = cursor_x - hotspot_x - screen_left
            paste_y = cursor_y - hotspot_y - screen_top
            image.paste(cursor_data, (paste_x, paste_y), cursor_data)
        else:
            _apply_monochrome_cursor(image, cursor_data, cursor_x, cursor_y, hotspot_x, hotspot_y, screen_left, screen_top)
        if highlight:
            _draw_cursor_highlight(image, cursor_x, cursor_y, screen_left, screen_top)
    else:
        cursor_x = None
        cursor_y = None

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = "screenshot_%s.png" % timestamp

    image.save(output_path)
    print("Screenshot saved: %s" % output_path)
    if cursor_x is not None:
        print("Cursor embedded at screen position: X=%d, Y=%d" % (cursor_x, cursor_y))
    else:
        print("Cursor was not visible at capture time.")
    return output_path


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else None
    screenshot_with_cursor(output)
