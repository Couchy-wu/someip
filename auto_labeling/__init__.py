# -*- coding: utf-8 -*-
"""auto_labeling —— 自动标注辅助：模板匹配、画框、生成标注

preprocessing.py 提供共用图像预处理；template_matching/ 为模板匹配算法。

依赖约束：上层（gui_handlers / can_gui / main）可依赖本包；
          本包不反向依赖界面层（保持可测试、可复用）。
说明：本文件只声明包边界与职责，不在导入时引入重依赖（无副作用）。
"""
