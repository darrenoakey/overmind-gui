"""
Update Queue - Simple message queue system for polling
Backend only queues unsent messages, frontend manages display and limits
"""

import time
import unittest
from collections import deque
from threading import Lock
from typing import Dict, List, Optional, Any, Tuple


class UpdateItem:
    """A single update item (either output line or status change)"""
    
    def __init__(self, update_type: str, data: Any, timestamp: float = None):
        self.type = update_type  # 'output' or 'status'
        self.data = data
        self.timestamp = timestamp or time.time()
        self.id = f"{self.timestamp}_{id(self)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'type': self.type,
            'data': self.data,
            'timestamp': self.timestamp
        }


class UpdateQueue:
    """Simple message queue system for polling clients"""
    
    def __init__(self, max_queue_size: int = 10000):
        self.updates: deque = deque(maxlen=max_queue_size)
        self.lock = Lock()
        self.last_poll_cleanup = time.time()
        self.max_age_seconds = 300  # Keep updates for 5 minutes max
        self.line_counter = 0
        
        # Current process statuses for tracking changes
        self.process_statuses: Dict[str, str] = {}
    
    def add_output_line(self, line_text: str, process_name: str):
        """Add a new output line update - just queue it"""
        with self.lock:
            self.line_counter += 1
            
            # Create line data
            line_dict = {
                'id': self.line_counter,
                'text': line_text,
                'process': process_name,
                'timestamp': time.time()
            }
            
            # Add to update queue
            update = UpdateItem('output', line_dict)
            self.updates.append(update)
    
    def add_status_update(self, process_name: str, status: str):
        """Add a process status update"""
        old_status = self.process_statuses.get(process_name)
        
        if old_status != status:
            self.process_statuses[process_name] = status
            
            update = UpdateItem('status', {
                'process': process_name,
                'status': status,
                'old_status': old_status
            })
            
            with self.lock:
                self.updates.append(update)
    
    def add_bulk_status_updates(self, status_updates: Dict[str, str]):
        """Add multiple status updates at once"""
        changed = {}
        
        for process_name, status in status_updates.items():
            old_status = self.process_statuses.get(process_name)
            if old_status != status:
                self.process_statuses[process_name] = status
                changed[process_name] = {
                    'status': status,
                    'old_status': old_status
                }
        
        if changed:
            update = UpdateItem('status_bulk', {
                'updates': changed
            })
            
            with self.lock:
                self.updates.append(update)
    
    def poll_updates(self, since_timestamp: float = None) -> Tuple[List[Dict[str, Any]], float]:
        """
        Poll for updates since timestamp
        Returns (updates, current_timestamp)
        """
        current_time = time.time()
        
        # Cleanup old updates periodically
        if current_time - self.last_poll_cleanup > 60:
            self._cleanup_old_updates(current_time)
            self.last_poll_cleanup = current_time
        
        with self.lock:
            if since_timestamp is None:
                # First poll - return recent updates (last 100)
                relevant_updates = list(self.updates)[-100:]
            else:
                # Return updates since timestamp
                relevant_updates = [
                    update for update in self.updates 
                    if update.timestamp > since_timestamp
                ]
        
        return [update.to_dict() for update in relevant_updates], current_time
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get basic current state (no lines, just metadata)"""
        return {
            'process_statuses': self.process_statuses.copy(),
            'timestamp': time.time(),
            'total_lines_sent': self.line_counter
        }
    
    def _cleanup_old_updates(self, current_time: float):
        """Remove updates older than max_age_seconds"""
        cutoff_time = current_time - self.max_age_seconds
        
        # Convert deque to list, filter, convert back
        updates_list = list(self.updates)
        filtered_updates = [u for u in updates_list if u.timestamp > cutoff_time]
        
        self.updates.clear()
        self.updates.extend(filtered_updates)
    
    def add_server_started(self, version: int):
        """Add a server started message"""
        update = UpdateItem('server_started', {
            'version': version,
            'message': f"🚀 Overmind GUI v{version} started"
        })
        
        with self.lock:
            self.updates.append(update)
    
    def clear_all(self):
        """Clear all updates"""
        with self.lock:
            self.updates.clear()
            # Don't reset line counter - frontend needs unique IDs


# Global instance
update_queue = UpdateQueue()


class TestUpdateItem(unittest.TestCase):
    """Test cases for UpdateItem"""
    
    def test_initialization(self):
        """Test UpdateItem initialization"""
        data = {'test': 'value'}
        item = UpdateItem('output', data)
        
        self.assertEqual(item.type, 'output')
        self.assertEqual(item.data, data)
        self.assertIsInstance(item.timestamp, float)
        self.assertIsInstance(item.id, str)
    
    def test_to_dict(self):
        """Test UpdateItem to_dict conversion"""
        data = {'process': 'web', 'line': 'test output'}
        item = UpdateItem('output', data)
        
        result = item.to_dict()
        
        expected_keys = {'id', 'type', 'data', 'timestamp'}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result['type'], 'output')
        self.assertEqual(result['data'], data)


class TestUpdateQueue(unittest.TestCase):
    """Test cases for UpdateQueue"""
    
    def test_initialization(self):
        """Test UpdateQueue initialization"""
        queue = UpdateQueue()
        
        self.assertEqual(len(queue.updates), 0)
        self.assertEqual(len(queue.process_statuses), 0)
        self.assertEqual(queue.line_counter, 0)
    
    def test_add_output_line(self):
        """Test adding output line"""
        queue = UpdateQueue()
        
        queue.add_output_line("test output", "web")
        
        self.assertEqual(len(queue.updates), 1)
        self.assertEqual(queue.updates[0].type, 'output')
        self.assertEqual(queue.line_counter, 1)
    
    def test_add_status_update(self):
        """Test adding status update"""
        queue = UpdateQueue()
        
        queue.add_status_update("web", "running")
        
        self.assertEqual(len(queue.updates), 1)
        self.assertEqual(queue.updates[0].type, 'status')
        self.assertEqual(queue.process_statuses["web"], "running")
    
    def test_no_duplicate_status_updates(self):
        """Test that duplicate status updates are ignored"""
        queue = UpdateQueue()
        
        queue.add_status_update("web", "running")
        queue.add_status_update("web", "running")  # Same status
        
        self.assertEqual(len(queue.updates), 1)  # Only one update
    
    def test_bulk_status_updates(self):
        """Test bulk status updates"""
        queue = UpdateQueue()
        
        updates = {"web": "running", "worker": "stopped"}
        queue.add_bulk_status_updates(updates)
        
        self.assertEqual(len(queue.updates), 1)
        self.assertEqual(queue.updates[0].type, 'status_bulk')
        self.assertEqual(queue.process_statuses["web"], "running")
        self.assertEqual(queue.process_statuses["worker"], "stopped")
    
    def test_poll_updates(self):
        """Test polling updates"""
        queue = UpdateQueue()
        
        # Add some updates
        queue.add_output_line("line 1", "web")
        queue.add_status_update("web", "running")
        
        # Poll updates
        updates, timestamp = queue.poll_updates()
        
        self.assertEqual(len(updates), 2)
        self.assertIsInstance(timestamp, float)
        
        # Poll again with timestamp - should get no new updates
        updates2, timestamp2 = queue.poll_updates(timestamp)
        
        self.assertEqual(len(updates2), 0)
        self.assertGreaterEqual(timestamp2, timestamp)
    
    def test_get_current_state(self):
        """Test getting current state"""
        queue = UpdateQueue()
        
        queue.add_output_line("test line", "web")
        queue.add_status_update("web", "running")
        
        state = queue.get_current_state()
        
        expected_keys = {'process_statuses', 'timestamp', 'total_lines_sent'}
        self.assertEqual(set(state.keys()), expected_keys)
        self.assertEqual(state['process_statuses']['web'], 'running')
        self.assertEqual(state['total_lines_sent'], 1)
    
    def test_clear_all(self):
        """Test clearing all data"""
        queue = UpdateQueue()
        
        queue.add_output_line("test", "web")
        queue.add_status_update("web", "running")
        
        queue.clear_all()
        
        self.assertEqual(len(queue.updates), 0)
        # line_counter should not be reset
