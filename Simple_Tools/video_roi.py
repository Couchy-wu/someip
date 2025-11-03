import os
import shutil
from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np

# 功能：将文件夹中的图片进行批量统一裁剪

class ImageCropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批量图片裁剪工具")
        self.root.geometry("500x300")

        self.folder_path = ""
        self.image_list = []
        self.selected_box = None  # 裁剪区域 (x1, y1, x2, y2)
        self.tk_img = None
        self.canvas_img = None

        # GUI 元素
        self.label = Label(root, text="批量图片裁剪工具", font=("Arial", 16))
        self.label.pack(pady=20)

        self.btn_select = Button(root, text="上传文件夹", command=self.load_folder, width=20, height=2)
        self.btn_select.pack(pady=10)

        self.btn_crop = Button(root, text="裁剪图片", command=self.start_crop, width=20, height=2, state=DISABLED)
        self.btn_crop.pack(pady=10)

        self.status_label = Label(root, text="未选择文件夹", fg="gray")
        self.status_label.pack(pady=10)

    def load_folder(self):
        self.folder_path = filedialog.askdirectory(title="选择图片文件夹")
        if not self.folder_path:
            return

        # 获取所有支持的图片格式
        supported_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
        self.image_list = [f for f in os.listdir(self.folder_path)
                           if f.lower().endswith(supported_exts)]

        if len(self.image_list) == 0:
            messagebox.showwarning("警告", "该文件夹中没有找到图片文件！")
            self.status_label.config(text="无图片文件", fg="red")
            self.btn_crop.config(state=DISABLED)
            return

        self.status_label.config(text=f"已加载 {len(self.image_list)} 张图片", fg="green")
        self.btn_crop.config(state=NORMAL)
        messagebox.showinfo("成功", f"已加载 {len(self.image_list)} 张图片")

    def start_crop(self):
        if len(self.image_list) < 10:
            messagebox.showwarning("警告", f"图片数量不足10张，无法显示第10张！共{len(self.image_list)}张。")
            return

        # 打开第10张图片（索引为9）
        tenth_image_path = os.path.join(self.folder_path, self.image_list[9])
        self.img_10th = Image.open(tenth_image_path).convert("RGB")
        self.img_copy = self.img_10th.copy()  # 保留原始图像用于裁剪

        # 创建裁剪选择窗口
        self.create_crop_window()

    def create_crop_window(self):
        # 新窗口用于选择裁剪区域
        self.crop_win = Toplevel(self.root)
        self.crop_win.title("选择裁剪区域")
        self.crop_win.geometry("800x600")

        # 缩放图片以适应窗口
        self.display_img, self.scale_ratio = self.resize_for_display(self.img_10th)

        # 创建Canvas显示图片
        self.canvas = Canvas(self.crop_win, bg="white")
        self.canvas.config(width=self.display_img.width(), height=self.display_img.height())
        self.canvas.pack(expand=True, fill=BOTH)

        # 显示图片
        self.canvas_img_obj = self.canvas.create_image(0, 0, anchor=NW, image=self.display_img)

        # 绑定鼠标事件
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # 提示标签
        Label(self.crop_win, text="请拖动鼠标选择裁剪区域，然后点击【确认裁剪】", fg="blue").pack(pady=5)

        # 按钮
        Button(self.crop_win, text="确认裁剪", command=self.confirm_crop, bg="green", fg="white").pack(side=RIGHT, padx=10, pady=10)
        Button(self.crop_win, text="取消", command=self.crop_win.destroy).pack(side=RIGHT, pady=10)

        self.rect = None
        self.start_x = None
        self.start_y = None

    def resize_for_display(self, img):
        # 缩放图像以便在屏幕上显示（最大800x600）
        max_w, max_h = 800, 600
        w, h = img.size
        ratio = min(max_w / w, max_h / h, 1.0)  # 不放大，只缩小
        new_size = (int(w * ratio), int(h * ratio))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        return tk_img, ratio

    def on_mouse_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline="red", width=2)

    def on_mouse_drag(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_release(self, event):
        self.end_x, self.end_y = event.x, event.y

    def confirm_crop(self):
        if self.start_x is None or not hasattr(self, 'end_x'):
            messagebox.showwarning("警告", "请先选择裁剪区域！")
            return

        # 获取原始图像中的真实坐标
        x1 = int(min(self.start_x, self.end_x) / self.scale_ratio)
        y1 = int(min(self.start_y, self.end_y) / self.scale_ratio)
        x2 = int(max(self.start_x, self.end_x) / self.scale_ratio)
        y2 = int(max(self.start_y, self.end_y) / self.scale_ratio)

        if x1 == x2 or y1 == y2:
            messagebox.showwarning("警告", "裁剪区域无效，请选择一个有效区域！")
            return

        self.selected_box = (x1, y1, x2, y2)
        self.crop_win.destroy()

        # 执行批量裁剪
        self.perform_batch_crop()

    def perform_batch_crop(self):
        # 选择输出文件夹
        output_dir = filedialog.asksaveasfilename(
            title="选择保存路径（输入文件夹名）",
            defaultextension="", initialfile="cropped_images",
            filetypes=[("Folder", "*/")]
        )
        if not output_dir:
            return

        # 创建输出目录
        output_folder = os.path.dirname(output_dir)
        output_folder = os.path.join(output_folder, os.path.basename(output_dir))
        if os.path.exists(output_folder):
            if messagebox.askyesno("覆盖确认", "该文件夹已存在，是否覆盖？"):
                shutil.rmtree(output_folder)
            else:
                return
        os.makedirs(output_folder)

        # 获取裁剪框
        x1, y1, x2, y2 = self.selected_box

        # 遍历所有图片进行裁剪
        success_count = 0
        for img_name in self.image_list:
            try:
                img_path = os.path.join(self.folder_path, img_name)
                img = Image.open(img_path).convert("RGB")
                cropped = img.crop((x1, y1, x2, y2))

                # 保持原始格式保存
                save_path = os.path.join(output_folder, img_name)
                cropped.save(save_path, quality=95)
                success_count += 1
            except Exception as e:
                print(f"裁剪失败: {img_name}, 错误: {e}")

        messagebox.showinfo("完成", f"批量裁剪完成！共处理 {success_count}/{len(self.image_list)} 张图片。\n保存路径：{output_folder}")


# 主程序
if __name__ == "__main__":
    root = Tk()
    app = ImageCropperApp(root)
    root.mainloop()
