import { create } from 'zustand';
import projectsApi from '../api/projects';

export const useArtifactStore = create((set, get) => ({
  // Состояние
  artifacts: [],
  loading: false,
  error: null,

  // Actions для артефактов
  fetchArtifacts: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const artifacts = await projectsApi.artifacts.getAll(projectId);
      set({ artifacts, loading: false });
      return artifacts;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  uploadArtifact: async (projectId, formData) => {
    set({ loading: true, error: null });
    try {
      const artifact = await projectsApi.artifacts.upload(projectId, formData);
      set((state) => ({
        artifacts: [...state.artifacts, artifact],
        loading: false,
      }));
      return artifact;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  downloadArtifact: async (projectId, artifactId) => {
    set({ loading: true, error: null });
    try {
      const blob = await projectsApi.artifacts.download(projectId, artifactId);
      set({ loading: false });
      return blob;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteArtifact: async (projectId, artifactId) => {
    set({ loading: true, error: null });
    try {
      await projectsApi.artifacts.delete(projectId, artifactId);
      set((state) => ({
        artifacts: state.artifacts.filter((a) => a.id !== artifactId),
        loading: false,
      }));
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));

export default useArtifactStore;
