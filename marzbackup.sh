#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
USAGE_LOG_FILE="/var/log/marzbackup_usage.log"
PID_FILE="/var/run/marzbackup.pid"
VERSION_FILE="$CONFIG_DIR/version.json"
CONFIG_FILE="$CONFIG_DIR/config.json"
USAGE_PID_FILE="/var/run/marzbackup_usage.pid"
SQL_FILE="$INSTALL_DIR/hourlyUsage.sql"

get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        version=$(grep -o '"installed_version": "[^"]*' "$VERSION_FILE" | grep -o '[^"]*$')
        echo $version
    else
        echo "stable"  # Default to stable if version file doesn't exist
    fi
}

update() {
    echo "Checking for updates..."
    current_version=$(get_current_version)
    
    if [ "$2" == "dev" ]; then
        BRANCH="dev"
        NEW_VERSION="dev"
    elif [ "$2" == "stable" ]; then
        BRANCH="main"
        NEW_VERSION="stable"
    elif [ -z "$2" ]; then
        BRANCH=$([ "$current_version" == "dev" ] && echo "dev" || echo "main")
        NEW_VERSION=$current_version
    else
        echo "Invalid version specified. Use 'dev' or 'stable'."
        exit 1
    fi

    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout $BRANCH
        LOCAL=$(git rev-parse HEAD)
        REMOTE=$(git rev-parse @{u})

        if [ "$LOCAL" = "$REMOTE" ] && [ "$NEW_VERSION" == "$current_version" ]; then
            echo "You are already using the latest $NEW_VERSION version."
            exit 0
        else
            echo "Updating MarzBackup to $NEW_VERSION version..."
            stop
            git reset --hard origin/$BRANCH
            pip3 install -r requirements.txt
            
            # Update marzbackup.sh
            if [ -f "$INSTALL_DIR/marzbackup.sh" ]; then
                sudo cp "$INSTALL_DIR/marzbackup.sh" "$TEMP_SCRIPT"
                sudo chmod +x "$TEMP_SCRIPT"
                echo "New version of marzbackup.sh downloaded. Applying update..."
                sudo mv "$TEMP_SCRIPT" "$SCRIPT_PATH"
                echo "{\"installed_version\": \"$NEW_VERSION\"}" > "$VERSION_FILE"
                echo "marzbackup.sh has been updated. Restarting with new version..."
                exec "$SCRIPT_PATH" start
            else
                echo "Error: marzbackup.sh not found in repository."
                exit 1
            fi
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

start() {
    echo "Starting MarzBackup..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        
        # Run setup.py if API_TOKEN or ADMIN_CHAT_ID is missing
        if ! grep -q "API_TOKEN" "$CONFIG_FILE" || ! grep -q "ADMIN_CHAT_ID" "$CONFIG_FILE"; then
            python3 setup.py
            if [ $? -ne 0 ]; then
                echo "Setup failed. Please check the error messages and try again."
                exit 1
            fi
        fi
        
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null; then
                echo "MarzBackup is already running. Use 'marzbackup restart' to restart it."
                return
            else
                echo "Stale PID file found. Removing it."
                rm "$PID_FILE"
            fi
        fi
        nohup python3 main.py > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
        sleep 2
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null; then
                echo "Bot is running in the background. PID: $PID"
                echo "You can check its status with 'marzbackup status'."
                echo "To view logs, use: tail -f $LOG_FILE"
            else
                echo "Failed to start the bot. Check logs for details."
                cat "$LOG_FILE"
            fi
        else
            echo "Failed to start the bot. PID file not created."
            cat "$LOG_FILE"
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

stop() {
    echo "Stopping MarzBackup..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill $PID
        rm "$PID_FILE"
        echo "MarzBackup stopped."
    else
        echo "MarzBackup is not running or PID file not found."
    fi
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "MarzBackup is running. PID: $PID"
            echo "Last 10 lines of log:"
            tail -n 10 "$LOG_FILE"
        else
            echo "MarzBackup is not running, but PID file exists. It may have crashed."
            echo "Last 20 lines of log:"
            tail -n 20 "$LOG_FILE"
            rm "$PID_FILE"
        fi
    else
        echo "MarzBackup is not running."
        if [ -f "$LOG_FILE" ]; then
            echo "Last 20 lines of log:"
            tail -n 20 "$LOG_FILE"
        else
            echo "No log file found."
        fi
    fi
}

start_user_usage() {
    echo "Starting user usage tracking system..."
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "User usage tracking system is already running. Use 'marzbackup restart user-usage' to restart it."
            return
        else
            echo "Stale PID file found. Removing it."
            rm "$USAGE_PID_FILE"
        fi
    fi
    nohup python3 "$INSTALL_DIR/hourlyReport.py" > "$USAGE_LOG_FILE" 2>&1 &
    echo $! > "$USAGE_PID_FILE"
    sleep 2
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "User usage tracking system started. PID: $PID"
            echo "To view usage logs, use: tail -f $USAGE_LOG_FILE"
        else
            echo "Failed to start the user usage tracking system. Check logs for details."
            cat "$USAGE_LOG_FILE"
        fi
    else
        echo "Failed to start the user usage tracking system. PID file not created."
        cat "$USAGE_LOG_FILE"
    fi
}

stop_user_usage() {
    echo "Stopping user usage tracking system..."
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            kill $PID
            rm "$USAGE_PID_FILE"
            echo "User usage tracking system stopped."
        else
            echo "User usage tracking system is not running, but PID file exists. Removing stale PID file."
            rm "$USAGE_PID_FILE"
        fi
    else
        echo "User usage tracking system is not running."
    fi
}

restart_user_usage() {
    stop_user_usage
    sleep 2
    start_user_usage
}

status_user_usage() {
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "User usage tracking system is running. PID: $PID"
            echo "Last 10 lines of usage log:"
            tail -n 10 "$USAGE_LOG_FILE"
        else
            echo "User usage tracking system is not running, but PID file exists. It may have crashed."
            echo "Last 20 lines of usage log:"
            tail -n 20 "$USAGE_LOG_FILE"
            rm "$USAGE_PID_FILE"
        fi
    else
        echo "User usage tracking system is not running."
        if [ -f "$USAGE_LOG_FILE" ]; then
            echo "Last 20 lines of usage log:"
            tail -n 20 "$USAGE_LOG_FILE"
        else
            echo "No usage log file found."
        fi
    fi
}

install_user_usage() {
    echo "Installing user usage tracking system..."
    
    # Force removal of USAGE_PID_FILE if it exists
    if [ -f "$USAGE_PID_FILE" ]; then
        echo "Removing existing PID file..."
        rm "$USAGE_PID_FILE"
    fi
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        echo "jq is not installed. Installing jq..."
        sudo apt-get update && sudo apt-get install -y jq
    fi
    
    # Load config and update it
    python3 "$INSTALL_DIR/config.py"
    
    # Read database information directly from config.json
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Config file not found at $CONFIG_FILE"
        exit 1
    fi
    
    config=$(cat "$CONFIG_FILE")
    db_container=$(echo $config | jq -r '.db_container')
    db_password=$(echo $config | jq -r '.db_password')
    db_type=$(echo $config | jq -r '.db_type')

    # Validate database information
    if [ -z "$db_container" ] || [ -z "$db_password" ] || [ -z "$db_type" ]; then
        echo "Error: Missing database configuration. Please check your config.json file."
        exit 1
    fi

    # Check if the database container is running
    if ! docker ps | grep -q "$db_container"; then
        echo "Error: Database container $db_container is not running."
        exit 1
    fi

    # Execute SQL script to create the database and required tables and procedures
    if [ -f "$SQL_FILE" ]; then
        echo "Setting up database structures using $db_type..."
        # Print the command with actual values (for debugging purposes)
        echo "Executing: docker exec -i $db_container $db_type -u root -p<password> < $SQL_FILE"
        docker exec -i "$db_container" "$db_type" -u root -p"$db_password" < "$SQL_FILE"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to execute SQL script. Please check your database credentials and permissions."
            exit 1
        else
            echo "SQL script executed successfully."
        fi
    else
        echo "Error: SQL file not found at $SQL_FILE"
        exit 1
    fi

    # Set a flag in the config file to indicate that user usage tracking is installed
    jq '. + {"user_usage_installed": true}' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    
    echo "Starting user usage tracking system..."
    start_user_usage
    
    echo "User usage tracking system installation completed."
}

uninstall_user_usage() {
    echo "Uninstalling user usage tracking system..."
    
    # Stop the user usage tracking system
    stop_user_usage
    
    # Load configuration
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Config file not found at $CONFIG_FILE"
        exit 1
    fi
    
    config=$(cat "$CONFIG_FILE")
    db_container=$(echo $config | jq -r '.db_container')
    db_password=$(echo $config | jq -r '.db_password')
    db_type=$(echo $config | jq -r '.db_type')

    # Validate database information
    if [ -z "$db_container" ] || [ -z "$db_password" ] || [ -z "$db_type" ]; then
        echo "Error: Missing database configuration. Please check your config.json file."
        exit 1
    fi

    # Drop the UserUsageAnalytics database
    echo "Dropping UserUsageAnalytics database..."
    docker exec -i "$db_container" "$db_type" -u root -p"$db_password" -e "DROP DATABASE IF EXISTS UserUsageAnalytics;"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to drop the UserUsageAnalytics database. Please check your database credentials and permissions."
        exit 1
    else
        echo "UserUsageAnalytics database dropped successfully."
    fi

    # Remove the user_usage_installed flag from the config file
    jq 'del(.user_usage_installed)' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    
    # Remove usage log file
    sudo rm -f "$USAGE_LOG_FILE"
    
    echo "User usage tracking system has been uninstalled."
}

uninstall_marzbackup() {
    echo "WARNING: This will completely remove MarzBackup, including all settings and data."
    echo "Are you sure you want to proceed? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])+$ ]]; then
        echo "Proceeding with uninstallation..."

        # Stop MarzBackup and user usage tracking
        stop
        stop_user_usage

        # Uninstall user usage tracking system
        uninstall_user_usage

        # Remove MarzBackup files and directories
        sudo rm -rf "$INSTALL_DIR"
        sudo rm -rf "$CONFIG_DIR"
        sudo rm -f "$LOG_FILE"
        sudo rm -f "$USAGE_LOG_FILE"
        sudo rm -f "$PID_FILE"
        sudo rm -f "$USAGE_PID_FILE"
        sudo rm -f "$SCRIPT_PATH"
        
        echo "MarzBackup has been completely uninstalled."
    else
        echo "Uninstallation cancelled."
    fi
}

case "$1" in
    update)
        update $@
        ;;
    start)
        if [ "$2" == "user-usage" ]; then
            start_user_usage
        else
            start
        fi
        ;;
    stop)
        if [ "$2" == "user-usage" ]; then
            stop_user_usage
        else
            stop
        fi
        ;;
    restart)
        if [ "$2" == "user-usage" ]; then
            restart_user_usage
        else
            restart
        fi
        ;;
    status)
        if [ "$2" == "user-usage" ]; then
            status_user_usage
        else
            status
        fi
        ;;
    install)
        if [ "$2" == "user-usage" ]; then
            install_user_usage
        else
            echo "Unknown install option: $2"
            echo "Usage: marzbackup install user-usage"
            exit 1
        fi
        ;;
    uninstall)
        if [ "$2" == "user-usage" ]; then
            uninstall_user_usage
        elif [ -z "$2" ]; then
            uninstall_marzbackup
        else
            echo "Unknown uninstall option: $2"
            echo "Usage: marzbackup uninstall [user-usage]"
            exit 1
        fi
        ;;
    *)
        echo "Usage: marzbackup {update [dev|stable]|start [user-usage]|stop [user-usage]|restart [user-usage]|status [user-usage]|install user-usage|uninstall [user-usage]}"
        exit 1
        ;;
esac

exit 0
