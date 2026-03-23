#!/usr/bin/env python3
"""Setup Max for macOS startup.

"The old 'launch on boot' trick. Works every time."

This script:
1. Creates the launchd plist with correct paths
2. Installs it to ~/Library/LaunchAgents/
3. Loads it with launchctl
"""
import os
import sys
import shutil
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_DIR, 'venv', 'bin', 'python')
PLIST_TEMPLATE = os.path.join(PROJECT_DIR, 'scripts', 'max.plist')
PLIST_NAME = 'com.control.max.plist'
LAUNCH_AGENTS = os.path.expanduser('~/Library/LaunchAgents')
PLIST_DEST = os.path.join(LAUNCH_AGENTS, PLIST_NAME)
LOGS_DIR = os.path.join(PROJECT_DIR, 'logs')


def install():
    print('🕵️  Setting up CONTROL headquarters for automatic startup...')
    print()

    # Create logs directory
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Read and fill template
    with open(PLIST_TEMPLATE) as f:
        content = f.read()

    content = content.replace('__VENV_PYTHON__', VENV_PYTHON)
    content = content.replace('__PROJECT_DIR__', PROJECT_DIR)

    # Write to LaunchAgents
    os.makedirs(LAUNCH_AGENTS, exist_ok=True)
    with open(PLIST_DEST, 'w') as f:
        f.write(content)

    print(f'  ✓ Plist written to {PLIST_DEST}')

    # Load with launchctl
    subprocess.run(['launchctl', 'load', PLIST_DEST], check=True)
    print(f'  ✓ Loaded with launchctl')
    print()
    print('  "And loving it!" — Max will start automatically on login.')
    print(f'  CONTROL HQ: http://localhost:8086')


def uninstall():
    print('🕵️  Standing down CONTROL startup agent...')

    if os.path.exists(PLIST_DEST):
        subprocess.run(['launchctl', 'unload', PLIST_DEST], check=False)
        os.remove(PLIST_DEST)
        print(f'  ✓ Removed {PLIST_DEST}')
        print('  "Agent 86, signing off."')
    else:
        print('  No startup agent found. Nothing to do.')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'uninstall':
        uninstall()
    else:
        install()
