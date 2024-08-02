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

-- Create table for cleanup log
CREATE TABLE IF NOT EXISTS cleanup_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cleanup_time DATETIME NOT NULL
);

-- Create a table for storing hourly usage data
CREATE TABLE IF NOT EXISTS user_hourly_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_last_hour BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create procedure to insert current usage for all users
CREATE OR REPLACE PROCEDURE insert_current_usage()
BEGIN
    SELECT 'Insertion is handled in Python code' AS message;
END;

-- Update the calculate_hourly_usage procedure to insert hourly data
CREATE OR REPLACE PROCEDURE calculate_hourly_usage()
BEGIN
    INSERT INTO user_hourly_usage (user_id, username, usage_in_last_hour, timestamp)
    SELECT 
        u.user_id,
        u.username,
        COALESCE(new.total_usage - old.total_usage, 0) AS usage_in_last_hour,
        DATE_FORMAT(NOW(), '%Y-%m-%d %H:00:00') AS timestamp
    FROM 
        (SELECT DISTINCT user_id, MAX(timestamp) as max_timestamp 
         FROM user_usage_snapshots 
         GROUP BY user_id) latest
    JOIN user_usage_snapshots u ON u.user_id = latest.user_id AND u.timestamp = latest.max_timestamp
    LEFT JOIN user_usage_snapshots new ON u.user_id = new.user_id AND new.timestamp = latest.max_timestamp
    LEFT JOIN user_usage_snapshots old ON u.user_id = old.user_id AND old.timestamp = (
        SELECT MAX(timestamp) 
        FROM user_usage_snapshots 
        WHERE user_id = u.user_id AND timestamp < new.timestamp
    )
    WHERE
        new.timestamp > DATE_SUB(NOW(), INTERVAL 1 HOUR);

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_last_hour
    FROM user_hourly_usage
    WHERE timestamp = (SELECT MAX(timestamp) FROM user_hourly_usage);
END;

-- Create procedure to clean up old data
CREATE OR REPLACE PROCEDURE cleanup_old_data()
BEGIN
    DELETE FROM user_usage_snapshots
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    DELETE FROM user_hourly_usage
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    INSERT INTO cleanup_log (cleanup_time) VALUES (NOW());
END;

-- Create a procedure to retrieve historical hourly usage data
CREATE OR REPLACE PROCEDURE get_historical_hourly_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT user_id, username, usage_in_last_hour, timestamp
    FROM user_hourly_usage
    WHERE timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY timestamp, user_id;
END;
