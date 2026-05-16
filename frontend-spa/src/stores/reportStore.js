import { create } from 'zustand';
import projectsApi from '../api/projects';

export const useReportStore = create((set, get) => ({
  // Состояние
  reports: [],
  currentReport: null,
  loading: false,
  error: null,

  // Actions для отчётов
  fetchReports: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const reports = await projectsApi.reports.getAll(projectId);
      set({ reports, loading: false });
      return reports;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  fetchReportById: async (projectId, reportId) => {
    set({ loading: true, error: null });
    try {
      const report = await projectsApi.reports.getById(projectId, reportId);
      set({ currentReport: report, loading: false });
      return report;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  createReport: async (projectId, reportData) => {
    set({ loading: true, error: null });
    try {
      const report = await projectsApi.reports.create(projectId, reportData);
      set((state) => ({
        reports: [...state.reports, report],
        currentReport: report,
        loading: false,
      }));
      return report;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  updateReport: async (projectId, reportId, reportData) => {
    set({ loading: true, error: null });
    try {
      const report = await projectsApi.reports.update(projectId, reportId, reportData);
      set((state) => ({
        reports: state.reports.map((r) => (r.id === reportId ? report : r)),
        currentReport: state.currentReport?.id === reportId ? report : state.currentReport,
        loading: false,
      }));
      return report;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteReport: async (projectId, reportId) => {
    set({ loading: true, error: null });
    try {
      await projectsApi.reports.delete(projectId, reportId);
      set((state) => ({
        reports: state.reports.filter((r) => r.id !== reportId),
        currentReport: state.currentReport?.id === reportId ? null : state.currentReport,
        loading: false,
      }));
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  exportReport: async (projectId, reportId) => {
    set({ loading: true, error: null });
    try {
      const blob = await projectsApi.reports.export(projectId, reportId);
      set({ loading: false });
      return blob;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  setCurrentReport: (report) => {
    set({ currentReport: report });
  },

  clearError: () => {
    set({ error: null });
  },
}));

export default useReportStore;
