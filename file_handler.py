import os
import shutil
from tkinter import filedialog, messagebox
import json
import pandas as pd  # 用于解析 Excel 文件

# 函数：上传测试用例 Excel 文件
def handle_file_upload():
    # 打开文件选择对话框
    file_path = filedialog.askopenfilename(
        title="选择Excel文件（此步骤请不要更改文件名）",
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )

    if file_path:
        # 指定目标文件夹路径
        target_folder = os.path.join(os.getcwd(), "测试用例集")
        # 创建目标文件夹（如果不存在）
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        # 获取文件名
        file_name = os.path.basename(file_path)
        # 弹出对话框允许用户输入新的文件名
        new_file_name = filedialog.asksaveasfilename(
            initialdir=target_folder,
            initialfile=file_name,
            title="请重新命名",
            filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
        )
        if new_file_name:
            target_path = os.path.normpath(new_file_name)
            if target_path == os.path.normpath(file_path):
                messagebox.showerror("错误", "目标路径与原文件路径相同，请选择不同的位置")
                return None
            target_folder = os.path.dirname(target_path)
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            if os.path.basename(new_file_name) in os.listdir(target_folder):
                messagebox.showerror("错误", "文件名称重复，无法上传")
                return None
            if not os.path.basename(target_path):
                messagebox.showerror("错误", "文件名不能为空")
                return None
            try:
                shutil.copy(file_path, target_path)
                print(f"文件已复制到：{target_path}")
                messagebox.showinfo("成功", "文件已成功上传")
                return os.path.basename(target_path)
            except Exception as e:
                messagebox.showerror("错误", f"文件上传失败：{str(e)}")
                return None
    return None

# 函数：更新 JSON 文件
def refresh_json_file(uploaded_file=None):
    target_folder = os.path.join(os.getcwd(), "测试用例集")
    json_file = os.path.join(target_folder, "test_cases.json")
    file_list = []

    if uploaded_file:
        file_list.append(uploaded_file)
    else:
        for file in os.listdir(target_folder):
            if file.endswith(('.xls', '.xlsx')):
                file_list.append(file)

    # 更新文件列表 JSON
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(file_list, f, indent=4, ensure_ascii=False)

    # 仅在有上传文件时，处理并生成对应的 data.json
    if uploaded_file:
        excel_path = os.path.join(target_folder, uploaded_file)
        try:
            df = pd.read_excel(excel_path, header=0)
            json_output_path = os.path.join(
                target_folder,
                os.path.splitext(uploaded_file)[0] + '_data.json'
            )
            df.to_json(
                json_output_path,
                orient='records',
                force_ascii=False,
                indent=4
            )
            print(f"生成 JSON 文件: {json_output_path}")
        except Exception as e:
            print(f"处理文件 {uploaded_file} 时出错: {str(e)}")