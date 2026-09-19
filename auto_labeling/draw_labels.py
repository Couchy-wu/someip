#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from tqdm import tqdm

# -------------------------------------------------
# 1️⃣ 参数 & 配置
# -------------------------------------------------
parser = argparse.ArgumentParser(description='追加目标检测标注（仅使用 os / os.path）')
parser.add_argument('--data_root',   type=str, default='dataset',
                    help='原始数据根目录')
parser.add_argument('--new_root',    type=str, default='new_labels',
                    help='新增标注根目录（同名 txt）')
parser.add_argument('--subset',      type=str, default='',
                    help='子集名称（train / val / test），空字符串表示全部')
# 注意：不要在模块级调用 parser.parse_args()。
# 早期版本在导入时即解析命令行，导致 `import` 本模块时若携带其它参数
# （主程序 / 测试框架的命令行）就会以 SystemExit(2) 终止进程。
# 现在：导入无副作用；作为脚本运行或显式调用 configure() 时才解析。
args = None


def configure(argv=None):
    """解析命令行参数并刷新模块级配置（argv=None 时取 sys.argv[1:]）。"""
    global args, DATA_ROOT, NEW_ROOT, SUBSET
    args = parser.parse_args(argv)
    DATA_ROOT = args.data_root
    NEW_ROOT = args.new_root
    SUBSET = args.subset.strip()
    return args

# 模块级默认值（导入无副作用）；脚本运行或调用 configure() 时由命令行覆盖
DATA_ROOT = 'dataset'
NEW_ROOT  = 'new_labels'
SUBSET    = ''                    # '' 表示全部子集

# -------------------------------------------------
# 2️⃣ 辅助函数（全部基于 os / os.path）
# -------------------------------------------------
def read_txt_lines(txt_path):
    """读取 txt，返回去除空行后的 list[str]"""
    if not os.path.isfile(txt_path):
        return []
    with open(txt_path, 'r', encoding='utf-8') as f:
        return [ln.strip() for ln in f if ln.strip()]

def append_to_file(old_path, new_path):
    """
    把 new_path 中的每一行（去重后）追加到 old_path。
    返回本次实际追加的行数。
    """
    old_lines = read_txt_lines(old_path)
    new_lines = read_txt_lines(new_path)

    # 去除已经存在的完全相同的行（防止重复写入）
    added = [ln for ln in new_lines if ln not in old_lines]

    if not added:
        return 0

    # 追加写入
    with open(old_path, 'a', encoding='utf-8') as f:
        for ln in added:
            f.write(ln + '\n')
    return len(added)

def ensure_dir(dir_path):
    """如果目录不存在则创建（包括多层）"""
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)

# -------------------------------------------------
# 3️⃣ 主流程
# -------------------------------------------------
def main():
    # 统计信息
    total_imgs = 0
    total_added_boxes = 0

    # 根据是否指定子集，决定遍历根路径
    img_root = os.path.join(DATA_ROOT, 'images')
    lbl_root = os.path.join(DATA_ROOT, 'labels')
    if SUBSET:
        img_root = os.path.join(img_root, SUBSET)
        lbl_root = os.path.join(lbl_root, SUBSET)

    # 新标注根路径（同样可能有子集）
    new_root = NEW_ROOT
    if SUBSET:
        new_root = os.path.join(new_root, SUBSET)

    # 支持 jpg、jpeg、png 三种后缀
    img_suffixes = ('*.jpg', '*.jpeg', '*.png')

    # 收集所有图片路径（使用 glob）
    img_files = []
    for suff in img_suffixes:
        pattern = os.path.join(img_root, '**', suff)
        img_files.extend([p for p in glob_recursive(pattern)])

    if not img_files:
        print('⚠️ 未在 %s 中找到任何图片文件' % img_root)
        sys.exit(1)

    for img_path in tqdm(img_files, desc='Processing images'):
        total_imgs += 1

        # 同名 txt（不带后缀）
        base_name = os.path.splitext(os.path.basename(img_path))[0]

        # 旧标注文件路径（如果目录不存在会在后面自动创建）
        old_lbl_path = os.path.join(lbl_root,
                                    os.path.relpath(os.path.dirname(img_path), img_root),
                                    base_name + '.txt')
        # 新标注文件路径
        new_lbl_path = os.path.join(new_root,
                                    os.path.relpath(os.path.dirname(img_path), img_root),
                                    base_name + '.txt')

        # 若新标注文件不存在，直接跳过
        if not os.path.isfile(new_lbl_path):
            continue

        # 确保旧标注所在目录已经创建
        ensure_dir(os.path.dirname(old_lbl_path))

        # 若旧标注文件根本不存在，先创建一个空文件（append 会自动追加）
        if not os.path.isfile(old_lbl_path):
            open(old_lbl_path, 'a').close()

        added_cnt = append_to_file(old_lbl_path, new_lbl_path)
        total_added_boxes += added_cnt

    # -------------------------------------------------
    # 4️⃣ 结果输出
    # -------------------------------------------------
    print('\n=== 统计结果 ===')
    print('处理的图片总数      : {}'.format(total_imgs))
    print('本次追加的标注框总数: {}'.format(total_added_boxes))

# -------------------------------------------------
# 5️⃣ 辅助: 递归 glob（兼容 Python 3.6+）
# -------------------------------------------------
def glob_recursive(pattern):
    """返回 pattern 匹配的所有文件，支持 ** 递归通配符"""
    import glob
    # Python 3.5+ 已经原生支持 **，但为了兼容低版本，这里手动实现
    return glob.glob(pattern, recursive=True)

# -------------------------------------------------
# 入口
# -------------------------------------------------
if __name__ == '__main__':
    configure()          # 脚本模式：解析命令行
    main()