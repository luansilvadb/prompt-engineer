import re
def _parse_manteve_regras(manteve_str: str) -> bool:
    if manteve_str is None:
        return False
    manteve_str = str(manteve_str).strip().lower()
    if not manteve_str:
        return False

    if manteve_str.startswith('false') or manteve_str.startswith('falso'):
        return False
        
    if manteve_str.startswith('true') or manteve_str.startswith('verdadeiro') or manteve_str.startswith('sim') or manteve_str.startswith('yes'):
        return True

    matches = re.findall(r'\b(false|falso|não|nao|true|verdadeiro|sim|yes)\b', manteve_str)
    
    if not matches:
        return False
        
    first_marker = matches[0]
    if first_marker in ['false', 'falso', 'não', 'nao']:
        return False
        
    return True

print("Test 1:", _parse_manteve_regras("False. A regra da Fase 1 foi violada."))
print("Test 2:", _parse_manteve_regras("A regra 1 não foi mantida, logo False."))
print("Test 3:", _parse_manteve_regras("True. A skill não violou nenhuma regra."))
print("Test 4:", _parse_manteve_regras("A versão otimizada não manteve a regra da Fase 1..."))
print("Test 5:", _parse_manteve_regras("True"))
print("Test 6:", _parse_manteve_regras("A skill manteve a regra, sim."))
