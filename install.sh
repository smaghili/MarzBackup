#!/bin/bash

# Update package lists
sudo apt update

# Install Python 3, pip, and git if not already installed
sudo apt install -y python3 python3-pip git

# Set the GitHub repository URL and installation directory
REPO_URL="https://github.com/smaghili/MarzBackup.git"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"

# Clone or update the GitHub repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
else
    echo "Performing fresh installation..."
    sudo git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create config directory if it doesn't exist
sudo mkdir -p "$CONFIG_DIR"

# Install required Python packages
pip3 install -r requirements.txt

# Copy the marzbackup.sh script to /usr/local/bin and make it executable
sudo cp "$INSTALL_DIR/marzbackup.sh" /usr/local/bin/marzbackup
sudo chmod +x /usr/local/bin/marzbackup

echo "Installation completed. Starting the bot..."

# Start the bot
python3 "$INSTALL_DIR/main.py"
