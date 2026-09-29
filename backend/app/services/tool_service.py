import ast
import json
import re
import time
import math
import hashlib
import operator
from typing import Dict, Any, List, Optional, Tuple
from backend.app.schemas.tool import (
    ToolDefinition,
    ToolParameter,
    ToolExecutionRequest,
    ToolExecutionResponse
)
from backend.app.core.logging import logger

# Supported safe arithmetic operators for AST math evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod
}


def _eval_ast(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported math operator: {type(node.op).__name__}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(operand)
    elif isinstance(node, ast.Call):
        # Allow safe math functions e.g. sqrt(144), sin(0), log(10)
        func_name = getattr(node.func, "id", None)
        allowed_math_funcs = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "log2": math.log2,
            "exp": math.exp,
            "floor": math.floor,
            "ceil": math.ceil,
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
        }
        if func_name in allowed_math_funcs:
            args = [_eval_ast(arg) for arg in node.args]
            return allowed_math_funcs[func_name](*args)
        raise ValueError(f"Function call '{func_name}' is not permitted in math sandbox.")
    else:
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


class SandboxedCodeExecutor:
    """Restricted AST Python code sandbox preventing system calls, I/O, and dunder escapes."""

    BANNED_NODES = (
        ast.Import,
        ast.ImportFrom,
        ast.Global,
        ast.Nonlocal,
        ast.Delete,
        ast.With,
        ast.AsyncWith,
    )

    SAFE_BUILTINS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "math": math,
    }

    @classmethod
    def execute_safe_python(cls, code: str, timeout_sec: float = 2.0) -> Tuple[bool, Any, Optional[str]]:
        """Parses AST, verifies security constraints, and executes in an isolated environment."""
        if not code or not code.strip():
            return False, None, "Code cannot be empty."

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, None, f"Syntax error: {e}"

        # AST Security Audit: Scan for forbidden operations
        for node in ast.walk(tree):
            if isinstance(node, cls.BANNED_NODES):
                return False, None, f"Security Violation: Statement '{type(node).__name__}' is forbidden in sandbox."
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, None, f"Security Violation: Dunder attribute access '{node.attr}' is forbidden."
            if isinstance(node, ast.Name) and node.id in ["eval", "exec", "open", "globals", "locals", "__import__", "compile"]:
                return False, None, f"Security Violation: Built-in '{node.id}' is forbidden."

        # Compile and execute in clean scope
        local_scope: Dict[str, Any] = {}
        global_scope: Dict[str, Any] = {"__builtins__": cls.SAFE_BUILTINS}

        try:
            compiled = compile(tree, filename="<sandbox>", mode="exec")
            exec(compiled, global_scope, local_scope)
            
            # Return result variable if defined, or all local variables
            result = local_scope.get("result", local_scope.get("output", local_scope))
            return True, result, None
        except Exception as e:
            return False, None, f"Runtime error: {e}"


