import sys
import ast
from pathlib import Path

def _analyze_file_ast(py_file: Path) -> list:
    findings = []
    content = py_file.read_text(encoding='utf-8')
    tree = ast.parse(content)
    
    imports = set()
    usages = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.asname if alias.asname else alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname if alias.asname else alias.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                usages.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                usages.add(node.value.id)
                
    unused_imports = imports - usages
    if unused_imports:
        for imp in unused_imports:
            findings.append(f"delete: Import sem leitor '{imp}'. O que não pulsa, desaparece. [{py_file.name}]")
            
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if hasattr(node, 'end_lineno') and node.end_lineno is not None:
                lines = node.end_lineno - node.lineno
                if lines > 25:
                    findings.append(f"shrink: Função '{node.name}' tem {lines} linhas. Névoa cobrindo núcleo. Atomiza. [{py_file.name}:{node.lineno}]")
        elif isinstance(node, ast.ClassDef):
            if len(node.body) == 0 or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                findings.append(f"yagni: Classe vazia/especulativa '{node.name}'. Camada abstrata sem lastro. [{py_file.name}:{node.lineno}]")
                
    return findings


