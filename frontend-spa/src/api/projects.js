import apiClient from './client';

export const projectsApi = {
  // Получить список всех проектов
  getAll: async (params = {}) => {
    const response = await apiClient.get('/projects', { params });
    return response.data;
  },

  // Получить проект по ID
  getById: async (id) => {
    const response = await apiClient.get(`/projects/${id}`);
    return response.data;
  },

  // Создать проект
  create: async (projectData) => {
    const response = await apiClient.post('/projects', projectData);
    return response.data;
  },

  // Обновить проект
  update: async (id, projectData) => {
    const response = await apiClient.put(`/projects/${id}`, projectData);
    return response.data;
  },

  // Удалить проект
  delete: async (id) => {
    await apiClient.delete(`/projects/${id}`);
  },

  // Отчёты проекта
  reports: {
    getAll: async (projectId) => {
      const response = await apiClient.get(`/projects/${projectId}/reports`);
      return response.data;
    },
    getById: async (projectId, reportId) => {
      const response = await apiClient.get(`/projects/${projectId}/reports/${reportId}`);
      return response.data;
    },
    create: async (projectId, reportData) => {
      const response = await apiClient.post(`/projects/${projectId}/reports`, reportData);
      return response.data;
    },
    update: async (projectId, reportId, reportData) => {
      const response = await apiClient.put(`/projects/${projectId}/reports/${reportId}`, reportData);
      return response.data;
    },
    delete: async (projectId, reportId) => {
      await apiClient.delete(`/projects/${projectId}/reports/${reportId}`);
    },
    export: async (projectId, reportId) => {
      const response = await apiClient.get(`/projects/${projectId}/reports/${reportId}/export`, {
        responseType: 'blob',
      });
      return response.data;
    },
  },

  // Артефакты проекта
  artifacts: {
    getAll: async (projectId) => {
      const response = await apiClient.get(`/projects/${projectId}/artifacts`);
      return response.data;
    },
    upload: async (projectId, formData) => {
      const response = await apiClient.post(`/projects/${projectId}/artifacts`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    },
    download: async (projectId, artifactId) => {
      const response = await apiClient.get(`/projects/${projectId}/artifacts/${artifactId}`, {
        responseType: 'blob',
      });
      return response.data;
    },
    delete: async (projectId, artifactId) => {
      await apiClient.delete(`/projects/${projectId}/artifacts/${artifactId}`);
    },
  },

  // Сессии сканирования
  sessions: {
    getAll: async (projectId) => {
      const response = await apiClient.get(`/projects/${projectId}/sessions`);
      return response.data;
    },
    create: async (projectId, sessionData) => {
      const response = await apiClient.post(`/projects/${projectId}/sessions`, sessionData);
      return response.data;
    },
    update: async (projectId, sessionId, sessionData) => {
      const response = await apiClient.put(`/projects/${projectId}/sessions/${sessionId}`, sessionData);
      return response.data;
    },
    delete: async (projectId, sessionId) => {
      await apiClient.delete(`/projects/${projectId}/sessions/${sessionId}`);
    },
  },

  // CTF машины
  ctfMachines: {
    getAll: async (projectId) => {
      const response = await apiClient.get(`/projects/${projectId}/ctf-machines`);
      return response.data;
    },
    getById: async (projectId, machineId) => {
      const response = await apiClient.get(`/projects/${projectId}/ctf-machines/${machineId}`);
      return response.data;
    },
    create: async (projectId, machineData) => {
      const response = await apiClient.post(`/projects/${projectId}/ctf-machines`, machineData);
      return response.data;
    },
    update: async (projectId, machineId, machineData) => {
      const response = await apiClient.put(`/projects/${projectId}/ctf-machines/${machineId}`, machineData);
      return response.data;
    },
    delete: async (projectId, machineId) => {
      await apiClient.delete(`/projects/${projectId}/ctf-machines/${machineId}`);
    },
  },

  // Git синхронизация
  gitSync: {
    get: async (projectId) => {
      const response = await apiClient.get(`/projects/${projectId}/git-sync`);
      return response.data;
    },
    create: async (projectId, syncData) => {
      const response = await apiClient.post(`/projects/${projectId}/git-sync`, syncData);
      return response.data;
    },
    update: async (projectId, syncData) => {
      const response = await apiClient.put(`/projects/${projectId}/git-sync`, syncData);
      return response.data;
    },
    sync: async (projectId) => {
      const response = await apiClient.post(`/projects/${projectId}/git-sync/sync`);
      return response.data;
    },
  },
};

export default projectsApi;
