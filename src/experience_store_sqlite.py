"""
Experience Store — SQLite Backend com schema versionado.

Substitui o armazenamento JSON Lines + dict em memória por SQLite com:
- Persistência entre reinícios (não perde experiências)
- Índices para query_similar (busca por texto completo)
- WAL mode para leitura concorrente durante escrita
- Migração automática do formato antigo JSON Lines

Implementa IExperienceStore (Protocol).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

# Reutiliza a classe Experience do módulo existente
from src.experience_store import Experience, _compute_idf, _compute_tf, _cosine_similarity, _tokenize

EXPERIENCES_DIR = Path("src/outputs/experiences")
DB_PATH = EXPERIENCES_DIR / "experiences.db"
SCHEMA_VERSION = 1


# ── SQLite Store ─────────────────────────────────────────────────────────────

class SqliteExperienceStore:
    """
    Experience Store com backend SQLite.

    Schema versionado (coluna user_version no PRAGMA).
    Suporta migração automática do formato antigo JSON Lines na primeira execução.
    """

    def __init__(self, gamma: float = 0.995, max_experiences: int = 500):
        self.gamma = gamma
        self.max_experiences = max_experiences
        EXPERIENCES_DIR.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
        self._conn.execute("PRAGMA busy_timeout=5000")  # 5s timeout em lock

        self._ensure_schema()
        self._migrate_from_jsonl_if_needed()

    def _ensure_schema(self) -> None:
        """Cria tabelas e índices se não existirem, aplica migrações de schema."""
        current_version = self._conn.execute("PRAGMA user_version").fetchone()[0]

        if current_version < 1:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_hash TEXT NOT NULL,
                    mutation_strategy TEXT NOT NULL,
                    delta_reward REAL NOT NULL DEFAULT 0.0,
                    absolute_reward REAL NOT NULL DEFAULT 0.0,
                    feedback TEXT NOT NULL DEFAULT '',
                    timestamp REAL NOT NULL,
                    parent_instruction_hash TEXT NOT NULL DEFAULT '',
                    instruction TEXT NOT NULL DEFAULT '',
                    parent_instruction TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_skill_hash ON experiences(skill_hash);
                CREATE INDEX IF NOT EXISTS idx_strategy ON experiences(mutation_strategy);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON experiences(timestamp);
                CREATE INDEX IF NOT EXISTS idx_delta ON experiences(delta_reward);

                PRAGMA user_version = 1;
                """
            )

    def _migrate_from_jsonl_if_needed(self) -> None:
        """Na primeira execução, importa experiências do formato JSON Lines antigo."""
        jsonl_path = EXPERIENCES_DIR / "experience_log.jsonl"
        if not jsonl_path.exists():
            return

        # Verifica se já importamos (marcador no banco)
        marker = self._conn.execute(
            "SELECT COUNT(*) FROM experiences"
        ).fetchone()[0]
        if marker > 0:
            return  # Já tem dados, pula migração

        imported = 0
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        exp = Experience.from_dict(json.loads(line))
                        self._conn.execute(
                            """INSERT INTO experiences
                               (skill_hash, mutation_strategy, delta_reward, absolute_reward,
                                feedback, timestamp, parent_instruction_hash, instruction, parent_instruction)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                exp.skill_hash,
                                exp.mutation_strategy,
                                exp.delta_reward,
                                exp.absolute_reward,
                                exp.feedback,
                                exp.timestamp,
                                exp.parent_instruction_hash,
                                exp.instruction,
                                exp.parent_instruction,
                            ),
                        )
                        imported += 1
                    except Exception:
                        continue

            self._conn.commit()

            # Renomeia o arquivo antigo como backup
            if imported > 0:
                backup = jsonl_path.with_suffix(".jsonl.bak")
                jsonl_path.rename(backup)
        except Exception:
            pass  # Arquivo corrompido ou inacessível — começar limpo

    @property
    def experiences(self) -> list[Experience]:
        """Retorna todas as experiências como objetos Experience (compatível com IExperienceStore)."""
        rows = self._conn.execute(
            "SELECT * FROM experiences ORDER BY timestamp DESC"
        ).fetchall()
        return [Experience.from_dict(dict(r)) for r in rows]

    def save(self) -> None:
        """Garante que todas as escritas estão persistidas (commit explícito)."""
        self._conn.commit()

    def add(self, experience: Experience) -> None:
        """Adiciona uma experiência e trunca se ultrapassar max_experiences."""
        self._conn.execute(
            """INSERT INTO experiences
               (skill_hash, mutation_strategy, delta_reward, absolute_reward,
                feedback, timestamp, parent_instruction_hash, instruction, parent_instruction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experience.skill_hash,
                experience.mutation_strategy,
                experience.delta_reward,
                experience.absolute_reward,
                experience.feedback,
                experience.timestamp,
                experience.parent_instruction_hash,
                experience.instruction,
                experience.parent_instruction,
            ),
        )

        # Truncar se exceder limite (mantém apenas as max_experiences mais recentes)
        count = self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
        if count > self.max_experiences:
            excess = count - self.max_experiences
            self._conn.execute(
                "DELETE FROM experiences WHERE id IN "
                "(SELECT id FROM experiences ORDER BY timestamp ASC LIMIT ?)",
                (excess,),
            )

    def query_similar(self, feedback_query: str, top_k: int = 5) -> list[Experience]:
        """
        Busca experiências com feedback similar usando TF-IDF + cosine similarity.
        Híbrido: carrega do SQLite e computa similaridade em memória (TF-IDF é leve).
        """
        rows = self._conn.execute(
            "SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?",
            (self.max_experiences,),
        ).fetchall()

        if not rows:
            return []

        all_experiences = [Experience.from_dict(dict(r)) for r in rows]
        query_tokens = _tokenize(feedback_query)

        if not query_tokens:
            return all_experiences[-top_k:]

        all_doc_tokens = [_tokenize(exp.feedback) for exp in all_experiences]
        all_doc_tokens.append(query_tokens)
        idf = _compute_idf(all_doc_tokens)

        query_tf = _compute_tf(query_tokens)
        query_tfidf = {word: tf * idf.get(word, 1.0) for word, tf in query_tf.items()}

        now = time.time()
        scored = []
        for i, exp in enumerate(all_experiences):
            doc_tf = _compute_tf(all_doc_tokens[i])
            doc_tfidf = {word: tf * idf.get(word, 1.0) for word, tf in doc_tf.items()}
            sim = _cosine_similarity(query_tfidf, doc_tfidf)

            age_days = (now - exp.timestamp) / 86400.0
            decay = self.gamma**age_days
            scored.append((sim * decay, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def get_strategy_stats(self) -> dict[str, dict[str, float]]:
        """Agrega estatísticas por mutation_strategy diretamente no SQL."""
        rows = self._conn.execute(
            """SELECT mutation_strategy,
                      SUM(delta_reward) as total_delta,
                      COUNT(*) as count,
                      SUM(absolute_reward) as total_reward
               FROM experiences
               GROUP BY mutation_strategy"""
        ).fetchall()

        stats: dict[str, dict[str, float]] = {}
        for r in rows:
            count = r["count"]
            stats[r["mutation_strategy"]] = {
                "total_delta": r["total_delta"] or 0.0,
                "count": count,
                "total_reward": r["total_reward"] or 0.0,
                "mean_delta": (r["total_delta"] or 0.0) / max(1, count),
            }
        return stats

    def close(self) -> None:
        """Fecha a conexão SQLite gracefulmente."""
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass


# ── Fallback Factory ─────────────────────────────────────────────────────────


def create_experience_store(gamma: float = 0.995, max_experiences: int = 500):
    """
    Factory que retorna o backend SQLite.

    Args:
        gamma: Fator de decaimento temporal
        max_experiences: Número máximo de experiências mantidas

    Returns:
        Instância compatível com IExperienceStore (Protocol).
    """
    return SqliteExperienceStore(gamma=gamma, max_experiences=max_experiences)
