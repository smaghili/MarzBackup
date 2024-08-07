#!/bin/bash

# Update package lists
sudo apt update

# Install Python 3, pip, and git if not already installed
sudo apt install -y python3 python3-pip git

# Set the GitHub repository URL and installation directory
REPO_URL="https://github.com/smaghili/MarzBackup.git"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
CONFIG_FILE="$CONFIG_DIR/config.json"

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

# Function to get and validate API_TOKEN
get_api_token() {
    while true; do
        read -p "Please enter your Telegram bot token: " API_TOKEN
        if [ -n "$API_TOKEN" ]; then
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
        if [ -n "$ADMIN_CHAT_ID" ]; then
            break
        else
            echo "ADMIN_CHAT_ID cannot be empty. Please try again."
        fi
    done
}

# Check if config file exists and contains necessary information
if [ ! -f "$CONFIG_FILE" ] || [ -z "$(grep API_TOKEN "$CONFIG_FILE")" ] || [ -z "$(grep ADMIN_CHAT_ID "$CONFIG_FILE")" ]; then
    echo "API_TOKEN or ADMIN_CHAT_ID is missing. Please provide the necessary information."
    get_api_token
    get_admin_chat_id
    
    # Create or update config file
    echo "{\"API_TOKEN\": \"$API_TOKEN\", \"ADMIN_CHAT_ID\": \"$ADMIN_CHAT_ID\"}" | sudo tee "$CONFIG_FILE" > /dev/null
    echo "Configuration saved."
else
    echo "Existing configuration found."
fi

echo "Installation completed. Starting the bot in the foreground to verify..."

# Start the bot in the foreground
python3 "$INSTALL_DIR/main.py"

# Check if the bot started successfully
if [ $? -eq 0 ]; then
    echo "Bot started successfully. Moving to background..."
    nohup python3 "$INSTALL_DIR/main.py" > "$LOG_FILE" 2>&1 &
    echo $! | sudo tee /var/run/marzbackup.pid > /dev/null
    echo "Bot is now running in the background. PID: $(cat /var/run/marzbackup.pid)"
    echo "You can check its status with 'marzbackup status'."
    echo "To view logs, use: tail -f $LOG_FILE"
else
    echo "Failed to start the bot. Please check the logs for more information."
    exit 1
fi
