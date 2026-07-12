import ast
from pathlib import Path

def _get_imports_from_node(node: ast.AST) -> set:
    imported = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            imported.add(alias.asname if alias.asname else alias.name.split('.')[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            imported.add(alias.asname if alias.asname else alias.name)
    return imported


def _get_usage_from_node(node: ast.AST) -> set:
    used = set()
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        used.add(node.id)
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        used.add(node.value.id)
    return used


def _collect_imports_and_usages(tree: ast.AST) -> tuple:
    imports = set()
    usages = set()
    for node in ast.walk(tree):
        imports.update(_get_imports_from_node(node))
        usages.update(_get_usage_from_node(node))
    return imports, usages


def _analyze_function_node(node: ast.FunctionDef, py_file_name: str) -> list:
    findings = []
    if hasattr(node, 'end_lineno') and node.end_lineno is not None:
        lines = node.end_lineno - node.lineno
        if lines > 25:
            findings.append(
                f"shrink: Função '{node.name}' tem {lines} linhas. Névoa cobrindo núcleo. Atomiza. [{py_file_name}:{node.lineno}]"
            )
    return findings


def _analyze_class_node(node: ast.ClassDef, py_file_name: str) -> list:
    findings = []
    is_empty = len(node.body) == 0
    is_speculative = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
    if is_empty or is_speculative:
        findings.append(
            f"yagni: Classe vazia/especulativa '{node.name}'. Camada abstrata sem lastro. [{py_file_name}:{node.lineno}]"
        )
    return findings


def _analyze_structure(tree: ast.AST, py_file_name: str) -> list:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            findings.extend(_analyze_function_node(node, py_file_name))
        elif isinstance(node, ast.ClassDef):
            findings.extend(_analyze_class_node(node, py_file_name))
    return findings


def _check_unused_imports(imports: set, usages: set, py_file_name: str) -> list:
    findings = []
    unused_imports = imports - usages
    for imp in sorted(unused_imports):
        findings.append(f"delete: Import sem leitor '{imp}'. O que não pulsa, desaparece. [{py_file_name}]")
    return findings


def _analyze_file_ast(py_file: Path) -> list:
    content = py_file.read_text(encoding='utf-8')
    tree = ast.parse(content)

    imports, usages = _collect_imports_and_usages(tree)

    findings = []
    findings.extend(_check_unused_imports(imports, usages, py_file.name))
    findings.extend(_analyze_structure(tree, py_file.name))

    return findings


