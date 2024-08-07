#!/bin/bash

set -e

CONFIG_DIR="/opt/marzbackup"
CONFIG_FILE="$CONFIG_DIR/config.json"
REPO_URL="https://github.com/smaghili/MarzBackup.git"
INSTALL_DIR="/opt/MarzBackup"
LOG_FILE="/var/log/marzbackup.log"

# Function to get and validate API_TOKEN
get_api_token() {
    while true; do
        read -p "Please enter your Telegram bot token: " API_TOKEN
        if [ -n "$API_TOKEN" ]; then
            echo "API_TOKEN received successfully."
            break
        else
            echo "API_TOKEN cannot be empty. Please try again."
        fi
    done
}

# Function to get and validate ADMIN_CHAT_ID
get_admin_chat_id() {
    while true; do
        read -p "Please enter the admin chat ID: " ADMIN_CHAT_ID
        if [[ "$ADMIN_CHAT_ID" =~ ^-?[0-9]+$ ]]; then
            echo "ADMIN_CHAT_ID received successfully."
            break
        else
            echo "ADMIN_CHAT_ID must be a valid integer. Please try again."
        fi
    done
}

# Function to save configuration
save_config() {
    sudo mkdir -p "$CONFIG_DIR"
    echo "{\"API_TOKEN\": \"$API_TOKEN\", \"ADMIN_CHAT_ID\": \"$ADMIN_CHAT_ID\"}" | sudo tee "$CONFIG_FILE" > /dev/null
    echo "Configuration saved successfully."
}

# Function to install or update MarzBackup
install_marzbackup() {
    echo "Updating package lists..."
    sudo apt update

    echo "Installing required packages..."
    sudo apt install -y python3 python3-pip git

    if [ -d "$INSTALL_DIR" ]; then
        echo "Updating existing MarzBackup installation..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
    else
        echo "Performing fresh MarzBackup installation..."
        sudo git clone "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt

    echo "Setting up MarzBackup command..."
    sudo cp "$INSTALL_DIR/marzbackup.sh" /usr/local/bin/marzbackup
    sudo chmod +x /usr/local/bin/marzbackup

    echo "MarzBackup installation completed successfully."
}

# Main installation process
echo "Welcome to MarzBackup installation!"

# Get configuration information
get_api_token
get_admin_chat_id

# Save configuration
save_config

# Install MarzBackup
install_marzbackup

echo "Installation process completed."
echo "You can now start MarzBackup using: marzbackup start"
echo "To run MarzBackup in the foreground for testing, use: python3 $INSTALL_DIR/main.py"

# Ask user if they want to start MarzBackup now
read -p "Do you want to start MarzBackup now? (y/n): " start_now
if [[ $start_now == "y" || $start_now == "Y" ]]; then
    echo "Starting MarzBackup..."
    marzbackup start
else
    echo "You can start MarzBackup later using: marzbackup start"
fi

echo "Thank you for installing MarzBackup!"
