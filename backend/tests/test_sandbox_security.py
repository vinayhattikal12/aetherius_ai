import pytest
from backend.app.services.tool_service import SandboxedCodeExecutor
from backend.app.core.config import settings


def test_sandbox_disabled_by_default():
    # Verify default state is False
    settings.ENABLE_PYTHON_SANDBOX = False
    success, output, err = SandboxedCodeExecutor.execute_safe_python("result = 1 + 1")
    assert success is False
    assert "disabled by default" in err


def test_sandbox_ast_violations_caught():
    settings.ENABLE_PYTHON_SANDBOX = True
    try:
        # Banned imports
        s, o, err = SandboxedCodeExecutor.execute_safe_python("import os\nresult = os.getcwd()")
        assert s is False
        assert "forbidden" in err.lower()

        # Banned builtins
        s, o, err = SandboxedCodeExecutor.execute_safe_python("f = open('secret.txt', 'r')")
        assert s is False
        assert "forbidden" in err.lower()

        # Dunder attributes
        s, o, err = SandboxedCodeExecutor.execute_safe_python("x = ().__class__.__bases__")
        assert s is False
        assert "dunder" in err.lower()
    finally:
        settings.ENABLE_PYTHON_SANDBOX = False


def test_sandbox_valid_math_and_logic():
    settings.ENABLE_PYTHON_SANDBOX = True
    try:
        code = """
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

result = fib(10)
"""
        success, output, err = SandboxedCodeExecutor.execute_safe_python(code)
        assert success is True
        assert output == 55
        assert err is None
    finally:
        settings.ENABLE_PYTHON_SANDBOX = False


def test_sandbox_timeout_infinite_loop():
    settings.ENABLE_PYTHON_SANDBOX = True
    try:
        code = """
while True:
    pass
"""
        success, output, err = SandboxedCodeExecutor.execute_safe_python(code, timeout_sec=0.5)
        assert success is False
        assert "timed out" in err.lower()
    finally:
        settings.ENABLE_PYTHON_SANDBOX = False
