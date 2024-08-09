#!/bin/bash

# Read configuration from JSON file
CONFIG_FILE="/opt/marzbackup/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Function to read JSON values
get_json_value() {
    key=$1
    jq -r ".$key" "$CONFIG_FILE"
}

# Read values from config file
TOKEN=$(get_json_value "API_TOKEN")
CHAT_ID=$(get_json_value "ADMIN_CHAT_ID")
CONTAINER_NAME=$(get_json_value "db_container")
DB_PASSWORD=$(get_json_value "db_password")
DB_NAME=$(get_json_value "db_name")
DB_TYPE=$(get_json_value "db_type")

# Other variables
USER="root"
BACKUP_DIR="/root/db-backup"
TEMP_DIR="/tmp/marzban_backup"
DB_BACKUP_DIR="$TEMP_DIR/var/lib/$DB_NAME/mysql/db-backup"

# Get the server's IP address
SERVER_IP=$(hostname -I | awk '{print $1}')

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$DB_BACKUP_DIR"

# Function to backup database
backup_database() {
    # Determine the correct dump command based on DB_TYPE
    if [ "$DB_TYPE" = "mariadb" ]; then
        DUMP_CMD="mariadb-dump"
    elif [ "$DB_TYPE" = "mysql" ]; then
        DUMP_CMD="mysqldump"
    else
        echo "Unsupported database type: $DB_TYPE"
        exit 1
    fi

    # Get list of databases
    databases=$(docker exec $CONTAINER_NAME $DB_TYPE -h 127.0.0.1 --user=$USER --password=$DB_PASSWORD -e "SHOW DATABASES;" 2>/dev/null | tr -d "| " | grep -v Database)

    # Backup each database
    for db in $databases; do
        # Check if the database is not a system database
        if [[ "$db" != "information_schema" && "$db" != "mysql" && "$db" != "performance_schema" && "$db" != "sys" ]]; then
            # Backup the database and save it as a .sql file
            if ! docker exec $CONTAINER_NAME $DUMP_CMD -h 127.0.0.1 --force --opt --user=$USER --password=$DB_PASSWORD --databases $db > "$DB_BACKUP_DIR/$db.sql" 2>/dev/null; then
                echo "Error dumping database: $db" >&2
            fi
        fi
    done
}

# Function to backup Marzban
backup_marzban() {
    backup_database
    
    # Copy Marzban directories excluding 'mysql'
    rsync -av --exclude='mysql' /opt/marzban "$TEMP_DIR/opt" >/dev/null 2>&1
    rsync -av --exclude='mysql' /var/lib/marzban "$TEMP_DIR/var/lib" >/dev/null 2>&1
}

# Function to backup Marzneshin
backup_marzneshin() {
    backup_database
    
    # Copy Marzneshin directories
    mkdir -p "$TEMP_DIR/etc/opt"
    rsync -av /etc/opt/marzneshin "$TEMP_DIR/etc/opt" >/dev/null 2>&1
    
    mkdir -p "$TEMP_DIR/var/lib"
    rsync -av /var/lib/marzneshin "$TEMP_DIR/var/lib" >/dev/null 2>&1
}

# Determine which system is installed based on DB_NAME
if [ "$DB_NAME" = "marzban" ]; then
    SYSTEM="Marzban"
    backup_marzban
elif [ "$DB_NAME" = "marzneshin" ]; then
    SYSTEM="Marzneshin"
    backup_marzneshin
else
    echo "Unknown system. DB_NAME should be either 'marzban' or 'marzneshin'"
    exit 1
fi

# Change to the temporary directory
cd "$TEMP_DIR" || exit

# Create a zip file with all backups
CAPITALIZED_SYSTEM=$(echo "$SYSTEM" | sed 's/./\U&/')
ZIP_FILE="$BACKUP_DIR/${CAPITALIZED_SYSTEM}_Backup_$(date +%F).zip"
if ! zip -r "$ZIP_FILE" . >/dev/null 2>&1; then
    echo "Error creating zip file" >&2
    exit 1
fi

# Send the zip file to Telegram with caption
CAPTION=$'Backup '"$SYSTEM"$'\n'"$SERVER_IP"

if ! curl -s -F "chat_id=$CHAT_ID" -F "document=@$ZIP_FILE" -F "caption=$CAPTION" "https://api.telegram.org/bot$TOKEN/sendDocument" >/dev/null 2>&1; then
    echo "Error sending file to Telegram" >&2
    exit 1
fi

# Clean up temporary files
rm -rf "$TEMP_DIR"

# Final success message
echo "Backup file for $SYSTEM created and sent successfully."
