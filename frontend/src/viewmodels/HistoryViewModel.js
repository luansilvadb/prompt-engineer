import { ViewModelBase } from './ViewModelBase.js';

export class HistoryViewModel extends ViewModelBase {
    constructor() {
        super();
        this.jobs = [];
        this.skip = 0;
        this.limit = 10;
        this.total = 0;
    }

    async loadJobs(newSkip = 0) {
        this.skip = newSkip;
        try {
            const res = await fetch(`/api/jobs?skip=${this.skip}&limit=${this.limit}`);
            if (!res.ok) throw new Error('Erro ao carregar histórico');
            const data = await res.json();
            
            this.jobs = data.items || [];
            this.total = data.total || 0;
            
            this.dispatchEvent(new CustomEvent('jobsLoaded', {
                detail: {
                    jobs: this.jobs,
                    skip: this.skip,
                    limit: this.limit,
                    total: this.total
                }
            }));
        } catch (e) {
            console.error(e);
            this.dispatchEvent(new CustomEvent('error', {
                detail: { message: 'Falha ao carregar histórico.' }
            }));
        }
    }

    async deleteJob(id) {
        try {
            const res = await fetch(`/api/jobs/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Erro ao deletar o job');
            
            this.dispatchEvent(new CustomEvent('jobDeleted', {
                detail: { id }
            }));
            
            // Recarrega os jobs após exclusão
            await this.loadJobs(this.skip);
        } catch (err) {
            console.error(err);
            this.dispatchEvent(new CustomEvent('error', {
                detail: { message: 'Falha ao excluir o job do histórico.' }
            }));
        }
    }

    async loadJobDetails(id) {
        try {
            const res = await fetch(`/api/jobs/${id}`);
            if (!res.ok) throw new Error('Erro ao carregar dados do job');
            const job = await res.json();
            
            this.dispatchEvent(new CustomEvent('jobDetailsLoaded', {
                detail: { job }
            }));
        } catch (err) {
            console.error(err);
            this.dispatchEvent(new CustomEvent('error', {
                detail: { message: 'Falha ao carregar detalhes do job.' }
            }));
        }
    }
}
