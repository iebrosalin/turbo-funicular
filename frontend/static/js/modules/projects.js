// modules/projects.js - Управление проектами

import { apiRequest, showNotification } from './utils.js';

// ===== State =====
let projects = [];
let groups = [];

// ===== DOM Elements =====
const projectsContainer = document.getElementById('projects-container');
const emptyState = document.getElementById('empty-state');
const projectModal = document.getElementById('projectModal');
const projectForm = document.getElementById('project-form');
const btnSaveProject = document.getElementById('btn-save-project');
const btnCreateProject = document.getElementById('btn-create-project');
const btnCreateProjectEmpty = document.getElementById('btn-create-project-empty');
const btnApplyFilters = document.getElementById('btn-apply-filters');
const filterStatus = document.getElementById('filter-status');
const filterPriority = document.getElementById('filter-priority');
const searchProjects = document.getElementById('search-projects');
const projectGroupsSelect = document.getElementById('project-groups');

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', async () => {
    await loadGroups();
    await loadProjects();
    setupEventListeners();
});

// ===== Event Listeners =====
function setupEventListeners() {
    btnCreateProject?.addEventListener('click', () => openProjectModal());
    btnCreateProjectEmpty?.addEventListener('click', () => openProjectModal());
    btnSaveProject?.addEventListener('click', saveProject);
    btnApplyFilters?.addEventListener('click', applyFilters);
    
    // Close modal on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && projectModal) {
            const modal = bootstrap.Modal.getInstance(projectModal);
            modal?.hide();
        }
    });
}

// ===== API Functions =====
async function loadProjects() {
    try {
        const response = await apiRequest('/api/projects');
        projects = response;
        renderProjects(projects);
    } catch (error) {
        console.error('Error loading projects:', error);
        showNotification('Ошибка загрузки проектов', 'error');
    }
}

