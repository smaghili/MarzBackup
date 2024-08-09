#!/bin/bash

CONFIG_DIR="/opt/marzbackup"
CONFIG_FILE="$CONFIG_DIR/config.json"
REPO_URL="https://github.com/smaghili/MarzBackup.git"
INSTALL_DIR="/opt/MarzBackup"
LOG_FILE="/var/log/marzbackup.log"
VERSION_FILE="$CONFIG_DIR/version.json"
PID_FILE="/var/run/marzbackup.pid"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"

# Function to get the current installed version
get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        version=$(grep -o '"installed_version": "[^"]*' "$VERSION_FILE" | grep -o '[^"]*$')
        echo $version
    else
        echo "stable" # Default to stable if version file doesn't exist
    fi
}

# Function to check and update to the latest version
check_and_update_version() {
    current_version=$(get_current_version)
    if [ "$current_version" == "dev" ]; then
        BRANCH="dev"
    else
        BRANCH="main"
    fi

    cd "$INSTALL_DIR"
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/$BRANCH)

    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "The latest version of MarzBackup is already installed."
        restart_bot_if_stopped
    else
        echo "Updating MarzBackup to the latest $BRANCH version..."
        git reset --hard origin/$BRANCH
        pip3 install -r requirements.txt
        # Update marzbackup.sh
        if [ -f "$INSTALL_DIR/marzbackup.sh" ]; then
            sudo cp "$INSTALL_DIR/marzbackup.sh" "$TEMP_SCRIPT"
            sudo chmod +x "$TEMP_SCRIPT"
            echo "New version of marzbackup.sh downloaded. Applying update..."
            sudo mv "$TEMP_SCRIPT" "$SCRIPT_PATH"
            echo "{\"installed_version\": \"$BRANCH\"}" > "$VERSION_FILE"
            echo "marzbackup.sh has been updated. Restarting with new version..."
            restart_bot
        else
            echo "Error: marzbackup.sh not found in repository."
            exit 1
        fi
    fi
}

# Function to restart the bot if it is stopped
restart_bot_if_stopped() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ! ps -p $PID > /dev/null; then
            echo "Bot is not running. Restarting..."
            start_bot
        else
            echo "Bot is already running."
        fi
    else
        echo "PID file not found. Starting bot..."
        start_bot
    fi
}

# Function to start the bot
start_bot() {
    cd "$INSTALL_DIR"
    nohup python3 main.py > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
    echo "Bot started with PID: $(cat $PID_FILE)"
}

# Function to read existing configuration
read_config() {
    if [ -f "$CONFIG_FILE" ]; then
        API_TOKEN=$(jq -r '.API_TOKEN' "$CONFIG_FILE")
        ADMIN_CHAT_ID=$(jq -r '.ADMIN_CHAT_ID' "$CONFIG_FILE")
        if [ -n "$API_TOKEN" ] && [ -n "$ADMIN_CHAT_ID" ]; then
            echo "Existing configuration found."
            return 0
        fi
    fi
    return 1
}

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

# Function to select version
select_version() {
    while true; do
        echo "Which version would you like to install?"
        echo "1) Stable (main branch)"
        echo "2) Development (dev branch)"
        read -p "Enter your choice (1 or 2): " version_choice
        case $version_choice in
            1)
                BRANCH="main"
                echo "Stable version (main branch) selected."
                break
                ;;
            2)
                BRANCH="dev"
                echo "Development version (dev branch) selected."
                break
                ;;
            *)
                echo "Invalid choice. Please enter 1 or 2."
                ;;
        esac
    done
    echo "You have chosen to install the $BRANCH branch. Proceeding with installation..."
}

# Main installation process
echo "Welcome to MarzBackup installation!"

# Select version
select_version

# Read existing configuration or prompt for new input
if ! read_config; then
    get_api_token
    get_admin_chat_id
    save_config
fi

# Update package lists
echo "Updating package lists..."
sudo apt update

# Install required packages
echo "Installing required packages..."
sudo apt install -y python3 python3-pip git

# Clone or update the repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing MarzBackup installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout $BRANCH
    git reset --hard origin/$BRANCH
    echo "Successfully updated to the latest $BRANCH version."
else
    echo "Performing fresh MarzBackup installation..."
    if git ls-remote --exit-code --heads $REPO_URL $BRANCH; then
        sudo git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
        echo "Successfully cloned the $BRANCH branch."
    else
        echo "Error: The $BRANCH branch does not exist. Falling back to main branch."
        BRANCH="main"
        sudo git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
fi

# Update the version file
echo "{\"installed_version\": \"$BRANCH\"}" | sudo tee "$VERSION_FILE" > /dev/null

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Copy the marzbackup.sh script to /usr/local/bin and make it executable
echo "Setting up MarzBackup command..."
sudo cp "$INSTALL_DIR/marzbackup.sh" /usr/local/bin/marzbackup
sudo chmod +x /usr/local/bin/marzbackup

echo "Installation completed. Starting the bot in the background..."

# Start the bot in the background
nohup python3 "$INSTALL_DIR/main.py" > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"

echo "Bot is now running in the background."
echo "You can check its status with 'marzbackup status'."
echo "To view logs, use: tail -f $LOG_FILE"

# Check and update to the latest version
check_and_update_version
