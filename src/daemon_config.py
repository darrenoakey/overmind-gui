"""
Configuration management for Overmind Daemon
Handles settings, discovery, and instance management
"""

import json
import os
from typing import Dict, Any, List


class DaemonConfig:
    """Configuration manager for daemon settings and instance discovery"""

    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.overmind - gui")
        self.config_file = os.path.join(self.config_dir, "daemon - config.json")
        self.instances_file = os.path.join(self.config_dir, "instances.json")

        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Default configuration
        self.default_config = {
            "daemon": {
                "api_port_range_start": 9000,
                "api_port_range_end": 9100,
                "max_output_lines": 100000,
                "cleanup_days": 30,
                "heartbeat_interval": 10,
                "log_level": "INFO",
            },
            "storage": {"database_name": "overmind.db", "backup_enabled": True, "backup_interval_hours": 24},
            "discovery": {"enabled": True, "broadcast_interval": 30, "cleanup_dead_instances": True},
        }

        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                # Merge with defaults to ensure new settings exist
                return self._merge_config(self.default_config, config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")

        # Create default config file
        self._save_config(self.default_config)
        return self.default_config.copy()

    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """Merge loaded config with defaults"""
        merged = default.copy()
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config file: {e}")

    def get(self, key_path: str, default=None):
        """Get configuration value by dot - separated key path"""
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any):
        """Set configuration value by dot - separated key path"""
        keys = key_path.split(".")
        config = self.config

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value
        self._save_config(self.config)

    def register_instance(
        self, instance_id: str, pid: int, api_port: int, working_directory: str, status: str = "running"
    ):
        """Register a daemon instance for discovery"""
        instances = self._load_instances()

        instances[instance_id] = {
            "instance_id": instance_id,
            "pid": pid,
            "api_port": api_port,
            "working_directory": working_directory,
            "status": status,
            "registered_at": os.times().elapsed,
            "last_seen": os.times().elapsed,
        }

        self._save_instances(instances)

    def update_instance_heartbeat(self, instance_id: str):
        """Update instance heartbeat timestamp"""
        instances = self._load_instances()

        if instance_id in instances:
            instances[instance_id]["last_seen"] = os.times().elapsed
            instances[instance_id]["status"] = "running"
            self._save_instances(instances)

    def unregister_instance(self, instance_id: str):
        """Remove instance from discovery"""
        instances = self._load_instances()

        if instance_id in instances:
            del instances[instance_id]
            self._save_instances(instances)

    def get_active_instances(self, max_age_seconds: int = 60) -> List[Dict[str, Any]]:
        """Get list of active daemon instances"""
        instances = self._load_instances()
        current_time = os.times().elapsed
        active_instances = []

        for instance_data in instances.values():
            age = current_time - instance_data["last_seen"]
            if age <= max_age_seconds:
                active_instances.append(instance_data)

        return active_instances

    def cleanup_dead_instances(self, max_age_seconds: int = 120):
        """Remove dead instances from discovery"""
        instances = self._load_instances()
        current_time = os.times().elapsed

        dead_instances = []
        for instance_id, instance_data in instances.items():
            age = current_time - instance_data["last_seen"]
            if age > max_age_seconds:
                dead_instances.append(instance_id)

        for instance_id in dead_instances:
            del instances[instance_id]

        if dead_instances:
            self._save_instances(instances)

        return len(dead_instances)

    def _load_instances(self) -> Dict[str, Dict]:
        """Load instances from file"""
        if os.path.exists(self.instances_file):
            try:
                with open(self.instances_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {}

    def _save_instances(self, instances: Dict[str, Dict]):
        """Save instances to file"""
        try:
            with open(self.instances_file, "w") as f:
                json.dump(instances, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save instances file: {e}")

    def get_database_path(self, working_directory: str) -> str:
        """Get database path for a working directory - always use overmind.db"""
        # We only use one database: overmind.db in the working directory
        return os.path.join(working_directory, "overmind.db")

    def get_api_port_range(self) -> tuple:
        """Get API port range for daemon instances"""
        start = self.get("daemon.api_port_range_start", 9000)
        end = self.get("daemon.api_port_range_end", 9100)
        return (start, end)

    def should_cleanup_dead_instances(self) -> bool:
        """Check if dead instance cleanup is enabled"""
        return self.get("discovery.cleanup_dead_instances", True)


# Global config instance
daemon_config = DaemonConfig()
