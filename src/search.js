// Search functionality for the output

class SearchManager {
    constructor() {
        this.searchText = '';
        this.searchResults = [];
        this.currentSearchIndex = -1;
        this.outputRef = null;
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
            return { results: [], currentIndex: -1 };
        }
        
        const results = [];
        const searchLower = searchText.toLowerCase();
        
        filteredOutput.forEach((line, index) => {
            // Search directly in HTML content
            const htmlContent = line.html || line.htmlContent || line;
            if (htmlContent.toLowerCase().includes(searchLower)) {
                results.push(index);
            }
        });
        
        // Update results
        this.searchResults = results;
        
        // Set initial position for new search
        if (results.length > 0) {
            // If we don't have a current position or it's no longer valid, start at beginning
            if (this.currentSearchIndex < 0 || this.currentSearchIndex >= results.length) {
                this.currentSearchIndex = 0;
            }
            // Immediately scroll to the first result
            this.scrollToCurrentResult();
        } else {
            this.currentSearchIndex = -1;
        }
        
        return { 
            results: this.searchResults, 
            currentIndex: this.currentSearchIndex 
        };
    }

    // Navigate to next search result
    nextSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.currentSearchIndex = (this.currentSearchIndex + 1) % this.searchResults.length;
        this.scrollToCurrentResult();
        return true;
    }

    // Navigate to previous search result
    prevSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.currentSearchIndex = this.currentSearchIndex <= 0 ? 
            this.searchResults.length - 1 : 
            this.currentSearchIndex - 1;
        this.scrollToCurrentResult();
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
            resultCount: this.searchResults.length
        };
    }

    // Check if a line index should be highlighted
    isLineHighlighted(lineIndex) {
        return this.searchResults.includes(lineIndex) && 
               this.searchResults[this.currentSearchIndex] === lineIndex;
    }

    // Check if a line contains search results (for general highlighting)
    hasSearchMatch(lineIndex) {
        return this.searchResults.includes(lineIndex);
    }

    // Clear search state
    clearSearch() {
        this.searchText = '';
        this.searchResults = [];
        this.currentSearchIndex = -1;
    }

}

// Export for use in other files
window.SearchManager = SearchManager;
