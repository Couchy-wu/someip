# mylog.py
import logging
import os
from datetime import datetime

# 使用字典管理多个 logger 实例，key: logger_name
loggers = {}

def setup_logger(logger_name, log_dir="./logs", log_prefix=None, level=logging.INFO, clear_old=False):
    """
    创建或获取一个独立的 logger，生成独立的日志文件
    :param logger_name: logger 的唯一标识（程序内部使用）
    :param log_dir: 日志保存目录
    :param log_prefix: 用户自定义日志文件名前缀，如 "name1"
    :param level: 日志级别
    :param clear_old: 是否删除日志目录下同前缀的旧日志文件
    :return: 配置好的 logger 实例
    """
    global loggers

    if logger_name in loggers:
        return loggers[logger_name]

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 如果开启清除旧日志功能
    if clear_old and log_prefix:
        try:
            for filename in os.listdir(log_dir):
                # 匹配以 "prefix_" 开头的 .log 文件
                if filename.startswith(f"{log_prefix}_") and filename.endswith(".log"):
                    file_path = os.path.join(log_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"[清理日志] 已删除旧日志文件: {file_path}")
        except Exception as e:
            print(f"[警告] 清除旧日志时发生错误: {e}")

    # 生成时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # 构造日志文件名：prefix_时间戳.log
    prefix = f"{log_prefix}_" if log_prefix else ""
    log_filename = f"{prefix}{timestamp}.log"
    log_file = os.path.join(log_dir, log_filename)

    # 创建唯一的 logger
    logger = logging.getLogger(f"MyLogger_{logger_name}")
    logger.setLevel(level)

    # 防止重复添加 handler
    if logger.handlers:
        logger.handlers.clear()

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    file_handler.setLevel(level)

    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # 添加处理器
    logger.addHandler(file_handler)

    # 缓存 logger
    loggers[logger_name] = logger

    return logger


def get_logger(logger_name):
    """
    获取已创建的 logger
    """
    if logger_name not in loggers:
        raise ValueError(f"Logger '{logger_name}' 未初始化，请先调用 setup_logger。")
    return loggers[logger_name]


def info(logger_name, msg):
    logger = get_logger(logger_name)
    logger.info(msg)


def debug(logger_name, msg):
    logger = get_logger(logger_name)
    logger.debug(msg)


def warning(logger_name, msg):
    logger = get_logger(logger_name)
    logger.warning(msg)


def error(logger_name, msg):
    logger = get_logger(logger_name)
    logger.error(msg)


def critical(logger_name, msg):
    logger = get_logger(logger_name)
    logger.critical(msg)


def close_logger(logger_name):
    """
    关闭并移除某个 logger（可选：释放资源）
    """
    if logger_name in loggers:
        for handler in loggers[logger_name].handlers:
            handler.close()
        del loggers[logger_name]



if __name__ == "__main__":
    # 创建第一个日志：保存在 logs1/，前缀为 "app"
    setup_logger(logger_name="app", log_dir="./logs1", log_prefix="app", level=logging.INFO)

    # 创建第二个日志：保存在 logs2/，前缀为 "debug"
    setup_logger(logger_name="debug", log_dir="./logs2", log_prefix="debug", level=logging.DEBUG)

    # 写入不同的日志文件
    info("app", "这是应用主日志")
    error("app", "出错了！")
    debug("app", "调试错误")

    info("debug", "这是调试日志")
    error("debug", "出错了！")
    debug("debug", "调试错误")

    # 输出：
    # ./logs1/app_2025-04-05_12-34-56.log
    # ./logs2/debug_2025-04-05_12-34-56.log