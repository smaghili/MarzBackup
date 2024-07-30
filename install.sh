#!/bin/bash

# Update package lists
sudo apt update

# Install Python 3 and pip if not already installed
sudo apt install -y python3 python3-pip

# Install required Python packages
pip3 install aiogram pyyaml

# Set the GitHub repository URL
repo_url="https://github.com/smaghili/MarzBackup.git"


# Clone the GitHub repository
git clone "$repo_url"

cd MarzBackup/
# Check if bot.py exists in the current directory
if [ -f "bot.py" ]; then
    echo "Starting bot.py..."
    python3 main.py
else
    echo "Error: bot.py not found in the current directory."
    exit 1
fi
