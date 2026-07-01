import asyncio
from typing import Dict

class JobState:
    def __init__(self):
        self.logs = []
        self.mcts_nodes = []
        self.status = 'idle'
        self.result = None
        self.original_skill = ''
        self.model_name = None
        self.model_prefix = None
        self.api_base = None
        self.api_key = None
        self.regras_adicionais = ''
        self.is_deleted = False
        self.events_queue = asyncio.Queue()

jobs: Dict[str, JobState] = {}
