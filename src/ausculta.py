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

def auscultar_repositorio(path_str: str):
    base_path = Path(path_str)
    if not base_path.exists() or not base_path.is_dir():
        print(f"[!] Diretório não encontrado ou inválido: {base_path}", file=sys.stderr)
        return
        
    print(f"[*] Auscultando repositório: {base_path.absolute()}")
    print("[*] Procurando entropia, funções longas (névoa) e código que não pulsa...\n")
    
    findings = []
    
    try:
        for py_file in base_path.rglob('*.py'):
            if any(part in ('.git', 'node_modules', '.venv', '__pycache__', 'build', 'dist') for part in py_file.parts):
                continue
            findings.extend(_analyze_file_ast(py_file))
    except Exception:
        pass
        
    def rank_score(finding):
        if finding.startswith('delete:'):
            return 3
        elif finding.startswith('yagni:'):
            return 2
        elif finding.startswith('shrink:'):
            return 1
        return 0
        
    findings.sort(key=rank_score, reverse=True)
    
    for f in findings:
        print(f)
        
    if not findings:
        print('Lean already. Ship.')
        return
        
    remocoes = len([f for f in findings if f.startswith('delete:') or f.startswith('yagni')])
    print(f'\nnet: -{remocoes} remoções propostas. Mantenha o sistema como um ACONTECIMENTO.')
