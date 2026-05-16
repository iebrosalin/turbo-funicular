from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import json
import hashlib
from datetime import datetime
import subprocess

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '../data')
PROJECTS_DIR = os.path.join(DATA_DIR, 'projects')

def get_main_db():
    conn = sqlite3.connect(os.path.join(DATA_DIR, 'main.db'))
    conn.row_factory = sqlite3.Row
    return conn

def get_project_db(project_id):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise Exception(f"Project {project_id} not found")
    db_path = os.path.join(project_path, 'project.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_main_db():
    conn = get_main_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            git_repo TEXT,
            ctf_machine BOOLEAN DEFAULT FALSE,
            status TEXT DEFAULT 'active'
        )
    ''')
    conn.commit()
    conn.close()

def init_project_db(project_id):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(project_path, exist_ok=True)
    os.makedirs(os.path.join(project_path, 'reports'), exist_ok=True)
    os.makedirs(os.path.join(project_path, 'artifacts'), exist_ok=True)
    os.makedirs(os.path.join(project_path, 'media'), exist_ok=True)
    os.makedirs(os.path.join(project_path, 'ctf'), exist_ok=True)
    
    db_path = os.path.join(project_path, 'project.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT,
            is_ctf BOOLEAN DEFAULT FALSE,
            ctf_machine_name TEXT,
            ctf_difficulty TEXT,
            ctf_flags TEXT,
            ctf_writeup_complete BOOLEAN DEFAULT FALSE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT,
            file_type TEXT,
            file_size INTEGER,
            file_hash TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            category TEXT,
            related_report_id INTEGER,
            FOREIGN KEY (related_report_id) REFERENCES reports(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            tool_name TEXT,
            command TEXT,
            output_file TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            notes TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            group_id TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = get_main_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
    projects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json
    project_id = hashlib.md5(f"{datetime.now().isoformat()}{data['name']}".encode()).hexdigest()[:12]
    
    conn = get_main_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projects (id, name, description, git_repo, ctf_machine)
        VALUES (?, ?, ?, ?, ?)
    ''', (project_id, data['name'], data.get('description'), data.get('git_repo'), data.get('ctf_machine', False)))
    conn.commit()
    conn.close()
    
    init_project_db(project_id)
    
    return jsonify({'id': project_id, 'message': 'Project created successfully'}), 201

@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    conn = get_main_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    conn.close()
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    return jsonify(dict(project))

@app.route('/api/projects/<project_id>/reports', methods=['GET'])
def get_reports(project_id):
    try:
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports ORDER BY updated_at DESC')
        reports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(reports)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/reports', methods=['POST'])
def create_report(project_id):
    try:
        data = request.json
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (title, content, tags, is_ctf, ctf_machine_name, ctf_difficulty, ctf_flags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'], 
            data.get('content', ''), 
            json.dumps(data.get('tags', [])),
            data.get('is_ctf', False),
            data.get('ctf_machine_name'),
            data.get('ctf_difficulty'),
            json.dumps(data.get('ctf_flags', []))
        ))
        conn.commit()
        report_id = cursor.lastrowid
        conn.close()
        return jsonify({'id': report_id, 'message': 'Report created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/reports/<report_id>', methods=['PUT'])
def update_report(project_id, report_id):
    try:
        data = request.json
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reports 
            SET title=?, content=?, tags=?, updated_at=CURRENT_TIMESTAMP,
                is_ctf=?, ctf_machine_name=?, ctf_difficulty=?, ctf_flags=?
            WHERE id=?
        ''', (
            data.get('title'),
            data.get('content'),
            json.dumps(data.get('tags', [])),
            data.get('is_ctf', False),
            data.get('ctf_machine_name'),
            data.get('ctf_difficulty'),
            json.dumps(data.get('ctf_flags', [])),
            report_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Report updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/reports/<report_id>', methods=['DELETE'])
def delete_report(project_id, report_id):
    try:
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reports WHERE id=?', (report_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Report deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/artifacts', methods=['GET'])
def get_artifacts(project_id):
    try:
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM artifacts ORDER BY upload_date DESC')
        artifacts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(artifacts)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/artifacts/upload', methods=['POST'])
def upload_artifact(project_id):
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        project_path = os.path.join(PROJECTS_DIR, project_id)
        artifacts_dir = os.path.join(project_path, 'artifacts')
        
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(artifacts_dir, filename)
        file.save(filepath)
        
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO artifacts (filename, original_name, file_type, file_size, file_hash, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            file.filename,
            file.content_type,
            os.path.getsize(filepath),
            file_hash,
            request.form.get('category', 'general')
        ))
        conn.commit()
        artifact_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'id': artifact_id,
            'filename': filename,
            'original_name': file.filename,
            'message': 'Artifact uploaded successfully'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/artifacts/<artifact_id>', methods=['GET'])
def download_artifact(project_id, artifact_id):
    try:
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('SELECT filename FROM artifacts WHERE id=?', (artifact_id,))
        artifact = cursor.fetchone()
        conn.close()
        
        if not artifact:
            return jsonify({'error': 'Artifact not found'}), 404
        
        project_path = os.path.join(PROJECTS_DIR, project_id)
        return send_from_directory(os.path.join(project_path, 'artifacts'), artifact['filename'], as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/git/sync', methods=['POST'])
def sync_git(project_id):
    try:
        conn = get_main_db()
        cursor = conn.cursor()
        cursor.execute('SELECT git_repo FROM projects WHERE id=?', (project_id,))
        project = cursor.fetchone()
        conn.close()
        
        if not project or not project['git_repo']:
            return jsonify({'error': 'Git repository not configured'}), 400
        
        project_path = os.path.join(PROJECTS_DIR, project_id)
        git_repo = project['git_repo']
        
        if not os.path.exists(os.path.join(project_path, '.git')):
            subprocess.run(['git', 'init'], cwd=project_path, check=True)
            subprocess.run(['git', 'remote', 'add', 'origin', git_repo], cwd=project_path, check=True)
        
        subprocess.run(['git', 'add', '.'], cwd=project_path, check=True)
        subprocess.run(['git', 'commit', '-m', 'Auto-sync: Updated project files'], cwd=project_path, check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], cwd=project_path, check=True)
        
        return jsonify({'message': 'Git sync completed successfully'})
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Git operation failed: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/export/<report_id>', methods=['GET'])
def export_report(project_id, report_id):
    try:
        conn = get_project_db(project_id)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports WHERE id=?', (report_id,))
        report = cursor.fetchone()
        conn.close()
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        md_content = f"# {report['title']}\n\n"
        
        if report['is_ctf']:
            md_content += "## CTF Machine Information\n\n"
            md_content += f"- **Machine Name**: {report['ctf_machine_name'] or 'N/A'}\n"
            md_content += f"- **Difficulty**: {report['ctf_difficulty'] or 'N/A'}\n"
            
            flags = json.loads(report['ctf_flags'] or '[]')
            if flags:
                md_content += "- **Flags**:\n"
                for flag in flags:
                    md_content += f"  - `{flag}`\n"
            md_content += "\n"
        
        md_content += "## Report Content\n\n"
        md_content += report['content'] or ''
        
        tags = json.loads(report['tags'] or '[]')
        if tags:
            md_content += "\n\n## Tags\n\n"
            for tag in tags:
                md_content += f"#{tag} "
        
        project_path = os.path.join(PROJECTS_DIR, project_id)
        reports_dir = os.path.join(project_path, 'reports')
        filename = f"{report['title'].replace(' ', '_')}.md"
        filepath = os.path.join(reports_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return send_from_directory(reports_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    init_main_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
