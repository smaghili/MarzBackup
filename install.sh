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

# Ask user which version to install
echo "Which version would you like to install?"
echo "1) Stable"
echo "2) Development"
read -p "Enter your choice (1 or 2): " version_choice

case $version_choice in
    1)
        BRANCH="main"
        VERSION="stable"
        ;;
    2)
        BRANCH="dev"
        VERSION="dev"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Clone or update the GitHub repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout $BRANCH
    git reset --hard origin/$BRANCH
else
    echo "Performing fresh installation..."
    sudo git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create config directory if it doesn't exist
sudo mkdir -p "$CONFIG_DIR"

# Install required Python packages
pip3 install -r requirements.txt

# Copy the marzbackup.sh script to /usr/local/bin and make it executable
sudo cp "$INSTALL_DIR/marzbackup.sh" /usr/local/bin/marzbackup
sudo chmod +x /usr/local/bin/marzbackup

# Save the installed version to config
echo "{\"installed_version\": \"$VERSION\"}" > "$CONFIG_DIR/version.json"

echo "Installation completed. Starting the bot in the background..."

# Start the bot in the background
nohup python3 "$INSTALL_DIR/main.py" > "$LOG_FILE" 2>&1 &

echo "Bot is running in the background. You can check its status with 'marzbackup status'."
echo "To view logs, use: tail -f $LOG_FILE"
