import { el } from '../dom.js';

export class HistoryView {
    constructor(viewModel) {
        this.vm = viewModel;
        this.initEvents();
        this.bindViewModel();
    }

    initEvents() {
        el.btnOpenHistory.addEventListener('click', () => {
            this.vm.loadJobs(0);
            el.historyModal.classList.add('active');
        });

        el.btnCloseHistory.addEventListener('click', () => {
            el.historyModal.classList.remove('active');
        });

        el.historyModal.addEventListener('click', (e) => {
            if (e.target === el.historyModal) {
                el.historyModal.classList.remove('active');
            }
        });

        el.btnHistoryPrev.addEventListener('click', () => {
            if (this.vm.skip > 0) {
                this.vm.loadJobs(this.vm.skip - this.vm.limit);
            }
        });

        el.btnHistoryNext.addEventListener('click', () => {
            if (this.vm.skip + this.vm.limit < this.vm.total) {
                this.vm.loadJobs(this.vm.skip + this.vm.limit);
            }
        });

        // Delegação de eventos no tbody da tabela
        el.historyTableBody.addEventListener('click', (e) => {
            const btnDelete = e.target.closest('.btn-action.delete');
            const btnLoad = e.target.closest('.btn-action.load');

            if (btnDelete) {
                const id = btnDelete.dataset.id;
                if (confirm('Tem certeza que deseja excluir esta otimização do histórico?')) {
                    this.vm.deleteJob(id);
                }
            } else if (btnLoad) {
                const id = btnLoad.dataset.id;
                this.vm.loadJobDetails(id);
            }
        });
    }

    bindViewModel() {
        this.vm.addEventListener('jobsLoaded', (e) => {
            const { jobs, skip, limit, total } = e.detail;
            this.renderTable(jobs);

            const currentPage = Math.floor(skip / limit) + 1;
            const totalPages = Math.ceil(total / limit) || 1;
            el.historyPageInfo.textContent = `Página ${currentPage} de ${totalPages}`;

            el.btnHistoryPrev.disabled = skip === 0;
            el.btnHistoryNext.disabled = skip + limit >= total;
        });

        this.vm.addEventListener('jobDetailsLoaded', () => {
            el.historyModal.classList.remove('active');
        });

        this.vm.addEventListener('error', (e) => {
            alert(e.detail.message);
        });
    }

    renderTable(jobs) {
        el.historyTableBody.innerHTML = '';

        if (jobs.length === 0) {
            el.historyTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Nenhum histórico encontrado.</td></tr>';
            return;
        }

        jobs.forEach(job => {
            const date = job.updated_at ? new Date(job.updated_at * 1000).toLocaleString() : 'Desconhecido';
            const model = job.model_name || 'Padrão';
            
            let statusClass = 'idle';
            if (job.status === 'completed') statusClass = 'completed';
            else if (job.status === 'running') statusClass = 'running';
            else if (job.status === 'error') statusClass = 'error';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${date}</td>
                <td>${model}</td>
                <td><span class="status-indicator ${statusClass}" style="margin-right: 6px;"></span>${job.status}</td>
                <td class="actions">
                    <button class="btn-action load" data-id="${job.id}" title="Carregar"><i class="fa-solid fa-folder-open"></i></button>
                    <button class="btn-action delete" data-id="${job.id}" title="Excluir"><i class="fa-solid fa-trash-can"></i></button>
                </td>
            `;
            el.historyTableBody.appendChild(tr);
        });
    }
}
