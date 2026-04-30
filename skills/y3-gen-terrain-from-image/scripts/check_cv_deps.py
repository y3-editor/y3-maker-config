#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_cv_deps.py
检测 CV 相关 Python 依赖是否已安装。
缺失时自动尝试 pip install，静默完成。

输出 JSON:
  成功: {"status": "ok", "auto_installed": []}
  失败: {"status": "missing", "missing": [...], "install_failed": true}

退出码: 0=全部就绪（已有或自动安装成功）, 1=仍有缺失
"""

import json
import subprocess
import sys


REQUIRED = {
    "opencv-python": "cv2",
    "numpy": "numpy",
}


def check():
    """检测缺失的包，返回缺失的包名列表。"""
    missing = []
    for pkg_name, import_name in REQUIRED.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)
    return missing


def auto_install(packages):
    """尝试自动安装缺失的包，返回仍然失败的包名列表。"""
    still_missing = []
    for pkg in packages:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            still_missing.append(pkg)
    return still_missing


def main():
    missing = check()

    if not missing:
        # 本来就全部就绪
        print(json.dumps({"status": "ok", "auto_installed": []}, ensure_ascii=False))
        sys.exit(0)

    # 有缺失，尝试自动安装
    still_missing = auto_install(missing)

    if still_missing:
        # 自动安装也失败了
        print(json.dumps({
            "status": "missing",
            "missing": still_missing,
            "install_failed": True,
        }, ensure_ascii=False))
        sys.exit(1)

    # 自动安装成功，再验证一次 import
    final_missing = check()
    if final_missing:
        print(json.dumps({
            "status": "missing",
            "missing": final_missing,
            "install_failed": True,
        }, ensure_ascii=False))
        sys.exit(1)

    auto_installed = [p for p in missing if p not in final_missing]
    print(json.dumps({"status": "ok", "auto_installed": auto_installed}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()