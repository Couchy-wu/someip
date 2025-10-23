# mylog.py
import logging
import os
from datetime import datetime

# 使用字典管理多个 logger 实例，key: logger_name
loggers = {}

# 缓存 logger 的配置，用于延迟初始化
logger_configs = {}


def setup_logger(logger_name, log_dir="./logs", log_prefix=None, level=logging.INFO, clear_old=False):
    """
    创建或获取一个独立的 logger，生成独立的日志文件
    但：日志文件和处理器延迟到第一条日志写入时才创建
    :param logger_name: logger 的唯一标识（程序内部使用）
    :param log_dir: 日志保存目录
    :param log_prefix: 用户自定义日志文件名前缀，如 "name1"
    :param level: 日志级别
    :param clear_old: 是否删除日志目录下同前缀的旧日志文件
    :return: 配置好的 logger 实例
    """
    global loggers, logger_configs

    if logger_name in loggers:
        return loggers[logger_name]

    # 先缓存配置，不立即创建文件
    logger_configs[logger_name] = {
        "log_dir": log_dir,
        "log_prefix": log_prefix,
        "level": level,
        "clear_old": clear_old,
    }

    # 创建 logger 实例
    logger = logging.getLogger(f"MyLogger_{logger_name}")
    logger.setLevel(level)

    # 防止重复添加 handler
    if logger.handlers:
        logger.handlers.clear()

    # 添加延迟处理器
    handler = DelayedFileHandler(logger_name)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    handler.setLevel(level)

    logger.addHandler(handler)
    loggers[logger_name] = logger

    return logger


class DelayedFileHandler(logging.Handler):
    """
    延迟创建日志文件的 Handler
    只有在 emit 第一条日志时，才：
    - 确保目录存在
    - 清理旧日志（如果需要）
    - 生成时间戳和文件名
    - 创建真正的 FileHandler
    """

    def __init__(self, logger_name):
        super().__init__()
        self.logger_name = logger_name
        self._initialized = False
        self._real_handler = None  # 真正的 FileHandler

    def emit(self, record):
        if not self._initialized:
            self._setup()
        if self._real_handler:
            self._real_handler.emit(record)

    def _setup(self):
        """在第一次 emit 时执行初始化"""
        config = logger_configs.get(self.logger_name)
        if not config:
            raise ValueError(f"Logger '{self.logger_name}' 配置丢失")

        log_dir = config["log_dir"]
        log_prefix = config["log_prefix"]
        level = config["level"]
        clear_old = config["clear_old"]

        # =============== 第一步：确保日志目录存在 ===============
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"[错误] 无法创建日志目录 {log_dir}: {e}")
            self._initialized = True
            return

        # =============== 第二步：清除旧日志（如果需要） ===============
        if clear_old and log_prefix:
            try:
                for filename in os.listdir(log_dir):
                    if filename.startswith(f"{log_prefix}_") and filename.endswith(".log"):
                        file_path = os.path.join(log_dir, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"[清理日志] 已删除旧日志文件: {file_path}")
            except Exception as e:
                print(f"[警告] 清除旧日志时发生错误: {e}")

        # =============== 第三步：生成文件名（使用第一条日志的时间） ===============
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prefix = f"{log_prefix}_" if log_prefix else ""
        log_filename = f"{prefix}{timestamp}.log"
        log_file = os.path.join(log_dir, log_filename)

        # =============== 第四步：创建真正的 FileHandler ===============
        try:
            self._real_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
            self._real_handler.setFormatter(self.formatter)
            self._real_handler.setLevel(self.level)
        except Exception as e:
            print(f"[错误] 无法创建日志文件 {log_file}: {e}")

        self._initialized = True

    def close(self):
        """关闭资源"""
        if self._real_handler:
            self._real_handler.close()
        super().close()


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
        logger = loggers[logger_name]
        for handler in logger.handlers:
            handler.close()
        # 注意：不移除 logger 本身，避免重复创建
        # del loggers[logger_name]


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 设置 logger，此时不会创建文件或目录
    setup_logger(
        logger_name="app",
        log_dir="./logs/testcase",
        log_prefix="testcase",
        level=logging.INFO,
        clear_old=True  # 会清理旧的 testcase_*.log
    )

    # 此时 ./logs/testcase 目录还不存在，也没关系

    # 第一次写日志时才：
    # 1. 创建目录
    # 2. 清理旧日志（如果有）
    # 3. 生成时间戳
    # 4. 创建文件
    info("app", "这是第一条日志，此时才创建文件！")
    info("app", "这是第二条日志")
    error("app", "出错了")

    # 关闭 logger
    close_logger("app")
