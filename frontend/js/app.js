/**
 * TUI Task Manager - Application Logic
 * AJAX interface with terminal-style commands
 * Fetch inicial + actualización tras operaciones CRUD
 */

class TaskManagerApp {
    constructor() {
        // Configuration
        this.API_BASE_URL = 'http://localhost:8000';
        
        // State
        this.tasks = [];
        this.isConnected = false;
        this.commandHistory = [];
        this.historyIndex = -1;
        this.hasLoaded = false;
        
        // Commands
        this.commands = {
            help: this.showHelp.bind(this),
            list: this.listTasks.bind(this),
            create: this.openCreateModal.bind(this),
            edit: this.handleEditCommand.bind(this),
            delete: this.handleDeleteCommand.bind(this),
            clear: this.clearOutput.bind(this),
            refresh: this.manualRefresh.bind(this),
            stats: this.showStats.bind(this),
            search: this.searchTasks.bind(this),
        };
        
        // Initialize
        this.init();
    }
    
    async init() {
        this.cacheElements();
        this.bindEvents();
        this.log('Sistema iniciando...', 'info');
        
        // Cargar tareas inmediatamente al iniciar
        await this.loadInitialData();
        
        // Mostrar ayuda inicial
        this.log('Escribe "help" para ver los comandos disponibles.', 'info');
    }
    
    cacheElements() {
        this.elements = {
            commandInput: document.getElementById('command-input'),
            commandHint: document.getElementById('command-hint'),
            output: document.getElementById('output'),
            statusIndicator: document.getElementById('status-indicator'),
            statusText: document.getElementById('status-text'),
            lastUpdate: document.getElementById('last-update'),
            statTotal: document.getElementById('stat-total'),
            statPending: document.getElementById('stat-pending'),
            statProgress: document.getElementById('stat-progress'),
            statCompleted: document.getElementById('stat-completed'),
            createModal: document.getElementById('create-modal'),
            createForm: document.getElementById('create-form'),
            editModal: document.getElementById('edit-modal'),
            editForm: document.getElementById('edit-form'),
        };
    }
    
