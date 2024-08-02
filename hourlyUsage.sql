-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS user_usage_tracking;
USE user_usage_tracking;

-- Create table for storing usage snapshots
CREATE TABLE IF NOT EXISTS user_usage_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    timestamp DATETIME NOT NULL,
    total_usage BIGINT NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create table for storing hourly usage data
CREATE TABLE IF NOT EXISTS user_hourly_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_last_hour BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create procedure to insert current usage for all users
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage(IN current_timestamp DATETIME)
BEGIN
    INSERT INTO user_usage_snapshots (user_id, timestamp, total_usage)
    SELECT id, current_timestamp, COALESCE(used_traffic, 0)
    FROM marzban.users;
END //

-- Create procedure to calculate and insert hourly usage data
CREATE OR REPLACE PROCEDURE calculate_hourly_usage(IN current_timestamp DATETIME)
BEGIN
    INSERT INTO user_hourly_usage (user_id, username, usage_in_last_hour, timestamp)
    SELECT 
        u.id AS user_id,
        u.username,
        COALESCE(new.total_usage - COALESCE(old.total_usage, 0), 0) AS usage_in_last_hour,
        current_timestamp AS timestamp
    FROM 
        marzban.users u
    LEFT JOIN user_usage_snapshots new ON u.id = new.user_id AND new.timestamp = (
        SELECT MAX(timestamp) FROM user_usage_snapshots WHERE user_id = u.id AND timestamp <= current_timestamp
    )
    LEFT JOIN user_usage_snapshots old ON u.id = old.user_id AND old.timestamp = (
        SELECT MAX(timestamp) FROM user_usage_snapshots 
        WHERE user_id = u.id AND timestamp < DATE_SUB(current_timestamp, INTERVAL 1 HOUR)
    )
    WHERE
        new.timestamp > DATE_SUB(current_timestamp, INTERVAL 1 HOUR);

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_last_hour, timestamp
    FROM user_hourly_usage
    WHERE timestamp = current_timestamp;
END //

DELIMITER ;
