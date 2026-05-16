import { create } from 'zustand';
import projectsApi from '../api/projects';

export const useProjectStore = create((set, get) => ({
  // Состояние
  projects: [],
  currentProject: null,
  loading: false,
  error: null,

  // Actions для проектов
  fetchProjects: async (params = {}) => {
    set({ loading: true, error: null });
    try {
      const projects = await projectsApi.getAll(params);
      set({ projects, loading: false });
      return projects;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  fetchProjectById: async (id) => {
    set({ loading: true, error: null });
    try {
      const project = await projectsApi.getById(id);
      set({ currentProject: project, loading: false });
      return project;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  createProject: async (projectData) => {
    set({ loading: true, error: null });
    try {
      const project = await projectsApi.create(projectData);
      set((state) => ({
        projects: [...state.projects, project],
        currentProject: project,
        loading: false,
      }));
      return project;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  updateProject: async (id, projectData) => {
    set({ loading: true, error: null });
    try {
      const project = await projectsApi.update(id, projectData);
      set((state) => ({
        projects: state.projects.map((p) => (p.id === id ? project : p)),
        currentProject: state.currentProject?.id === id ? project : state.currentProject,
        loading: false,
      }));
      return project;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteProject: async (id) => {
    set({ loading: true, error: null });
    try {
      await projectsApi.delete(id);
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== id),
        currentProject: state.currentProject?.id === id ? null : state.currentProject,
        loading: false,
      }));
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  setCurrentProject: (project) => {
    set({ currentProject: project });
  },

  clearError: () => {
    set({ error: null });
  },
}));

export default useProjectStore;
