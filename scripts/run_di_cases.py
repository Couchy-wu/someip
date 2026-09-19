# -*- coding: utf-8 -*-
"""scripts.run_di_cases —— Di 测试用例批量执行/体检（命令行）

用法（**在项目根目录**执行；按项目约定以包模块方式运行，不做 sys.path 注入）：

    # 1) 体检用例集：只解析与分类，不碰设备（默认，安全）
    python -m scripts.run_di_cases

    # 2) 指定目录 / 只跑可全自动的用例 / 只跑某个场景
    python -m scripts.run_di_cases --cases TestcaseCollection/Di_testcases --auto-only
    python -m scripts.run_di_cases --only TC-ACC --limit 20

    # 3) 真执行（需已初始化 CAN 设备；SOME/IP 需回放库可用）
    python -m scripts.run_di_cases --execute --chan 0 --someip

    # 4) 用一张离线画面校验标贴（没有相机时也能验校验链路）
    python -m scripts.run_di_cases --execute --frame output_ocr/hud.png --only TC-ACC

    # 5) 导出 JSON 报告
    python -m scripts.run_di_cases --report logs/di_run.json

开关：`--format legacy|di|auto`（默认跟随 `HUD_TESTCASE_FORMAT` 或 `di`；本脚本面向 Di 用例，
默认取 `di`），旧格式仍由原解析链路处理，互不影响。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from can_data_tools import case_format, di_case_parser as parser, di_case_runner as runner  # noqa: E402
from can_data_tools.label_verify import LabelVerifier, LabelVerifierError                # noqa: E402
from hudcore import logging_setup                                                        # noqa: E402
from hudcore.platform.paths import paths                                                 # noqa: E402

LOGGER_NAME = "di_case"


def _frame_provider(args):
    """画面来源：离线图片（--frame）或相机（--camera）。"""
    if args.frame:
        frame_path = Path(args.frame)
        if not frame_path.is_file():
            print(f"[错误] 画面文件不存在：{frame_path}")
            return None
        return lambda: frame_path
    if args.camera:
        def _grab():
            from camera_tools.camera_preview import try_open_camera
            cap, index = try_open_camera(indices=(args.camera_index,))
            if index is None:
                return None
            ret, frame = cap.read()
            cap.release()
            return frame if ret else None
        return _grab
    return None


def _open_can(args):
    """真执行时打开 CAN 设备（由本脚本负责生命周期），返回 (sender, closer)。

    没有硬件/未插卡时返回 (None, None) 并打印可读提示；此时含 CAN 输入的用例会记为 error。
    """
    if not args.execute:
        return None, None
    try:
        from can_core import device
        dev, handles, threads = device.Initialize_Canfd_Device()
    except Exception as exc:                              # noqa: BLE001
        print(f"[错误] CAN 设备初始化异常：{exc}")
        return None, None
    if not dev or not handles:
        print("[错误] CAN 设备初始化失败（未插卡/驱动未就绪）；可先去掉 --execute 只做体检")
        return None, None
    if args.chan >= len(handles):
        print(f"[错误] 通道 {args.chan} 不存在（设备报告 {len(handles)} 个通道）")
        device.Close_Canfd_Device(dev, handles, threads)
        return None, None

    def _close():
        try:
            device.Close_Canfd_Device(dev, handles, threads)
        except Exception as exc:                          # noqa: BLE001
            print(f"[警告] 关闭 CAN 设备异常：{exc}")

    return runner.DeviceCanSender(handles[args.chan], msg_type=args.msg_type), _close


def _someip_controller(args):
    if not (args.execute and args.someip):
        return None
    try:
        return runner.SomeipReplayController(unicast=args.unicast)
    except Exception as exc:                              # noqa: BLE001 - 回放库不可用时给出可读提示
        print(f"[警告] SOME/IP 回放库不可用，字段型/链路型用例将被记为不可下发：{exc}")
        print("       " + _driver_hint())
        return None


def _driver_hint() -> str:
    from hudcore.someip import describe_library_status
    return describe_library_status().replace("\n", "\n       ")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Di 测试用例批量执行/体检")
    ap.add_argument("--cases", default=str(paths.project_root / parser.DEFAULT_CASE_DIR),
                    help="用例目录或单个 JSON 文件（默认 TestcaseCollection/Di_testcases）")
    ap.add_argument("--format", default="di", choices=["di", "legacy", "auto"],
                    help="用例格式开关（默认 di；legacy 走原解析链路，本脚本不处理）")
    ap.add_argument("--limit", type=int, default=None, help="最多执行多少条")
    ap.add_argument("--only", default=None, help="只跑 scenario_id 含该子串的用例")
    ap.add_argument("--auto-only", action="store_true", help="只跑输入可全部下发的用例")
    ap.add_argument("--execute", action="store_true", help="真下发（默认只体检）")
    ap.add_argument("--someip", action="store_true", help="真执行时同时驱动 SOME/IP（会打开服务端）")
    ap.add_argument("--unicast", default=None, help="SOME/IP 本机地址（默认由库决定）")
    ap.add_argument("--chan", type=int, default=0, help="CAN 通道号（默认 0）")
    ap.add_argument("--msg-type", default="canfd", choices=["can", "canfd"], help="下发报文类型")
    ap.add_argument("--frame", default=None, help="用这张离线画面校验标贴")
    ap.add_argument("--camera", action="store_true", help="用相机取帧校验标贴")
    ap.add_argument("--camera-index", type=int, default=0, help="相机序号（默认 0）")
    ap.add_argument("--wait-scale", type=float, default=1.0, help="wait_ms 缩放系数")
    ap.add_argument("--report", default=None, help="把 JSON 报告写到该路径")
    ap.add_argument("--summary-only", action="store_true", help="只打印汇总，不逐条列出")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    fmt = case_format.set_format(args.format)
    if fmt != case_format.DI:
        print(f"[提示] 当前开关 = {fmt}；本脚本处理 Di 用例，请用 --format di")
        return 2

    target = Path(args.cases)
    if not target.exists():
        print(f"[错误] 用例路径不存在：{target}")
        return 2

    cases = parser.load_cases(target)
    if not cases:
        print(f"[错误] 未从 {target} 解析出任何用例")
        return 2

    stats = parser.summarize(cases)
    print(f"== Di 用例集：{target} ==")
    print(f"用例 {stats['cases']} 个｜支持度 {stats['support']}")
    print(f"输入：CAN {stats['can_entries']} 条、SOME/IP 字段 {stats['someip_field_entries']} 条、"
          f"SOME/IP 链路 {stats['someip_link_entries']} 条、mem {stats['mem_entries']} 条")
    if stats["anomalies"]:
        print(f"格式特征：{stats['anomalies']}")

    verifier = None
    if args.frame or args.camera:
        try:
            verifier = LabelVerifier()
            coverage = verifier.coverage(
                [c.expected.primary_label for c in cases] +
                [c.expected.negative_label for c in cases])
            print(f"标贴参考图覆盖：{coverage['covered']}/{coverage['labels']} 个标签可校验"
                  f"（{coverage['uncovered']} 个无参考图，会记为 unverifiable）")
        except LabelVerifierError as exc:
            print(f"[警告] 标贴校验器不可用：{exc}")

    can_sender, close_can = _open_can(args)
    exec_runner = runner.DiCaseRunner(
        can_sender=can_sender,
        someip_controller=_someip_controller(args),
        frame_provider=_frame_provider(args),
        verifier=verifier,
        dry_run=not args.execute,
        wait_scale=args.wait_scale,
        on_log=lambda m: logging_setup.info(LOGGER_NAME, m),
    )
    if args.execute and exec_runner.can_sender is None and any(c.can for c in cases):
        print("[警告] 没有可用的 CAN 下发实现，含 CAN 输入的用例会记为 error")

    report = exec_runner.run_cases(cases, limit=args.limit, only=args.only,
                                   only_auto=args.auto_only)
    print(report.describe(limit=1 if args.summary_only else 12))
    if args.report:
        path = report.dump(args.report)
        print(f"报告已写入：{path}")

    if exec_runner.someip_controller is not None:
        exec_runner.someip_controller.close()
    if close_can is not None:
        close_can()

    failed = report.summary["status"].get(runner.STATUS_FAIL, 0)
    errors = report.summary["status"].get(runner.STATUS_ERROR, 0)
    return 1 if (failed or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
