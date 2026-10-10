"""
utils/code_sandbox.py
代码真实执行沙箱

职责：
1. 在隔离的临时目录中真实运行生成的Python代码，不再"只看代码"
2. 设置执行超时，防止死循环/无限等待耗尽资源
3. 捕获 stdout / stderr / returncode，供测试工程师判断真实运行结果
4. 仅用Python标准库（subprocess/tempfile），不引入第三方依赖

说明：
- 本模块提供"真实执行验证"能力，是解决"测试没发现真问题"的基础
- 出于安全考虑：只在临时目录运行，不接触项目主目录；限制超时；不落盘敏感数据
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from config import SANDBOX_TIMEOUT
from utils.logger import logger


class CodeRunResult:
    """代码运行结果对象，封装真实执行后的全部信息"""
    def __init__(self, returncode, stdout, stderr, timed_out=False, error="", timeout=None):
        self.returncode = returncode      # 0=正常退出；非0=运行异常
        self.stdout = stdout              # 标准输出
        self.stderr = stderr              # 标准错误
        self.timed_out = timed_out        # 是否执行超时
        self.error = error                # 执行前的错误（如代码为空）
        self.timeout = timeout            # 本次实际生效的超时秒数

    @property
    def success(self) -> bool:
        """是否成功：非超时、非前置错误、returncode==0"""
        if self.error:
            return False
        if self.timed_out:
            return False
        return self.returncode == 0

    @property
    def summary(self) -> str:
        """精简结果摘要，供测试报告引用，避免超长文本挤爆上下文"""
        if self.error:
            return f"执行错误：{self.error}"
        if self.timed_out:
            return f"执行超时（>{self.timeout or SANDBOX_TIMEOUT}s），可能陷入死循环"
        if self.returncode != 0:
            return f"运行失败，退出码={self.returncode}，错误摘要：{self.stderr[:500]}"
        return "运行成功，无报错"


def run_python_code(code: str, timeout: int | None = None) -> CodeRunResult:
    """
    在隔离临时目录中真实运行一段Python代码
    :param code: 待执行的完整Python源码字符串
    :param timeout: 超时秒数，不传则取config.SANDBOX_TIMEOUT
    :return: CodeRunResult
    """
    if not code or not code.strip():
        return CodeRunResult(returncode=-1, stdout="", stderr="", error="代码内容为空",
                             timeout=timeout or SANDBOX_TIMEOUT)

    use_timeout = timeout or SANDBOX_TIMEOUT

    # 隔离临时目录运行，避免与项目主目录冲突、防止污染项目文件
    with tempfile.TemporaryDirectory(prefix="agent04_sandbox_") as tmp_dir:
        tmp_file = Path(tmp_dir) / "main.py"
        try:
            tmp_file.write_text(code, encoding="utf-8")
        except Exception as e:
            return CodeRunResult(returncode=-1, stdout="", stderr="", error=f"写临时文件失败：{str(e)}",
                                 timeout=use_timeout)

        try:
            # 强制子进程python以UTF-8输出，解决Windows控制台默认GBK导致的中文乱码
            import os
            run_env = os.environ.copy()
            run_env["PYTHONIOENCODING"] = "utf-8"
            # 在临时目录下用当前解释器执行，捕获全部输出
            proc = subprocess.run(
                [sys.executable, str(tmp_file)],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=use_timeout,
                encoding="utf-8",
                errors="replace",
                env=run_env,
            )
            return CodeRunResult(
                returncode=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                timeout=use_timeout,
            )
        except subprocess.TimeoutExpired as e:
            logger.warning(f"代码执行超时（>{use_timeout}s），已强制终止")
            return CodeRunResult(
                returncode=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or "") + "\n[执行超时，已强制终止]",
                timed_out=True,
                timeout=use_timeout,
            )
        except Exception as e:
            return CodeRunResult(returncode=-1, stdout="", stderr="", error=f"执行异常：{str(e)}",
                                 timeout=use_timeout)


if __name__ == "__main__":
    """自测：uv run python -m utils.code_sandbox"""
    print("==== code_sandbox 自测 ====")
    # 1. 正常代码
    ok = run_python_code("print('hello sandbox')")
    print(f"正常代码  → success={ok.success}, stdout={ok.stdout.strip()}, summary={ok.summary}")
    # 2. 报错代码
    err = run_python_code("print(1/0)")
    print(f"报错代码  → success={err.success}, returncode={err.returncode}, summary={err.summary}")
    # 3. 死循环代码（会触发超时，用2秒验证）
    to = run_python_code("while True: pass", timeout=2)
    print(f"死循环    → timed_out={to.timed_out}, success={to.success}, summary={to.summary}")
    print("✅ code_sandbox 自测完成")
