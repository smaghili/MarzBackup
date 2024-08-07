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

ensure_single_instance() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo "MarzBackup is already running. Stopping the old instance..."
            kill $OLD_PID
            sleep 2
        fi
    fi
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
    fi
}

get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        version=$(grep -o '"installed_version": "[^"]*' "$VERSION_FILE" | grep -o '[^"]*$')
        echo $version
    else
        echo "stable" # Default to stable if version file doesn't exist
    fi
}

check_and_get_config() {
    API_TOKEN=$(jq -r '.API_TOKEN // empty' "$CONFIG_FILE")
    ADMIN_CHAT_ID=$(jq -r '.ADMIN_CHAT_ID // empty' "$CONFIG_FILE")
    if [ -z "$API_TOKEN" ] || [ -z "$ADMIN_CHAT_ID" ]; then
        echo "API_TOKEN or ADMIN_CHAT_ID is missing. Running setup..."
        python3 "$INSTALL_DIR/setup.py"
        if [ $? -ne 0 ]; then
            echo "Setup failed. Please check the error messages and try again."
            exit 1
        fi
    fi
}

send_telegram_message() {
    message="$1"
    python3 -c "
import asyncio
from aiogram import Bot
from config import load_config

async def send_message():
    config = load_config()
    bot = Bot(token=config['API_TOKEN'])
    await bot.send_message(chat_id=config['ADMIN_CHAT_ID'], text='$message')
    await bot.session.close()

asyncio.run(send_message())
"
}

start() {
    echo "Starting MarzBackup..."
    ensure_single_instance
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        check_and_get_config
        echo "Running MarzBackup in background..."
        nohup python3 main.py > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        echo $NEW_PID > "$PID_FILE"
        sleep 2
        if ps -p $NEW_PID > /dev/null 2>&1; then
            echo "Bot is running in the background. PID: $NEW_PID"
            echo "You can check its status with 'marzbackup status'."
            echo "To view logs, use: tail -f $LOG_FILE"
            send_telegram_message "ربات MarzBackup با موفقیت راه‌اندازی شد!"
        else
            echo "Failed to start the bot in background. Check logs for details."
            cat "$LOG_FILE"
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

stop() {
    echo "Stopping MarzBackup..."
    ensure_single_instance
    echo "MarzBackup stopped."
}

restart() {
    stop
    sleep 2
    start
    send_telegram_message "ربات MarzBackup با موفقیت راه‌اندازی مجدد شد!"
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

get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        version=$(jq -r '.installed_version' "$VERSION_FILE")
        echo $version
    else
        echo "unknown"
    fi
}

update() {
    echo "Checking for updates..."
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    
    if [ ! -d ".git" ]; then
        echo "Git repository not found. Initializing..."
        git init
        git remote add origin "$REPO_URL"
    fi
    
    git fetch origin
    
    current_version=$(get_current_version)
    if [ "$2" == "dev" ] || [ "$current_version" == "dev" ]; then
        BRANCH="dev"
        NEW_VERSION="dev"
    else
        BRANCH="main"
        NEW_VERSION="stable"
    fi
    
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/$BRANCH)
    
    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "You are already using the latest $NEW_VERSION version."
    else
        echo "Updating MarzBackup to the latest $NEW_VERSION version..."
        git reset --hard origin/$BRANCH
        
        # Update Python dependencies
        pip3 install -r requirements.txt
        
        # Update marzbackup.sh
        if [ -f "$INSTALL_DIR/marzbackup.sh" ]; then
            sudo cp "$INSTALL_DIR/marzbackup.sh" "$0"
            sudo chmod +x "$0"
        else
            echo "Error: marzbackup.sh not found in repository."
            exit 1
        fi
        
        # Update other crucial files
        sudo cp "$INSTALL_DIR/backup.py" "/opt/MarzBackup/backup.py"
        sudo cp "$INSTALL_DIR/handlers.py" "/opt/MarzBackup/handlers.py"
        sudo cp "$INSTALL_DIR/config.py" "/opt/MarzBackup/config.py"
        
        echo "{\"installed_version\": \"$NEW_VERSION\"}" > "$VERSION_FILE"
        echo "MarzBackup has been updated successfully to $NEW_VERSION version."
        
        # Restart the service
        marzbackup restart
    fi
}

