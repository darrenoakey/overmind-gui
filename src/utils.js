// Utility functions for frontend text processing
// Note: ANSI processing now happens on the backend

// Highlight search terms in pre-rendered HTML from backend
const highlightSearchInHtml = (html, searchTerm) => {
    if (!searchTerm) return html;
    
    // Create a regex for the search term (case insensitive)
    const searchRegex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    
    // We need to be careful not to highlight inside HTML tags
    // Split by HTML tags to process only text content
    const parts = html.split(/(<[^>]*>)/);
    
    return parts.map(part => {
        // If this part is an HTML tag, leave it unchanged
        if (part.startsWith('<') && part.endsWith('>')) {
            return part;
        }
        // Otherwise, highlight search terms in the text content
        return part.replace(searchRegex, '<mark class="search-highlight">$1</mark>');
    }).join('');
};

// Strip ANSI codes for legacy compatibility
const stripAnsiCodes = (text) => {
    return text.replace(/[\x1b\u001b]\[[0-9;]*m/g, '');
};

// Export minimal utilities for frontend use
window.AnsiUtils = {
    highlightSearchInHtml,
    stripAnsiCodes  // Kept for backward compatibility
};