/**
 * UI module for Overmind GUI
 * Handles user interface interactions, DOM manipulation, and state management
 * Updated with proper auto-scroll, search/filter separation, and ANSI handling
 */

class UIManager {
    constructor() {
        // Local line buffer with 5000 line limit
        this.currentLines = [];
        this.maxLines = 5000;
        this.lineIdMap = new Map(); // For quick lookup of lines by ID
        
        this.selectedProcesses = new Set();
        this.filteredLineIds = new Set();
        this.searchMatchIds = new Set();
        this.currentSearchIndex = -1;
        this.searchMatches = [];
        
        // Auto-scroll state - ON by default
        this.autoScroll = true;
        this.isSearchActive = false;
        this.isFilterActive = false;
        this.programmaticScroll = false; // Flag to prevent mouse wheel from triggering during our scroll
        
        // Debounce timers
        this.searchDebounceTimer = null;
        this.filterDebounceTimer = null;
        
        // DOM elements
        this.elements = {};
        
        // State
        this.processes = {};
        this.stats = {};
        this.overmindStatus = 'unknown';
        
        // Scroll monitoring
        this.scrollCheckInterval = null;
    }
    
    /**
     * Initialize UI manager
     */
    init() {
        this.bindElements();
        this.bindEvents();
        this.updatePollingIndicator('disconnected');
        this.updateAutoScrollButton();
        this.startScrollMonitoring();
    }
    
