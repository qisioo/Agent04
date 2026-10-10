"""
config.py 项目根目录
全局配置模块
.env仅配置4项：
DEEPSEEK_API_KEY      # 必填，deepseek密钥
DEEPSEEK_MODEL        # 必填，模型名称
MAX_ITERATIONS        # 选填，整个graph最大循环轮次
SANDBOX_TIMEOUT       # 选填，沙箱超时秒数

.env没有的配置全部使用代码内置默认值，不会报缺失异常
所有路径常量在此统一管理，业务代码禁止直接操作os.environ
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ===================== 项目路径定义 =====================
# config.py在项目根目录，__file__取当前文件路径
PROJECT_ROOT: Path = Path(__file__).parent
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
AGENTS_DIR: Path = PROJECT_ROOT / "agents"
UTILS_DIR: Path = PROJECT_ROOT / "utils"

# 自动创建输出文件夹，已存在不会报错
OUTPUTS_DIR.mkdir(exist_ok=True, parents=True)

# 加载根目录 .env 文件
env_file = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_file, override=True)


def _get_str_env(env_key: str, default: str | None = None):
    """
    读取字符串环境变量
    :param env_key: .env中的变量名
    :param default: 不存在时返回默认；default=None代表【必填】，为空直接抛错
    """
    raw_val = os.environ.get(env_key)
    if raw_val is not None:
        raw_val = raw_val.strip()

    # 必填项，为空直接抛出明确错误
    if default is None and (not raw_val):
        raise ValueError(f"【必填缺失】.env 必须配置 {env_key}")
    if raw_val is None:
        return default
    return raw_val


def _get_int_env(env_key: str, default: int):
    """
    读取整数环境变量，选填，读取失败直接返回默认值，不崩溃
    :param env_key: .env变量名
    :param default: 读取不到/格式错误就使用该默认值
    """
    raw_val = os.environ.get(env_key)
    if not raw_val:
        return default
    try:
        return int(raw_val.strip())
    except ValueError:
        # 数字格式错误，打印提示，使用默认值继续运行，不中断程序
        print(f"[WARN] {env_key} 格式不是整数，使用默认值:{default}")
        return default


# ===================== 从.env读取 4个变量 =====================
# 必填：密钥、模型名称
DEEPSEEK_API_KEY = _get_str_env("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = _get_str_env("DEEPSEEK_MODEL")

# 选填：没有写在.env会使用内置默认
MAX_ITERATIONS = _get_int_env("MAX_ITERATIONS", default=15)
SANDBOX_TIMEOUT = _get_int_env("SANDBOX_TIMEOUT", default=60)

# ===================== 项目内部常量（不在.env配置，代码写死默认） =====================
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
LLM_TEMPERATURE = 0          # agent开发场景，温度固定0，确定性输出
ENABLE_CODE_SANDBOX = False  # 默认关闭沙箱
ENABLE_FILE_LOG = True       # 默认开启本地日志输出


def get_config_mask_summary() -> dict:
    """
    获取配置摘要，密钥做掩码，打印日志使用，防止明文密钥泄露
    """
    mask_key = "***" + DEEPSEEK_API_KEY[-6:] if len(DEEPSEEK_API_KEY) > 6 else "***"
    summary = {
        "project_root": str(PROJECT_ROOT),
        "outputs_dir": str(OUTPUTS_DIR),
        "deepseek_model": DEEPSEEK_MODEL,
        "api_key_mask": mask_key,
        "max_iterations": MAX_ITERATIONS,
        "sandbox_timeout": SANDBOX_TIMEOUT,
        "temperature": LLM_TEMPERATURE,
    }
    return summary


if __name__ == "__main__":
    """
    自测入口
    PowerShell命令： uv run python config.py
    只校验两个必填项，剩下两项缺失/格式错不会抛异常
    """
    print("==== config配置自检 ====")
    for k, v in get_config_mask_summary().items():
        print(f"{k:<20} → {v}")
    print("✅ config加载完成\n")
