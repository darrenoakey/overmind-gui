"""
Update Queue - Message-based queue system with incremental IDs for polling
Backend keeps last 10,000 messages with incremental message IDs starting at 1
Clients poll with last received message ID to get newer messages
"""

import time
import unittest
from collections import deque
from threading import Lock
from typing import Dict, List, Optional, Any, Tuple

from ansi_processor import ansi_processor


class UpdateItem:
    """A single update item (either output line or status change) with message ID"""
    
    def __init__(self, update_type: str, data: Any, message_id: int, timestamp: float = None):
        self.type = update_type  # 'output', 'status', 'status_bulk', etc.
        self.data = data
        self.message_id = message_id  # Incremental integer starting at 1
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'message_id': self.message_id,
            'type': self.type,
            'data': self.data,
            'timestamp': self.timestamp
        }


class UpdateQueue:
    """Message-based queue system for polling clients with incremental IDs"""
    
    def __init__(self, max_messages: int = 10000):
        self.updates: deque = deque(maxlen=max_messages)
        self.lock = Lock()
        self.last_poll_cleanup = time.time()
        self.max_age_seconds = 600  # Keep updates for 10 minutes max (fallback)
        self.line_counter = 0
        self.message_counter = 0  # Incremental message ID starting at 1
        
        # Current process statuses for tracking changes
        self.process_statuses: Dict[str, str] = {}
    
    def _get_next_message_id(self) -> int:
        """Get the next message ID (thread-safe)"""
        self.message_counter += 1
        return self.message_counter
    
    def add_output_line(self, line_text: str, process_name: str):
        """Add a new output line update - pre-process with ANSI conversion"""
        with self.lock:
            self.line_counter += 1
            message_id = self._get_next_message_id()
            
            # Process line through ANSI processor for pre-rendered HTML
            processed_line = ansi_processor.process_line(
                line_text, 
                self.line_counter, 
                process_name, 
                time.time()
            )
            
            # Create update with pre-processed data and message ID
            update = UpdateItem('output', processed_line, message_id)
            self.updates.append(update)
    
    def add_status_update(self, process_name: str, status: str):
        """Add a process status update"""
        old_status = self.process_statuses.get(process_name)
        
        if old_status != status:
            self.process_statuses[process_name] = status
            
            with self.lock:
                message_id = self._get_next_message_id()
                update = UpdateItem('status', {
                    'process': process_name,
                    'status': status,
                    'old_status': old_status
                }, message_id)
                
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
            with self.lock:
                message_id = self._get_next_message_id()
                update = UpdateItem('status_bulk', {
                    'updates': changed
                }, message_id)
                
                self.updates.append(update)
    
    def poll_updates(self, last_message_id: int = 0) -> Tuple[Dict[str, Any], int]:
        """
        Poll for updates since last message ID - NEW MESSAGE-BASED FORMAT
        
        Args:
            last_message_id: Last message ID client received (0 for first poll)
        
        Returns:
            (response_package, latest_message_id)
        
        Response package format:
        {
            'output_lines': [{'id': int, 'html': str, 'clean_text': str, 'process': str, 'timestamp': float}],
            'status_updates': {'process_name': 'status', ...},
            'total_lines': int,  # Total lines in backend buffer
            'other_updates': [...]  # server_started, etc.
        }
        """
        current_time = time.time()
        
        # Cleanup old updates periodically (fallback to prevent memory issues)
        if current_time - self.last_poll_cleanup > 120:
            self._cleanup_old_updates(current_time)
            self.last_poll_cleanup = current_time
        
        with self.lock:
            if last_message_id == 0:
                # First poll - return recent updates (last 100 messages)
                relevant_updates = list(self.updates)[-100:]
            else:
                # Return updates with message_id > last_message_id
                relevant_updates = [
                    update for update in self.updates 
                    if update.message_id > last_message_id
                ]
            
            # Get the latest message ID from all updates
            latest_message_id = self.message_counter
        
        # Separate and consolidate updates by type
        output_lines = []
        latest_statuses = {}
        other_updates = []
        
        for update in relevant_updates:
            if update.type == 'output':
                output_lines.append(update.data)
            elif update.type == 'status':
                # Keep only the latest status for each process
                process = update.data['process']
                latest_statuses[process] = update.data['status']
            elif update.type == 'status_bulk':
                # Merge bulk status updates
                for process, status_info in update.data['updates'].items():
                    latest_statuses[process] = status_info['status']
            else:
                other_updates.append(update.to_dict())
        
        # Build optimized response package
        response_package = {
            'output_lines': output_lines,
            'status_updates': latest_statuses,
            'total_lines': self.line_counter,  # For frontend line limit management
            'other_updates': other_updates
        }
        
        return response_package, latest_message_id
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get basic current state (no lines, just metadata)"""
        return {
            'process_statuses': self.process_statuses.copy(),
            'timestamp': time.time(),
            'total_lines_sent': self.line_counter,
            'latest_message_id': self.message_counter
        }
    
    def _cleanup_old_updates(self, current_time: float):
        """Remove updates older than max_age_seconds (fallback protection)"""
        cutoff_time = current_time - self.max_age_seconds
        
        # Convert deque to list, filter, convert back
        updates_list = list(self.updates)
        filtered_updates = [u for u in updates_list if u.timestamp > cutoff_time]
        
        self.updates.clear()
        self.updates.extend(filtered_updates)
        
        print(f"Cleanup: Removed {len(updates_list) - len(filtered_updates)} old messages")
    
    def add_server_started(self, version: int):
        """Add a server started message"""
        with self.lock:
            message_id = self._get_next_message_id()
            update = UpdateItem('server_started', {
                'version': version,
                'message': f"🚀 Overmind GUI v{version} started"
            }, message_id)
            
            self.updates.append(update)
    
    def clear_all(self):
        """Clear all updates"""
        with self.lock:
            self.updates.clear()
            # Don't reset message counter - clients need unique IDs across clears
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self.lock:
            return {
                'total_messages': len(self.updates),
                'latest_message_id': self.message_counter,
                'total_lines': self.line_counter,
                'queue_capacity': self.updates.maxlen
            }


# Global instance
update_queue = UpdateQueue()


class TestUpdateItem(unittest.TestCase):
    """Test cases for UpdateItem"""
    
    def test_initialization(self):
        """Test UpdateItem initialization"""
        data = {'test': 'value'}
        item = UpdateItem('output', data, 1)
        
        self.assertEqual(item.type, 'output')
        self.assertEqual(item.data, data)
        self.assertEqual(item.message_id, 1)
        self.assertIsInstance(item.timestamp, float)
    
    def test_to_dict(self):
        """Test UpdateItem to_dict conversion"""
        data = {'process': 'web', 'line': 'test output'}
        item = UpdateItem('output', data, 5)
        
        result = item.to_dict()
        
        expected_keys = {'message_id', 'type', 'data', 'timestamp'}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result['type'], 'output')
        self.assertEqual(result['data'], data)
        self.assertEqual(result['message_id'], 5)


class TestUpdateQueue(unittest.TestCase):
    """Test cases for UpdateQueue"""
    
    def test_initialization(self):
        """Test UpdateQueue initialization"""
        queue = UpdateQueue()
        
        self.assertEqual(len(queue.updates), 0)
        self.assertEqual(len(queue.process_statuses), 0)
        self.assertEqual(queue.line_counter, 0)
        self.assertEqual(queue.message_counter, 0)
    
    def test_add_output_line(self):
        """Test adding output line with message ID"""
        queue = UpdateQueue()
        
        queue.add_output_line("test output", "web")
        
        self.assertEqual(len(queue.updates), 1)
        self.assertEqual(queue.updates[0].type, 'output')
        self.assertEqual(queue.updates[0].message_id, 1)
        self.assertEqual(queue.line_counter, 1)
        self.assertEqual(queue.message_counter, 1)
    
    def test_message_id_increment(self):
        """Test that message IDs increment properly"""
        queue = UpdateQueue()
        
        queue.add_output_line("line 1", "web")
        queue.add_status_update("web", "running")
        queue.add_output_line("line 2", "web")
        
        self.assertEqual(queue.updates[0].message_id, 1)
        self.assertEqual(queue.updates[1].message_id, 2)
        self.assertEqual(queue.updates[2].message_id, 3)
        self.assertEqual(queue.message_counter, 3)
    
    def test_poll_updates_by_message_id(self):
        """Test polling updates using message ID"""
        queue = UpdateQueue()
        
        # Add some updates
        queue.add_output_line("line 1", "web")  # message_id = 1
        queue.add_status_update("web", "running")  # message_id = 2
        queue.add_output_line("line 2", "web")  # message_id = 3
        
        # Poll from beginning (first poll)
        updates1, latest_id1 = queue.poll_updates(0)
        self.assertEqual(len(updates1['output_lines']), 2)
        self.assertEqual(len(updates1['status_updates']), 1)
        self.assertEqual(latest_id1, 3)
        
        # Add another update
        queue.add_output_line("line 3", "web")  # message_id = 4
        
        # Poll with last received ID
        updates2, latest_id2 = queue.poll_updates(3)
        self.assertEqual(len(updates2['output_lines']), 1)
        self.assertEqual(len(updates2['status_updates']), 0)
        self.assertEqual(latest_id2, 4)
        
        # Poll again with latest ID - should get nothing new
        updates3, latest_id3 = queue.poll_updates(4)
        self.assertEqual(len(updates3['output_lines']), 0)
        self.assertEqual(latest_id3, 4)
    
    def test_get_stats(self):
        """Test getting queue statistics"""
        queue = UpdateQueue()
        
        queue.add_output_line("test", "web")
        queue.add_status_update("web", "running")
        
        stats = queue.get_stats()
        
        expected_keys = {'total_messages', 'latest_message_id', 'total_lines', 'queue_capacity'}
        self.assertEqual(set(stats.keys()), expected_keys)
        self.assertEqual(stats['total_messages'], 2)
        self.assertEqual(stats['latest_message_id'], 2)
        self.assertEqual(stats['total_lines'], 1)
