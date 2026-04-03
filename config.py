"""
Configuration management for Claw Code.

Config file: ~/.claw-code/config.json
Env vars: OPENROUTER_API_KEY, ANTHROPIC_API_KEY
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".claw-code"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "default_model": "deepseek",
    "approval_mode": True,
    "max_turns": 25,
    "models": {
        "deepseek": {
            "provider": "openrouter",
            "model_id": "deepseek/deepseek-chat-v3",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "cost_input": 0.14,
            "cost_output": 0.28,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "sonnet": {
            "provider": "openrouter",
            "model_id": "anthropic/claude-sonnet-4-20250514",
            "context_window": 200000,
            "max_output_tokens": 16384,
            "cost_input": 3.0,
            "cost_output": 15.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "opus": {
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-20250514",
            "context_window": 200000,
            "max_output_tokens": 16384,
            "cost_input": 15.0,
            "cost_output": 75.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "mercury": {
            "provider": "openrouter",
            "model_id": "inception/mercury-2",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "cost_input": 0.25,
            "cost_output": 1.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "minimax": {
            "provider": "openrouter",
            "model_id": "minimax/minimax-m2.7",
            "context_window": 205000,
            "max_output_tokens": 8192,
            "cost_input": 0.30,
            "cost_output": 1.10,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "flash": {
            "provider": "openrouter",
            "model_id": "google/gemini-2.5-flash-preview",
            "context_window": 1000000,
            "max_output_tokens": 16384,
            "cost_input": 0.15,
            "cost_output": 0.60,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "gemini-pro": {
            "provider": "openrouter",
            "model_id": "google/gemini-2.5-pro-preview",
            "context_window": 1000000,
            "max_output_tokens": 16384,
            "cost_input": 1.25,
            "cost_output": 10.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "haiku": {
            "provider": "openrouter",
            "model_id": "anthropic/claude-3.5-haiku",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "cost_input": 0.80,
            "cost_output": 4.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
        "qwen-local": {
            "provider": "lmstudio",
            "model_id": "qwen/qwen3.5-35b-a3b",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "cost_input": 0.0,
            "cost_output": 0.0,
            "temperature": 0.7,
            "top_p": 0.95,
        },
    },
}


def load_config() -> dict:
    """Load config from ~/.claw-code/config.json, creating defaults if needed."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                user_config = json.load(f)
            # Merge: user overrides defaults
            merged = {**DEFAULT_CONFIG, **user_config}
            # Deep merge models
            merged["models"] = {**DEFAULT_CONFIG["models"], **user_config.get("models", {})}
            return merged
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Config parse error ({e}), using defaults", flush=True)
            return DEFAULT_CONFIG
    else:
        # Create default config
        _write_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def _write_config(config: dict):
    """Write config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    # Set reasonable permissions
    CONFIG_PATH.chmod(0o600)


def get_model_config(config: dict, model_name: str) -> dict | None:
    """Get model configuration by name."""
    return config.get("models", {}).get(model_name)


def save_config(config: dict):
    """Save updated config to disk."""
    _write_config(config)
