from src.ausculta import _analyze_file_ast

def test_ausculta_unused_imports(tmp_path):
    # Setup: File with unused imports
    code = """
import os
import sys
from collections import Counter, defaultdict

print(Counter([1, 2, 2]))
"""
    test_file = tmp_path / "temp_code.py"
    test_file.write_text(code, encoding="utf-8")

    findings = _analyze_file_ast(test_file)

    # "os", "sys" and "defaultdict" should be flagged as unused
    assert any("Import sem leitor 'os'" in f for f in findings)
    assert any("Import sem leitor 'sys'" in f for f in findings)
    assert any("Import sem leitor 'defaultdict'" in f for f in findings)

    # "Counter" is used, so it shouldn't be flagged
    assert not any("Import sem leitor 'Counter'" in f for f in findings)

def test_ausculta_long_functions(tmp_path):
    # Setup: File with a function that has 26 lines
    lines = ["def long_function():"]
    for i in range(26):
        lines.append(f"    print({i})")

    code = "\n".join(lines)
    test_file = tmp_path / "temp_code.py"
    test_file.write_text(code, encoding="utf-8")

    findings = _analyze_file_ast(test_file)

    assert any("shrink: Função 'long_function'" in f for f in findings)

def test_ausculta_short_functions(tmp_path):
    code = """
def short_function():
    print("hello")
    print("world")
"""
    test_file = tmp_path / "temp_code.py"
    test_file.write_text(code, encoding="utf-8")

    findings = _analyze_file_ast(test_file)
    assert not any("shrink: Função" in f for f in findings)

def test_ausculta_empty_classes(tmp_path):
    code = """
class EmptyClass:
    pass

class ActiveClass:
    def method(self):
        pass
"""
    test_file = tmp_path / "temp_code.py"
    test_file.write_text(code, encoding="utf-8")

    findings = _analyze_file_ast(test_file)

    assert any("yagni: Classe vazia/especulativa 'EmptyClass'" in f for f in findings)
    assert not any("yagni: Classe vazia/especulativa 'ActiveClass'" in f for f in findings)
