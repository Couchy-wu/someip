import sys
import os
# 获取当前文件所在目录，并将其添加到模块搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import pandas as pd
import numpy as np
from can_testcase_processor import TestCaseProcessor
import mylog, logging

# 代码功能：上传测试用例表格文件，将其解析为json，再根据json解析“脚本”部分

def handle_file_upload():
    """
    只负责把用户选中的 Excel 复制到 TestcaseCollection 并返回目标文件名。
    解析、生成 JSON、日志等交给调用方（FileUpdater）完成。
    """
    # 选择原始 Excel 文件
    file_path = filedialog.askopenfilename(
        title="选择Excel文件（此步骤请不要更改文件名）",
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )
    if not file_path:
        return None

    # 提示用户必须重新命名文件
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("提示", "请更改名字")

    # 确保目标文件夹存在
    target_folder = os.path.join(os.getcwd(), "TestcaseCollection")
    os.makedirs(target_folder, exist_ok=True)

    # 获取原文件名，让用户输入新文件名（带路径）
    file_name = os.path.basename(file_path)
    new_file_name = filedialog.asksaveasfilename(
        initialdir=target_folder,
        initialfile=file_name,
        title="请重新命名",
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )
    if not new_file_name:
        return None

    # 规范化路径并进行基本校验
    target_path = os.path.normpath(new_file_name)
    if target_path == os.path.normpath(file_path):
        messagebox.showerror("错误", "目标路径与原文件路径相同，请选择不同的位置")
        return None
    if os.path.basename(target_path) in os.listdir(os.path.dirname(target_path)):
        messagebox.showerror("错误", "文件名称重复，无法上传")
        return None
    if not os.path.basename(target_path):
        messagebox.showerror("错误", "文件名不能为空")
        return None

    # 执行文件复制和后续处理
    try:
        shutil.copy(file_path, target_path)
        messagebox.showinfo("上传成功", "文件已成功复制")
        return os.path.basename(target_path)
    except Exception as e:
        messagebox.showerror("错误", f"文件上传失败：{str(e)}")
        return None


def _replace_nan(obj):
    """
    将 np.nan 替换为 None，支持嵌套字典和列表，便于 JSON 序列化。
    """
    if isinstance(obj, dict):
        return {k: _replace_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan(v) for v in obj]
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def refresh_json_file(uploaded_file=None):
    """
    更新 test_cases.json 文件，并在上传新文件时：
    - 将 Excel 按每4行分组生成 <filename>_data.json；
    - 使用 TestCaseProcessor 解析该 JSON，日志输出至同名 .log。
    """
    target_folder = os.path.join(os.getcwd(), "TestcaseCollection")
    json_file = os.path.join(target_folder, "test_cases.json")
    file_list = []

    # 扫描目录下所有 Excel 文件，更新 test_cases.json
    for file in os.listdir(target_folder):
        if file.lower().endswith(('.xls', '.xlsx')):
            file_list.append(file)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(file_list, f, indent=4, ensure_ascii=False)

    # 如果指定了上传文件，则处理该文件
    if uploaded_file:
        excel_path = os.path.join(target_folder, uploaded_file)
        try:
            # 读取 Excel 数据
            df = pd.read_excel(excel_path, header=0)
            df = df.reset_index(drop=True)
            df = df.replace({np.nan: None})

            # 按每 4 行分组并构建结构化数据
            grouped_data = []
            num_rows = len(df)
            for i in range(0, num_rows, 4):
                group = df.iloc[i:i + 4].to_dict(orient='records')
                group = _replace_nan(group)
                grouped_data.append({
                    "test_case_id": f"TC_{(i // 4) + 1}",
                    "rows": group
                })

            # 写入 _data.json 文件
            json_output_path = os.path.join(
                target_folder,
                os.path.splitext(uploaded_file)[0] + '_data.json'
            )
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(grouped_data, f, indent=4, ensure_ascii=False)
            print(f"生成分组 JSON 文件: {json_output_path}")

            # 准备日志文件路径
            log_basename = os.path.splitext(os.path.basename(json_output_path))[0]
            log_path = os.path.join(target_folder, f"{log_basename}.log")

            # 配置专用 logger，输出到指定日志文件
            mylog.setup_logger(
                logger_name=log_basename,
                log_dir=target_folder,
                log_prefix=log_basename,
                level=logging.INFO,
                clear_old=True,
                use_timestamp=False
            )

            # 调用处理器解析测试用例，并记录日志
            try:
                print(f"正在解析生成的测试用例文件: {json_output_path}")
                processor = TestCaseProcessor(
                    json_file_path=json_output_path,
                    logger_name=log_basename
                )
                processor.process()
                print(f"解析完成 → 日志已写入: {log_path}")
            except Exception as e:
                print(f"解析测试用例时出错: {str(e)}")

        except Exception as e:
            print(f"处理文件 {uploaded_file} 时出错: {str(e)}")
