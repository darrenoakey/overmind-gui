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
     * Create a debounce function with its own timer
     */
    debounce(func, wait) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), wait);
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
            shutdownBtn: document.getElementById('shutdown-btn'),
            
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
        this.elements.shutdownBtn.addEventListener('click', () => this.shutdownOvermind());
        
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
        
        // PROPER EVENT-DRIVEN AUTO-SCROLL: Listen for actual scroll events
        this.elements.outputLines.addEventListener('scroll', (e) => {
            // Only react to user-initiated scrolling (not our programmatic scrolls)
            if (this.programmaticScroll) {
                return; // Ignore programmatic scrolls
            }
            
            // Check if user scrolled away from the bottom
            const container = this.elements.outputLines;
            const isAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 10;
            
            if (this.autoScroll && !isAtBottom) {
                // User scrolled up - disable auto-scroll
                this.autoScroll = false;
                this.updateAutoScrollButton();
                console.log('Auto-scroll disabled by user scrolling up');
            } else if (!this.autoScroll && isAtBottom) {
                // User scrolled back to bottom - enable auto-scroll
                this.autoScroll = true;
                this.updateAutoScrollButton();
                console.log('Auto-scroll enabled by user scrolling to bottom');
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
     * Shutdown Overmind and close server
     */
    async shutdownOvermind() {
        try {
            // Disable the button and show loading state
            this.elements.shutdownBtn.disabled = true;
            this.elements.shutdownBtn.innerHTML = '<span class="spinner"></span> Shutting down...';
            
            console.log('Initiating shutdown...');
            
            // Call the shutdown API
            const response = await fetch('/api/shutdown', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                console.log('Shutdown successful:', result.message);
                
                // Show success message briefly
                this.elements.shutdownBtn.innerHTML = '✓ Shutdown Complete';
                
                // Update UI to show shutdown state
                this.showLoading('System shutting down...');
                
                // The server will close the connection, so we don't need to do anything else
                setTimeout(() => {
                    this.hideLoading();
                }, 2000);
                
            } else {
                throw new Error(result.error || `Server returned ${response.status}`);
            }
            
        } catch (error) {
            console.error('Shutdown failed:', error);
            
            // Reset button and show error
            this.elements.shutdownBtn.disabled = false;
            this.elements.shutdownBtn.innerHTML = '⚠ Shutdown';
            
            this.showError(`Failed to shutdown: ${error.message}`, error);
            
            // Reset button text after a delay
            setTimeout(() => {
                this.elements.shutdownBtn.innerHTML = '⚠ Shutdown';
            }, 3000);
        }
    }
    
    /**
     * Apply filter to lines (optimized with batched DOM operations)
     */
    applyFilter(filterText) {
        const filter = filterText.trim().toLowerCase();
        this.isFilterActive = filter.length > 0;
        
        const lines = this.elements.outputLines.children;
        let visibleCount = 0;
        
        // Batch process all lines
        for (let i = 0; i < lines.length; i++) {
            const lineElement = lines[i];
            const lineText = lineElement.dataset.cleanText?.toLowerCase() || lineElement.textContent.toLowerCase();
            const shouldBeVisible = !this.isFilterActive || lineText.includes(filter);
            
            // Only modify DOM if class needs to change
            const isCurrentlyHidden = lineElement.classList.contains('filtered-hidden');
            
            if (shouldBeVisible && isCurrentlyHidden) {
                lineElement.classList.remove('filtered-hidden');
            } else if (!shouldBeVisible && !isCurrentlyHidden) {
                lineElement.classList.add('filtered-hidden');
            }
            
            // Count visible lines (not hidden by filter AND not hidden by process selection)
            if (shouldBeVisible && !lineElement.classList.contains('process-hidden')) {
                visibleCount++;
            }
        }
        
        // Update line count once at the end
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
            const lineText = lineElement.dataset.cleanText?.toLowerCase() || lineElement.textContent.toLowerCase();
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
     * Highlight all search matches with neon yellow (optimized)
     */
    highlightAllMatches(searchTerm) {
        const lines = this.elements.outputLines.children;
        
        // Batch process all lines
        for (let i = 0; i < lines.length; i++) {
            const lineElement = lines[i];
            const originalHtml = lineElement.dataset.originalHtml || lineElement.innerHTML;
            lineElement.dataset.originalHtml = originalHtml;
            
            if (this.isSearchActive) {
                // Use simple text-based highlighting since we don't need ANSI preservation for search
                const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi');
                const highlightedHtml = originalHtml.replace(regex, '<mark class="search-highlight">$1</mark>');
                // Only update innerHTML if it's actually different
                if (lineElement.innerHTML !== highlightedHtml) {
                    lineElement.innerHTML = highlightedHtml;
                }
            } else {
                // Only update innerHTML if it's actually different
                if (lineElement.innerHTML !== originalHtml) {
                    lineElement.innerHTML = originalHtml;
                }
            }
        }
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
     * Batch update multiple process statuses - optimized for performance
     */
    updateProcessStatuses(statusUpdates) {
        // Batch DOM queries and updates for better performance
        const processItems = this.elements.processList.querySelectorAll('[data-process]');
        const processItemMap = new Map();
        
        // Build a map of process names to DOM elements
        processItems.forEach(item => {
            const processName = item.dataset.process;
            if (processName && statusUpdates.hasOwnProperty(processName)) {
                processItemMap.set(processName, item);
            }
        });
        
        // Update all statuses at once
        Object.entries(statusUpdates).forEach(([processName, status]) => {
            // Update DOM
            const processItem = processItemMap.get(processName);
            if (processItem) {
                const statusElement = processItem.querySelector('.process-status');
                if (statusElement) {
                    statusElement.textContent = status;
                    statusElement.className = `process-status ${status}`;
                }
            }
            
            // Update in our processes data
            if (this.processes[processName]) {
                this.processes[processName].status = status;
            }
        });
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
        
        // Update displayed line count (do this for every line to keep count accurate)
        this.updateDisplayedLineCount(this.getVisibleLineCount());
        
        // Update search matches if search is active (but don't re-run full search, just check this line)
        if (this.isSearchActive) {
            const searchTerm = this.elements.searchInput.value.trim();
            if (searchTerm) {
                const lineText = lineElement.dataset.cleanText?.toLowerCase() || lineElement.textContent.toLowerCase();
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
        
        // OLD METHOD - should not be called with new protocol
        console.warn('addOutputLine called - should use addPreRenderedLines instead');
        
        // Fallback: treat as plain text since we don't have pre-rendered HTML
        lineElement.textContent = line.text;
        
        // Add search highlighting if needed (basic text highlighting)
        if (this.isSearchActive && this.elements.searchInput.value.trim()) {
            const searchTerm = this.elements.searchInput.value.trim();
            if (line.text.toLowerCase().includes(searchTerm.toLowerCase())) {
                const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi');
                lineElement.innerHTML = line.text.replace(regex, '<mark class="search-highlight">$1</mark>');
            }
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
     * Add multiple output lines efficiently with batched DOM operations
     */
    addOutputLines(lines) {
        if (lines.length === 0) return;
        
        if (lines.length === 1) {
            // Single line - use existing method
            this.addOutputLine(lines[0]);
            return;
        }
        
        // Batch processing for multiple lines
        const fragment = document.createDocumentFragment();
        const elementsToRemove = [];
        
        // Process all lines and build fragment
        for (const line of lines) {
            // Add to local buffer
            this.currentLines.push(line);
            this.lineIdMap.set(line.id, line);
            
            // Create DOM element
            const lineElement = this.createLineElement(line);
            fragment.appendChild(lineElement);
            
            // Track elements to remove if over limit
            if (this.currentLines.length > this.maxLines) {
                const removedLine = this.currentLines.shift();
                this.lineIdMap.delete(removedLine.id);
                
                // Find DOM element to remove
                const oldElement = this.elements.outputLines.querySelector(`[data-line-id="${removedLine.id}"]`);
                if (oldElement) {
                    elementsToRemove.push(oldElement);
                }
            }
        }
        
        // Batch DOM operations
        // 1. Remove old elements first
        elementsToRemove.forEach(el => el.remove());
        
        // 2. Add all new elements at once
        this.elements.outputLines.appendChild(fragment);
        
        // 3. Update counts once at the end
        this.updateDisplayedLineCount(this.getVisibleLineCount());
        
        // 4. Auto-scroll if enabled
        if (this.autoScroll) {
            this.scrollToBottom();
        }
        
        // 5. Update search matches if needed (batch process)
        if (this.isSearchActive) {
            this.updateSearchMatchesForNewLines(lines);
        }
    }
    
    /**
     * Add pre-rendered HTML lines - OPTIMIZED for backend-processed content
     */
    addPreRenderedLines(preRenderedLines, totalBackendLines) {
        if (preRenderedLines.length === 0) return;
        
        console.log(`Adding ${preRenderedLines.length} pre-rendered lines`);
        
        // 1. Create document fragment for batch DOM insertion
        const fragment = document.createDocumentFragment();
        
        // 2. Process each pre-rendered line
        preRenderedLines.forEach(lineData => {
            // lineData = {id, html, clean_text, process, timestamp}
            
            const lineElement = document.createElement('div');
            lineElement.className = 'output-line';
            lineElement.dataset.lineId = lineData.id;
            lineElement.dataset.process = lineData.process;
            lineElement.dataset.timestamp = lineData.timestamp;
            
            // Use pre-rendered HTML directly - NO FRONTEND ANSI PROCESSING!
            lineElement.innerHTML = lineData.html;
            
            // Store clean text for search/filter (only when needed)
            lineElement.dataset.cleanText = lineData.clean_text;
            
            // Add to our line tracking
            this.currentLines.push({
                id: lineData.id,
                element: lineElement,
                cleanText: lineData.clean_text,
                process: lineData.process
            });
            
            // Check if this line should be visible (filter/process selection)
            const shouldShow = this.shouldShowLine(lineData.process, lineData.clean_text);
            if (!shouldShow) {
                lineElement.classList.add('filtered-hidden');
            }
            
            fragment.appendChild(lineElement);
        });
        
        // 3. Manage line limit efficiently
        if (this.currentLines.length > this.maxLines) {
            const toRemove = this.currentLines.length - this.maxLines;
            console.log(`Removing ${toRemove} old lines to maintain ${this.maxLines} limit`);
            
            // Remove old elements from DOM
            for (let i = 0; i < toRemove; i++) {
                const oldLine = this.currentLines[i];
                if (oldLine.element && oldLine.element.parentNode) {
                    oldLine.element.parentNode.removeChild(oldLine.element);
                }
            }
            
            // Remove from our tracking
            this.currentLines.splice(0, toRemove);
        }
        
        // 4. Add all new lines to DOM at once
        this.elements.outputLines.appendChild(fragment);
        
        // 5. Auto-scroll if enabled
        if (this.autoScroll) {
            this.scrollToBottom();
        }
        
        // 6. Update search matches ONLY if search is active
        if (this.isSearchActive) {
            this.updateSearchMatchesForPreRenderedLines(preRenderedLines);
        }
        
        // 7. Update line count
        this.updateDisplayedLineCount(this.getVisibleLineCount());
    }
    
    /**
     * Check if a line should be shown based on current filters
     */
    shouldShowLine(processName, cleanText) {
        // Check process selection
        if (this.processes[processName] && !this.processes[processName].selected) {
            return false;
        }
        
        // Check text filter
        if (this.isFilterActive) {
            const filterText = this.elements.filterInput.value.trim().toLowerCase();
            if (filterText && !cleanText.toLowerCase().includes(filterText)) {
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Update search matches for pre-rendered lines - only when search is active
     */
    updateSearchMatchesForPreRenderedLines(preRenderedLines) {
        const searchTerm = this.elements.searchInput.value.trim().toLowerCase();
        if (!searchTerm) return;
        
        // Process new lines for search matches using pre-processed clean text
        preRenderedLines.forEach(lineData => {
            if (lineData.clean_text.toLowerCase().includes(searchTerm)) {
                const lineElement = this.elements.outputLines.querySelector(`[data-line-id="${lineData.id}"]`);
                if (lineElement && !lineElement.classList.contains('filtered-hidden')) {
                    this.searchMatches.push(lineElement);
                }
            }
        });
        
        this.updateSearchResults();
    }
    
    /**
     * Batch update search matches for new lines
     */
    updateSearchMatchesForNewLines(lines) {
        const searchTerm = this.elements.searchInput.value.trim().toLowerCase();
        if (!searchTerm) return;
        
        // Process all new lines for search matches
        lines.forEach(line => {
            const lineElement = this.elements.outputLines.querySelector(`[data-line-id="${line.id}"]`);
            if (lineElement) {
                const lineText = lineElement.dataset.cleanText?.toLowerCase() || lineElement.textContent.toLowerCase();
                if (lineText.includes(searchTerm)) {
                    this.searchMatches.push({
                        element: lineElement,
                        lineId: line.id
                    });
                }
            }
        });
    }
    
    /**
     * Get count of visible lines (optimized - cache when possible)
     */
    getVisibleLineCount() {
        // For performance, we could maintain counters instead of querying DOM
        // But for now, keep the query but make it more efficient
        const lines = this.elements.outputLines.children;
        let count = 0;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (!line.classList.contains('filtered-hidden') && 
                !line.classList.contains('process-hidden')) {
                count++;
            }
        }
        
        return count;
    }
    
    /**
     * Update line visibility based on selected processes (optimized)
     */
    updateLineVisibility() {
        const lines = this.elements.outputLines.children;
        
        // Batch DOM class changes
        for (let i = 0; i < lines.length; i++) {
            const lineElement = lines[i];
            const process = lineElement.dataset.process;
            
            if (this.selectedProcesses.has(process)) {
                if (lineElement.classList.contains('process-hidden')) {
                    lineElement.classList.remove('process-hidden');
                }
            } else {
                if (!lineElement.classList.contains('process-hidden')) {
                    lineElement.classList.add('process-hidden');
                }
            }
        }
        
        // Update displayed line count once at the end
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
        // Set flag to prevent scroll event from disabling auto-scroll during our programmatic scroll
        this.programmaticScroll = true;
        
        // Perform the scroll
        this.elements.outputLines.scrollTop = this.elements.outputLines.scrollHeight;
        
        // Clear flag after scroll event fires (use requestAnimationFrame for better timing)
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.programmaticScroll = false;
            });
        });
    }
    
    /**
     * Initialize scroll event handling (event-driven, not polling)
     */
    startScrollMonitoring() {
        // PERFORMANCE FIX: No more polling! Auto-scroll is now purely event-driven:
        // 1. User scrolls → 'scroll' event → disable auto-scroll if scrolled up
        // 2. New content arrives → addOutputLines() → scroll to bottom if auto-scroll enabled
        // 3. User clicks scroll button → enable auto-scroll + scroll to bottom
        
        // Clear any old interval (legacy cleanup)
        if (this.scrollCheckInterval) {
            clearInterval(this.scrollCheckInterval);
            this.scrollCheckInterval = null;
        }
        
        console.log('Auto-scroll is now purely event-driven - no polling!');
    }
    
    /**
     * Cleanup resources and intervals
     */
    cleanup() {
        if (this.scrollCheckInterval) {
            clearInterval(this.scrollCheckInterval);
            this.scrollCheckInterval = null;
        }
        
        if (this.searchDebounceTimer) {
            clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = null;
        }
        
        if (this.filterDebounceTimer) {
            clearTimeout(this.filterDebounceTimer);
            this.filterDebounceTimer = null;
        }
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