/**
 * Initialization script for Overmind GUI
 * Creates and starts the polling manager and UI manager
 * Enhanced with proper error handling and display
 */

// Global instances
let pollingManager;
let uiManager;

/**
 * Show early error before UI is initialized
 */
function showEarlyError(message, error = null) {
    // Hide loading overlay
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }
    
    // Show error modal
    const errorModal = document.getElementById('error-modal');
    const errorMessage = document.getElementById('error-message');
    
    if (errorModal && errorMessage) {
        let errorText = message;
        
        // Add stack trace for internal app debugging
        if (error && error.stack) {
            errorText += '\n\nStack Trace:\n' + error.stack;
        }
        
        errorMessage.style.whiteSpace = 'pre-wrap';
        errorMessage.textContent = errorText;
        errorModal.classList.remove('hidden');
        
        // Add close functionality
        const closeBtn = document.getElementById('error-modal-close');
        if (closeBtn) {
            closeBtn.onclick = () => errorModal.classList.add('hidden');
        }
        
        // Click outside to close
        errorModal.onclick = (e) => {
            if (e.target === errorModal) {
                errorModal.classList.add('hidden');
            }
        };
    } else {
        // Fallback to alert if modal not available
        alert('Critical Error: ' + message + (error ? '\n\n' + error.stack : ''));
    }
}

/**
 * Initialize the application
 */
async function initializeApp() {
    console.log('Initializing Overmind GUI...');
    
    try {
        // Check if required classes are available
        if (typeof window.UIManager === 'undefined') {
            throw new Error('UIManager class not loaded. Check ui.js for syntax errors.');
        }
        
        if (typeof window.PollingManager === 'undefined') {
            throw new Error('PollingManager class not loaded. Check polling.js for syntax errors.');
        }
        
        if (typeof window.AnsiUtils === 'undefined') {
            throw new Error('AnsiUtils not loaded. Check utils.js for syntax errors.');
        }
        
        // Create UI manager
        uiManager = new window.UIManager();
        uiManager.init();
        
        // Create polling manager
        pollingManager = new window.PollingManager();
        window.pollingManager = pollingManager; // Make available globally for UI
        
        // Set up polling manager event handlers - NEW PROTOCOL
        pollingManager.onPollingResponse = (data) => {
            handlePollingResponse(data);
        };
        
        pollingManager.onError = (error) => {
            console.error('Polling error:', error);
            uiManager.showError('Connection error: ' + error.message, error);
        };
        
        pollingManager.onStatusChange = (statusUpdates) => {
            handleStatusChange(statusUpdates);
        };
        
        // Get initial state
        console.log('Loading initial state...');
        const initialState = await pollingManager.getInitialState();
        
        // Load initial state into UI
        await uiManager.loadInitialState(initialState);
        
        // Start polling
        pollingManager.start();
        
        // Update connection indicator
        uiManager.updatePollingIndicator('connected');
        
        // Hide loading overlay
        uiManager.hideLoading();
        
        console.log('Overmind GUI initialized successfully');
        
    } catch (error) {
        console.error('Failed to initialize app:', error);
        
        if (uiManager && uiManager.showError) {
            uiManager.hideLoading();
            uiManager.showError('Failed to initialize: ' + error.message, error);
        } else {
            // Use early error handler if UI not available
            showEarlyError('Failed to initialize Overmind GUI: ' + error.message, error);
        }
    }
}

/**
 * Handle updates from polling - NEW OPTIMIZED PROTOCOL with pre-rendered HTML
 */
function handlePollingResponse(data) {
    if (!uiManager) return;
    
    // NEW OPTIMIZED FORMAT:
    // data = {
    //   output_lines: [{id, html, clean_text, process, timestamp}, ...],
    //   status_updates: {process: status, ...},
    //   total_lines: int,
    //   other_updates: [...],
    //   timestamp: float,
    //   stats: {...}
    // }
    
    let shouldReload = false;
    
    // 1. Handle other updates first (server restart, etc)
    if (data.other_updates && data.other_updates.length > 0) {
        data.other_updates.forEach(update => {
            if (update.type === 'server_started') {
                console.log('Server restarted - reloading page...');
                shouldReload = true;
            }
        });
    }
    
    // 2. Add all output lines in one batch (pre-rendered HTML!)
    if (data.output_lines && data.output_lines.length > 0) {
        uiManager.addPreRenderedLines(data.output_lines, data.total_lines);
    }
    
    // 3. Update all process statuses in one batch
    if (data.status_updates && Object.keys(data.status_updates).length > 0) {
        uiManager.updateProcessStatuses(data.status_updates);
    }
    
    // 4. Handle page reload if needed
    if (shouldReload) {
        setTimeout(() => {
            window.location.reload();
        }, 500);
    }
}

/**
 * Handle status changes
 */
function handleStatusChange(statusUpdates) {
    if (!uiManager) return;
    
    Object.entries(statusUpdates).forEach(([key, value]) => {
        if (key === 'connection') {
            // Handle connection status
            const status = value.status === 'connected' ? 'connected' : 'disconnected';
            uiManager.updatePollingIndicator(status);
        } else {
            // Handle process status
            if (value.status) {
                uiManager.updateProcessStatus(key, value.status);
            }
        }
    });
}

/**
 * Cleanup on page unload
 */
function cleanup() {
    if (pollingManager) {
        pollingManager.stop();
    }
    
    if (uiManager && uiManager.cleanup) {
        uiManager.cleanup();
    }
}

/**
 * Global error handler for unhandled errors
 */
window.addEventListener('error', (event) => {
    console.error('Unhandled error:', event.error);
    
    if (uiManager && uiManager.showError) {
        uiManager.showError('Unhandled error: ' + event.error.message, event.error);
    } else {
        showEarlyError('Unhandled error: ' + event.error.message, event.error);
    }
});

/**
 * Global handler for unhandled promise rejections
 */
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    
    if (uiManager && uiManager.showError) {
        uiManager.showError('Unhandled promise rejection: ' + event.reason, event.reason);
    } else {
        showEarlyError('Unhandled promise rejection: ' + event.reason, event.reason);
    }
});

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    // DOM already loaded
    initializeApp();
}

// Cleanup on page unload
window.addEventListener('beforeunload', cleanup);

// Export for debugging
window.appState = {
    pollingManager: () => pollingManager,
    uiManager: () => uiManager,
    reinitialize: initializeApp,
    showError: showEarlyError
};