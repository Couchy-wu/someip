import os
import shutil
from tkinter import filedialog, messagebox

# 模块功能：上传测试用例

# 函数功能：上传测试用例Excel，并将其复制到“测试用例集”文件夹中
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
            # 确保目标路径不在当前文件夹内
            target_path = os.path.normpath(new_file_name)
            
            # 检查目标路径是否与原文件路径相同
            if target_path == os.path.normpath(file_path):
                messagebox.showerror("错误", "目标路径与原文件路径相同，请选择不同的位置")
                return
            
            # 检查目标文件夹是否存在
            target_folder = os.path.dirname(target_path)
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            
            # 获取目标文件夹中的所有文件
            existing_files = os.listdir(target_folder)
            
            # 检查文件名是否重复
            if os.path.basename(new_file_name) in existing_files:
                messagebox.showerror("错误", "文件名称重复，无法上传")
                return
            
            # 检查文件名是否有效
            if not os.path.basename(target_path):
                messagebox.showerror("错误", "文件名不能为空")
                return
            
            try:
                # 复制文件
                shutil.copy(file_path, target_path)
                print(f"文件已复制到：{target_path}")
                messagebox.showinfo("成功", "文件已成功上传")
            except Exception as e:
                messagebox.showerror("错误", f"文件上传失败：{str(e)}")
                return