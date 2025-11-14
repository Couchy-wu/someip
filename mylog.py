import logging
import os
from datetime import datetime

# 使用字典管理多个 logger 实例，key: logger_name
loggers = {}

# 缓存 logger 的配置，用于延迟初始化
logger_configs = {}


def setup_logger(logger_name, log_dir="./logs", log_prefix=None, level=logging.INFO, clear_old=False, use_timestamp=True, show_prefix=True):
    """
    创建或获取一个独立的 logger，生成独立的日志文件
    但：日志文件和处理器延迟到第一条日志写入时才创建
    :param logger_name: logger 的唯一标识（程序内部使用）
    :param log_dir: 日志保存目录
    :param log_prefix: 用户自定义日志文件名前缀，如 "name1"
    :param level: 日志级别
    :param clear_old: 是否删除日志目录下同前缀的旧日志文件
    :param use_timestamp: 是否在日志文件名中添加时间戳。False 表示只用 log_prefix.log
    :param show_prefix: 是否显示日志前缀（时间戳和日志级别）。False 表示只输出消息内容
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
        "use_timestamp": use_timestamp,
        "show_prefix": show_prefix,  # 新增
    }

    # 创建 logger 实例
    logger = logging.getLogger(f"MyLogger_{logger_name}")
    logger.setLevel(level)

    # 防止重复添加 handler
    if logger.handlers:
        logger.handlers.clear()

    # 添加延迟处理器
    handler = DelayedFileHandler(logger_name)
    
    # 根据 show_prefix 创建默认 formatter（临时，真正 formatter 在 _setup 中设置）
    if show_prefix:
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter('%(message)s')

    handler.setFormatter(formatter)  # 这个 formatter 会被 _setup 覆盖，但用于临时 emit
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
    - 生成文件名（可选带时间戳）
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
        use_timestamp = config.get("use_timestamp", True)
        show_prefix = config.get("show_prefix", True)  # 获取新参数

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
                # 根据 use_timestamp 的值确定要删除的文件模式
                if use_timestamp:
                    # 带时间戳模式：删除所有以 log_prefix_ 开头的文件
                    for filename in os.listdir(log_dir):
                        if filename.startswith(f"{log_prefix}_") and filename.endswith(".log"):
                            file_path = os.path.join(log_dir, filename)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                print(f"[清理日志] 已删除旧日志文件: {file_path}")
                else:
                    # 不带时间戳模式：只删除与当前日志文件同名的文件
                    current_log_filename = f"{log_prefix}.log"
                    file_path = os.path.join(log_dir, current_log_filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"[清理日志] 已删除旧日志文件: {file_path}")
            except Exception as e:
                print(f"[警告] 清除旧日志时发生错误: {e}")

        # =============== 第三步：生成文件名 ===============
        prefix = log_prefix or "app"
        if use_timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"{prefix}_{timestamp}.log"
        else:
            log_filename = f"{prefix}.log"

        log_file = os.path.join(log_dir, log_filename)

        # =============== 第四步：创建真正的 FileHandler ===============
        try:
            self._real_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
            self._real_handler.setLevel(level)

            # 根据 show_prefix 设置 formatter
            if show_prefix:
                formatter = logging.Formatter(
                    '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            else:
                formatter = logging.Formatter('%(message)s')

            self._real_handler.setFormatter(formatter)

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


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 示例：不显示日志前缀（时间戳、INFO 等）
    setup_logger(
        logger_name="simple",
        log_dir="./logs",
        log_prefix="simple",
        level=logging.INFO,
        clear_old=True,
        use_timestamp=False,
        show_prefix=False  
    )

    info("simple", "这条日志将不包含任何前缀，只有这句话本身")
    debug("simple", "调试信息也一样")
