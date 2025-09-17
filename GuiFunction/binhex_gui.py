# GuiFunction/binhex_gui.py
import tkinter as tk
from tkinter import ttk


class BinHexRow(ttk.Frame):
    """
    单行组件：左侧显示行号 → 8 个二进制位按钮（bit7~bit0） → 十六进制显示
    """
    def __init__(self, master, row_index: int, display_index: int,
                 on_change=None, **kw):
        super().__init__(master, **kw)
        self.row_index = row_index          # 逻辑上的行号（0‑based），供外部使用
        self.on_change = on_change

        # ------------------------------------------------------------------
        # 行号标签（从 1 开始递增，由外层传入 display_index）
        # ------------------------------------------------------------------
        self.row_label = ttk.Label(
            self,
            text=str(display_index),   # 已改为正向递增的行号
            width=2,
            anchor="center",
        )
        self.row_label.grid(row=0, column=0, padx=2)

        # ------------------------------------------------------------------
        # 8 个二进制按钮：左侧是 bit7，右侧是 bit0
        # ------------------------------------------------------------------
        self.bit_vars = []   # 保存 IntVar，顺序为 [bit7, bit6, …, bit0]
        self.bit_btns = []   # 对应的按钮列表（顺序同上）

        # 这里使用从 7 到 0 的倒序循环，使列的顺序为 7 6 5 4 3 2 1 0
        for bit in range(7, -1, -1):
            var = tk.IntVar(value=0)
            btn = ttk.Button(
                self,
                text="0",
                command=lambda idx=len(self.bit_vars): self.toggle_bit(idx),
                width=3,
            )
            # 列号 = 8 - bit（bit7 → col1，bit0 → col8）
            btn.grid(row=0, column=8 - bit, padx=1)
            self.bit_vars.append(var)
            self.bit_btns.append(btn)

        # ------------------------------------------------------------------
        # 十六进制显示（右侧）
        # ------------------------------------------------------------------
        self.hex_var = tk.StringVar(value="00")
        self.hex_label = ttk.Label(
            self,
            textvariable=self.hex_var,
            width=4,
            anchor="center",
            font=("Consolas", 12),
            relief="solid",
        )
        self.hex_label.grid(row=0, column=9, padx=5)

        # 初始化十六进制显示
        self.update_hex_from_bits()

    # ----------------------------------------------------------------------
    # 位按钮的切换逻辑
    # ----------------------------------------------------------------------
    def toggle_bit(self, idx: int):
        """切换第 idx 位（idx 按 bit7→bit0 的顺序）"""
        new_val = 1 - self.bit_vars[idx].get()
        self.bit_vars[idx].set(new_val)
        self.bit_btns[idx].config(text=str(new_val))
        self.update_hex_from_bits()

    # ----------------------------------------------------------------------
    # 依据当前位的值计算十六进制并回调
    # ----------------------------------------------------------------------
    def update_hex_from_bits(self):
        bits = [var.get() for var in self.bit_vars]   # 已是 bit7~bit0 的顺序
        bin_str = "".join(str(b) for b in bits)
        value = int(bin_str, 2)
        self.hex_var.set(f"{value:02X}")
        if callable(self.on_change):
            self.on_change()

    # ----------------------------------------------------------------------
    # 清空本行所有位
    # ----------------------------------------------------------------------
    def reset_bits(self):
        for var, btn in zip(self.bit_vars, self.bit_btns):
            var.set(0)
            btn.config(text="0")
        self.update_hex_from_bits()


class BinHexConverter:
    """整个对话框窗口（8 行、每行 8 位）"""
    TOTAL_ROWS = 8

    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("can数据生成器")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.focus_force()

        # ------------------------------------------------------------------
        # 数据字符串变量（只读 Entry 用）
        # ------------------------------------------------------------------
        self.data_var = tk.StringVar()

        # ------------------------------------------------------------------
        # 样式
        # ------------------------------------------------------------------
        style = ttk.Style(self.window)
        default_font = ("Segoe UI", 11)
        style.configure("TButton", font=default_font, padding=2)
        style.configure("TLabel", font=default_font)

        # ------------------------------------------------------------------
        # 主容器
        # ------------------------------------------------------------------
        container = ttk.Frame(self.window, padding=10)
        container.grid(row=0, column=0)

        # ------------------------------------------------------------------
        # 表头：左侧空白 + 8 列位号（7~0） + Hex
        # ------------------------------------------------------------------
        header = ttk.Frame(container)
        header.grid(row=0, column=0, pady=(0, 4))
        ttk.Label(header, text=" ").grid(row=0, column=0)

        for col in range(7, -1, -1):                     # 7→0
            ttk.Label(
                header,
                text=str(col),
                width=4,
                anchor="center"
            ).grid(row=0, column=8 - col, padx=1)      # 对齐列号

        ttk.Label(
            header,
            text="Hex",
            width=4,
            anchor="center"
        ).grid(row=0, column=9, padx=5)

        # ------------------------------------------------------------------
        # 创建行（行号从 1 开始递增）
        # ------------------------------------------------------------------
        self.rows = []
        for r in range(self.TOTAL_ROWS):
            display_idx = r + 1                     # 正向递增的行号
            row = BinHexRow(
                container,
                row_index=r,
                display_index=display_idx,
                on_change=self.refresh_data_display,
            )
            row.grid(row=r + 1, column=0, pady=2, sticky="w")
            self.rows.append(row)

        # ------------------------------------------------------------------
        # 底部：整体 data 显示 + “清空” 按钮
        # ------------------------------------------------------------------
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.grid(row=1, column=0, sticky="ew")
        ttk.Label(bottom_frame, text="", font=default_font).grid(
            row=0, column=0, sticky="w"
        )
        data_entry = ttk.Entry(
            bottom_frame,
            textvariable=self.data_var,
            font=("Consolas", 10),
            width=60,
            state="readonly",
        )
        data_entry.grid(row=0, column=1, padx=(5, 0), sticky="w")
        clear_btn = ttk.Button(
            bottom_frame, text="清空", command=self.clear_all, width=8
        )
        clear_btn.grid(row=0, column=2, padx=(10, 0))

        # 初始化一次 data 显示
        self.refresh_data_display()

    # ----------------------------------------------------------------------
    # 根据各行的十六进制值拼装 data 列表字符串
    # ----------------------------------------------------------------------
    def refresh_data_display(self):
        hex_strings = [row.hex_var.get() for row in self.rows]
        hex_items = [f"0x{hs}" for hs in hex_strings]
        final_text = f"data = [{', '.join(hex_items)}]"
        self.data_var.set(final_text)

    # ----------------------------------------------------------------------
    # 清空全部位并刷新显示
    # ----------------------------------------------------------------------
    def clear_all(self):
        for row in self.rows:
            row.reset_bits()
        self.refresh_data_display()


def open_binhex_converter(parent):
    """供主程序调用的公共接口"""
    BinHexConverter(parent)