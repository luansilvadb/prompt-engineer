def _parse_manteve_regras(manteve_str: str) -> bool:
    if manteve_str is None:
        return False
    manteve_str = str(manteve_str).strip().lower()
    if not manteve_str:
        return False
    false_markers = ['false', 'não', 'nao', 'no', '0']
    if any(m == manteve_str or manteve_str.startswith(m) for m in false_markers):
        return False
    if manteve_str.startswith('un') and 'true' in manteve_str:
        return False
    true_markers = ['true', 'sim', 'yes', '1']
    return any(m in manteve_str for m in true_markers)

print('Test 1:', _parse_manteve_regras('False. A regra da Fase 1 foi violada.'))
print('Test 2:', _parse_manteve_regras('A regra 1 não foi mantida, logo False.'))
print('Test 3:', _parse_manteve_regras('Falso. Manteve as regras? Não.'))
print('Test 4:', _parse_manteve_regras('False. Fase 1'))
print('Test 5:', _parse_manteve_regras('False. simples'))
