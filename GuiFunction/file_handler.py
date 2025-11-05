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
    实现测试用例 Excel 文件的上传流程：
    1. 用户选择原始文件；
    2. 提示用户重命名并指定保存路径；
    3. 将文件复制到 TestcaseCollection 目录；
    4. 调用 refresh_json_file 生成对应的 JSON 和日志文件；
    5. 所有步骤成功后统一提示“上传成功”。
    返回值：成功时返回目标文件名（不含路径），失败返回 None。
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
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

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

    # 检查是否与原路径相同
    if target_path == os.path.normpath(file_path):
        messagebox.showerror("错误", "目标路径与原文件路径相同，请选择不同的位置")
        return None

    # 确保目标目录存在
    target_folder = os.path.dirname(target_path)
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    # 防止文件名重复
    if os.path.basename(new_file_name) in os.listdir(target_folder):
        messagebox.showerror("错误", "文件名称重复，无法上传")
        return None

    # 检查文件名是否为空
    if not os.path.basename(target_path):
        messagebox.showerror("错误", "文件名不能为空")
        return None

    # 执行文件复制和后续处理
    try:
        # 复制文件到目标路径
        shutil.copy(file_path, target_path)
        print(f"文件已复制到：{target_path}")

        # 生成对应的 JSON 和日志文件
        try:
            refresh_json_file(uploaded_file=os.path.basename(target_path))
        except Exception as e:
            messagebox.showerror("生成错误", f"文件已复制，但生成 JSON/LOG 失败：{e}")
            return None

        # 全部成功后显示统一提示
        messagebox.showinfo("上传成功", "文件已成功上传，并成功解析")
        return os.path.basename(target_path)

    except Exception as e:
        messagebox.showerror("错误", f"文件上传失败：{str(e)}")
        return None


def _replace_nan(obj):
    """
    递归地将对象中的 np.nan 替换为 None，以便正确序列化为 JSON 中的 null。
    支持嵌套的字典和列表结构。
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
    更新测试用例元数据文件 test_cases.json，并在上传新文件时：
    - 读取 Excel 文件，按每 4 行分组生成 <filename>_data.json；
    - 使用 TestCaseProcessor 解析该 JSON，并将日志输出至同名 .log 文件。
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
