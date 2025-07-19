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
            // Search in clean text without ANSI codes
            const cleanLine = window.AnsiUtils.stripAnsiCodes(line);
            if (cleanLine.toLowerCase().includes(searchLower)) {
                results.push(index);
            }
        });
        
        this.searchResults = results;
        this.currentSearchIndex = results.length > 0 ? 0 : -1;
        
        // Scroll to first result if found
        if (this.currentSearchIndex >= 0) {
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
        if (this.currentSearchIndex < 0 || !this.outputRef?.current) return;
        
        const lineElements = this.outputRef.current.children;
        const targetLineIndex = this.searchResults[this.currentSearchIndex];
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
}

// Export for use in other files
window.SearchManager = SearchManager;
