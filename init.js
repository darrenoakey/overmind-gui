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
        
        // Set up polling manager event handlers
        pollingManager.onUpdate = (updates) => {
            handleUpdates(updates);
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
 * Handle updates from polling
 */
function handleUpdates(updates) {
    if (!uiManager) return;
    
    const outputLines = [];
    
    updates.forEach(update => {
        switch (update.type) {
            case 'output':
                if (update.data && update.data.line) {
                    outputLines.push(update.data.line);
                } else if (update.data) {
                    // Handle direct line data
                    outputLines.push(update.data);
                }
                break;
                
            case 'status':
                if (update.data && update.data.process && update.data.status) {
                    uiManager.updateProcessStatus(update.data.process, update.data.status);
                }
                break;
                
            case 'status_bulk':
                if (update.data && update.data.updates) {
                    Object.entries(update.data.updates).forEach(([processName, statusInfo]) => {
                        uiManager.updateProcessStatus(processName, statusInfo.status);
                    });
                }
                break;
                
            case 'server_started':
                console.log('Server restarted - reloading page...');
                // Give a moment for any final updates, then reload
                setTimeout(() => {
                    window.location.reload();
                }, 500);
                break;
        }
    });
    
    // Add any new output lines
    if (outputLines.length > 0) {
        uiManager.addOutputLines(outputLines);
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