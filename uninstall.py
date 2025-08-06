import sys
import requests
import tkinter as tk
from tkinter import simpledialog, messagebox
import os

SERVER_URL = "http://172.16.0.106:8888/api/admin_password"

def get_admin_password():
    try:
        response = requests.get(SERVER_URL)
        if response.status_code == 200:
            return response.json().get("password")
    except Exception as e:
        return None

def main():
    root = tk.Tk()
    root.withdraw()

    user_input = simpledialog.askstring("卸载验证", "请输入管理员密码以继续卸载：", show="*")
    if not user_input:
        messagebox.showwarning("操作取消", "未输入密码，卸载已取消。")
        sys.exit(1)

    server_password = get_admin_password()
    if server_password is None:
        messagebox.showerror("错误", "无法连接服务器验证密码。")
        sys.exit(1)

    if user_input == server_password:
        # 验证通过，允许卸载
        sys.exit(0)
    else:
        messagebox.showerror("错误", "管理员密码错误，禁止卸载。")
        sys.exit(1)

if __name__ == "__main__":
    main()

