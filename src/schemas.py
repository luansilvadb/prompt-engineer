from typing import List, Optional
from pydantic import BaseModel

class OtimizacaoRequestDTO(BaseModel):
    skillOriginal: str
    modelName: Optional[str] = None
    modelPrefix: Optional[str] = None
    apiBase: Optional[str] = None
    apiKey: Optional[str] = None
    regrasAdicionais: Optional[List[str]] = None

class ConfigRequestDTO(BaseModel):
    modelName: Optional[str] = None
    modelPrefix: Optional[str] = None
    apiBase: Optional[str] = None
    apiKey: Optional[str] = None

class ConfigResponseDTO(BaseModel):
    modelName: str
    modelPrefix: str
    apiBase: str
    hasApiKey: bool

class CompileRequestDTO(BaseModel):
    optimizerType: Optional[str] = "bootstrap"
    minReward: Optional[float] = 0.8
