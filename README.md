# Overmind GUI

![Overmind GUI](splash.png)

A modern web-based graphical user interface for the Overmind process manager. This application provides an intuitive web interface to monitor, control, and interact with your Overmind-managed processes through a clean, responsive web UI.

## Features

- **Real-time Process Monitoring** - Live updates of process status and output
- **WebSocket Communication** - Instant updates without page refreshes  
- **Process Output Buffering** - Stores up to 10,000 lines of output per process
- **Responsive Design** - Works seamlessly on desktop and mobile devices
- **Automatic App Integration** - Launches the native Overmind.app on startup
- **RESTful API** - Clean API endpoints for process management
- **Shutdown Controls** - Safe process termination through the web interface

## Prerequisites

- **Python 3.8+** - Required for running the web server
- **macOS** - Required for Overmind.app integration
- **Overmind.app** - Must be installed at `/Applications/Overmind.app`
- **Overmind CLI** - The overmind binary must be available in your PATH

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/[username]/overmind-gui.git
   cd overmind-gui
   ```

2. **Install Python dependencies:**
   ```bash
   pip install sanic websockets
   ```

3. **Verify Overmind.app is installed:**
   ```bash
   ls /Applications/Overmind.app
   ```

4. **Ensure overmind binary is available:**
   ```bash
   which overmind
   ```

## Usage

### Starting the Web Interface

1. **Launch the web server:**
   ```bash
   python main.py
   ```
   
   The server will:
   - Start on the default port (usually 8000)
   - Automatically launch `/Applications/Overmind.app` after 0.2 seconds
   - Begin serving the web interface

2. **Access the web interface:**
   - Open your web browser
   - Navigate to `http://localhost:8000`
   - The web interface will display your process dashboard

### Web Interface Features

- **Process Dashboard** - View all managed processes and their current status
- **Real-time Output** - See live process output with automatic scrolling
- **Process Controls** - Start, stop, and restart individual processes
- **System Status** - Monitor overall system health and resource usage
- **Shutdown Button** - Safely terminate all processes and the web server

### API Endpoints

The application provides several API endpoints for programmatic access:

- **Message Polling** - `/api/poll?last_message_id=<id>` - Retrieve new messages since the specified ID
- **Static Assets** - Serves JavaScript, CSS, and image files
- **WebSocket** - Real-time bidirectional communication for live updates

## Architecture

### Core Components

- **`main.py`** - Application entry point and Sanic web server configuration
- **`process_manager.py`** - Process state management and output buffering
- **`overmind_controller.py`** - Interface to the overmind binary with quit() functionality
- **`static_files.py`** - Static asset routing for JavaScript, CSS, and images
- **`api_routes.py`** - RESTful API endpoints for process management
- **`styles.css`** - Responsive CSS styling (22,638 bytes)

### Technology Stack

- **Backend:** Python 3 + Sanic (async web framework)
- **Frontend:** HTML5 + JavaScript + CSS3
- **Communication:** WebSockets + REST API
- **Integration:** Native macOS Overmind.app
- **Process Management:** Overmind CLI binary

## Configuration

### Static File Serving

The application serves several JavaScript modules:
- `polling.js` - Handles API polling for updates
- `ui.js` - Main user interface logic
- `init.js` - Application initialization

### Process Output Management

- **Buffer Limit:** 10,000 lines per process maximum
- **Real-time Updates:** WebSocket-based live output streaming
- **Message Polling:** Uses `last_message_id` parameter for efficient updates

## Development

### Project Structure

```
overmind-gui-web/
├── main.py                 # Web server entry point
├── process_manager.py      # Process state management  
├── overmind_controller.py  # Overmind binary interface
├── static_files.py         # Static asset routing
├── api_routes.py          # API endpoint definitions
├── styles.css             # UI styling
├── index.html             # Main web interface
├── app.js                 # Frontend JavaScript
└── static/                # Additional static assets
```

### Key Design Principles

- **No Version Files** - Always work directly on production files (no v2, backup versions)
- **Responsive Design** - Shutdown button and controls remain visible on all screen sizes
- **Process Safety** - Safe shutdown procedures through `overmind_controller.quit()` method
- **Real-time First** - WebSocket-based architecture for immediate updates

## Troubleshooting

### Common Issues

**"Overmind.app not found"**
- Ensure Overmind.app is installed at `/Applications/Overmind.app`
- Check that you have permission to launch the application

**"overmind binary not found"**  
- Install overmind CLI: `brew install tmux overmind` (if using Homebrew)
- Verify overmind is in your PATH: `which overmind`

**Web interface not loading**
- Check that the Python server started successfully
- Verify no other service is using the same port
- Check browser console for JavaScript errors

**Processes not updating**
- Ensure WebSocket connection is established
- Check that overmind is running and managing processes
- Verify API endpoints are responding correctly

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes following the project conventions
4. Test thoroughly with actual Overmind processes
5. Submit a pull request with a clear description

## License

This project is open source. Please check the LICENSE file for specific terms.

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check existing issues for similar problems
- Provide detailed information about your environment and the problem

---

**Note:** This application is designed specifically for macOS environments with Overmind.app installed. It provides a web-based alternative to the native application interface while maintaining full integration with the underlying Overmind process management system.