import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading

# 模块功能：提取信号矩阵，转化为csv。方便后续进行信号查找

class XlsmToCsvConverter:
    def __init__(self, root, skip_first_row: bool = False):
        """
        :param root: Tk 主窗口
        :param skip_first_row: 是否在读取 Excel 时跳过第一行
                               True  → 跳过（等价于原来的 skiprows=1）
                               False → 不跳过（等价于原来的 skiprows=0）
        """
        self.root = root
        self.root.title("信号矩阵 转 CSV 工具")
        self.root.geometry("500x200")

        # ---------- 这里是新增的布尔开关 ----------
        self.skip_first_row = skip_first_row
        # -----------------------------------------

        self.label = tk.Label(root, text="请上传修改后的信号矩阵", font=("Arial", 12))
        self.label.pack(pady=20)

        self.upload_button = tk.Button(
            root, text="上传 XLSM 文件", command=self.start_conversion, font=("Arial", 12)
        )
        self.upload_button.pack(pady=10)

        # 进度条
        self.progress_frame = tk.Frame(root)
        self.progress_frame.pack(pady=10, fill=tk.X, padx=20)

        self.progress_label = tk.Label(self.progress_frame, text="进度: 0%", font=("Arial", 10))
        self.progress_label.pack()

        self.progress_bar = ttk.Progressbar(
            self.progress_frame, orient="horizontal", length=400, mode="determinate"
        )
        self.progress_bar.pack()

    def start_conversion(self):
        # 禁用所有控件，防止重复操作
        self.set_widgets_state('disabled')
        # 启动后台线程处理文件转换
        threading.Thread(target=self.convert_xlsm_to_csv, daemon=True).start()

    def set_widgets_state(self, state):
        """设置界面控件的状态（正常或禁用）"""
        self.upload_button.config(state=state)

    def convert_xlsm_to_csv(self):
        file_path = filedialog.askopenfilename(
            title="选择 XLSM 文件",
            filetypes=[("Excel Macro-Enabled Workbook", "*.xlsm")]
        )
        if not file_path:
            self.root.after(0, self.reset_ui)
            return

        try:
            # -------------------------------------------------
            # 根据布尔开关决定是否跳过第一行
            # skiprows = 1 → 跳过第一行
            # skiprows = 0 → 不跳过第一行（读取全部行）
            # -------------------------------------------------
            skiprows = 1 if self.skip_first_row else 0

            df = pd.read_excel(
                file_path,
                engine='openpyxl',
                header=None,
                skiprows=skiprows   # ← 这里使用了上面的变量
            )
            # -------------------------------------------------

            if df.empty:
                self.root.after(0, lambda: messagebox.showwarning("警告", "表格为空！"))
                self.root.after(0, self.reset_ui)
                return

            # 输出路径：保存到 CanDataProcessing 文件夹中
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_dir)
            testcase_folder = os.path.join(parent_dir, "CanDataProcessing")
            csv_path = os.path.join(testcase_folder, "outputMatrix.csv")

            # 确保 CanDataProcessing 文件夹存在（若不存在则创建）
            os.makedirs(testcase_folder, exist_ok=True)

            # 确保 DataFrame 是标准索引
            df = df.reset_index(drop=True)
            result = df.copy()
            total_rows = len(df)

            # 设置进度条最大值
            self.progress_bar['maximum'] = total_rows

            # 缓存最近一个“锚点行”（第一列非空的行）
            anchor_row = None

            for idx in range(total_rows):
                row = df.iloc[idx]

                if pd.notna(row.iloc[0]):
                    # 当前行第一列有值，作为新的锚点行
                    anchor_row = row.copy()
                else:
                    # 第一列为空，用锚点行填充空值
                    if anchor_row is not None:
                        for col_idx in range(len(row)):
                            if pd.isna(row.iloc[col_idx]):
                                result.iat[idx, col_idx] = anchor_row.iloc[col_idx]

                # 更新进度条
                self.root.after(0, self.update_progress, idx + 1, total_rows)

            # 保存结果为 CSV（覆盖已有文件）
            result.to_csv(csv_path, index=False, header=False, encoding='utf-8-sig')
            self.root.after(0, self.show_success, csv_path)

        except Exception as e:
            self.root.after(0, self.show_error, str(e))

    def update_progress(self, current, total):
        self.progress_bar['value'] = current
        percent = (current / total) * 100
        self.progress_label.config(text=f"进度: {percent:.1f}%")
        self.root.update_idletasks()

    def show_success(self, csv_path):
        messagebox.showinfo("成功", f"已转换完成！\n保存为：\n{csv_path}")
        self.reset_ui()

    def show_error(self, error_msg):
        messagebox.showerror("错误", f"处理失败：\n{error_msg}")
        self.reset_ui()

    def reset_ui(self):
        self.progress_bar['value'] = 0
        self.progress_label.config(text="进度: 0%")
        self.set_widgets_state('normal')  # 恢复界面控件可操作


if __name__ == "__main__":
    root = tk.Tk()

    # ------------------- 这里决定是否跳过第一行 -------------------
    # 设为 True → 跳过第一行
    # 设为 False → 不跳过第一行（读取完整表格）
    converter = XlsmToCsvConverter(root, skip_first_row=False)
    # ------------------------------------------------------------

    root.mainloop()