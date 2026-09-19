# -*- coding: utf-8 -*-
"""can_gui —— CAN 信号自动收发界面

依赖 can_core（设备操作）与 can_data_tools（用例解析）。

依赖约束：上层（gui_handlers / can_gui / main）可依赖本包；
          本包不反向依赖界面层（保持可测试、可复用）。
说明：本文件只声明包边界与职责，不在导入时引入重依赖（无副作用）。
"""
