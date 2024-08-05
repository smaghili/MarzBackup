-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS UserUsageAnalytics;

-- Switch to the UserUsageAnalytics database
USE UserUsageAnalytics;

-- Create a function to get current Tehran time
DELIMITER //
CREATE OR REPLACE FUNCTION get_tehran_time() 
RETURNS DATETIME
DETERMINISTIC
BEGIN
  RETURN CONVERT_TZ(NOW(), 'UTC', 'Asia/Tehran');
END //
DELIMITER ;

-- Create table for storing usage snapshots if it doesn't exist
CREATE TABLE IF NOT EXISTS UsageSnapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    timestamp DATETIME NOT NULL,
    total_usage BIGINT NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create table for cleanup log if it doesn't exist
CREATE TABLE IF NOT EXISTS CleanupLog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cleanup_time DATETIME NOT NULL
);

-- Create or replace the view that links to the users table in the main database
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_users AS
SELECT id, username, used_traffic
FROM marzban.users;

-- Create or replace procedure to insert current usage for all users
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage(IN p_timestamp DATETIME)
BEGIN
    INSERT INTO UsageSnapshots (user_id, username, timestamp, total_usage)
    SELECT id, username, p_timestamp, COALESCE(used_traffic, 0)
    FROM v_users;
END //
DELIMITER ;

-- Create or replace procedure to calculate usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE calculate_usage()
BEGIN
    DECLARE last_report_time DATETIME;
    
    -- Get the timestamp of the last report
    SELECT COALESCE(MAX(timestamp), DATE_SUB(get_tehran_time(), INTERVAL 5 MINUTE)) 
    INTO last_report_time FROM UsageSnapshots;
    
    -- Calculate and return the usage data
    SELECT 
        u.id AS user_id,
        u.username,
        COALESCE(new.total_usage - COALESCE(old.total_usage, 0), 0) AS usage_in_period,
        get_tehran_time() AS timestamp
    FROM 
        v_users u
    LEFT JOIN UsageSnapshots new ON u.id = new.user_id AND new.timestamp = (
        SELECT MAX(timestamp) FROM UsageSnapshots WHERE user_id = u.id AND timestamp <= get_tehran_time()
    )
    LEFT JOIN UsageSnapshots old ON u.id = old.user_id AND old.timestamp = (
        SELECT MAX(timestamp) FROM UsageSnapshots 
        WHERE user_id = u.id AND timestamp <= last_report_time
    )
    WHERE
        new.timestamp > last_report_time OR old.timestamp IS NULL
    ORDER BY u.id;
END //
DELIMITER ;

-- Create or replace procedure to clean up old data
DELIMITER //
CREATE OR REPLACE PROCEDURE cleanup_old_data(IN p_current_time DATETIME)
BEGIN
    DELETE FROM UsageSnapshots
    WHERE timestamp < DATE_SUB(p_current_time, INTERVAL 1 YEAR);
    
    INSERT INTO CleanupLog (cleanup_time) VALUES (p_current_time);
END //
DELIMITER ;

-- Create or replace procedure to retrieve historical usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE get_historical_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT 
        s1.user_id,
        s1.username,
        s1.total_usage - COALESCE(s2.total_usage, 0) AS usage_in_period,
        s1.timestamp
    FROM 
        UsageSnapshots s1
    LEFT JOIN UsageSnapshots s2 ON 
        s1.user_id = s2.user_id AND 
        s2.timestamp = (
            SELECT MAX(timestamp) 
            FROM UsageSnapshots 
            WHERE user_id = s1.user_id AND timestamp < s1.timestamp
        )
    WHERE 
        s1.timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY 
        s1.user_id, s1.timestamp;
END //
DELIMITER ;
