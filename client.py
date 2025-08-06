import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
import socket
import psutil
import requests
import json
import winreg
import threading
import time
import os
import ctypes
import sys
import base64
import string
from PIL import Image
import pystray
from pystray import MenuItem as item

SERVER_URL = 'http://192.168.1.1:8888/upload'  # 请替换为你的服务器地址

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_config_dir():
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    config_dir = os.path.join(appdata, 'SJHTSwScan')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return config_dir

CONFIG_FILE = os.path.join(get_config_dir(), 'client.json')

def get_machine_name():
    return socket.gethostname()

def get_mac_addresses():
    macs = set()
    for nic, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                mac = addr.address
                if mac and mac != '00:00:00:00:00:00' and len(mac) >= 11:
                    formatted_mac = mac.upper().replace('-', ':')
                    macs.add(formatted_mac)
    return sorted(macs)

def get_installed_programs():
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    programs = []
    for key_path in uninstall_keys:
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            for i in range(winreg.QueryInfoKey(reg_key)[0]):
                try:
                    sub_key_name = winreg.EnumKey(reg_key, i)
                    sub_key = winreg.OpenKey(reg_key, sub_key_name)
                    name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                    version = ""
                    try:
                        version, _ = winreg.QueryValueEx(sub_key, "DisplayVersion")
                    except FileNotFoundError:
                        pass
                    programs.append({"name": name, "version": version})
                    sub_key.Close()
                except Exception:
                    continue
            reg_key.Close()
        except FileNotFoundError:
            continue
    return programs

def get_all_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            drives.append(chr(65 + i) + ":\\")
    return drives

def get_green_software():
    greens = []
    drives = get_all_drives()
    for drive in drives:
        for root, dirs, files in os.walk(drive):
            dirs[:] = [d for d in dirs if d.lower() not in ['windows', 'program files', 'program files (x86)', '$recycle.bin', 'system volume information']]
            for file in files:
                if file.lower().endswith('.exe'):
                    greens.append({"name": os.path.join(root, file), "version": ""})
    return greens

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("非标软件扫描客户端")
        self.geometry("800x600")
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.withdraw()  # 初始隐藏窗口

        self.username = None
        self.load_username()
        self.machine_name = get_machine_name()
        self.macs = get_mac_addresses()
        self.software_list = []

        self.create_widgets()
        self.create_tray_icon()

        if not self.username:
            self.after(100, self.force_set_username)
        else:
            self.after(1000, self.auto_background_work)

    def create_widgets(self):
        self.label_user = tk.Label(self, text=f"姓 名: {self.username if self.username else '未设置'}")
        self.label_user.pack(pady=5)

        self.label_machine = tk.Label(self, text=f"机器名: {self.machine_name}")
        self.label_machine.pack()

        self.label_mac = tk.Label(self, text="MAC地址:\n" + "\n".join(self.macs))
        self.label_mac.pack(pady=5)

        self.text_area = scrolledtext.ScrolledText(self, width=100, height=25)
        self.text_area.pack(pady=10)

        self.btn_scan = tk.Button(self, text="扫描软件", command=self.scan_software)
        self.btn_scan.pack(pady=5)

        self.btn_upload = tk.Button(self, text="上传清单", command=self.upload_data)
        self.btn_upload.pack(pady=5)

        self.btn_set_user = tk.Button(self, text="设置姓名", command=self.set_username)
        self.btn_set_user.pack(pady=5)

        if self.username:
            self.btn_set_user.config(state=tk.DISABLED)

    def load_username(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username", None)
            except Exception:
                pass

    def save_username(self):
        if self.username:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"username": self.username}, f)
            except Exception as e:
                messagebox.showerror("保存失败", f"保存姓名失败：{e}")

    def force_set_username(self):
        self.deiconify()
        while not self.username:
            name = simpledialog.askstring("设置员工名", "请输入员工名（必填）：", parent=self)
            if name and name.strip():
                self.username = name.strip()
                self.save_username()
                self.label_user.config(text=f"姓名: {self.username}")
                self.btn_set_user.config(state=tk.DISABLED)
                break
            else:
                messagebox.showwarning("提示", "姓名不能为空")

        self.scan_software()
        threading.Thread(target=self.auto_upload_with_retry, daemon=True).start()

    def set_username(self):
        messagebox.showinfo("已锁定", "姓名已设置，不能再次修改。")

    def scan_software(self):
        self.text_area.delete(1.0, tk.END)
        installed = get_installed_programs()
        green = get_green_software()
        self.software_list = installed + green

        self.text_area.insert(tk.END, "=== 已安装软件列表 ===\n")
        for s in installed:
            self.text_area.insert(tk.END, f"{s['name']} 版本: {s.get('version','')}\n")

        self.text_area.insert(tk.END, "\n=== 绿色软件（全盘扫描） ===\n")
        for s in green:
            self.text_area.insert(tk.END, f"{s['name']}\n")

    def upload_data(self):
        if not self.username:
            messagebox.showwarning("未设置姓名", "请先设置姓名")
            return
        if not self.software_list:
            messagebox.showwarning("无软件数据", "请先扫描软件")
            return

        data = {
            "username": self.username,
            "hostname": self.machine_name,
            "macs": self.macs,
            "softwares": self.software_list
        }

        try:
            resp = requests.post(SERVER_URL, json=data, timeout=15)
            if resp.status_code == 200:
                messagebox.showinfo("上传成功", "软件清单上传成功")
            else:
                messagebox.showerror("上传失败", f"服务器返回错误: {resp.text}")
        except Exception as e:
            messagebox.showerror("上传失败", f"请求异常: {e}")

    def auto_upload_with_retry(self):
        while True:
            try:
                if not self.software_list:
                    self.scan_software()
                data = {
                    "username": self.username,
                    "hostname": self.machine_name,
                    "macs": self.macs,
                    "softwares": self.software_list
                }
                resp = requests.post(SERVER_URL, json=data, timeout=15)
                if resp.status_code == 200:
                    print("自动上传成功")
                    break
                else:
                    print(f"自动上传失败: {resp.text}")
            except Exception as e:
                print(f"上传异常: {e}")
            time.sleep(30)

    def create_tray_icon(self):
        icon_path = resource_path("app_icon.ico")
        if not os.path.exists(icon_path):
            return

        image = Image.open(icon_path)
        menu = (item('显示窗口', self.show_window), item('退出程序', self.quit_app))
        self.tray_icon = pystray.Icon("swscan", image, "软件扫描", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        self.deiconify()
        self.lift()

    def auto_background_work(self):
        self.scan_software()
        threading.Thread(target=self.auto_upload_with_retry, daemon=True).start()

    def quit_app(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.destroy()

if __name__ == "__main__":
    try:
        import psutil
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "requests"])
        import psutil
        import requests

    app = App()
    app.mainloop()

