import os
import logging
from tkinter import filedialog, messagebox


# --- 新增：关闭指定名称的 logger ---
def close_logger_if_in_use(logger_name: str):
    """
    关闭指定名称的 logger 中的所有 FileHandler，释放 .log 文件占用
    :param logger_name: 日志记录器名称（如 '001_data'）
    """
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        return  # 没有处理器，无需处理

    for handler in logger.handlers[:]:  # 复制列表以避免修改中迭代
        try:
            handler.close()      # 关闭处理器
            logger.removeHandler(handler)  # 从 logger 移除
            print(f"已关闭并移除处理器：{handler}")
        except Exception as e:
            print(f"关闭处理器时出错：{e}")


def delete_test_case():
    target_folder = os.path.join(os.getcwd(), "TestcaseCollection")

    if not os.path.exists(target_folder):
        messagebox.showerror("错误", "TestcaseCollection文件夹不存在")
        return

    file_path = filedialog.askopenfilename(
        title="选择要删除的测试用例",
        initialdir=target_folder,
        filetypes=(("Excel 文件", "*.xlsx"), ("Excel 文件", "*.xls"), ("所有文件", "*.*"))
    )

    if not file_path:
        return

    file_path = os.path.normpath(file_path)
    target_folder = os.path.normpath(target_folder)

    if not file_path.startswith(target_folder):
        messagebox.showerror("错误", "请选择TestcaseCollection文件夹中的文件")
        return

    file_name = os.path.basename(file_path)
    base_name = os.path.splitext(file_name)[0]

    # 构造关联文件路径
    json_file_path = os.path.join(target_folder, f"{base_name}_data.json")
    log_file_path = os.path.join(target_folder, f"{base_name}_data.log")
    image_json_path = os.path.join(target_folder, f"{base_name}_ImageData.json") 

    confirm = messagebox.askyesno("确认删除", f"确定要删除 {file_name} 及其关联文件吗？")
    if not confirm:
        return

    try:
        deleted_files = []

        # === 关键步骤：先关闭可能占用 log 文件的 logger ===
        potential_logger_name = base_name + "_data"  # 与 logging_setup.setup_logger 中一致
        close_logger_if_in_use(potential_logger_name)

        # 删除 Excel 文件
        os.remove(file_path)
        deleted_files.append(file_name)
        print(f"已删除 Excel 文件：{file_path}")

        # 删除 JSON 文件
        if os.path.exists(json_file_path):
            os.remove(json_file_path)
            deleted_files.append(os.path.basename(json_file_path))
            print(f"已删除 JSON 文件：{json_file_path}")

        # 删除 ImageData JSON 文件
        if os.path.exists(image_json_path):
            os.remove(image_json_path)
            deleted_files.append(os.path.basename(image_json_path))
            print(f"已删除 ImageData JSON 文件：{image_json_path}")

        # 删除 LOG 文件
        if os.path.exists(log_file_path):
            try:
                os.remove(log_file_path)
                deleted_files.append(os.path.basename(log_file_path))
                print(f"已删除 LOG 文件：{log_file_path}")
            except PermissionError:
                messagebox.showwarning("警告", f"日志文件正在使用中，无法删除：{os.path.basename(log_file_path)}")
        else:
            print(f"未找到 LOG 文件：{log_file_path}")

        if deleted_files:
            messagebox.showinfo("删除成功", "已删除以下文件：\n" + "\n".join(deleted_files))

    except Exception as e:
        messagebox.showerror("错误", f"删除失败：{str(e)}")