check_version() {
    cd "$INSTALL_DIR" || { echo "Error: $INSTALL_DIR not found."; exit 1; }
    
    if [ ! -f "$VERSION_FILE" ]; then
        echo "Version file not found. Unable to check version."
        return 1
    fi
    
    CURRENT_VERSION=$(get_current_version)
    echo "Current installed version: $CURRENT_VERSION"
    
    # Check for updates
    git fetch origin --quiet
    if [ "$CURRENT_VERSION" == "dev" ]; then
        LATEST_VERSION=$(git rev-parse origin/dev)
        CURRENT_COMMIT=$(git rev-parse HEAD)
        if [ "$CURRENT_COMMIT" != "$LATEST_VERSION" ]; then
            echo "A new dev version is available. Use 'marzbackup update dev' to upgrade."
        else
            echo "You are using the latest dev version."
        fi
    else
        LATEST_VERSION=$(git describe --tags $(git rev-list --tags --max-count=1))
        if [ "$CURRENT_VERSION" != "$LATEST_VERSION" ]; then
            echo "A new version ($LATEST_VERSION) is available. Use 'marzbackup update' to upgrade."
        else
            echo "You are using the latest stable version."
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
        echo "Error: Invalid interval. Please use intervals that divide evenly into hours."
        return 1
    fi

    # Remove previous cron job for backup
    (crontab -l 2>/dev/null | grep -v "/usr/bin/python3 /opt/MarzBackup/backup.py") | crontab -

    # Install new cron job for backup using flock to ensure only one instance runs
    (crontab -l 2>/dev/null; echo "$cron_schedule /usr/bin/flock -n /tmp/marzbackup.lock /usr/bin/python3 /opt/MarzBackup/backup.py >> $LOG_FILE 2>&1") | crontab -

    echo "Backup cron job updated. Backup will run every $backup_interval minutes."
}

uninstall_marzbackup() {
echo "Starting comprehensive cleanup of MarzBackup..."

# Kill all Python processes related to MarzBackup
echo "Stopping all MarzBackup related processes..."
pkill -f "/opt/MarzBackup/main.py"
pkill -f "/opt/MarzBackup/hourlyReport.py"
pkill -f "/opt/MarzBackup/backup.py"
pkill -f "aiogram"  # Kill any running Telegram bot processes

# Force kill any remaining Python processes related to MarzBackup
pids=$(pgrep -f "python.*MarzBackup")
if [ ! -z "$pids" ]; then
    echo "Force stopping remaining MarzBackup processes..."
    kill -9 $pids
fi

# Remove cron jobs
echo "Removing cron jobs..."
(crontab -l 2>/dev/null | grep -v "/opt/MarzBackup") | crontab -

# Remove installation directories
echo "Removing MarzBackup directories..."
sudo rm -rf /opt/MarzBackup
sudo rm -rf /opt/marzbackup

# Remove log files
echo "Removing log files..."
sudo rm -f /var/log/marzbackup.log
sudo rm -f /var/log/marzbackup_usage.log

# Remove PID and lock files
echo "Removing PID and lock files..."
sudo rm -f /var/run/marzbackup.pid
sudo rm -f /var/run/marzbackup_usage.pid
sudo rm -f /var/run/hourlyReport.lock
sudo rm -f /tmp/marzbackup.lock
sudo rm -f /tmp/marzbackup_bot.lock

# Remove marzbackup script and any potential symlinks
echo "Removing MarzBackup scripts..."
sudo rm -f /usr/local/bin/marzbackup
sudo find /usr/local/bin -lname '*MarzBackup*' -delete

# Remove any potential systemd service
echo "Removing systemd service if exists..."
if systemctl is-active --quiet marzbackup.service; then
    sudo systemctl stop marzbackup.service
    sudo systemctl disable marzbackup.service
fi
sudo rm -f /etc/systemd/system/marzbackup.service
sudo systemctl daemon-reload

# Remove any potential startup scripts
echo "Removing any startup scripts..."
sudo rm -f /etc/init.d/marzbackup
sudo update-rc.d marzbackup remove 2>/dev/null

# Remove any potential Docker containers (if used)
if command -v docker &> /dev/null; then
    echo "Removing any Docker containers related to MarzBackup..."
    docker stop $(docker ps -a | grep marzbackup | awk '{print $1}') 2>/dev/null
    docker rm $(docker ps -a | grep marzbackup | awk '{print $1}') 2>/dev/null
fi

    # Final checks
    echo "Performing final checks..."
    if pgrep -f "MarzBackup" > /dev/null; then
        echo "Warning: Some MarzBackup processes are still running. You may need to manually stop them or reboot."
    else
        echo "All MarzBackup processes have been stopped."
    fi
    
    if [ -d "$INSTALL_DIR" ] || [ -d "$CONFIG_DIR" ]; then
        echo "Warning: Some MarzBackup directories still exist. You may need to manually remove them."
    else
        echo "All MarzBackup directories have been removed."
    fi
    
    echo "MarzBackup has been completely uninstalled."
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

case "$1" in
    update)
        update $@
        send_telegram_message "ربات MarzBackup با موفقیت به‌روزرسانی شد!"
        ;;
    check-version)
        check_version
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
