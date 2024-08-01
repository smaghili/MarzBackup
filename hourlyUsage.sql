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

-- Create a new table for storing hourly usage data
CREATE TABLE IF NOT EXISTS user_hourly_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_last_hour BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create a view that links to the users table in the main database
-- Note: Adjust the database name if your main database is not named 'marzban'
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_users AS
SELECT id, username, used_traffic
FROM marzban.users;

-- Create procedure to insert current usage for all users
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage()
BEGIN
    INSERT INTO user_usage_snapshots (user_id, timestamp, total_usage)
    SELECT id, NOW(), COALESCE(used_traffic, 0)
    FROM v_users;
END //

-- Update the calculate_recent_usage procedure to insert hourly data
CREATE OR REPLACE PROCEDURE calculate_hourly_usage()
BEGIN
    INSERT INTO user_hourly_usage (user_id, username, usage_in_last_hour, timestamp)
    SELECT 
        u.id AS user_id,
        u.username,
        COALESCE(new.total_usage - old.total_usage, 0) AS usage_in_last_hour,
        DATE_FORMAT(NOW(), '%Y-%m-%d %H:00:00') AS timestamp
    FROM 
        v_users u
    LEFT JOIN user_usage_snapshots new ON u.id = new.user_id AND new.timestamp = (
        SELECT MAX(timestamp) FROM user_usage_snapshots WHERE user_id = u.id
    )
    LEFT JOIN user_usage_snapshots old ON u.id = old.user_id AND old.timestamp = (
        SELECT MAX(timestamp) FROM user_usage_snapshots 
        WHERE user_id = u.id AND timestamp < new.timestamp
    )
    WHERE
        new.timestamp > DATE_SUB(NOW(), INTERVAL 1 HOUR);

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_last_hour
    FROM user_hourly_usage
    WHERE timestamp = (SELECT MAX(timestamp) FROM user_hourly_usage);
END //

-- Create procedure to clean up old data
CREATE OR REPLACE PROCEDURE cleanup_old_data()
BEGIN
    DELETE FROM user_usage_snapshots
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    DELETE FROM user_hourly_usage
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    INSERT INTO cleanup_log (cleanup_time) VALUES (NOW());
END //

-- Create a new procedure to retrieve historical hourly usage data
CREATE OR REPLACE PROCEDURE get_historical_hourly_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT user_id, username, usage_in_last_hour, timestamp
    FROM user_hourly_usage
    WHERE timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY timestamp, user_id;
END //

DELIMITER ;
