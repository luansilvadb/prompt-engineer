import json
import os
from pathlib import Path

JOBS_DIR = Path('src/outputs/jobs')

def init_store():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)

def save_job_state(job_id: str, job) -> None:
    init_store()
    file_path = JOBS_DIR / f"{job_id}.json"
    
    # We serialize all fields except the events_queue and api keys for security
    state_dict = {
        "id": job_id,
        "status": job.status,
        "original_skill": job.original_skill,
        "result": job.result,
        "logs": job.logs,
        "mcts_nodes": job.mcts_nodes,
        "model_name": job.model_name,
        "model_prefix": job.model_prefix,
        "regras_adicionais": job.regras_adicionais
    }
    
    # Write atomically via temp file to avoid corruption
    temp_path = file_path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, file_path)
    except Exception as e:
        print(f"[Store] Failed to save job {job_id}: {e}")

def _read_job_summary(file_path: Path, status: str = None) -> dict:
    try:
        mtime = file_path.stat().st_mtime
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            job_status = data.get("status", "unknown")
            
            if status and job_status != status:
                return None
                
            return {
                "id": data.get("id", file_path.stem),
                "status": job_status,
                "model_name": data.get("model_name"),
                "original_skill": data.get("original_skill", "")[:100] + "...",
                "updated_at": mtime
            }
    except Exception as e:
        print(f"[Store] Error loading job file {file_path}: {e}")
        return None

def load_all_jobs(skip: int = 0, limit: int = 50, status: str = None) -> dict:
    init_store()
    jobs = []
    for file_path in JOBS_DIR.glob('*.json'):
        job_data = _read_job_summary(file_path, status)
        if job_data:
            jobs.append(job_data)
            
    jobs.sort(key=lambda x: x["updated_at"], reverse=True)
    
    total = len(jobs)
    items = jobs[skip : skip + limit]
    
    return {
        "total": total,
        "items": items,
        "skip": skip,
        "limit": limit
    }

def load_job(job_id: str) -> dict:
    init_store()
    file_path = JOBS_DIR / f"{job_id}.json"
    if not file_path.exists():
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Store] Error loading job {job_id}: {e}")
        return None

def delete_job(job_id: str) -> bool:
    init_store()
    file_path = JOBS_DIR / f"{job_id}.json"
    if file_path.exists():
        try:
            file_path.unlink()
            return True
        except Exception as e:
            print(f"[Store] Error deleting job {job_id}: {e}")
            return False
    return False
