# Overmind GUI Web - Project Index

## Project Overview

A decoupled web-based GUI for managing Overmind processes with daemon-based architecture. The system provides persistent process management, real-time output streaming, and multi-client support through an independent daemon process.

**Key Features:**
- Independent daemon process managing Overmind instances
- Persistent SQLite storage for output history
- Web-based GUI client with real-time updates
- Process control and monitoring capabilities
- Multi-client connection support
- Automatic reconnection and recovery

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    OVERMIND DAEMON                          │
│  ┌─────────────────┐    ┌──────────────┐    ┌─────────────┐│
│  │ OvrmindManager  │───→│ DatabaseMgr  │───→│ DaemonAPI   ││
│  │                 │    │ (SQLite)     │    │ (HTTP)      ││
│  └─────────────────┘    └──────────────┘    └─────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────┐
│                     GUI CLIENT                              │
│  ┌─────────────────┐    ┌──────────────┐    ┌─────────────┐│
│  │ DaemonClient    │───→│ UpdateQueue  │───→│ API Routes  ││
│  │                 │    │              │    │             ││
│  └─────────────────┘    └──────────────┘    └─────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                ↓
                    ┌─────────────────────┐
                    │    Web Frontend     │
                    │    (JavaScript)     │
                    └─────────────────────┘
