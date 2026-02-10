# TUI Task Manager Frontend

Frontend profesional con estilo Terminal User Interface (TUI) para la aplicación de gestión de tareas.

## Características

- **Estilo Terminal**: Interfaz tipo terminal monocromática con colores cuidadosamente seleccionados
- **Carga Inicial Automática**: Al abrir la página se cargan todas las tareas automáticamente
- **AJAX en Operaciones CRUD**: Las tareas se actualizan automáticamente después de crear, editar o eliminar
- **Comandos Tipo Terminal**: Interfaz de línea de comandos intuitiva
- **Diseño Responsivo**: Adaptable a diferentes tamaños de pantalla
- **Modalidades Modernas**: Formularios elegantes sin recargar la página
- **Indicadores de Estado**: Visualización en tiempo real de conexión y estadísticas
- **Atajos de Teclado**: Navegación eficiente con teclas rápidas

## Estructura

```
frontend/
├── index.html          # Estructura principal
├── css/
│   └── style.css       # Estilos TUI profesionales
└── js/
    └── app.js          # Lógica AJAX y comandos
```

## Uso

1. **Iniciar el backend**:
   ```bash
   cd backend_fastapi
   uvicorn main:app --reload --port 8000
   ```

2. **Abrir el frontend**:
   - Abrir `frontend/index.html` directamente en el navegador, o
   - Servir con un servidor local:
     ```bash
     cd frontend
     python -m http.server 3000
     ```
   - Visitar: http://localhost:3000

## Comandos Disponibles

| Comando | Descripción |
|---------|-------------|
| `help` | Muestra ayuda de comandos |
| `list` | Lista todas las tareas |
| `create` | Abre formulario para crear tarea |
| `edit <id>` | Edita una tarea existente |
| `delete <id>` | Elimina una tarea |
| `search <query>` | Busca tareas por título |
| `stats` | Muestra estadísticas |
| `refresh` | Actualiza datos manualmente |
| `clear` | Limpia la terminal |

## Flujo de Trabajo

1. **Al cargar la página**: Se hace un `fetch` automático y se muestran todas las tareas
2. **Crear tarea**: Después de crear, se hace `fetch` automático y se actualiza la vista
3. **Editar tarea**: Después de editar, se hace `fetch` automático y se actualiza la vista  
4. **Eliminar tarea**: Después de eliminar, se hace `fetch` automático y se actualiza la vista
5. **No hay polling**: Las tareas solo se recargan cuando hay cambios o al usar el comando `list`/`refresh`

## Atajos de Teclado

- **Tab**: Autocompletar comandos
- **Enter**: Ejecutar comando
- **↑/↓**: Navegar historial de comandos
- **Esc**: Cerrar modales

## API Integration

El frontend se comunica con la API REST en `http://localhost:8000`:

- `GET /tareas` - Listar tareas
- `POST /tareas` - Crear tarea
- `PUT /tareas/{id}` - Actualizar tarea
- `DELETE /tareas/{id}` - Eliminar tarea

## Diseño

### Paleta de Colores

- **Fondo**: `#0d1117` (Negro suave)
- **Texto Principal**: `#e6edf3` (Blanco)
- **Texto Secundario**: `#8b949e` (Gris)
- **Éxito**: `#3fb950` (Verde)
- **Advertencia**: `#d29922` (Amarillo)
- **Error**: `#f85149` (Rojo)
- **Info**: `#58a6ff` (Azul)

### Tipografía

- **Font**: JetBrains Mono (monospace)
- **Efectos**: Scanlines sutiles para efecto CRT