    /**
     * Debounce function for search and filter
     */
    debounce(func, wait) {
        return (...args) => {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => func.apply(this, args), wait);
        };
    }
    
    /**
     * Bind DOM elements
     */
    bindElements() {
        this.elements = {
            // Header elements
            overmindStatus: document.getElementById('overmind-status'),
            versionNumber: document.getElementById('version-number'),
            autoscrollIndicator: document.getElementById('autoscroll-indicator'),
            lineCount: document.getElementById('line-count'),
            processCount: document.getElementById('process-count'),
            pollingStatus: document.getElementById('polling-status'),
            
            
            // Control buttons (in processes header)
            selectAllBtn: document.getElementById('select-all-btn'),
            deselectAllBtn: document.getElementById('deselect-all-btn'),
            
            // Filter elements (separate from search)
            filterInput: document.getElementById('filter-input'),
            
            // Search elements (separate from filter)
            searchInput: document.getElementById('search-input'),
            searchUpBtn: document.getElementById('search-up-btn'),
            searchDownBtn: document.getElementById('search-down-btn'),
            searchResultsText: document.getElementById('search-results-text'),
            
            // Lists and displays
            processList: document.getElementById('process-list'),
            outputLines: document.getElementById('output-lines'),
            outputContainer: document.getElementById('output-container'),
            
            // Auto-scroll button (floating)
            autoScrollBtn: document.getElementById('auto-scroll-btn'),
            
            
            // Modal elements
            loadingOverlay: document.getElementById('loading-overlay'),
            errorModal: document.getElementById('error-modal'),
            errorMessage: document.getElementById('error-message'),
            errorModalClose: document.getElementById('error-modal-close')
        };
    }
    
    /**
     * Bind event listeners
     */
    bindEvents() {
        // Control buttons (in processes header)
        this.elements.selectAllBtn.addEventListener('click', () => this.selectAllProcesses());
        this.elements.deselectAllBtn.addEventListener('click', () => this.deselectAllProcesses());
        
        // Filter input - debounced, no button
        const debouncedFilter = this.debounce((value) => this.applyFilter(value), 300);
        this.elements.filterInput.addEventListener('input', (e) => {
            debouncedFilter(e.target.value);
        });
        
        // Search input - debounced
        const debouncedSearch = this.debounce((value) => this.performSearch(value), 300);
        this.elements.searchInput.addEventListener('input', (e) => {
            debouncedSearch(e.target.value);
        });
        
        // Search navigation buttons
        this.elements.searchUpBtn.addEventListener('click', () => this.searchPrevious());
        this.elements.searchDownBtn.addEventListener('click', () => this.searchNext());
        
        // Auto-scroll button (floating)
        this.elements.autoScrollBtn.addEventListener('click', () => this.enableAutoScroll());
        
        // Mouse wheel detection - disable autoscroll on user wheel scroll
        this.elements.outputLines.addEventListener('wheel', (e) => {
            // Only disable autoscroll if this is a real user wheel event, not our programmatic scroll
            if (this.autoScroll && !this.programmaticScroll) {
                this.autoScroll = false;
                this.updateAutoScrollButton();
                console.log('Auto-scroll disabled by mouse wheel');
            }
        });
        
        // Detect scrollbar interaction - only way to disable autoscroll via scrolling
        this.elements.outputLines.addEventListener('mousedown', (e) => {
            // Check if mousedown is on scrollbar (right side of output-lines)
            const containerRect = this.elements.outputLines.getBoundingClientRect();
            const clickX = e.clientX - containerRect.left;
            
            // If clicking in scrollbar area (right edge), disable autoscroll
            if (clickX > this.elements.outputLines.clientWidth) {
                this.autoScroll = false;
                this.updateAutoScrollButton();
                console.log('Auto-scroll disabled by scrollbar interaction');
            }
        });
        
        // Modal close
        this.elements.errorModalClose.addEventListener('click', () => this.hideErrorModal());
        
        // Click outside modal to close
        this.elements.errorModal.addEventListener('click', (e) => {
            if (e.target === this.elements.errorModal) {
                this.hideErrorModal();
            }
        });
    }
    
    
    /**
     * Enable auto-scroll and scroll to bottom
     */
    enableAutoScroll() {
        this.autoScroll = true;
        this.updateAutoScrollButton();
        this.scrollToBottom();
        console.log('Auto-scroll enabled');
    }
    
    /**
     * Update auto-scroll button visibility and indicator
     */
    updateAutoScrollButton() {
        if (this.autoScroll) {
            this.elements.autoScrollBtn.style.display = 'none';
            this.elements.autoscrollIndicator.textContent = 'ON';
            this.elements.autoscrollIndicator.className = 'status-value autoscroll-on';
        } else {
            this.elements.autoScrollBtn.style.display = 'block';
            this.elements.autoscrollIndicator.textContent = 'OFF';
            this.elements.autoscrollIndicator.className = 'status-value autoscroll-off';
        }
    }
    
    /**
     * Apply filter to lines (immediate CSS hiding)
     */
    applyFilter(filterText) {
        const filter = filterText.trim().toLowerCase();
        this.isFilterActive = filter.length > 0;
        
        const lineElements = this.elements.outputLines.querySelectorAll('.output-line');
        let visibleCount = 0;
        
        lineElements.forEach(lineElement => {
            const lineText = window.AnsiUtils.stripAnsiCodes(lineElement.textContent).toLowerCase();
            const isVisible = !this.isFilterActive || lineText.includes(filter);
            
            if (isVisible) {
                lineElement.classList.remove('filtered-hidden');
                visibleCount++;
            } else {
                lineElement.classList.add('filtered-hidden');
            }
        });
        
        // Update line count to show visible lines
        this.updateDisplayedLineCount(visibleCount);
    }
    
    /**
     * Perform search and highlight matches
     */
    performSearch(searchText) {
        const search = searchText.trim();
        
        if (search.length === 0) {
            this.clearSearch();
            return;
        }
        
        this.isSearchActive = true;
        // Disable auto-scroll when searching (one of only two reasons)
        this.autoScroll = false;
        this.updateAutoScrollButton();
        
        // Find all matching lines
        this.searchMatches = [];
        const lineElements = this.elements.outputLines.querySelectorAll('.output-line:not(.filtered-hidden)');
        
        lineElements.forEach((lineElement, index) => {
            const lineText = window.AnsiUtils.stripAnsiCodes(lineElement.textContent).toLowerCase();
            if (lineText.includes(search.toLowerCase())) {
                this.searchMatches.push({
                    element: lineElement,
                    index: index
                });
            }
        });
        
        // Highlight all matches
        this.highlightAllMatches(search);
        
        // Jump to first match
        if (this.searchMatches.length > 0) {
            this.currentSearchIndex = 0;
            this.scrollToSearchMatch(0);
        } else {
            this.currentSearchIndex = -1;
        }
        
        // Update search results text
        this.updateSearchResults();
    }
    
    /**
     * Highlight all search matches with neon yellow
     */
    highlightAllMatches(searchTerm) {
        const lineElements = this.elements.outputLines.querySelectorAll('.output-line');
        
        lineElements.forEach(lineElement => {
            const originalHtml = lineElement.dataset.originalHtml || lineElement.innerHTML;
            lineElement.dataset.originalHtml = originalHtml;
            
            if (this.isSearchActive) {
                const highlightedHtml = window.AnsiUtils.highlightSearchInHtml(originalHtml, searchTerm);
                lineElement.innerHTML = highlightedHtml;
            } else {
                lineElement.innerHTML = originalHtml;
            }
        });
    }
    
    /**
     * Clear search highlighting and re-enable auto-scroll
     */
    clearSearch() {
        this.isSearchActive = false;
        this.searchMatches = [];
        this.currentSearchIndex = -1;
        
        // Remove all highlighting
        const lineElements = this.elements.outputLines.querySelectorAll('.output-line');
        lineElements.forEach(lineElement => {
            if (lineElement.dataset.originalHtml) {
                lineElement.innerHTML = lineElement.dataset.originalHtml;
            }
            lineElement.classList.remove('search-current');
        });
        
        // Re-enable auto-scroll (search was disabled, now re-enable)
        this.autoScroll = true;
        this.updateAutoScrollButton();
        this.scrollToBottom();
        
        this.updateSearchResults();
    }
    
    /**
     * Navigate to next search match
     */
    searchNext() {
        if (this.searchMatches.length === 0) return;
        
        this.currentSearchIndex = (this.currentSearchIndex + 1) % this.searchMatches.length;
        this.scrollToSearchMatch(this.currentSearchIndex);
        this.updateSearchResults();
    }
    
    /**
     * Navigate to previous search match
     */
    searchPrevious() {
        if (this.searchMatches.length === 0) return;
        
        this.currentSearchIndex = this.currentSearchIndex <= 0 
            ? this.searchMatches.length - 1 
            : this.currentSearchIndex - 1;
        this.scrollToSearchMatch(this.currentSearchIndex);
        this.updateSearchResults();
    }
    
    /**
     * Scroll to specific search match
     */
    scrollToSearchMatch(index) {
        if (index < 0 || index >= this.searchMatches.length) return;
        
        // Remove current class from all lines
        this.elements.outputLines.querySelectorAll('.search-current').forEach(el => {
            el.classList.remove('search-current');
        });
        
        // Add current class to selected match
        const match = this.searchMatches[index];
        match.element.classList.add('search-current');
        
        // Scroll to the element
        match.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    /**
     * Update search results text
     */
    updateSearchResults() {
        if (this.searchMatches.length === 0) {
            this.elements.searchResultsText.textContent = this.isSearchActive ? 'No matches' : '';
        } else {
            this.elements.searchResultsText.textContent = 
                `${this.currentSearchIndex + 1} of ${this.searchMatches.length} matches`;
        }
    }
    
    /**
     * Update displayed line count
     */
    updateDisplayedLineCount(count) {
        this.elements.lineCount.textContent = count.toLocaleString();
    }
    
    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        this.elements.loadingOverlay.classList.remove('hidden');
        const loadingText = this.elements.loadingOverlay.querySelector('p');
        if (loadingText) {
            loadingText.textContent = message;
        }
    }
    
    /**
     * Hide loading overlay
     */
    hideLoading() {
        this.elements.loadingOverlay.classList.add('hidden');
    }
    
    /**
     * Show error modal with optional stack trace
     */
    showError(message, error = null) {
        let errorText = message;
        
        // Add stack trace for internal app
        if (error && error.stack) {
            errorText += '\n\nStack Trace:\n' + error.stack;
        }
        
        this.elements.errorMessage.style.whiteSpace = 'pre-wrap';
        this.elements.errorMessage.textContent = errorText;
        this.elements.errorModal.classList.remove('hidden');
    }
    
    /**
     * Hide error modal
     */
    hideErrorModal() {
        this.elements.errorModal.classList.add('hidden');
    }
    
    /**
     * Update polling indicator
     */
    updatePollingIndicator(status) {
        const indicator = this.elements.pollingStatus;
        
        indicator.className = 'polling-dot';
        
        if (status === 'connected') {
            // Green, pulsing
            indicator.style.background = 'var(--status-running)';
        } else {
            // Red, static
            indicator.classList.add('error');
            indicator.style.background = 'var(--status-dead)';
        }
    }
    
    /**
     * Update header status
     */
    updateStatus(data) {
        // Update overmind status
        if (data.overmind_status) {
            this.overmindStatus = data.overmind_status;
            this.elements.overmindStatus.textContent = data.overmind_status.charAt(0).toUpperCase() + 
                                                      data.overmind_status.slice(1);
            this.elements.overmindStatus.className = `status-value ${data.overmind_status}`;
        }
        
        // Update process count
        if (data.stats && data.stats.total !== undefined) {
            this.elements.processCount.textContent = data.stats.total;
        }
        
        // Update version
        if (data.version !== undefined) {
            this.elements.versionNumber.textContent = data.version;
        }
    }
    
    /**
     * Update processes list
     */
    updateProcesses(processes) {
        this.processes = processes;
        
        // Clear existing process list
        this.elements.processList.innerHTML = '';
        
        // Add each process
        Object.values(processes).forEach(process => {
            this.addProcessToList(process);
            
            // Update selected processes set
            if (process.selected) {
                this.selectedProcesses.add(process.name);
            } else {
                this.selectedProcesses.delete(process.name);
            }
        });
        
        // Update line visibility based on selected processes
        this.updateLineVisibility();
    }
    
    /**
     * Add a process to the processes list
     */
    addProcessToList(process) {
        const processItem = document.createElement('div');
        processItem.className = `process-item ${process.selected ? 'selected' : ''}`;
        processItem.dataset.process = process.name;
        
        processItem.innerHTML = `
            <div class="process-info">
                <span class="process-name">${process.name}</span>
                <span class="process-status ${process.status}">${process.status}</span>
            </div>
            <div class="process-actions">
                <button class="btn btn-success btn-start" title="Restart">▶</button>
                <button class="btn btn-danger btn-stop" title="Stop">⏹</button>
            </div>
        `;
        
        // Add event listeners
        processItem.addEventListener('click', (e) => {
            // Don't toggle if clicking on action buttons
            if (e.target.classList.contains('btn')) {
                return;
            }
            this.toggleProcessSelection(process.name);
        });
        
        // Action button listeners
        const startBtn = processItem.querySelector('.btn-start');
        const stopBtn = processItem.querySelector('.btn-stop');
        
        startBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.restartProcess(process.name);
        });
        
        stopBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.stopProcess(process.name);
        });
        
        this.elements.processList.appendChild(processItem);
    }
    
    /**
     * Update process status in the list
     */
    updateProcessStatus(processName, status) {
        const processItem = this.elements.processList.querySelector(`[data-process="${processName}"]`);
        if (processItem) {
            const statusElement = processItem.querySelector('.process-status');
            statusElement.textContent = status;
            statusElement.className = `process-status ${status}`;
        }
        
        // Update in our processes data
        if (this.processes[processName]) {
            this.processes[processName].status = status;
        }
    }
    
    /**
     * Add a single output line with efficient buffer management
     */
    addOutputLine(line) {
        // Add to local buffer
        this.currentLines.push(line);
        this.lineIdMap.set(line.id, line);
        
        // Create DOM element
        const lineElement = this.createLineElement(line);
        
        // Check if we need to remove old lines (buffer limit)
        let removedElement = null;
        if (this.currentLines.length > this.maxLines) {
            const removedLine = this.currentLines.shift(); // Remove from start
            this.lineIdMap.delete(removedLine.id);
            
            // Remove corresponding DOM element
            const oldElement = this.elements.outputLines.querySelector(`[data-line-id="${removedLine.id}"]`);
            if (oldElement) {
                removedElement = oldElement;
                oldElement.remove();
            }
        }
        
        // Add new element to bottom
        this.elements.outputLines.appendChild(lineElement);
        
        // Auto-scroll if enabled - ALWAYS scroll to bottom when autoscroll is on
        if (this.autoScroll) {
            this.scrollToBottom();
        }
        
        // Update displayed line count
        this.updateDisplayedLineCount(this.getVisibleLineCount());
        
        // Update search matches if search is active (but don't re-run full search, just check this line)
        if (this.isSearchActive) {
            const searchTerm = this.elements.searchInput.value.trim();
            if (searchTerm) {
                const lineText = window.AnsiUtils.stripAnsiCodes(lineElement.textContent).toLowerCase();
                if (lineText.includes(searchTerm.toLowerCase())) {
                    this.searchMatches.push({
                        element: lineElement,
                        lineId: line.id
                    });
                }
            }
        }
    }
    
    /**
     * Create a DOM element for a line
     */
    createLineElement(line) {
        const lineElement = document.createElement('div');
        lineElement.className = `output-line process-${line.process}`;
        lineElement.dataset.lineId = line.id;
        lineElement.dataset.process = line.process;
        
        // Convert ANSI codes to HTML and store original
        const htmlContent = window.AnsiUtils.ansiToHtml(line.text);
        lineElement.innerHTML = htmlContent;
        lineElement.dataset.originalHtml = htmlContent;
        
        // Apply current search highlighting if active
        if (this.isSearchActive && this.elements.searchInput.value.trim()) {
            const searchTerm = this.elements.searchInput.value.trim();
            const highlightedHtml = window.AnsiUtils.highlightSearchInHtml(htmlContent, searchTerm);
            lineElement.innerHTML = highlightedHtml;
        }
        
        // Apply visibility based on current filter settings
        if (!this.selectedProcesses.has(line.process)) {
            lineElement.classList.add('process-hidden');
        }
        
        // Apply active filter to new line
        if (this.isFilterActive) {
            const filterValue = this.elements.filterInput.value.trim().toLowerCase();
            if (filterValue && !line.text.toLowerCase().includes(filterValue)) {
                lineElement.classList.add('filtered-hidden');
            }
        }
        
        return lineElement;
    }
    
    /**
     * Add multiple output lines efficiently
     */
    addOutputLines(lines) {
        lines.forEach(line => this.addOutputLine(line));
    }
    
    /**
     * Get count of visible lines (not hidden by filter or process selection)
     */
    getVisibleLineCount() {
        return this.elements.outputLines.querySelectorAll('.output-line:not(.filtered-hidden):not(.process-hidden)').length;
    }
    
    /**
     * Update line visibility based on selected processes
     */
    updateLineVisibility() {
        const lineElements = this.elements.outputLines.querySelectorAll('.output-line');
        
        lineElements.forEach(lineElement => {
            const process = lineElement.dataset.process;
            
            if (this.selectedProcesses.has(process)) {
                lineElement.classList.remove('process-hidden');
            } else {
                lineElement.classList.add('process-hidden');
            }
        });
        
        // Update displayed line count
        this.updateDisplayedLineCount(this.getVisibleLineCount());
    }
    
    /**
     * Toggle process selection
     */
    async toggleProcessSelection(processName) {
        try {
            if (window.pollingManager) {
                const result = await window.pollingManager.toggleProcessSelection(processName);
                
                if (result.success) {
                    // Update UI immediately
                    const processItem = this.elements.processList.querySelector(`[data-process="${processName}"]`);
                    if (processItem) {
                        if (result.selected) {
                            processItem.classList.add('selected');
                            this.selectedProcesses.add(processName);
                        } else {
                            processItem.classList.remove('selected');
                            this.selectedProcesses.delete(processName);
                        }
                    }
                    
                    // Update line visibility
                    this.updateLineVisibility();
                }
            }
        } catch (error) {
            console.error('Toggle process error:', error);
            this.showError('Failed to toggle process: ' + error.message, error);
        }
    }
    
    /**
     * Process control methods
     */
    async startProcess(processName) {
        try {
            if (window.pollingManager) {
                await window.pollingManager.startProcess(processName);
            }
        } catch (error) {
            console.error('Start process error:', error);
            this.showError(`Failed to start ${processName}: ${error.message}`, error);
        }
    }
    
    async restartProcess(processName) {
        try {
            if (window.pollingManager) {
                await window.pollingManager.restartProcess(processName);
            }
        } catch (error) {
            console.error('Restart process error:', error);
            this.showError(`Failed to restart ${processName}: ${error.message}`, error);
        }
    }
    
    async stopProcess(processName) {
        try {
            if (window.pollingManager) {
                await window.pollingManager.stopProcess(processName);
            }
        } catch (error) {
            console.error('Stop process error:', error);
            this.showError(`Failed to stop ${processName}: ${error.message}`, error);
        }
    }
    
    async selectAllProcesses() {
        try {
            if (window.pollingManager) {
                const result = await window.pollingManager.selectAllProcesses();
                if (result.processes) {
                    this.updateProcesses(result.processes);
                }
            }
        } catch (error) {
            console.error('Select all error:', error);
            this.showError('Failed to select all processes: ' + error.message, error);
        }
    }
    
    async deselectAllProcesses() {
        try {
            if (window.pollingManager) {
                const result = await window.pollingManager.deselectAllProcesses();
                if (result.processes) {
                    this.updateProcesses(result.processes);
                }
            }
        } catch (error) {
            console.error('Deselect all error:', error);
            this.showError('Failed to deselect all processes: ' + error.message, error);
        }
    }
    
    async clearOutput() {
        try {
            if (window.pollingManager) {
                await window.pollingManager.clearOutput();
                
                // Clear local buffer and UI immediately
                this.elements.outputLines.innerHTML = '';
                this.currentLines = [];
                this.lineIdMap.clear();
                this.updateDisplayedLineCount(0);
                this.clearSearch();
            }
        } catch (error) {
            console.error('Clear output error:', error);
            this.showError('Failed to clear output: ' + error.message, error);
        }
    }
    
    /**
     * Scroll to bottom of output
     */
    scrollToBottom() {
        // Set flag to prevent wheel event from firing during our programmatic scroll
        this.programmaticScroll = true;
        this.elements.outputLines.scrollTop = this.elements.outputLines.scrollHeight;
        // Clear flag after scroll completes
        setTimeout(() => {
            this.programmaticScroll = false;
        }, 10);
    }
    
    /**
     * Start monitoring scroll position to enforce autoscroll
     */
    startScrollMonitoring() {
        // Check every 100ms if autoscroll is on and we're not at bottom
        this.scrollCheckInterval = setInterval(() => {
            if (this.autoScroll) {
                const container = this.elements.outputLines;
                const isAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 10;
                
                if (!isAtBottom) {
                    // Force scroll to bottom when autoscroll is on
                    this.scrollToBottom();
                }
            }
        }, 100);
    }
    
    /**
     * Load initial state and populate UI
     */
    async loadInitialState(state) {
        // Update status
        this.updateStatus(state);
        
        
        // Update processes
        if (state.processes) {
            this.updateProcesses(state.processes);
        }
        
        // No initial lines from backend - they come via polling updates
        console.log('Initial state loaded, waiting for polling updates...');
    }
}

// Export for use in other modules
window.UIManager = UIManager;