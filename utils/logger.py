"""
utils/logger.py
全局日志工具模块
功能：
1. 统一项目日志输出格式；包含时间、日志级别、模块名、日志内容
2. 支持控制台打印；可开关本地日志文件写入（读取config.ENABLE_FILE_LOG）
3. 日志文件自动输出到 PROJECT_ROOT/logs 目录
4. 对外暴露: logger 对象，整个项目全部使用本logger，禁止print打业务日志
依赖：config.py 的 ENABLE_FILE_LOG、PROJECT_ROOT
"""
import logging
import os
from pathlib import Path
from config import ENABLE_FILE_LOG, PROJECT_ROOT

# 日志存放目录
LOG_DIR: Path = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE_PATH = LOG_DIR / "dev_team_agent.log"

# 定义日志输出格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 获取根logger，防止第三方库日志干扰
logger = logging.getLogger("DevTeamAgent")
logger.setLevel(logging.INFO)
# 避免重复添加handler
logger.handlers.clear()

formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

# 1. 控制台输出handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 2. 文件输出handler，由ENABLE_FILE_LOG控制是否开启
if ENABLE_FILE_LOG:
    file_handler = logging.FileHandler(
        filename=LOG_FILE_PATH,
        encoding="utf-8",
        mode="a"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


if __name__ == "__main__":
    """
    自测命令：uv run python -m utils.logger
    测试日志打印，看控制台输出；开启时会写入 logs/dev_team_agent.log
    """
    logger.debug("这是debug调试日志")
    logger.info("这是info普通信息日志")
    logger.warning("这是warning警告日志")
    logger.error("这是error错误日志")
    print("✅ logger模块自测完成")