    bindEvents() {
        // Command input events
        this.elements.commandInput.addEventListener('keydown', (e) => this.handleInputKeydown(e));
        this.elements.commandInput.addEventListener('input', () => this.handleInputChange());
        this.elements.commandInput.addEventListener('focus', () => this.showHint());
        this.elements.commandInput.addEventListener('blur', () => this.hideHint());
        
        // Form submissions
        this.elements.createForm.addEventListener('submit', (e) => this.handleCreateSubmit(e));
        this.elements.editForm.addEventListener('submit', (e) => this.handleEditSubmit(e));
        
        // Modal close on backdrop click
        this.elements.createModal.addEventListener('click', (e) => {
            if (e.target === this.elements.createModal) this.closeCreateModal();
        });
        this.elements.editModal.addEventListener('click', (e) => {
            if (e.target === this.elements.editModal) this.closeEditModal();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeCreateModal();
                this.closeEditModal();
            }
        });
    }
    
    // ==================== API Methods ====================
    
    async apiRequest(endpoint, options = {}) {
        const url = `${this.API_BASE_URL}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        };
        
        try {
            this.setStatus('syncing');
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                const error = await response.text();
                throw new Error(`HTTP ${response.status}: ${error}`);
            }
            
            this.setStatus('online');
            return await response.json();
        } catch (error) {
            this.setStatus('offline');
            throw error;
        }
    }
    
    async fetchTasks() {
        try {
            this.tasks = await this.apiRequest('/tareas');
            this.updateStats();
            this.updateLastRefresh();
            return this.tasks;
        } catch (error) {
            console.error('Error fetching tasks:', error);
            this.log(`Error al cargar tareas: ${error.message}`, 'error');
            return [];
        }
    }
    
    async createTask(data) {
        try {
            const task = await this.apiRequest('/tareas', {
                method: 'POST',
                body: JSON.stringify(data),
            });
            this.log(`✓ Tarea creada: "${task.titulo}"`, 'success');
            
            // Después de crear, recargar y mostrar lista automáticamente
            await this.refreshAndShowList();
            
            return task;
        } catch (error) {
            this.log(`✗ Error al crear tarea: ${error.message}`, 'error');
            throw error;
        }
    }
    
    async updateTask(id, data) {
        try {
            const task = await this.apiRequest(`/tareas/${id}`, {
                method: 'PUT',
                body: JSON.stringify(data),
            });
            this.log(`✓ Tarea actualizada: "${task.titulo}"`, 'success');
            
            // Después de actualizar, recargar y mostrar lista automáticamente
            await this.refreshAndShowList();
            
            return task;
        } catch (error) {
            this.log(`✗ Error al actualizar tarea: ${error.message}`, 'error');
            throw error;
        }
    }
    
    async deleteTask(id) {
        try {
            await this.apiRequest(`/tareas/${id}`, {
                method: 'DELETE',
            });
            this.log('✓ Tarea eliminada exitosamente', 'success');
            
            // Después de eliminar, recargar y mostrar lista automáticamente
            await this.refreshAndShowList();
            
        } catch (error) {
            this.log(`✗ Error al eliminar tarea: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // ==================== Data Loading ====================
    
    async loadInitialData() {
        this.log('Cargando tareas desde el servidor...', 'info');
        await this.fetchTasks();
        this.hasLoaded = true;
        
        // Mostrar lista automáticamente al cargar
        if (this.tasks.length > 0) {
            this.renderTasks(true); // true = clear previous output
        } else {
            this.showEmptyState();
        }
    }
    
    async refreshAndShowList() {
        // Recargar datos del servidor
        await this.fetchTasks();
        
        // Limpiar output anterior y mostrar lista actualizada
        this.renderTasks(true);
    }
    
    async manualRefresh() {
        this.log('Actualizando datos...', 'info');
        await this.refreshAndShowList();
        this.log('Datos actualizados ✓', 'success');
    }
    
    // ==================== Command Handling ====================
    
    handleInputKeydown(e) {
        if (e.key === 'Enter') {
            const command = this.elements.commandInput.value.trim();
            if (command) {
                this.executeCommand(command);
                this.commandHistory.push(command);
                this.historyIndex = this.commandHistory.length;
                this.elements.commandInput.value = '';
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.elements.commandInput.value = this.commandHistory[this.historyIndex];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (this.historyIndex < this.commandHistory.length - 1) {
                this.historyIndex++;
                this.elements.commandInput.value = this.commandHistory[this.historyIndex];
            } else {
                this.historyIndex = this.commandHistory.length;
                this.elements.commandInput.value = '';
            }
        } else if (e.key === 'Tab') {
            e.preventDefault();
            this.autocompleteCommand();
        }
    }
    
    handleInputChange() {
        // Could add real-time command validation here
    }
    
    autocompleteCommand() {
        const input = this.elements.commandInput.value.toLowerCase();
        const matches = Object.keys(this.commands).filter(cmd => cmd.startsWith(input));
        
        if (matches.length === 1) {
            this.elements.commandInput.value = matches[0];
        } else if (matches.length > 1) {
            this.log(`Comandos disponibles: ${matches.join(', ')}`, 'info');
        }
    }
    
    executeCommand(commandLine) {
        this.logCommand(commandLine);
        
        const parts = commandLine.split(' ');
        const command = parts[0].toLowerCase();
        const args = parts.slice(1);
        
        if (this.commands[command]) {
            this.commands[command](args);
        } else {
            this.log(`Comando desconocido: "${command}". Escribe "help" para ver los comandos disponibles.`, 'error');
        }
    }
    
    // ==================== Command Implementations ====================
    
    showHelp() {
        const helpText = `
╔══════════════════════════════════════════════════════════════╗
║                     COMANDOS DISPONIBLES                      ║
╠══════════════════════════════════════════════════════════════╣
║  help              - Muestra esta ayuda                       ║
║  list              - Lista todas las tareas                   ║
║  create            - Abre formulario para crear tarea         ║
║  edit <id>         - Edita una tarea existente                ║
║  delete <id>       - Elimina una tarea                        ║
║  search <query>    - Busca tareas por título                  ║
║  stats             - Muestra estadísticas                     ║
║  refresh           - Actualiza datos manualmente              ║
║  clear             - Limpia la terminal                       ║
╚══════════════════════════════════════════════════════════════╝
        `;
        this.appendToOutput(helpText, 'help');
    }
    
    async listTasks() {
        await this.refreshAndShowList();
    }
    
    renderTasks(clearOutput = false) {
        if (clearOutput) {
            this.elements.output.innerHTML = '';
        }
        
        if (this.tasks.length === 0) {
            this.showEmptyState();
            return;
        }
        
        const taskCards = this.tasks.map(task => this.createTaskCard(task)).join('');
        
        this.appendToOutput(`
            <div class="task-list-header" style="margin-bottom: 16px; color: var(--text-secondary); font-size: 0.9rem;">
                Mostrando ${this.tasks.length} tarea(s) — Última actualización: ${this.elements.lastUpdate.textContent}
            </div>
            <div class="task-list">
                ${taskCards}
            </div>
        `, 'html');
    }
    
    showEmptyState() {
        this.elements.output.innerHTML = '';
        this.appendToOutput(`
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-text">No hay tareas registradas</div>
                <div style="margin-top: 12px; color: var(--text-muted); font-size: 0.9rem;">
                    Usa el comando <span style="color: var(--accent-green);">create</span> para agregar una tarea
                </div>
            </div>
        `, 'html');
    }
    
    createTaskCard(task) {
        const statusClass = task.estado.toLowerCase().replace(' ', '_');
        const statusLabels = {
            'pendiente': 'PENDIENTE',
            'en_progreso': 'EN PROGRESO',
            'completada': 'COMPLETADA'
        };
        
        return `
            <div class="task-card status-${statusClass}">
                <div class="task-header">
                    <span class="task-title">${this.escapeHtml(task.titulo)}</span>
                    <div class="task-id-container">
                        <span class="task-id">${task.id.substring(0, 8)}...</span>
                        <button class="copy-btn" onclick="app.copyToClipboard('${task.id}', this)" title="Copiar ID">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                ${task.descripcion ? `<div class="task-description">${this.escapeHtml(task.descripcion)}</div>` : ''}
                <div class="task-meta">
                    <span class="task-status ${statusClass}">${statusLabels[task.estado] || task.estado}</span>
                    <div class="task-actions">
                        <button class="task-btn edit" onclick="app.openEditModal('${task.id}')">Editar</button>
                        <button class="task-btn delete" onclick="app.confirmDelete('${task.id}', '${this.escapeHtml(task.titulo)}')">Eliminar</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    handleEditCommand(args) {
        if (args.length === 0) {
            this.log('Uso: edit <id>', 'error');
            return;
        }
        this.openEditModal(args[0]);
    }
    
    handleDeleteCommand(args) {
        if (args.length === 0) {
            this.log('Uso: delete <id>', 'error');
            return;
        }
        const task = this.tasks.find(t => t.id.startsWith(args[0]) || t.id === args[0]);
        if (task) {
            this.confirmDelete(task.id, task.titulo);
        } else {
            this.log(`No se encontró tarea con ID: ${args[0]}`, 'error');
        }
    }
    
    searchTasks(args) {
        if (args.length === 0) {
            this.log('Uso: search <término>', 'error');
            return;
        }
        
        const query = args.join(' ').toLowerCase();
        const filtered = this.tasks.filter(task => 
            task.titulo.toLowerCase().includes(query) ||
            (task.descripcion && task.descripcion.toLowerCase().includes(query))
        );
        
        if (filtered.length === 0) {
            this.log(`No se encontraron tareas con: "${query}"`, 'info');
        } else {
            this.log(`Encontradas ${filtered.length} tarea(s):`, 'success');
            const taskCards = filtered.map(task => this.createTaskCard(task)).join('');
            this.appendToOutput(`<div class="task-list">${taskCards}</div>`, 'html');
        }
    }
    
    showStats() {
        const total = this.tasks.length;
        const pending = this.tasks.filter(t => t.estado === 'pendiente').length;
        const progress = this.tasks.filter(t => t.estado === 'en_progreso').length;
        const completed = this.tasks.filter(t => t.estado === 'completada').length;
        
        const statsText = `
╔══════════════════════════════════════════════════════════════╗
║                     ESTADÍSTICAS                              ║
╠══════════════════════════════════════════════════════════════╣
║  Total de tareas:    ${total.toString().padStart(3)}                                       ║
║  Pendientes:         ${pending.toString().padStart(3)}                                       ║
║  En progreso:        ${progress.toString().padStart(3)}                                       ║
║  Completadas:        ${completed.toString().padStart(3)}                                       ║
║  Progreso:           ${total > 0 ? Math.round((completed / total) * 100) : 0}%                                       ║
╚══════════════════════════════════════════════════════════════╝
        `;
        this.appendToOutput(statsText, 'stats');
    }
    
    clearOutput() {
        this.elements.output.innerHTML = '';
        this.log('Terminal limpiada', 'info');
    }
    
    // ==================== Modal Handling ====================
    
    openCreateModal() {
        this.elements.createModal.classList.remove('hidden');
        document.getElementById('create-title').focus();
    }
    
    closeCreateModal() {
        this.elements.createModal.classList.add('hidden');
        this.elements.createForm.reset();
    }
    
    openEditModal(taskId) {
        const task = this.tasks.find(t => t.id === taskId || t.id.startsWith(taskId));
        if (!task) {
            this.log(`Tarea no encontrada: ${taskId}`, 'error');
            return;
        }
        
        document.getElementById('edit-id').value = task.id;
        document.getElementById('edit-title').value = task.titulo;
        document.getElementById('edit-description').value = task.descripcion || '';
        document.getElementById('edit-status').value = task.estado;
        
        this.elements.editModal.classList.remove('hidden');
        document.getElementById('edit-title').focus();
    }
    
    closeEditModal() {
        this.elements.editModal.classList.add('hidden');
        this.elements.editForm.reset();
    }
    
    async handleCreateSubmit(e) {
        e.preventDefault();
        
        const data = {
            titulo: document.getElementById('create-title').value,
            descripcion: document.getElementById('create-description').value || undefined,
            estado: document.getElementById('create-status').value,
        };
        
        try {
            await this.createTask(data);
            this.closeCreateModal();
        } catch (error) {
            // Error already logged
        }
    }
    
    async handleEditSubmit(e) {
        e.preventDefault();
        
        const id = document.getElementById('edit-id').value;
        const data = {
            titulo: document.getElementById('edit-title').value,
            descripcion: document.getElementById('edit-description').value || undefined,
            estado: document.getElementById('edit-status').value,
        };
        
        try {
            await this.updateTask(id, data);
            this.closeEditModal();
        } catch (error) {
            // Error already logged
        }
    }
    
    confirmDelete(id, title) {
        if (confirm(`¿Eliminar tarea "${title}"?`)) {
            this.deleteTask(id);
        }
    }
    
    // ==================== UI Utilities ====================
    
    log(message, type = 'info') {
        const line = document.createElement('div');
        line.className = `output-line ${type}`;
        line.textContent = message;
        this.elements.output.appendChild(line);
        this.scrollToBottom();
    }
    
    logCommand(command) {
        const line = document.createElement('div');
        line.className = 'output-line command';
        line.textContent = command;
        this.elements.output.appendChild(line);
        this.scrollToBottom();
    }
    
    appendToOutput(content, type = 'html') {
        const wrapper = document.createElement('div');
        wrapper.className = 'output-content';
        
        if (type === 'html') {
            wrapper.innerHTML = content;
        } else {
            wrapper.textContent = content;
        }
        
        this.elements.output.appendChild(wrapper);
        this.scrollToBottom();
    }
    
    scrollToBottom() {
        this.elements.output.scrollTop = this.elements.output.scrollHeight;
    }
    
    updateStats() {
        const total = this.tasks.length;
        const pending = this.tasks.filter(t => t.estado === 'pendiente').length;
        const progress = this.tasks.filter(t => t.estado === 'en_progreso').length;
        const completed = this.tasks.filter(t => t.estado === 'completada').length;
        
        this.elements.statTotal.textContent = total;
        this.elements.statPending.textContent = pending;
        this.elements.statProgress.textContent = progress;
        this.elements.statCompleted.textContent = completed;
    }
    
    updateLastRefresh() {
        const now = new Date();
        this.elements.lastUpdate.textContent = now.toLocaleTimeString();
    }
    
    setStatus(status) {
        const indicator = this.elements.statusIndicator;
        const text = this.elements.statusText;
        
        indicator.className = 'status ' + status;
        
        const statusTexts = {
            online: 'connected',
            offline: 'disconnected',
            syncing: 'syncing...'
        };
        
        text.textContent = statusTexts[status] || status;
        this.isConnected = status === 'online';
    }
    
    showHint() {
        this.elements.commandHint.classList.remove('hidden');
    }
    
    hideHint() {
        setTimeout(() => {
            if (document.activeElement !== this.elements.commandInput) {
                this.elements.commandHint.classList.add('hidden');
            }
        }, 200);
    }
    
    async copyToClipboard(text, btnElement) {
        try {
            await navigator.clipboard.writeText(text);
            
            // Cambiar el icono temporalmente para mostrar feedback
            const originalHTML = btnElement.innerHTML;
            btnElement.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            `;
            btnElement.classList.add('copied');
            
            // Mostrar mensaje temporal
            this.log(`ID copiado: ${text.substring(0, 8)}...`, 'success');
            
            // Restaurar después de 2 segundos
            setTimeout(() => {
                btnElement.innerHTML = originalHTML;
                btnElement.classList.remove('copied');
            }, 2000);
            
        } catch (err) {
            this.log('Error al copiar al portapapeles', 'error');
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize application
const app = new TaskManagerApp();
