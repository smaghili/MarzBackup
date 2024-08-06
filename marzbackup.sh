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
LOCK_FILE="/var/run/hourlyReport.lock"

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
        
        # Check if API_TOKEN and ADMIN_CHAT_ID are set in the config file
        API_TOKEN=$(jq -r '.API_TOKEN // empty' "$CONFIG_FILE")
        ADMIN_CHAT_ID=$(jq -r '.ADMIN_CHAT_ID // empty' "$CONFIG_FILE")

        if [ -z "$API_TOKEN" ] || [ -z "$ADMIN_CHAT_ID" ]; then
            echo "API_TOKEN or ADMIN_CHAT_ID is missing. Running setup..."
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

convert_to_cron() {
    local minutes=$1
    if [ $minutes -eq 60 ]; then
        echo "0 * * * *"
    elif [ $minutes -lt 60 ]; then
        echo "*/$minutes * * * *"
    else
        local hours=$((minutes / 60))
        local remaining_minutes=$((minutes % 60))
        if [ $remaining_minutes -eq 0 ]; then
            echo "0 */$hours * * *"
        else
            return 1
        fi
    fi
}

update_backup_cron() {
    local backup_interval=$(jq -r '.backup_interval_minutes' "$CONFIG_FILE")
    local cron_schedule=$(convert_to_cron $backup_interval)
    if [ $? -ne 0 ]; then
        echo "ERROR: Invalid time interval. Please use intervals that divide evenly into hours."
        return 1
    fi
    
    # Remove existing crontab entry for backup
    (crontab -l 2>/dev/null | grep -v "/usr/bin/python3 /opt/MarzBackup/backup.py") | crontab -
    
    # Install new crontab for backup with flock to ensure only one instance runs
    (crontab -l 2>/dev/null; echo "$cron_schedule /usr/bin/flock -n /tmp/marzbackup.lock /usr/bin/python3 /opt/MarzBackup/backup.py >> $LOG_FILE 2>&1") | crontab -
    
    echo "Backup cron job updated. Backups will run every $backup_interval minutes."
}

install_user_usage() {
    echo "Installing user usage tracking system..."
    
    # Check if hourlyReport.py is already running
    if check_hourlyreport_running; then
        echo "hourlyReport.py is already running. Please stop it before installation."
        return 1
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
    report_interval=$(echo $config | jq -r '.report_interval // 60')

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
    SQL_FILE="$INSTALL_DIR/hourlyUsage.sql"
    if [ -f "$SQL_FILE" ]; then
        echo "Setting up database structures using $db_type..."
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
    
    # Convert report interval to cron format
    cron_schedule=$(convert_to_cron $report_interval)
    if [ $? -ne 0 ]; then
        echo "ERROR: Invalid report interval. Please use intervals that divide evenly into hours."
        return 1
    fi
    
    # Remove existing crontab entry for hourlyReport.py
    echo "Removing existing crontab entry for user usage tracking..."
    (crontab -l 2>/dev/null | grep -v "/opt/MarzBackup/hourlyReport.py") | crontab -
    
    # Install new crontab for hourlyReport.py
    echo "Installing new crontab for user usage tracking..."
    (crontab -l 2>/dev/null; echo "$cron_schedule /usr/bin/python3 $INSTALL_DIR/hourlyReport.py >> $USAGE_LOG_FILE 2>&1") | crontab -
    
    # Start hourlyReport.py
    start_hourlyreport
    
    # Update backup cron job
    update_backup_cron
    
    echo "User usage tracking system installation completed."
    echo "Report interval set to every $report_interval minutes."
}

uninstall_marzbackup() {
    echo "Uninstalling MarzBackup..."
    stop

    # Remove cron jobs
    (crontab -l 2>/dev/null | grep -v "/usr/bin/python3 /opt/MarzBackup/backup.py") | crontab -
    (crontab -l 2>/dev/null | grep -v "/opt/MarzBackup/hourlyReport.py") | crontab -

    # Remove installation directory
    sudo rm -rf "$INSTALL_DIR"
    sudo rm -rf "$CONFIG_DIR"

    # Remove log files
    sudo rm -f "$LOG_FILE"
    sudo rm -f "$USAGE_LOG_FILE"

    # Remove script
    sudo rm -f "$SCRIPT_PATH"

    echo "MarzBackup has been uninstalled."
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
            stop_user_usage
            start_user_usage
        else
            restart
        fi
        ;;
    status)
        if [ "$2" == "user-usage" ]; then
            if check_hourlyreport_running; then
                echo "hourlyReport.py is running."
            else
                echo "hourlyReport.py is not running."
            fi
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
    update_backup_interval)
        update_backup_cron
        ;;
    *)
        echo "Usage: marzbackup {update [dev|stable]|start [user-usage]|stop [user-usage]|restart [user-usage]|status [user-usage]|install user-usage|uninstall [user-usage]|update_backup_interval}"
        exit 1
        ;;
esac

exit 0
