// static/js/modules/theme.js

import { renderAssets } from './assets.js';

export function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}

export function toggleTheme() {
    const html = document.documentElement; 
    const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition'); 
    html.setAttribute('data-bs-theme', newTheme); 
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme); 
    setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle'); 
    if (!toggle) return;
    const moon = toggle.querySelector('.bi-moon');
    const sun = toggle.querySelector('.bi-sun');
    if(moon) moon.style.display = theme === 'dark' ? 'none' : 'block';
    if(sun) sun.style.display = theme === 'dark' ? 'block' : 'none';
}

export function highlightActiveGroupFromUrl() {
    const params = new URLSearchParams(window.location.search);
    let targetId = null;
    let isUngrouped = false;

    if (params.has('group_id')) {
        targetId = params.get('group_id');
    } else if (params.has('ungrouped')) {
        isUngrouped = true;
        targetId = 'ungrouped';
    }

    if (!targetId) return;

    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));

    if (isUngrouped) {
        const node = document.querySelector('.tree-node[data-id="ungrouped"]');
        if (node) {
            node.classList.add('active');
            node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }

    const activeNode = document.querySelector(`.tree-node[data-id="${targetId}"]`);
    if (activeNode) {
        let parent = activeNode.parentElement;
        while (parent) {
            if (parent.classList.contains('nested')) {
                parent.classList.add('active');
                const parentLi = parent.previousElementSibling;
                if (parentLi && parentLi.querySelector('.caret')) {
                    parentLi.querySelector('.caret').classList.add('caret-down');
                }
            }
            if (parent.id === 'group-tree') break;
            parent = parent.parentElement;
        }

        activeNode.classList.add('active');
        activeNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

export function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    
    groupId = String(groupId);
    
    const currentPage = window.location.pathname;
    if (currentPage !== '/' && !currentPage.endsWith('/index.html')) {
        const url = groupId === 'ungrouped' 
            ? '/?ungrouped=true' 
            : `/?group_id=${parseInt(groupId)}`;
        window.location.href = url;
        return;
    }
    
    const url = groupId === 'ungrouped' 
        ? '/api/assets?ungrouped=true' 
        : `/api/assets?group_id=${parseInt(groupId)}`;
    
    fetch(url)
        .then(r => r.json())
        .then(data => renderAssets(data))
        .catch(e => console.error(e));
}

export function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree'); 
    if (!groupTree) return;
    
    const newGroupTree = groupTree.cloneNode(true);
    groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node'); 
        if (!treeNode) return;
        
        if (e.target.classList.contains('caret') || e.target.closest('.caret')) {
            e.preventDefault(); 
            e.stopPropagation();
            const nested = treeNode.querySelector(".nested");
            if (nested) { 
                nested.classList.toggle("active"); 
                const caret = treeNode.querySelector('.caret'); 
                if (caret) caret.classList.toggle("caret-down"); 
            }
            return;
        }
        
        filterByGroup(treeNode.dataset.id);
    });

    highlightActiveGroupFromUrl();
}