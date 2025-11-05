import sys
import os
# 获取当前文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 将该目录加入模块搜索路径
sys.path.append(current_dir)

import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import pandas as pd
import numpy as np   # 用于识别 NaN
from can_testcase_processor import TestCaseProcessor

# 函数：上传测试用例 Excel 文件
def handle_file_upload():
    # 打开文件选择对话框
    file_path = filedialog.askopenfilename(
        title="选择Excel文件（此步骤请不要更改文件名）",
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )

    if file_path:
        # 弹出更改名字提醒的对话框
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showinfo("提示", "请更改名字")
        # 指定目标文件夹路径
        target_folder = os.path.join(os.getcwd(), "TestcaseCollection")
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



def _replace_nan(obj):
    """
    递归遍历任意嵌套的容器（list / dict），把 np.nan 替换为 None。
    json.dump 会把 None 序列化为 null。
    """
    if isinstance(obj, dict):
        return {k: _replace_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan(v) for v in obj]
    # 直接比较 np.nan（因为 float('nan') != float('nan')）
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def refresh_json_file(uploaded_file=None):
    """
    - 生成/更新 `test_cases.json`（仅保存目录下所有 Excel 文件名）。
    - 若提供 `uploaded_file`，读取该 Excel，按每 4 行分组并写入
      `<excel_name>_data.json`，其中所有 NaN 均被写成 JSON 的 null。
    - 新增：自动调用 can_testcase_processor.py 解析生成的 JSON 文件
    """
    target_folder = os.path.join(os.getcwd(), "TestcaseCollection")
    json_file = os.path.join(target_folder, "test_cases.json")
    file_list = []

    # -------------------------------------------------
    # 1️⃣ 读取目录下的所有 Excel 文件名并写入 test_cases.json
    # -------------------------------------------------
    for file in os.listdir(target_folder):
        if file.lower().endswith(('.xls', '.xlsx')):
            file_list.append(file)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(file_list, f, indent=4, ensure_ascii=False)

    # -------------------------------------------------
    # 2️⃣ 若有上传文件，则生成对应的 *_data.json 并解析
    # -------------------------------------------------
    if uploaded_file:
        excel_path = os.path.join(target_folder, uploaded_file)

        try:
            # 读取 Excel
            df = pd.read_excel(excel_path, header=0)

            # 确保索引连续
            df = df.reset_index(drop=True)

            # 将所有 NaN 替换为 None（即后面的 null）
            df = df.replace({np.nan: None})

            # 按每 4 行分组
            grouped_data = []
            num_rows = len(df)

            for i in range(0, num_rows, 4):
                # 取当前 4 行（不足 4 行的最后一组也会被保留）
                group = df.iloc[i:i + 4].to_dict(orient='records')
                # 递归确保深层的 NaN 已经是 None
                group = _replace_nan(group)

                grouped_data.append({
                    "test_case_id": f"TC_{(i // 4) + 1}",
                    "rows": group
                })

            # 输出路径
            json_output_path = os.path.join(
                target_folder,
                os.path.splitext(uploaded_file)[0] + '_data.json'
            )

            # 写入 JSON（此时所有 None 会自动转成 null）
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(grouped_data, f, indent=4, ensure_ascii=False)

            print(f"生成分组 JSON 文件: {json_output_path}")

            # 新增：调用 can_testcase_processor.py 解析该 JSON 文件
            try:
                print(f"正在解析生成的测试用例文件: {json_output_path}")
                processor = TestCaseProcessor(json_file_path=json_output_path)
                processor.process()
                print(f"解析完成: {json_output_path}")
            except Exception as e:
                print(f"解析测试用例时出错: {str(e)}")

        except Exception as e:
            print(f"处理文件 {uploaded_file} 时出错: {str(e)}")
