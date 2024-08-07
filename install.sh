#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Function to check if we're in an interactive environment
check_interactive() {
    if [ ! -t 0 ]; then
        echo "Error: This script must be run in an interactive environment."
        echo "Please download the script first and then run it directly:"
        echo "1. curl -O https://raw.githubusercontent.com/smaghili/MarzBackup/main/install.sh"
        echo "2. chmod +x install.sh"
        echo "3. ./install.sh"
        exit 1
    fi
}

# Check interactivity before doing anything else
check_interactive

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

# Main installation function
install_marzbackup() {
    echo "Starting MarzBackup installation..."

    # Get necessary information first
    get_api_token
    get_admin_chat_id

    # Set the GitHub repository URL and installation directory
    REPO_URL="https://github.com/smaghili/MarzBackup.git"
    INSTALL_DIR="/opt/MarzBackup"
    CONFIG_DIR="/opt/marzbackup"
    LOG_FILE="/var/log/marzbackup.log"
    CONFIG_FILE="$CONFIG_DIR/config.json"

    # Create config directory if it doesn't exist
    sudo mkdir -p "$CONFIG_DIR"

    # Create or update config file
    echo "{\"API_TOKEN\": \"$API_TOKEN\", \"ADMIN_CHAT_ID\": \"$ADMIN_CHAT_ID\"}" | sudo tee "$CONFIG_FILE" > /dev/null
    echo "Configuration saved."

    # Update package lists
    sudo apt update

    # Install Python 3, pip, and git if not already installed
    sudo apt install -y python3 python3-pip git

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

    # Install required Python packages
    pip3 install -r requirements.txt

    # Copy the marzbackup.sh script to /usr/local/bin and make it executable
    sudo cp "$INSTALL_DIR/marzbackup.sh" /usr/local/bin/marzbackup
    sudo chmod +x /usr/local/bin/marzbackup

    echo "Installation completed. Starting the bot in the foreground..."

    # Start the bot in the foreground
    python3 "$INSTALL_DIR/main.py"

    # The script will exit here if the bot doesn't start successfully
    echo "MarzBackup is now running. To start it in the background, use: marzbackup start"
}

# Run the installation
install_marzbackup
