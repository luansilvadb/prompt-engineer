import re
def _parse_manteve_regras(manteve_str: str) -> bool:
    if manteve_str is None:
        return False
    manteve_str = str(manteve_str).strip().lower()
    if not manteve_str:
        return False
        
    # Primeiro checamos se existe uma afirmação clara de FALSO
    false_words = r'\b(false|falso|não|nao|no|0)\b'
    
    # Mas cuidado com negações como "não omitiu" (que significa True)
    # Então vamos buscar os padrões.
    
    # Vamos achar a última palavra relevante (true/false) pois o modelo as vezes raciocina antes
    matches = re.findall(r'\b(false|falso|não|nao|no|0|true|verdadeiro|sim|yes|1)\b', manteve_str)
    
    if not matches:
        # Tenta fallback para buscar dentro da string se não achar palavras soltas
        if 'false' in manteve_str: return False
        if 'true' in manteve_str: return True
        return False
        
    last_marker = matches[-1]
    if last_marker in ['false', 'falso', 'não', 'nao', 'no', '0']:
        return False
    return True

print("Test 1:", _parse_manteve_regras("False. A regra da Fase 1 foi violada."))
print("Test 2:", _parse_manteve_regras("A regra 1 não foi mantida, logo False."))
print("Test 3:", _parse_manteve_regras("Falso. Manteve as regras? Não."))
print("Test 4:", _parse_manteve_regras("A versão otimizada não manteve a regra da Fase 1..."))
print("Test 5:", _parse_manteve_regras("True"))
print("Test 6:", _parse_manteve_regras("It is true that the rules were kept."))