class ToolExecutionEngine:
    """Provides sandboxed workspace tool registry and safe execution."""

    TOOLS: Dict[str, ToolDefinition] = {
        "calculate_expression": ToolDefinition(
            name="calculate_expression",
            display_name="Safe Math Calculator",
            category="math",
            description="Safely evaluate mathematical and arithmetic expressions without arbitrary code execution.",
            parameters=[
                ToolParameter(name="expression", type="string", description="Arithmetic formula e.g. '(120 * 45) + (10 ** 3)' or 'sqrt(144)'")
            ],
            workspace_types=["general", "developer", "finance", "research", "student"]
        ),
        "python_sandbox": ToolDefinition(
            name="python_sandbox",
            display_name="Safe Python Code Sandbox",
            category="code",
            description="Safely execute pure Python algorithms, data transformations, and calculations in a restricted sandbox.",
            parameters=[
                ToolParameter(name="code", type="string", description="Python code block storing output in 'result' variable.")
            ],
            workspace_types=["general", "developer", "research", "finance"]
        ),
        "format_json": ToolDefinition(
            name="format_json",
            display_name="JSON Formatter & Validator",
            category="code",
            description="Parses, validates, and beautifies JSON text.",
            parameters=[
                ToolParameter(name="raw_json", type="string", description="Raw unformatted or escaped JSON string"),
                ToolParameter(name="indent", type="integer", description="Spaces for indentation", required=False, default=2)
            ],
            workspace_types=["general", "developer", "research"]
        ),
        "regex_search": ToolDefinition(
            name="regex_search",
            display_name="Regex Pattern Extractor",
            category="system",
            description="Searches for pattern matches across text using regular expressions.",
            parameters=[
                ToolParameter(name="pattern", type="string", description="Regular expression pattern"),
                ToolParameter(name="text", type="string", description="Source text to search")
            ],
            workspace_types=["general", "developer", "research", "content"]
        ),
        "calculate_hash": ToolDefinition(
            name="calculate_hash",
            display_name="Cryptographic Hasher",
            category="system",
            description="Generates SHA256 or MD5 hashes for integrity verification.",
            parameters=[
                ToolParameter(name="data", type="string", description="Input string to hash"),
                ToolParameter(name="algorithm", type="string", description="Algorithm: 'sha256' or 'md5'", required=False, default="sha256")
            ],
            workspace_types=["general", "developer"]
        ),
        "summarize_text_stats": ToolDefinition(
            name="summarize_text_stats",
            display_name="Text Metrics & Word Counter",
            category="content",
            description="Computes word counts, character lengths, sentence totals, and estimated reading time.",
            parameters=[
                ToolParameter(name="text", type="string", description="Text to analyze")
            ],
            workspace_types=["general", "content", "student", "research", "hr"]
        ),
        "finance_compound_interest": ToolDefinition(
            name="finance_compound_interest",
            display_name="Compound Interest Calculator",
            category="finance",
            description="Calculates compound growth, total balance, and accrued interest over time.",
            parameters=[
                ToolParameter(name="principal", type="number", description="Starting principal amount"),
                ToolParameter(name="annual_rate_percent", type="number", description="Annual interest rate percentage e.g. 7.5"),
                ToolParameter(name="years", type="number", description="Investment period in years"),
                ToolParameter(name="compounding_frequency", type="integer", description="Times compounded per year (12 = monthly)", required=False, default=12)
            ],
            workspace_types=["general", "finance", "executive"]
        )
    }

    @classmethod
    def list_tools(cls, workspace_slug: Optional[str] = None) -> List[ToolDefinition]:
        tools = list(cls.TOOLS.values())
        if workspace_slug:
            return [t for t in tools if workspace_slug in t.workspace_types or "general" in t.workspace_types]
        return tools

    @classmethod
    def execute_tool(cls, request: ToolExecutionRequest) -> ToolExecutionResponse:
        tool = cls.TOOLS.get(request.tool_name)
        if not tool:
            return ToolExecutionResponse(
                tool_name=request.tool_name,
                status="error",
                result=None,
                error_message=f"Tool '{request.tool_name}' not found in registry.",
                execution_time_ms=0.0
            )

        start_time = time.perf_counter()
        args = request.arguments or {}

        try:
            if request.tool_name == "calculate_expression":
                expr = args.get("expression", "").strip()
                if not expr:
                    raise ValueError("Expression cannot be empty")
                tree = ast.parse(expr, mode="eval")
                val = _eval_ast(tree.body)
                result = {"expression": expr, "result": val}

            elif request.tool_name == "python_sandbox":
                code = args.get("code", "").strip()
                success, output, err = SandboxedCodeExecutor.execute_safe_python(code)
                if not success:
                    raise ValueError(err or "Execution error in Python sandbox")
                result = {"code": code, "output": output}

            elif request.tool_name == "format_json":
                raw = args.get("raw_json", "")
                indent = args.get("indent", 2)
                parsed = json.loads(raw)
                formatted = json.dumps(parsed, indent=indent)
                result = {"valid": True, "formatted_json": formatted, "keys_count": len(parsed) if isinstance(parsed, dict) else len(parsed)}

            elif request.tool_name == "regex_search":
                pattern = args.get("pattern", "")
                text = args.get("text", "")
                matches = re.findall(pattern, text)
                result = {"pattern": pattern, "match_count": len(matches), "matches": matches[:50]}

            elif request.tool_name == "calculate_hash":
                data = args.get("data", "")
                algo = args.get("algorithm", "sha256").lower()
                if algo == "md5":
                    h = hashlib.md5(data.encode("utf-8")).hexdigest()
                else:
                    h = hashlib.sha256(data.encode("utf-8")).hexdigest()
                result = {"algorithm": algo, "hash": h, "bytes_length": len(data.encode("utf-8"))}

            elif request.tool_name == "summarize_text_stats":
                text = args.get("text", "")
                words = text.split()
                sentences = re.split(r"[.!?]+", text)
                sentences = [s for s in sentences if s.strip()]
                reading_time_min = round(len(words) / 200.0, 1)
                result = {
                    "word_count": len(words),
                    "character_count": len(text),
                    "sentence_count": len(sentences),
                    "estimated_reading_minutes": reading_time_min
                }

            elif request.tool_name == "finance_compound_interest":
                principal = float(args.get("principal", 0))
                rate = float(args.get("annual_rate_percent", 0)) / 100.0
                years = float(args.get("years", 1))
                freq = int(args.get("compounding_frequency", 12))

                # Formula: A = P * (1 + r/n)**(n*t)
                total_balance = principal * ((1 + (rate / freq)) ** (freq * years))
                total_interest = total_balance - principal

                result = {
                    "principal": round(principal, 2),
                    "annual_rate_percent": round(rate * 100, 2),
                    "years": years,
                    "final_balance": round(total_balance, 2),
                    "total_interest_earned": round(total_interest, 2)
                }

            else:
                raise ValueError(f"Handler not implemented for {request.tool_name}")

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolExecutionResponse(
                tool_name=request.tool_name,
                status="success",
                result=result,
                error_message=None,
                execution_time_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Tool execution error for {request.tool_name}: {e}")
            return ToolExecutionResponse(
                tool_name=request.tool_name,
                status="error",
                result=None,
                error_message=str(e),
                execution_time_ms=elapsed_ms
            )
