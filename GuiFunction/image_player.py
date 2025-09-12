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
    
    # 预加载所有图像
    print('图像预加载中...')
    preloaded_images = []
    for file in files:
        path = os.path.join(folder, file)
        try:
            img = Image.open(path)
            preloaded_images.append(ImageTk.PhotoImage(img))
        except Exception as e:
            print(f"无法加载图片 {file}: {e}")
            # 如果有图片加载失败，提示用户并退出
            messagebox.showwarning("警告", f"无法加载图片：{file}")
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
    pause_btn.pack(pady=2)
    # 重新播放按钮
    replay_btn = tk.Button(ctrl, text="重新播放", width=12, height=2)
    replay_btn.pack(pady=2)
    # 倒退按钮
    back_btn = tk.Button(ctrl, text="倒退5秒", width=12, height=2)
    back_btn.pack(pady=2)

    # ---------- 播放状态变量 ----------
    idx = 0                         # 当前显示的帧索引
    delay = int(1000 / FPS)        # 两帧之间的延迟（毫秒）
    after_id = None                # after 调用的 ID，用于取消
    paused = False                 # 是否处于暂停状态

    # ----------------------------------------------------------
    # 1️⃣ 重新播放（Replay）
    # ----------------------------------------------------------
    def replay():
        nonlocal idx, after_id, paused
        # 重置索引和暂停状态
        idx = 0                
        paused = False
        # 如果有正在运行的播放任务，取消它
        if after_id:
            player.after_cancel(after_id)
            after_id = None
        # 恢复按钮文字为 “暂停播放”
        pause_btn.config(text="暂停播放")
        show_next()                # 从第一帧重新开始播放

    replay_btn.config(command=replay)

    # ----------------------------------------------------------
    # 2️⃣ 显示当前帧（用于倒退后立即刷新画面）
    # ----------------------------------------------------------
    def show_current():
        nonlocal idx
        if 0 <= idx < len(preloaded_images):
            label.config(image=preloaded_images[idx])

    # ----------------------------------------------------------
    # 3️⃣ 播放下一帧
    # ----------------------------------------------------------
    def show_next():
        nonlocal idx, after_id, paused
        if idx >= len(preloaded_images):
            # 播放结束：把按钮恢复为 “暂停播放”，并标记为已暂停
            pause_btn.config(text="重新播放")
            paused = True
            return
        label.config(image=preloaded_images[idx])
        idx += 1
        after_id = player.after(delay, show_next)

    # ----------------------------------------------------------
    # 4️⃣ 暂停 / 继续
    # ----------------------------------------------------------
    def toggle_pause():
        nonlocal paused, after_id
        if paused:                      # 当前是暂停状态 → 继续播放
            paused = False
            pause_btn.config(text="暂停播放")
            # 继续播放时先显示当前帧，防止“跳帧”
            show_current()
            show_next()
        else:                           # 正在播放 → 暂停
            paused = True
            pause_btn.config(text="继续播放")
            if after_id:
                player.after_cancel(after_id)
                after_id = None

    pause_btn.config(command=toggle_pause)

    # ----------------------------------------------------------
    # 5️⃣ 倒退 5 秒
    # ----------------------------------------------------------
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

    back_btn.config(command=rewind_5s)

    # 函数功能：关闭窗口
    def stop(win):
        nonlocal after_id, paused
        if after_id:
            win.after_cancel(after_id)
            after_id = None
        # 恢复主窗口交互
        main_root.attributes("-disabled", False)
        main_root.lift()
        # 重置按钮文字（防止下次打开时残留）
        pause_btn.config(text="暂停播放")
        paused = False
        win.destroy()

    # 开始播放
    show_next()
