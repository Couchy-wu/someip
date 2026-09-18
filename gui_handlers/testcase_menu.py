import os
import json
import threading
import traceback
import queue
from tkinter import ttk, messagebox
from gui_handlers.testcase_upload import handle_file_upload, refresh_json_file
from gui_handlers.testcase_delete import delete_test_case

# 主要功能：更新 JSON 文件列表
    # 用于在 Tkinter 界面中管理 test_cases.json：
    # - 上传文件后解析并写入 JSON；
    # - 删除已存在的测试用例；

class FileUpdater:
    # 锁，防止并发读写 test_cases.json
    _json_lock = threading.Lock()
    # 队列，用于把子线程异常传回主线程弹窗（可选）
    _error_queue = queue.Queue()

    def __init__(self, target_folder="TestcaseCollection", json_filename="test_cases.json"):
        self.target_folder = target_folder
        self.json_file = os.path.join(target_folder, json_filename)
        self._start_error_monitor()

    def refresh_file_list(self, menu_var, option_menu):
        """在主线程中安全刷新下拉菜单"""
        try:
            with self._json_lock:
                if os.path.exists(self.json_file):
                    with open(self.json_file, 'r', encoding='utf-8') as f:
                        file_list = json.load(f)
                else:
                    file_list = []
            menu = option_menu['menu']
            menu.delete(0, 'end')
            if file_list:
                for file in file_list:
                    menu.add_command(label=file, command=lambda f=file: menu_var.set(f))
                menu_var.set(file_list[0])
            else:
                menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
                menu_var.set("无文件")
        except Exception as e:
            print(f"刷新下拉菜单时出错：{e}")
            menu = option_menu['menu']
            menu.delete(0, 'end')
            menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
            menu_var.set("无文件")

    def on_upload(self, menu_var, option_menu):
        """异步执行上传和解析，避免阻塞 GUI"""
        uploaded_file = handle_file_upload()          # 主线程弹出文件对话框
        if not uploaded_file:
            print("文件上传失败或用户取消")
            return

        def upload_task():
            try:
                print(f"开始解析测试用例文件：{uploaded_file}")
                with self._json_lock:
                    refresh_json_file(uploaded_file)   # 耗时解析
                print(f"解析完成：{uploaded_file}")
            except Exception:
                self._error_queue.put(traceback.format_exc())
            finally:
                option_menu.after(0, lambda: self.refresh_file_list(menu_var, option_menu))

        threading.Thread(target=upload_task, daemon=True).start()

    def on_delete(self, menu_var, option_menu):
        """删除操作异步执行"""
        def delete_task():
            try:
                delete_test_case()
                with self._json_lock:
                    refresh_json_file()               # 仅更新文件列表
            except Exception:
                self._error_queue.put(traceback.format_exc())
            finally:
                option_menu.after(0, lambda: self.refresh_file_list(menu_var, option_menu))

        threading.Thread(target=delete_task, daemon=True).start()

    def initialize_menu(self, menu_var, option_menu):
        """初始化菜单，可在主线程执行"""
        self.refresh_file_list(menu_var, option_menu)

    # ------------------- 错误监控 -------------------
    def _start_error_monitor(self):
        """使用任意 widget 的 after 循环检查错误队列并弹窗"""
        # 需要外部调用一次，例如：self._error_monitor(option_menu)
        self._error_monitor = lambda widget: self._process_errors(widget)

    def _process_errors(self, widget):
        try:
            err = self._error_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            messagebox.showerror("后台异常", err)
        widget.after(300, lambda: self._process_errors(widget))