import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk   # pip install pillow

# 配置项
FPS = 25                     # 播放帧率
PRELOAD_COUNT = 200          # 启动时同步预加载的帧数

main_root = None   # 用于存储主窗口引用（在多次调用时保持一致）

def play_image_sequence():
    """ 主入口：选择文件夹 → 预加载 → 启动后台加载 → 播放 """
    global main_root
    if main_root is None:
        main_root = tk._default_root
    # 选择图片文件夹
    folder = filedialog.askdirectory(title="请选择包含图片的文件夹")
    if not folder:
        return
    # 筛选有效图片文件
    valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
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

    total_frames = len(files)

    # ----------  前 PRELOAD_COUNT 帧同步加载 ----------
    frames = []                     # 保存 ImageTk.PhotoImage 对象
    preload_num = min(PRELOAD_COUNT, total_frames)

    print(f"预加载前 {preload_num} 帧中...")
    for i in range(preload_num):
        path = os.path.join(folder, files[i])
        try:
            img = Image.open(path)
            frames.append(ImageTk.PhotoImage(img))
        except Exception as e:
            print(f"加载失败 {files[i]}: {e}")
            messagebox.showwarning("警告", f"无法加载图片：{files[i]}")
            return

    # ----------  启动后台加载线程 ----------
    stop_loader = threading.Event()   # 用来通知线程退出
    load_lock = threading.Lock()      # 保护 frames 列表的写入

    def loader():
        """后台线程函数：把剩余帧逐帧读取并追加到 frames 列表。"""
        for i in range(preload_num, total_frames):
            if stop_loader.is_set():
                break
            path = os.path.join(folder, files[i])
            try:
                img = Image.open(path)
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"[loader] 加载失败 {files[i]}: {e}")
                continue
            # 追加到共享列表（加锁防止竞争）
            with load_lock:
                frames.append(photo)
        print("所有帧已加载完毕止")

    loader_thread = threading.Thread(target=loader, daemon=True)
    loader_thread.start()

    # ----------  UI 布局 ----------
    main_root.attributes("-disabled", True)   # 禁止主窗口操作
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

    # ----------  辅助函数 ----------
    def get_current_frame():
        """安全获取当前帧的 PhotoImage（若未加载完成返回 None）"""
        with load_lock:
            if idx < len(frames):
                return frames[idx]
        return None

    def show_frame():
        """把当前帧（若已就绪）显示到 label 上"""
        photo = get_current_frame()
        if photo:
            label.config(image=photo)

    # ---------- 播放循环 ----------
    def play_step():
        """播放单步：显示当前帧 → 索引 +1 → 计划下一步"""
        nonlocal idx, after_id, paused

        # 如果已经到达末尾，停止并把按钮文字改为 “重新播放”
        if idx >= total_frames:
            pause_btn.config(text="重新播放")
            paused = True
            return

        # 若当前帧尚未被后台加载，则稍后再尝试
        if idx >= len(frames):
            # 这里可以显示一个 “加载中...” 的占位图，或保持上一帧不动
            # 为了不卡死 UI，使用 after 再检查一次
            after_id = player.after(50, play_step)   # 50ms 后重新检查
            return

        # 正常显示
        show_frame()
        idx += 1
        after_id = player.after(delay, play_step)

    # ---------- 控制按钮 ----------
    def replay():
        """重新从第一帧播放"""
        nonlocal idx, after_id, paused
        # 重置索引和暂停状态
        idx = 0                
        paused = False
        pause_btn.config(text="暂停播放")
        if after_id:
            player.after_cancel(after_id)
            after_id = None
        play_step()

    replay_btn.config(command=replay)

    def toggle_pause():
        """暂停 / 继续"""
        nonlocal paused, after_id
        if paused:                     # 继续
            paused = False
            pause_btn.config(text="暂停播放")
            # 若当前帧已经就绪，立刻显示一次（防止“跳帧”）
            show_frame()
            play_step()
        else:                          # 暂停
            paused = True
            pause_btn.config(text="继续播放")
            if after_id:
                player.after_cancel(after_id)
                after_id = None

    pause_btn.config(command=toggle_pause)

    def rewind_5s():
        """倒退 5 秒（即 5*FPS 帧）"""
        nonlocal idx, after_id, paused
        frames_back = 5 * FPS
        new_idx = max(0, idx - frames_back)
        idx = new_idx
        # 取消已经排队的 after
        if after_id:
            player.after_cancel(after_id)
            after_id = None
        show_frame()
        if not paused:
            play_step()

    back_btn.config(command=rewind_5s)

    # 函数功能：关闭窗口
    def stop(win):
        """关闭播放窗口时的清理工作"""
        nonlocal after_id, paused
        # 停止播放计时器
        if after_id:
            win.after_cancel(after_id)
            after_id = None
        # 停止后台加载线程
        stop_loader.set()
        loader_thread.join(timeout=1.0)   # 最多等 1 秒
        # 恢复主窗口交互
        main_root.attributes("-disabled", False)
        main_root.lift()
        paused = False
        win.destroy()

    # ----------  开始播放 ----------
    play_step()


# --------------------------------------------------------------
# 若把本文件直接作为脚本运行，这里创建一个最小的主窗口
# --------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("图片序列播放器（Demo）")
    root.geometry("300x120")
    ttk_btn = tk.Button(root, text="打开文件夹播放", command=play_image_sequence)
    ttk_btn.pack(expand=True, fill="both", padx=20, pady=20)
    root.mainloop()
