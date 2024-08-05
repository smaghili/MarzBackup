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
    timestamp DATETIME NOT NULL,
    total_usage BIGINT NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
) ENGINE=InnoDB;

-- Create table for cleanup log if it doesn't exist
CREATE TABLE IF NOT EXISTS CleanupLog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cleanup_time DATETIME NOT NULL
) ENGINE=InnoDB;

-- Create a new table for storing periodic usage data if it doesn't exist
CREATE TABLE IF NOT EXISTS PeriodicUsage (
    user_id INT NOT NULL,
    report_number INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_period BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (user_id, report_number),
    INDEX idx_report_number (report_number)
) ENGINE=InnoDB;

-- Create or replace the view that links to the users table in the main database
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_users AS
SELECT id, username, used_traffic
FROM marzban.users;

-- Create or replace procedure to insert current usage for all users
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage(IN p_timestamp DATETIME)
BEGIN
    INSERT INTO UsageSnapshots (user_id, timestamp, total_usage)
    SELECT id, p_timestamp, COALESCE(used_traffic, 0)
    FROM v_users;
END //
DELIMITER ;

-- Create or replace procedure to calculate usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE calculate_usage()
BEGIN
    DECLARE current_report_number INT;
    DECLARE last_report_time DATETIME;
    
    -- Get the current report number
    SELECT COALESCE(MAX(report_number), 0) + 1 INTO current_report_number FROM PeriodicUsage;
    
    -- Get the timestamp of the last report
    SELECT COALESCE(MAX(timestamp), DATE_SUB(get_tehran_time(), INTERVAL 5 MINUTE)) 
    INTO last_report_time FROM PeriodicUsage;
    
    INSERT INTO PeriodicUsage (user_id, report_number, username, usage_in_period, timestamp)
    SELECT 
        u.id AS user_id,
        current_report_number AS report_number,
        u.username,
        CASE
            WHEN current_report_number = 1 THEN 0
            ELSE COALESCE(new.total_usage - COALESCE(old.total_usage, 0), 0)
        END AS usage_in_period,
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
    ON DUPLICATE KEY UPDATE
        username = u.username,
        usage_in_period = CASE
            WHEN current_report_number = 1 THEN 0
            ELSE COALESCE(new.total_usage - COALESCE(old.total_usage, 0), 0)
        END,
        timestamp = get_tehran_time();

    -- Return the inserted/updated data for display
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE report_number = current_report_number
    ORDER BY user_id, report_number;
END //
DELIMITER ;

-- Create or replace procedure to clean up old data
DELIMITER //
CREATE OR REPLACE PROCEDURE cleanup_old_data(IN p_current_time DATETIME)
BEGIN
    DELETE FROM UsageSnapshots
    WHERE timestamp < DATE_SUB(p_current_time, INTERVAL 1 YEAR);
    
    DELETE FROM PeriodicUsage
    WHERE timestamp < DATE_SUB(p_current_time, INTERVAL 1 YEAR);
    
    INSERT INTO CleanupLog (cleanup_time) VALUES (p_current_time);
END //
DELIMITER ;

-- Create or replace procedure to retrieve historical usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE get_historical_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY user_id, report_number;
END //
DELIMITER ;

-- Create a function to check auto_increment settings
DELIMITER //
CREATE OR REPLACE FUNCTION check_auto_increment_settings()
RETURNS VARCHAR(1000)
DETERMINISTIC
BEGIN
    DECLARE result VARCHAR(1000);
    SET result = CONCAT(
        'auto_increment_increment: ', @@auto_increment_increment, 
        ', auto_increment_offset: ', @@auto_increment_offset
    );
    RETURN result;
END //
DELIMITER ;
