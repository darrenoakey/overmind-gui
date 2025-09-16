/**
 * Data Processing Web Worker
 * Layer 1: Handles all computationally intensive tasks off the main thread
 * - Data formatting and processing
 * - Batching and queuing
 * Note: ANSI processing now happens on the backend
 */

// Simple data processor that works with pre-processed backend data
class DataProcessor {
    constructor() {
        // No ANSI processing needed - backend handles this
    }
    
    processLine(backendData) {
        // Backend provides only HTML - we use this for everything including search
        return {
            id: backendData.id,
            htmlContent: backendData.html, // Only HTML representation
            processName: backendData.process,
            // Add computed properties for virtualization
            estimatedHeight: Math.ceil((backendData.html || '').length / 80) * 20 + 4
        };
    }
}

// Initialize processor
const dataProcessor = new DataProcessor();

// Message handling
self.onmessage = function(e) {
    const { type, data } = e.data;
    
    switch (type) {
        case 'PROCESS_BATCH':
            // Process a batch of pre-processed lines from backend
            const processedLines = data.lines.map(line => 
                dataProcessor.processLine(line)
            );
            
            // Send back processed batch
            self.postMessage({
                type: 'BATCH_PROCESSED',
                data: {
                    processedLines: processedLines,
                    statusUpdates: data.statusUpdates || {},
                    batchId: data.batchId
                }
            });
            break;
            
        case 'PROCESS_SINGLE':
            // Process a single pre-processed line from backend
            const processedLine = dataProcessor.processLine(data);
            
            self.postMessage({
                type: 'LINE_PROCESSED',
                data: processedLine
            });
            break;
            
        case 'CLEAR_CACHE':
            // No cache to clear - backend handles ANSI processing
            self.postMessage({
                type: 'CACHE_CLEARED'
            });
            break;
            
        default:
            console.warn('Unknown worker message type:', type);
    }
};

// Send ready signal
self.postMessage({
    type: 'WORKER_READY'
});