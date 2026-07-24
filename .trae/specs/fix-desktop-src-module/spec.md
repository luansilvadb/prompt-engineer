# Corrigir ModuleNotFoundError: src no Build Desktop

## Why
Após corrigir os caminhos do `.spec`, o build compila mas o executável falha em runtime com `ModuleNotFoundError: No module named 'src.api'`. O PyInstaller não inclui o pacote `src` porque o `pathex` no Analysis está vazio, e o diretório raiz do projeto não está no path de busca de módulos.

## What Changes
- Adicionar `'.'` ao `pathex` no `SkillOptimizer.spec` para que o PyInstaller encontre o pacote `src` a partir da raiz do projeto

## Impact
- Affected specs: Nenhum
- Affected code: `SkillOptimizer.spec`

## MODIFIED Requirements
### Requirement: Build Desktop
O sistema DEVE incluir o pacote `src` e suas dependências no executável desktop.

#### Scenario: Executável funcional
- **WHEN** o executável `SkillOptimizer.exe` é iniciado
- **THEN** o módulo `src.api` é encontrado e o servidor FastAPI inicia sem `ModuleNotFoundError`
