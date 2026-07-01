from typing import List, Optional
from pydantic import BaseModel

class OtimizacaoRequestDTO(BaseModel):
    skillOriginal: str
    modelName: Optional[str] = None
    modelPrefix: Optional[str] = None
    apiBase: Optional[str] = None
    apiKey: Optional[str] = None
    regrasAdicionais: Optional[List[str]] = None
