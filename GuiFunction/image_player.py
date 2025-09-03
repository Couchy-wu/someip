import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk   # pip install pillow

FPS = 25  # 帧率
main_root = None    # 用于存储窗口

# 函数功能：执行图像序列播放逻辑
def play_image_sequence():
    # 获取窗口
    global main_root
    if main_root is None:
        main_root = tk._default_root
    # 选择图片文件夹
    folder = filedialog.askdirectory(title="请选择包含图片的文件夹")
    if not folder:
        return
    # 筛选有效图片文件
    valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"}
    files = [f for f in os.listdir(folder)
             if os.path.splitext(f.lower())[1] in valid_ext]
    # 按文件名排序
    try:
        files.sort(key=lambda x: int(os.path.splitext(x)[0]))
    except ValueError:
        messagebox.showwarning("提示", "图片文件名必须是纯数字！")
        return
    if not files:
        messagebox.showwarning("提示", "该文件夹中没有合法图片！")
        return
    # 禁用主窗口，防止用户在播放时操作其他控件。（但是后续可能会改）
    main_root.attributes("-disabled", True)
    # 创建播放窗口
    player = tk.Toplevel()
    player.title("播放窗口")
    player.protocol("WM_DELETE_WINDOW", lambda: stop(player))
    # 创建主框架：左边图片，右边控制
    main_frame = tk.Frame(player)
    main_frame.pack(fill="both", expand=True)
    # 左侧图片标签
    label = tk.Label(main_frame, bg="black")
    label.pack(side="left", fill="both", expand=True)
    # 右侧控制面板
    ctrl = tk.Frame(main_frame, padx=10, pady=10)
    ctrl.pack(side="right", fill="y")
    # 暂停/继续按钮
    pause_btn = tk.Button(ctrl, text="暂停播放", width=12, height=2)
    pause_btn.pack()
    # 重新播放按钮
    replay_btn = tk.Button(ctrl, text="重新播放", width=12, height=2)
    replay_btn.pack()
    # 播放控制变量
    idx = 0                     # 当前播放的图片索引
    delay = int(1000 / FPS)     # 美珍之间的延迟（毫秒），根据帧率计算
    after_id = None             # Tkinter 的 after 调用的 ID，用于取消定时任务
    paused = False              # 标记是否已暂停
    # 在创建控制面板后添加倒退按钮
    back_btn = tk.Button(ctrl, text="倒退5秒", width=12, height=2)
    back_btn.pack()

    # 函数功能：定义重新播放函数
    def replay():
        nonlocal idx, after_id, paused
        # 重置索引和暂停状态
        idx = 0                
        paused = False
        # 如果有正在运行的播放任务，取消它
        if after_id:
            player.after_cancel(after_id)
            after_id = None
        # 调用 show_next() 开始播放
        show_next()
    # 绑定重新播放按钮
    replay_btn.config(command=replay)

    # 函数功能：显示下一帧图片
    def show_next():
        nonlocal idx, after_id
        # 检查是否已经播放完所有图片
        if idx >= len(files):
            return
        path = os.path.join(folder, files[idx])
        # 加载并显示当前图片
        try:
            img = Image.open(path)
            imgtk = ImageTk.PhotoImage(img)
            label.config(image=imgtk)
            label.image = imgtk
        except Exception as e:
            print("无法加载图片:", e)
        idx += 1
        after_id = player.after(delay, show_next)

    # 函数功能：暂停/继续播放
    def toggle_pause():
        nonlocal paused, after_id
        if paused:
            paused = False
            pause_btn.config(text="暂停播放")
            show_next()
        else:
            paused = True
            pause_btn.config(text="继续播放")
            if after_id:
                player.after_cancel(after_id)
                after_id = None
    pause_btn.config(command=toggle_pause)

    # 函数功能：用于显示当前索引 idx 对应的图片
    def show_current():
        nonlocal idx
        if idx >= len(files):
            return
        path = os.path.join(folder, files[idx])
        try:
            img = Image.open(path)
            imgtk = ImageTk.PhotoImage(img)
            label.config(image=imgtk)
            label.image = imgtk
        except Exception as e:
            print("无法加载图片:", e)

    # 定义倒退函数
    def rewind_5s():
        nonlocal idx, after_id, paused
        frames_to_rewind = 5 * FPS
        new_idx = max(0, idx - frames_to_rewind)
        if after_id:
            player.after_cancel(after_id)
            after_id = None
        idx = new_idx
        show_current()
        if not paused:
            show_next()
    # 绑定倒退按钮
    back_btn.config(command=rewind_5s)

    # 函数功能：关闭窗口
    def stop(win):
        nonlocal after_id
        if after_id:
            win.after_cancel(after_id)
            after_id = None
        main_root.attributes("-disabled", False)
        main_root.lift()
        win.destroy()  # 关闭并销毁播放窗口

    # 开始播放
    show_next()