async function loadGroups() {
    try {
        const response = await apiRequest('/api/groups');
        groups = response;
        populateGroupsSelect();
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

async function createProject(projectData) {
    try {
        const response = await apiRequest('/api/projects', {
            method: 'POST',
            body: JSON.stringify(projectData)
        });
        showNotification('Проект успешно создан', 'success');
        await loadProjects();
        return response;
    } catch (error) {
        console.error('Error creating project:', error);
        showNotification('Ошибка создания проекта', 'error');
        throw error;
    }
}

async function updateProject(projectId, projectData) {
    try {
        const response = await apiRequest(`/api/projects/${projectId}`, {
            method: 'PUT',
            body: JSON.stringify(projectData)
        });
        showNotification('Проект успешно обновлён', 'success');
        await loadProjects();
        return response;
    } catch (error) {
        console.error('Error updating project:', error);
        showNotification('Ошибка обновления проекта', 'error');
        throw error;
    }
}

async function deleteProject(projectId) {
    if (!confirm('Вы уверены, что хотите удалить этот проект? Все отчёты и артефакты будут удалены.')) {
        return;
    }
    
    try {
        await apiRequest(`/api/projects/${projectId}`, {
            method: 'DELETE'
        });
        showNotification('Проект успешно удалён', 'success');
        await loadProjects();
    } catch (error) {
        console.error('Error deleting project:', error);
        showNotification('Ошибка удаления проекта', 'error');
    }
}

// ===== UI Functions =====
function renderProjects(projectsToRender) {
    if (!projectsContainer) return;
    
    if (projectsToRender.length === 0) {
        projectsContainer.classList.add('d-none');
        emptyState?.classList.remove('d-none');
        return;
    }
    
    projectsContainer.classList.remove('d-none');
    emptyState?.classList.add('d-none');
    
    projectsContainer.innerHTML = projectsToRender.map(project => `
        <div class="col-md-6 col-lg-4">
            <div class="card h-100 shadow-sm border-0 project-card" data-project-id="${project.id}">
                <div class="card-header d-flex justify-content-between align-items-center ${getStatusBg(project.status)}">
                    <span class="badge ${getPriorityBadge(project.priority)}">${translatePriority(project.priority)}</span>
                    <small class="text-muted">${formatDate(project.created_at)}</small>
                </div>
                <div class="card-body">
                    <h5 class="card-title">${escapeHtml(project.name)}</h5>
                    <p class="card-text text-muted small">${escapeHtml(project.description) || 'Нет описания'}</p>
                    
                    ${project.customer ? `<p class="mb-2"><i class="bi bi-person me-1"></i><strong>Заказчик:</strong> ${escapeHtml(project.customer)}</p>` : ''}
                    
                    <div class="mb-2">
                        <span class="badge bg-secondary">${translateType(project.project_type)}</span>
                        <span class="badge ${getStatusBadge(project.status)}">${translateStatus(project.status)}</span>
                    </div>
                    
                    <div class="small text-muted">
                        ${project.groups?.length ? `<p><i class="bi bi-folder me-1"></i>Группы: ${project.groups.join(', ')}</p>` : ''}
                        <p><i class="bi bi-file-text me-1"></i>Отчётов: ${project.reports_count || 0}</p>
                        <p><i class="bi bi-paperclip me-1"></i>Артефактов: ${project.artifacts_count || 0}</p>
                    </div>
                </div>
                <div class="card-footer bg-transparent border-0">
                    <div class="btn-group w-100" role="group">
                        <a href="/projects/${project.id}" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-eye me-1"></i>Открыть
                        </a>
                        <button class="btn btn-sm btn-outline-secondary" onclick="editProject(${project.id})">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteProjectFromCard(${project.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function populateGroupsSelect() {
    if (!projectGroupsSelect) return;
    
    projectGroupsSelect.innerHTML = groups.map(group => 
        `<option value="${group.id}">${escapeHtml(group.name)}</option>`
    ).join('');
}

function openProjectModal(project = null) {
    if (!projectModal) return;
    
    const modalTitle = document.getElementById('projectModalLabel');
    
    if (project) {
        modalTitle.textContent = 'Редактировать проект';
        document.getElementById('project-id').value = project.id;
        document.getElementById('project-name').value = project.name;
        document.getElementById('project-description').value = project.description || '';
        document.getElementById('project-customer').value = project.customer || '';
        document.getElementById('project-type').value = project.project_type || 'pentest';
        document.getElementById('project-status').value = project.status || 'planning';
        document.getElementById('project-priority').value = project.priority || 'medium';
        
        if (project.start_date) {
            document.getElementById('project-start-date').value = new Date(project.start_date).toISOString().slice(0, 16);
        }
        if (project.end_date) {
            document.getElementById('project-end-date').value = new Date(project.end_date).toISOString().slice(0, 16);
        }
        
        // Select groups
        if (projectGroupsSelect && project.groups) {
            const groupIds = project.groups;
            for (const option of projectGroupsSelect.options) {
                option.selected = groupIds.includes(option.value);
            }
        }
    } else {
        modalTitle.textContent = 'Новый проект';
        projectForm.reset();
        document.getElementById('project-id').value = '';
    }
    
    const modal = new bootstrap.Modal(projectModal);
    modal.show();
}

async function saveProject() {
    const projectId = document.getElementById('project-id').value;
    const selectedGroups = Array.from(projectGroupsSelect?.selectedOptions || []).map(opt => parseInt(opt.value));
    
    const projectData = {
        name: document.getElementById('project-name').value.trim(),
        description: document.getElementById('project-description').value.trim(),
        customer: document.getElementById('project-customer').value.trim(),
        project_type: document.getElementById('project-type').value,
        status: document.getElementById('project-status').value,
        priority: document.getElementById('project-priority').value,
        start_date: document.getElementById('project-start-date').value || null,
        end_date: document.getElementById('project-end-date').value || null,
        group_ids: selectedGroups
    };
    
    if (!projectData.name) {
        showNotification('Название проекта обязательно', 'error');
        return;
    }
    
    try {
        if (projectId) {
            await updateProject(parseInt(projectId), projectData);
        } else {
            await createProject(projectData);
        }
        
        const modal = bootstrap.Modal.getInstance(projectModal);
        modal.hide();
    } catch (error) {
        // Error already shown in create/update functions
    }
}

function applyFilters() {
    let filtered = [...projects];
    
    const status = filterStatus?.value;
    const priority = filterPriority?.value;
    const search = searchProjects?.value.toLowerCase();
    
    if (status) {
        filtered = filtered.filter(p => p.status === status);
    }
    
    if (priority) {
        filtered = filtered.filter(p => p.priority === priority);
    }
    
    if (search) {
        filtered = filtered.filter(p => 
            p.name.toLowerCase().includes(search) ||
            (p.customer && p.customer.toLowerCase().includes(search))
        );
    }
    
    renderProjects(filtered);
}

// ===== Helper Functions =====
function getStatusBg(status) {
    const map = {
        planning: 'bg-info-subtle',
        active: 'bg-success-subtle',
        paused: 'bg-warning-subtle',
        completed: 'bg-primary-subtle',
        archived: 'bg-secondary-subtle'
    };
    return map[status] || 'bg-light';
}

function getStatusBadge(status) {
    const map = {
        planning: 'bg-info',
        active: 'bg-success',
        paused: 'bg-warning',
        completed: 'bg-primary',
        archived: 'bg-secondary'
    };
    return map[status] || 'bg-secondary';
}

function getPriorityBadge(priority) {
    const map = {
        low: 'bg-secondary',
        medium: 'bg-info',
        high: 'bg-warning',
        critical: 'bg-danger'
    };
    return map[priority] || 'bg-secondary';
}

function translateStatus(status) {
    const map = {
        planning: 'Планирование',
        active: 'Активный',
        paused: 'На паузе',
        completed: 'Завершён',
        archived: 'Архив'
    };
    return map[status] || status;
}

function translatePriority(priority) {
    const map = {
        low: 'Низкий',
        medium: 'Средний',
        high: 'Высокий',
        critical: 'Критический'
    };
    return map[priority] || priority;
}

function translateType(type) {
    const map = {
        pentest: 'Пентест',
        audit: 'Аудит',
        research: 'Исследование'
    };
    return map[type] || type;
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== Global Functions (for onclick handlers) =====
window.editProject = async (projectId) => {
    const project = projects.find(p => p.id === projectId);
    if (project) {
        openProjectModal(project);
    }
};

window.deleteProjectFromCard = async (projectId) => {
    await deleteProject(projectId);
};
