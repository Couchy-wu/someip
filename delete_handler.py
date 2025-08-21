import os
from tkinter import filedialog, messagebox

# 模块功能：删除测试用例

# 函数功能：删除测试用例集中的Excel文件
def delete_test_case():
    # 指定测试用例集文件夹路径
    target_folder = os.path.join(os.getcwd(), "测试用例集")
    
    # 检查文件夹是否存在
    if not os.path.exists(target_folder):
        messagebox.showerror("错误", "测试用例集文件夹不存在")
        return
    
    # 弹出文件选择对话框，仅允许选择Excel文件
    file_path = filedialog.askopenfilename(
        title="选择要删除的测试用例",
        initialdir=target_folder,
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )
    
    if file_path:
        # 检查文件是否在测试用例集文件夹中
        if not file_path.startswith(target_folder):
            messagebox.showerror("错误", "请选择测试用例集文件夹中的文件")
            return
        
        # 获取文件名
        file_name = os.path.basename(file_path)
        
        # 弹出确认对话框
        confirm = messagebox.askyesno("确认删除", f"确定要删除 {file_name} 吗？")
        if confirm:
            try:
                os.remove(file_path)
                messagebox.showinfo("成功", f"已删除 {file_name}")
                print(f"已删除：{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败：{str(e)}")