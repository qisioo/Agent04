"""
utils/code_inspect.py
代码迭代的【增量Diff机制】核心工具
让程序员Agent修复bug时，只接收"结构骨架 + bug相关代码"，而非完整旧代码全文，从而大幅降低token。

三个核心能力：
1. extract_skeleton:      AST提取代码结构骨架（imports/函数签名/类，含行号），替代完整代码省token
2. find_bug_locations:    从测试报告定位bug位置（行号 + 函数名）
3. extract_relevant_code: 提取bug相关函数的完整实现 + 附近行上下文，作为重点修复对象
"""
import ast
import re


def extract_skeleton(code: str) -> str:
    """
    用AST解析代码，提取结构骨架（函数/类/imports签名 + 行号）
    只保留签名，不保留函数体，大幅降低token
    返回空字符串表示解析失败（调用方应回退完整代码）
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ast.unparse(node.args)
            out.append(f"def {node.name}({args})  # 行 {node.lineno}-{node.end_lineno}")
        elif isinstance(node, ast.ClassDef):
            out.append(f"class {node.name}  # 行 {node.lineno}-{node.end_lineno}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = ast.unparse(sub.args)
                    out.append(f"  def {sub.name}({args})  # 行 {sub.lineno}-{sub.end_lineno}")
        elif isinstance(node, ast.Import):
            out.append(f"import {', '.join(a.name for a in node.names)}  # 行 {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            out.append(f"from {node.module} import {', '.join(a.name for a in node.names)}  # 行 {node.lineno}")
    return "\n".join(out)


def find_bug_locations(code: str, test_report: str | None) -> dict:
    """
    从测试报告定位bug位置，返回 {"lines":[...], "funcs":[...]}
    lines: 有效行号列表（过滤到文件行数范围内）
    funcs: 测试报告中提到的、且代码里真实存在的函数名
    """
    total = len(code.splitlines())
    lines = set()
    for m in re.finditer(r"(?:第)?\s*(\d{1,4})\s*(?:行|line)", test_report or "", re.IGNORECASE):
        n = int(m.group(1))
        if 1 <= n <= total:
            lines.add(n)
    # 收集代码里真实存在的函数名
    try:
        tree = ast.parse(code)
        func_names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    except SyntaxError:
        func_names = set()
    funcs = []
    for name in func_names:
        # 函数名以"后跟括号或'函数'字样"的形式出现在测试报告中才算提到该函数
        if re.search(rf"{re.escape(name)}\s*(?:\(|函数)", test_report or ""):
            funcs.append(name)
    return {"lines": sorted(lines), "funcs": funcs}


def extract_relevant_code(code: str, funcs: list, lines: list, window: int = 8) -> str:
    """
    提取bug相关代码：
    - funcs 里每个函数的完整函数体（含前后window行）
    - lines 里每个行号附近 ±window 行
    返回带行号的代码文本；无相关内容返回空字符串
    """
    code_lines = code.splitlines()
    selected = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in funcs:
                for i in range(node.lineno, node.end_lineno + 1):
                    selected.add(i)
                for i in range(max(1, node.lineno - window), min(len(code_lines), node.end_lineno + window) + 1):
                    selected.add(i)
    for ln in lines:
        for i in range(max(1, ln - window), min(len(code_lines), ln + window) + 1):
            selected.add(i)
    if not selected:
        return ""
    ctx = [f"{i:4d} | {code_lines[i-1]}" for i in sorted(selected)]
    return "\n".join(ctx)
