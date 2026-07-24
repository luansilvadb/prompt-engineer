# Corrigir Caminhos do Build Desktop

## Why
O build desktop falha porque o `SkillOptimizer.spec` está localizado em `d:\good\scripts\` e contém caminhos relativos incorretos. O PyInstaller resolve caminhos na seção `Analysis` relativos ao diretório do `.spec`, causando a duplicação `scripts/scripts/desktop.py`.

## What Changes
- Mover `scripts/SkillOptimizer.spec` para a raiz do projeto (`d:\good\`)
- Atualizar `build_desktop.ps1` para referenciar o `.spec` na nova localização

## Impact
- Affected specs: Nenhum
- Affected code: `scripts/SkillOptimizer.spec`, `build_desktop.ps1`

## MODIFIED Requirements
### Requirement: Build Desktop
O sistema DEVE compilar o executável desktop com sucesso a partir da raiz do projeto.

#### Scenario: Build bem-sucedido
- **WHEN** o usuário executa `.\build_desktop.ps1`
- **THEN** o PyInstaller localiza corretamente `scripts/desktop.py`, `frontend/` e `src/outputs/`
- **AND** o executável `dist/SkillOptimizer/SkillOptimizer.exe` é gerado
