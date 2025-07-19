// Search functionality for the output

class SearchManager {
    constructor() {
        this.searchText = '';
        this.searchResults = [];
        this.currentSearchIndex = -1;
        this.outputRef = null;
        this.isNavigating = false; // Flag to prevent auto-updates during navigation
    }

    setOutputRef(ref) {
        this.outputRef = ref;
    }

    // Update search results based on text and filtered output
    updateSearch(searchText, filteredOutput) {
        this.searchText = searchText;
        
        if (!searchText) {
            this.searchResults = [];
            this.currentSearchIndex = -1;
            this.isNavigating = false;
            return { results: [], currentIndex: -1 };
        }
        
        const results = [];
        const searchLower = searchText.toLowerCase();
        
        filteredOutput.forEach((line, index) => {
            // Search in clean text without ANSI codes
            const cleanLine = window.AnsiUtils.stripAnsiCodes(line);
            if (cleanLine.toLowerCase().includes(searchLower)) {
                results.push(index);
            }
        });
        
        // If we're not actively navigating and this is a new search or first search
        if (!this.isNavigating || this.searchResults.length === 0) {
            this.searchResults = results;
            this.currentSearchIndex = results.length > 0 ? 0 : -1;
        } else {
            // We're actively navigating, so try to maintain position more carefully
            const oldResultCount = this.searchResults.length;
            const newResultCount = results.length;
            
            if (newResultCount === 0) {
                this.searchResults = [];
                this.currentSearchIndex = -1;
            } else if (oldResultCount === 0) {
                // First time finding results
                this.searchResults = results;
                this.currentSearchIndex = 0;
            } else {
                // Try to maintain relative position
                const relativePosition = this.currentSearchIndex / oldResultCount;
                this.searchResults = results;
                this.currentSearchIndex = Math.min(
                    Math.floor(relativePosition * newResultCount),
                    newResultCount - 1
                );
                this.currentSearchIndex = Math.max(0, this.currentSearchIndex);
            }
        }
        
        // Auto-scroll to current result only if we have one and we're not navigating
        if (this.currentSearchIndex >= 0 && !this.isNavigating) {
            this.scrollToCurrentResult();
        }
        
        return { 
            results: this.searchResults, 
            currentIndex: this.currentSearchIndex 
        };
    }

    // Navigate to next search result
    nextSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.isNavigating = true;
        this.currentSearchIndex = (this.currentSearchIndex + 1) % this.searchResults.length;
        this.scrollToCurrentResult();
        
        // Reset navigating flag after a short delay
        setTimeout(() => {
            this.isNavigating = false;
        }, 100);
        
        return true;
    }

    // Navigate to previous search result
    prevSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.isNavigating = true;
        this.currentSearchIndex = this.currentSearchIndex <= 0 ? 
            this.searchResults.length - 1 : 
            this.currentSearchIndex - 1;
        this.scrollToCurrentResult();
        
        // Reset navigating flag after a short delay
        setTimeout(() => {
            this.isNavigating = false;
        }, 100);
        
        return true;
    }

    // Scroll to the current search result
    scrollToCurrentResult() {
        if (this.currentSearchIndex < 0 || !this.outputRef?.current || this.searchResults.length === 0) return;
        
        const lineElements = this.outputRef.current.children;
        const targetLineIndex = this.searchResults[this.currentSearchIndex];
        
        // Make sure the target index is valid
        if (targetLineIndex >= 0 && targetLineIndex < lineElements.length) {
            const lineElement = lineElements[targetLineIndex];
            if (lineElement) {
                // Smooth scroll to the element
                lineElement.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'center',
                    inline: 'nearest'
                });
            }
        }
    }

    // Get current search state
    getSearchState() {
        return {
            searchText: this.searchText,
            results: this.searchResults,
            currentIndex: this.currentSearchIndex,
            hasResults: this.searchResults.length > 0,
            resultCount: this.searchResults.length,
            isNavigating: this.isNavigating
        };
    }

    // Check if a line index should be highlighted
    isLineHighlighted(lineIndex) {
        return this.searchResults.includes(lineIndex) && 
               this.searchResults[this.currentSearchIndex] === lineIndex;
    }

    // Clear search state
    clearSearch() {
        this.searchText = '';
        this.searchResults = [];
        this.currentSearchIndex = -1;
        this.isNavigating = false;
    }
}

// Export for use in other files
window.SearchManager = SearchManager;
