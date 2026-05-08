#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPV Player 离线安装包创建工具 (Windows版)
"""

import os
import zipfile
import shutil
from pathlib import Path

def create_offline_package():
    script_dir = Path(__file__).parent.resolve()
    
    print("============================================")
    print("  MPV Player 离线安装包创建工具")
    print("============================================\n")
    
    # 创建临时目录
    temp_dir = script_dir / "temp_offline"
    if temp_dir.exists():
        def handle_remove_readonly(func, path, exc):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    installer_dir = temp_dir / "mpvplayer_installer"
    installer_dir.mkdir(parents=True, exist_ok=True)
    
    print("[1/3] 复制项目文件...")
    
    # 复制目录（跳过videos中的视频文件）
    dirs_to_copy = ["src", "data", "scripts", "models"]
    for dir_name in dirs_to_copy:
        src = script_dir / dir_name
        dst = installer_dir / dir_name
        if src.exists():
            shutil.copytree(src, dst)
            print(f"      复制目录: {dir_name}")
    
    # 复制文件
    files_to_copy = [
        "start_kylin.sh",
        "mpvplayer.service",
        "mpvplayer.desktop",
        "requirements.txt",
        "requirements_ai.txt",
        "install_kylin_deps_v2.sh",
    ]
    
    for file_name in files_to_copy:
        src = script_dir / file_name
        dst = installer_dir / file_name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"      复制文件: {file_name}")
    
    # 复制安装说明
    guide_file = script_dir / "麒麟系统安装指南.md"
    if guide_file.exists():
        shutil.copy2(guide_file, installer_dir / "麒麟系统安装指南.md")
        print("      复制: 麒麟系统安装指南.md")
    
    print("\n[2/3] 打包生成zip文件...")
    
    zip_path = script_dir / "mpvplayer_kylin_offline.zip"
    if zip_path.exists():
        zip_path.unlink()
    
    # 先打包，再清理
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in installer_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(installer_dir)
                zipf.write(file_path, arcname)
    
    print(f"      已生成: mpvplayer_kylin_offline.zip")
    
    print("\n[3/3] 清理临时文件...")
    
    # 清理临时目录（忽略失败）
    def handle_remove_readonly(func, path, exc):
        import stat
        os.chmod(path, stat.S_IWRITE)
        try:
            func(path)
        except:
            pass
    
    try:
        shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
    except:
        pass
    
    print(f"\n============================================")
    print(f"  完成！")
    print(f"  zip文件: {zip_path}")
    print(f"============================================")
    print("\n使用方法：")
    print("1. 将zip文件复制到麒麟系统")
    print("2. 解压后运行: sudo ./install_kylin_deps_v2.sh")
    print("\n按回车键退出...")


if __name__ == "__main__":
    try:
        create_offline_package()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input()
