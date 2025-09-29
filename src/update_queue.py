#!/usr/bin/env python3
"""
Update Queue - Simple message queue for frontend/backend communication
Simplified version that works with the new database - polling architecture
"""

import time
from typing import Dict, Any
import threading


class UpdateQueue:
    """Simple in - memory update queue for GUI communication"""

    def __init__(self):
        self.message_counter = 0
        self.output_lines = []
        self.status_updates = []
        self.lock = threading.Lock()

    def get_current_state(self) -> Dict[str, Any]:
        """Get current state for initial page load"""
        with self.lock:
            return {
                'output_lines': self.output_lines.copy(),
                'status_updates': self.status_updates.copy(),
                'latest_message_id': self.message_counter,
                'processes': {},  # Will be populated by process manager
                'stats': {}       # Will be populated by process manager
            }

    def get_updates_since(self, last_message_id: int) -> Dict[str, Any]:
        """Get updates since specified message ID"""
        with self.lock:
            # For simplicity, return recent items
            # In practice, this would filter by message ID
            recent_output = self.output_lines[-100:] if self.output_lines else []
            recent_status = self.status_updates[-50:] if self.status_updates else []

            return {
                'output_lines': recent_output,
                'status_updates': recent_status,
                'latest_message_id': self.message_counter
            }

    def add_output_line(self, html: str, process: str):
        """Add an output line"""
        with self.lock:
            self.message_counter += 1
            self.output_lines.append({
                'id': self.message_counter,
                'process': process,
                'html': html,
                'timestamp': time.time()
            })

            # Keep only recent lines to avoid memory growth
            if len(self.output_lines) > 1000:
                self.output_lines = self.output_lines[-500:]

    def add_status_update(self, process: str, status: str):
        """Add a status update"""
        with self.lock:
            self.message_counter += 1
            self.status_updates.append({
                'id': self.message_counter,
                'process': process,
                'status': status,
                'timestamp': time.time()
            })

            # Keep only recent updates
            if len(self.status_updates) > 200:
                self.status_updates = self.status_updates[-100:]

    def add_bulk_status_updates(self, updates: Dict[str, str]):
        """Add multiple status updates"""
        for process, status in updates.items():
            self.add_status_update(process, status)

    def clear_all(self):
        """Clear all queued data"""
        with self.lock:
            self.output_lines.clear()
            self.status_updates.clear()
            self.message_counter += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self.lock:
            return {
                'total_messages': self.message_counter,
                'total_lines': len(self.output_lines),
                'total_status_updates': len(self.status_updates)
            }


# Global instance
update_queue = UpdateQueue()
