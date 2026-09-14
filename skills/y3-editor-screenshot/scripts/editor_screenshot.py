#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Y3 Editor Window Screenshot Tool - Uses only Python stdlib (ctypes)."""

import ctypes
import ctypes.wintypes
import argparse
import os
import sys
import struct
import time
import zlib
from datetime import datetime

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
DWMWA_EXTENDED_FRAME_BOUNDS = 9
PW_RENDERFULLCONTENT = 2

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    dwmapi = ctypes.windll.dwmapi
except OSError:
    dwmapi = None


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]

WINDOW_TARGETS = {
    "main":     ("main",     ["Y3 - "]),
    "object":   ("object",   ["\u7269\u4f53\u7f16\u8f91\u5668"]),
    "ui":       ("ui",       ["\u754c\u9762\u7f16\u8f91\u5668"]),
    "resource": ("resource", ["\u8d44\u6e90\u7ba1\u7406"]),
    "trigger":  ("trigger",  ["\u89e6\u53d1\u5668\u7f16\u8f91\u5668", "ECA"]),
    "scene":    ("scene",    ["\u573a\u666f\u7f16\u8f91\u5668"]),
}

def get_window_title(hwnd):
    length = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    u32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def find_window(target_key):
    keywords = WINDOW_TARGETS[target_key][1]
    results = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def callback(hwnd, lp):
        if not u32.IsWindowVisible(hwnd):
            return True
        title = get_window_title(hwnd)
        if not title:
            return True
        cls = get_window_class(hwnd)
        if "Qt" not in cls:
            return True
        for kw in keywords:
            if kw in title:
                rect = ctypes.wintypes.RECT()
                u32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 10 and h > 10:
                    results.append((hwnd, title, w, h))
                break
        return True
    u32.EnumWindows(WNDENUMPROC(callback), 0)
    if not results:
        return None, None
    results.sort(key=lambda x: x[2] * x[3], reverse=True)
    return results[0][0], results[0][1]

def _save_png(path, width, height, rgba_data):
    def _chunk(ct, data):
        c = ct + data
        crc = zlib.crc32(c) & 0xffffffff
        return struct.pack(chr(62)+chr(73), len(data)) + c + struct.pack(chr(62)+chr(73), crc)
    sig = bytes([0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A])
    ihdr_data = struct.pack(chr(62)+chr(73)*2+chr(66)*5, width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_rows = bytearray()
    stride = width * 4
    for y in range(height):
        raw_rows.append(0)
        raw_rows.extend(rgba_data[y * stride:(y + 1) * stride])
    compressed = zlib.compress(bytes(raw_rows), 9)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")
    with open(path, "wb") as fout:
        fout.write(sig + ihdr + idat + iend)

import sys as _sys
for _p in ["E:/pip_packages", "E:\\pip_packages"]:
    if os.path.isdir(_p) and _p not in _sys.path:
        _sys.path.insert(0, _p)

_wgc_ok = False
try:
    from windows_capture import WindowsCapture as _WC, Frame as _Frame
    from windows_capture import InternalCaptureControl as _ICC
    _wgc_ok = True
except ImportError:
    pass


def _wgc_capture(hwnd, output_path):
    if not _wgc_ok: return False
    try:
        import threading
        cap = _WC(cursor_capture=False, draw_border=None, window_hwnd=int(hwnd))
        evt = threading.Event()
        @cap.event
        def on_frame_arrived(frame, ctrl):
            frame.save_as_image(output_path)
            evt.set()
            ctrl.stop()
        @cap.event
        def on_closed():
            evt.set()
        t = threading.Thread(target=cap.start, daemon=True)
        t.start()
        evt.wait(timeout=5.0)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def _bitblt_capture(hwnd):
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    rect = ctypes.wintypes.RECT()
    got_dwm = False
    if dwmapi:
        hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect), ctypes.sizeof(rect))
        if hr == 0: got_dwm = True
    if not got_dwm:
        u32.GetWindowRect(hwnd, ctypes.byref(rect))
    l,t = rect.left,rect.top
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0: return None
    sdc = u32.GetDC(0)
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    gdi32.BitBlt(mdc, 0, 0, w, h, sdc, l, t, SRCCOPY)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
    gdi32.SelectObject(mdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    u32.ReleaseDC(0, sdc)
    return w, h, bytearray(buf.raw)

def capture_window(hwnd, output_path):
    if _wgc_capture(hwnd, output_path):
        sz = os.path.getsize(output_path)
        print("OK (WGC): " + str(sz) + " bytes -> " + output_path)
        return True
    result = _bitblt_capture(hwnd)
    if result is None:
        print("ERROR: Failed")
        return False
    w, h, bgra = result
    for i in range(0, len(bgra), 4):
        bgra[i], bgra[i+2] = bgra[i+2], bgra[i]
    try:
        _save_png(output_path, w, h, bgra)
        print("OK (BitBlt): " + str(w) + "x" + str(h) + " -> " + output_path)
        return True
    except Exception as e:
        print("ERROR:", e)
        return False


def list_windows():
    print("Scanning for Y3 editor windows...")
    print()
    found_any = False
    for key, (eng_name, _kw) in WINDOW_TARGETS.items():
        hwnd, title = find_window(key)
        if hwnd:
            rect = ctypes.wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            print("  [FOUND] --target", key.ljust(10), str(w)+"x"+str(h), " title=["+title+"]")
            found_any = True
        else:
            print("  [-----] --target", key.ljust(10), "(not found)")
    if not found_any:
        print()
        print("No Y3 editor windows detected.")

def main():
    parser = argparse.ArgumentParser(description="Y3 Editor Screenshot")
    targets_list = list(WINDOW_TARGETS.keys()) + ["all"]
    parser.add_argument("--target", default="main", choices=targets_list)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    if args.list:
        list_windows()
        return

    if args.output_dir:
        out_dir = args.output_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(os.path.dirname(script_dir), "result")

    os.makedirs(out_dir, exist_ok=True)

    if args.target == "all":
        targets = list(WINDOW_TARGETS.keys())
    else:
        targets = [args.target]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    captured = []

    for tk in targets:
        hwnd, title = find_window(tk)
        eng_name = WINDOW_TARGETS[tk][0]
        if not hwnd:
            if args.target != "all":
                print("ERROR: Window not found for ["+tk+"]")
                print("Use --list to see detectable windows.")
            else:
                print("SKIP: ["+tk+"] not found")
            continue
        print("Capturing ["+tk+"] title=["+title+"] ...")
        if args.delay > 0:
            time.sleep(args.delay)
        fn = eng_name + "_" + ts + ".png"
        out_path = os.path.join(out_dir, fn)
        if capture_window(hwnd, out_path):
            captured.append(out_path)

    print()
    if captured:
        print("=== Screenshot Summary ===")
        for p2 in captured:
            print("  " + p2)
        print("Total:", len(captured), "screenshot(s)")
    else:
        print("No screenshots captured.")


if __name__ == "__main__":
    main()