```

## Directory Structure

```
overmind-gui-web/
├── src/                          # Source code
│   ├── Python Backend/
│   │   ├── overmind_daemon.py        # Main daemon process
│   │   ├── daemon_overmind_manager.py # Overmind subprocess management
│   │   ├── daemon_manager.py         # Daemon lifecycle management
│   │   ├── daemon_config.py          # Configuration management
│   │   ├── database_client.py        # Database operations
│   │   ├── api_routes_daemon.py      # Daemon API endpoints
│   │   ├── main.py                   # GUI server (client mode)
│   │   ├── update_queue.py           # Message queue management
│   │   ├── process_manager.py        # Process state management
│   │   ├── event_handlers.py         # Event processing
│   │   ├── ansi_to_html.py          # ANSI to HTML conversion
│   │   └── static_files.py           # Static file serving
│   │
│   ├── JavaScript Frontend/
│   │   ├── app.js                    # Main application logic
│   │   ├── ui.js                     # UI components and rendering
│   │   ├── state-manager.js          # Frontend state management
│   │   ├── polling.js                # API polling mechanism
│   │   ├── search.js                 # Search functionality
│   │   ├── utils.js                  # Utility functions
│   │   ├── constants.js              # Configuration constants
│   │   ├── init.js                   # Application initialization
│   │   ├── components.js             # Reusable UI components
│   │   ├── virtual-list.js           # Virtual scrolling
│   │   └── data-processor.worker.js  # Web worker for data processing
│   │
│   └── HTML/
│       └── index.html                 # Main application UI
│
├── output/                       # Test outputs and logs
├── architecture.txt              # Architecture documentation
├── run                          # Main execution script
├── requirements.txt             # Python dependencies
└── version.txt                  # Version information
```

## Core Components

### Daemon Layer

#### `overmind_daemon.py`
- **Purpose**: Standalone daemon process managing Overmind instances
- **Key Classes**:
  - `DatabaseManager`: SQLite persistence layer
  - `OvrmindDaemon`: Main daemon orchestrator
- **Responsibilities**:
  - Process lifecycle management
  - Output persistence
  - Client connection handling
  - Instance discovery

#### `daemon_overmind_manager.py`
- **Purpose**: Manages Overmind subprocess within daemon
- **Key Classes**:
  - `DaemonOvrmindManager`: Subprocess control and monitoring
- **Responsibilities**:
  - Start/stop/restart Overmind processes
  - Capture and process output streams
  - Monitor process health
  - Handle process control commands

#### `database_client.py`
- **Purpose**: Database operations and data persistence
- **Key Methods**:
  - `store_output()`: Persist process output
  - `get_output()`: Retrieve historical output
  - `get_process_status()`: Query process states
- **Storage Schema**:
  - Output lines with HTML formatting
  - Process status tracking
  - System events logging

#### `daemon_config.py`
- **Purpose**: Configuration and discovery management
- **Features**:
  - Daemon settings management
  - Instance discovery mechanism
  - Configuration persistence
  - Default values and validation

### GUI Server Layer

#### `main.py`
- **Purpose**: GUI server operating as daemon client
- **Key Components**:
  - FastAPI application
  - WebSocket handling
  - Static file serving
  - Daemon connection management
- **API Endpoints**:
  - `/api/output`: Fetch process output
  - `/api/status`: Get process status
  - `/api/process/*`: Process control
  - `/api/config`: Configuration management

#### `update_queue.py`
- **Purpose**: Message queue for frontend updates
- **Functionality**:
  - Output buffering
  - Rate limiting
  - Client synchronization
  - Memory optimization

#### `process_manager.py`
- **Purpose**: Process state and control logic
- **Features**:
  - Process status tracking
  - Command execution
  - State synchronization
  - Error handling

### Frontend Layer

#### `app.js`
- **Purpose**: Main application controller
- **Responsibilities**:
  - Application lifecycle
  - Component coordination
  - Event handling
  - State management integration

#### `ui.js`
- **Purpose**: UI rendering and interaction
- **Key Functions**:
  - `renderUI()`: Main rendering pipeline
  - `handleProcessClick()`: Process selection
  - `updateProcessList()`: Status updates
  - `applyFilters()`: Search and filtering
- **Features**:
  - Virtual scrolling for performance
  - Real-time updates
  - Process control buttons
  - Search and filtering

#### `state-manager.js`
- **Purpose**: Centralized state management
- **State Components**:
  - Process list and status
  - Output buffer
  - UI preferences
  - Connection status
- **Methods**:
  - `updateState()`: State modifications
  - `getState()`: State queries
  - `subscribe()`: Change notifications

#### `polling.js`
- **Purpose**: Server communication layer
- **Features**:
  - Periodic status polling
  - Output fetching
  - Error recovery
  - Connection management

## API Documentation

### Daemon API Endpoints

#### Process Control
```
POST /api/process/start/{process_name}
POST /api/process/stop/{process_name}
POST /api/process/restart/{process_name}
POST /api/process/kill/{process_name}
```

#### Status and Monitoring
```
GET /api/status
  Response: {
    "processes": {
      "web": "running",
      "worker": "stopped"
    },
    "daemon": "healthy"
  }

GET /api/output
  Query params:
    - after_id: Message ID to fetch after
    - process: Filter by process name
    - limit: Maximum messages to return
  Response: {
    "messages": [...],
    "has_more": boolean
  }
```

#### Configuration
```
GET /api/config
  Response: Current configuration

POST /api/config
  Body: Configuration updates
```

### WebSocket Events

#### From Server
```javascript
{
  "type": "output_batch",
  "lines": [
    {
      "id": 12345,
      "process": "web",
      "html": "<span>Output line</span>"
    }
  ]
}

{
  "type": "status_update",
  "updates": {
    "web": "running",
    "worker": "stopped"
  }
}
```

#### To Server
```javascript
{
  "type": "subscribe",
  "processes": ["web", "worker"]
}

{
  "type": "command",
  "action": "restart",
  "process": "web"
}
```

## Data Flow

### Output Pipeline
1. Overmind process generates output
2. DaemonOvrmindManager captures stdout/stderr
3. ANSI codes converted to HTML
4. DatabaseManager persists to SQLite
5. UpdateQueue batches for transmission
6. Frontend receives via polling/WebSocket
7. UI renders with virtual scrolling

### Process Control Flow
1. User clicks control button
2. Frontend sends API request
3. GUI server forwards to daemon
4. Daemon executes command via OvrmindManager
5. Status update broadcast to all clients
6. UI updates reflect new state

## Configuration

### Daemon Configuration (`~/.overmind-gui/daemon-config.json`)
```json
{
  "daemon": {
    "api_port_range_start": 9000,
    "api_port_range_end": 9100,
    "max_output_lines": 100000,
    "cleanup_days": 30,
    "heartbeat_interval": 10
  },
  "storage": {
    "database_name": "daemon.db",
    "backup_enabled": true,
    "backup_interval_hours": 24
  },
  "discovery": {
    "enabled": true,
    "broadcast_interval": 30
  }
}
```

### Frontend Configuration (`constants.js`)
```javascript
{
  POLLING_INTERVAL: 1000,
  MAX_MESSAGES: 10000,
  VIRTUAL_SCROLL_BUFFER: 50,
  DEBOUNCE_DELAY: 300,
  RECONNECT_DELAY: 2000
}
```

## Key Features Implementation

### Persistent Storage
- SQLite database for output history
- Survives GUI restarts
- Configurable retention period
- Automatic cleanup of old data

### Multi-Client Support
- Multiple GUI instances can connect
- Synchronized state across clients
- Independent client sessions
- Broadcast updates to all connected clients

### Process Management
- Start/stop/restart processes
- Kill unresponsive processes
- Process selection and filtering
- Status monitoring

### Performance Optimizations
- Virtual scrolling for large output
- Debounced search filtering
- Batch message processing
- Web worker for heavy operations
- Efficient database indexing

### Error Recovery
- Automatic reconnection
- Graceful degradation
- Error state handling
- Fallback mechanisms

## Testing

### Test Files
- `integration_test.py`: End-to-end testing
- `quick_daemon_gui_test.py`: Daemon functionality
- `test_*.js`: Frontend unit tests
- `output/test-run/`: Test execution results

### Testing Strategy
1. Unit tests for individual components
2. Integration tests for daemon-GUI communication
3. End-to-end tests for complete workflows
4. Performance testing for large output volumes

## Development Workflow

### Starting the System
```bash
# Start daemon (if not running)
python src/overmind_daemon.py

# Start GUI server
./run

# Or combined startup
./run --with-daemon
```

### Development Mode
```bash
# Run with debug logging
LOG_LEVEL=DEBUG ./run

# Run tests
./run test

# Check daemon status
./run status
```

## Migration from Legacy

### Key Changes from Tightly-Coupled Architecture
1. **Process Ownership**: Daemon owns Overmind, not GUI
2. **Persistence**: SQLite replaces in-memory storage
3. **Communication**: HTTP/WebSocket replaces direct subprocess
4. **Lifecycle**: Independent GUI and Overmind lifecycles
5. **Discovery**: File-based instance discovery mechanism

### Backward Compatibility
- Legacy mode available with `--legacy` flag
- Gradual migration path
- Configuration migration utilities
- Data preservation during transition

## Future Enhancements

### Planned Features
- WebSocket real-time streaming (partially implemented)
- Advanced search and filtering
- Process grouping and templates
- Metrics and monitoring dashboard
- Plugin system for extensions
- Cloud synchronization option

### Performance Improvements
- Connection pooling optimization
- Caching layer for frequent queries
- Compression for large outputs
- Incremental UI updates

## Troubleshooting

### Common Issues

#### Daemon Connection Failed
- Check daemon is running: `ps aux | grep overmind_daemon`
- Verify port availability: `lsof -i :9000-9100`
- Check logs: `tail -f overmind-daemon.log`

#### Output Not Appearing
- Verify database writes: `sqlite3 ~/.overmind-gui/daemon.db`
- Check UpdateQueue status in browser console
- Ensure proper process selection

#### Performance Issues
- Monitor database size: `du -h ~/.overmind-gui/daemon.db`
- Check message count in browser console
- Review virtual scrolling behavior

## Contributing

### Code Style
- Python: PEP 8 compliance
- JavaScript: ESLint configuration
- Comments for complex logic
- Type hints where applicable

### Submission Process
1. Create feature branch
2. Implement with tests
3. Update documentation
4. Submit pull request

## License and Credits

Project developed as part of Overmind GUI enhancement initiative.
Architecture design based on decoupling requirements for improved reliability and flexibility.

---
*Generated: September 2024*
*Version: See version.txt*