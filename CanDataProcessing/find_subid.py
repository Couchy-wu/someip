# generate_can_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, Button, Label
import os
import re


# 找子ID的副产物，与测试无关


# 导入你已有的模块（确保 find_can_from_csv.py 在同一目录或可导入路径）
try:
    from find_can_from_csv import create_can_data_by_signal
except ImportError as e:
    messagebox.showerror("导入错误", f"无法导入 find_can_from_csv 模块：{e}")
    raise e

class CANDataGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CAN子ID生成工具")
        self.root.geometry("500x200")

        self.file_path = None

        # 标题标签
        Label(root, text="CAN 子ID 自动生成工具", font=("Arial", 16)).pack(pady=20)

        # 按钮区域
        Button(root, text="📁 选择输入文件", command=self.load_file, width=20, height=2).pack(pady=5)
        Button(root, text="⚡ 生成输出文件", command=self.process_file, width=20, height=2).pack(pady=5)

    def load_file(self):
        self.file_path = filedialog.askopenfilename(
            title="选择TXT文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if self.file_path:
            messagebox.showinfo("文件已选择", f"已选择文件：\n{os.path.basename(self.file_path)}")
        else:
            messagebox.showwarning("未选择", "未选择任何文件。")

    def process_file(self):
        if not self.file_path:
            messagebox.showwarning("错误", "请先选择输入文件！")
            return

        output_file = filedialog.asksaveasfilename(
            title="保存输出文件",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="output_with_subID.txt"
        )
        if not output_file:
            return  # 用户取消保存

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            output_lines = []

            for line_num, line in enumerate(lines, start=1):
                line = line.strip()
                if not line:
                    continue

                parts = [part.strip() for part in line.split(',', 2)]
                if len(parts) < 3:
                    messagebox.showwarning("格式错误", f"第 {line_num} 行格式不正确（缺少字段）：\n{line}")
                    continue

                message_id_hex = parts[0].strip()
                bit_range = parts[1].strip()
                signal_full_name = parts[2].strip()

                # 提取英文信号名（最后一个单词）
                words = signal_full_name.split()
                if not words:
                    signal_name_en = ""
                else:
                    signal_name_en = words[-1]

                # 清洗 message_id（去 0x，转大写）
                message_id_clean = message_id_hex.upper().replace('0X', '').strip()

                # 调用函数获取 sub_id_raw
                try:
                    result = create_can_data_by_signal(
                        message_id=message_id_clean,
                        signal_name_en=signal_name_en,
                        enum_value=0  # 默认值
                    )

                    if isinstance(result, dict) and result.get("success"):
                        sub_id = result.get("sub_id_raw", "NULL")
                        if pd.isna(sub_id) or str(sub_id).strip().upper() == 'NO' or str(sub_id).strip() == '':
                            sub_id = "NULL"
                        else:
                            sub_id = str(sub_id).strip()
                    else:
                        sub_id = "NULL"
                except Exception as e:
                    print(f"调用 create_can_data_by_signal 失败: {e}")
                    sub_id = "NULL"

                # 构造新行：原第1列, sub_id, 原第2列, 原第3列
                new_line = f"{message_id_hex}, {sub_id}, {bit_range}, {signal_full_name}"
                output_lines.append(new_line)

            # 写入输出文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))

            messagebox.showinfo("完成", f"文件已成功生成：\n{output_file}")

        except Exception as e:
            messagebox.showerror("处理失败", f"处理过程中发生错误：\n{str(e)}")


if __name__ == "__main__":
    import pandas as pd  # 确保 pd 在作用域内（用于 isna 判断）
    root = tk.Tk()
    app = CANDataGeneratorApp(root)
    root.mainloop()
