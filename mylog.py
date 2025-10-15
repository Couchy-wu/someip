# mylog.py
import logging
import os
from datetime import datetime

# 全局变量保存 logger 实例
logger = None

def setup_logger(log_dir="./logs", level=logging.INFO):
    """
    初始化日志系统
    :param log_dir: 日志保存的目录
    :param level: 日志级别
    :return: 配置好的 logger
    """
    global logger

    # 如果已初始化，不再重复初始化
    if logger is not None:
        return logger

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 生成日志文件名：年-月-日_时-分-秒.log
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"{timestamp}.log")

    # 创建 logger
    logger = logging.getLogger("MyLogger")
    logger.setLevel(level)

    # 防止重复添加 handler
    if logger.handlers:
        logger.handlers.clear()

    # 创建文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    file_handler.setLevel(level)

    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # 添加 handler 到 logger
    logger.addHandler(file_handler)

    return logger


def info(msg):
    logger = setup_logger()
    logger.info(msg)

def debug(msg):
    logger = setup_logger()
    logger.debug(msg)

def warning(msg):
    logger = setup_logger()
    logger.warning(msg)

def error(msg):
    logger = setup_logger()
    logger.error(msg)

def critical(msg):
    logger = setup_logger()
    logger.critical(msg)
