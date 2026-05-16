import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useProjectStore } from '../stores/projectStore';
import { useReportStore } from '../stores/reportStore';
import { useArtifactStore } from '../stores/artifactStore';
import MDEditor from '@uiw/react-md-editor';
import { FileText, FolderOpen, HardDrive, GitBranch, Plus, Save, Download } from 'lucide-react';

const ProjectDetailPage = () => {
  const { projectId } = useParams();
  const { currentProject, fetchProjectById } = useProjectStore();
  const { reports, fetchReports, createReport, updateReport } = useReportStore();
  const { artifacts, fetchArtifacts } = useArtifactStore();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedReport, setSelectedReport] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    fetchProjectById(projectId);
    fetchReports(projectId);
    fetchArtifacts(projectId);
  }, [projectId]);

  if (!currentProject) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: FileText },
    { id: 'reports', label: 'Отчёты', icon: FileText },
    { id: 'artifacts', label: 'Артефакты', icon: FolderOpen },
    { id: 'sessions', label: 'Сессии', icon: HardDrive },
    { id: 'ctf', label: 'CTF', icon: FolderOpen },
    { id: 'git', label: 'Git', icon: GitBranch },
  ];

  return (
    <div className="space-y-6">
      {/* Заголовок проекта */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{currentProject.name}</h1>
            {currentProject.description && (
              <p className="text-gray-600 mt-2">{currentProject.description}</p>
            )}
            {currentProject.customer && (
              <p className="text-sm text-gray-500 mt-1">Заказчик: {currentProject.customer}</p>
            )}
          </div>
          <div className="flex gap-2">
            <span className={`px-3 py-1 rounded-full text-xs text-white ${
              currentProject.status === 'active' ? 'bg-green-500' : 'bg-gray-500'
            }`}>
              {currentProject.status}
            </span>
            <span className={`px-3 py-1 rounded-full text-xs ${
              currentProject.priority === 'high' || currentProject.priority === 'critical'
                ? 'bg-red-100 text-red-800'
                : 'bg-blue-100 text-blue-800'
            }`}>
              {currentProject.priority}
            </span>
          </div>
        </div>
      </div>

      {/* Вкладки */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Контент вкладок */}
      {activeTab === 'overview' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Информация о проекте</h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">Тип проекта</dt>
              <dd className="mt-1 text-sm text-gray-900">{currentProject.project_type}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Статус</dt>
              <dd className="mt-1 text-sm text-gray-900">{currentProject.status}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Приоритет</dt>
              <dd className="mt-1 text-sm text-gray-900">{currentProject.priority}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Дата начала</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {currentProject.start_date ? new Date(currentProject.start_date).toLocaleDateString() : 'Не указана'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Отчётов</dt>
              <dd className="mt-1 text-sm text-gray-900">{reports.length}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Артефактов</dt>
              <dd className="mt-1 text-sm text-gray-900">{artifacts.length}</dd>
            </div>
          </dl>
        </div>
      )}

      {activeTab === 'reports' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Отчёты</h2>
            <button
              onClick={() => {
                setSelectedReport(null);
                setIsEditing(true);
              }}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4 mr-2" />
              Новый отчёт
            </button>
          </div>

          {isEditing ? (
            <div className="bg-white rounded-lg shadow p-4">
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="Заголовок отчёта"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  defaultValue={selectedReport?.title || ''}
                />
              </div>
              <MDEditor
                value={selectedReport?.content || '# Новый отчёт\n\nНачните писать...'}
                onChange={(value) => setSelectedReport({ ...selectedReport, content: value })}
                preview="edit"
                height={400}
              />
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => {
                    // Сохранение отчёта
                    setIsEditing(false);
                  }}
                  className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Сохранить
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                >
                  Отмена
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {reports.map((report) => (
                <div
                  key={report.id}
                  onClick={() => {
                    setSelectedReport(report);
                    setIsEditing(true);
                  }}
                  className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow"
                >
                  <h3 className="font-semibold text-gray-900">{report.title}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {new Date(report.created_at).toLocaleDateString()}
                  </p>
                  <div className="flex gap-2 mt-2">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                      {report.report_type}
                    </span>
                    {report.is_final && (
                      <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                        Финальный
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'artifacts' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Артефакты</h2>
            <label className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer">
              <Plus className="w-4 h-4 mr-2" />
              Загрузить файл
              <input type="file" className="hidden" />
            </label>
          </div>
          {artifacts.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Артефакты не загружены</p>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Название</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Размер</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {artifacts.map((artifact) => (
                    <tr key={artifact.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{artifact.name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{artifact.artifact_type}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {(artifact.file_size / 1024).toFixed(2)} KB
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(artifact.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button className="text-blue-600 hover:text-blue-900 mr-3">
                          <Download className="w-4 h-4 inline" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'sessions' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Сессии сканирования</h2>
          <p className="text-gray-500">Функционал в разработке...</p>
        </div>
      )}

      {activeTab === 'ctf' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">CTF машины</h2>
          <p className="text-gray-500">Функционал в разработке...</p>
        </div>
      )}

      {activeTab === 'git' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Git синхронизация</h2>
          <p className="text-gray-500">Функционал в разработке...</p>
        </div>
      )}
    </div>
  );
};

export default ProjectDetailPage;
