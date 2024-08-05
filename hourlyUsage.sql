-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS UserUsageAnalytics;
USE UserUsageAnalytics;

-- Create table for storing usage snapshots
CREATE TABLE IF NOT EXISTS UsageSnapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    timestamp DATETIME NOT NULL,
    total_usage BIGINT NOT NULL,
    INDEX idx_user_timestamp (user_id, timestamp)
);

-- Create table for cleanup log
CREATE TABLE IF NOT EXISTS CleanupLog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cleanup_time DATETIME NOT NULL
);

-- Create a new table for storing periodic usage data
CREATE TABLE IF NOT EXISTS PeriodicUsage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_period BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    report_number INT NOT NULL,
    INDEX idx_user_report (user_id, report_number)
);

-- Create a view that links to the users table in the main database
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_users AS
SELECT id, username, used_traffic
FROM marzban.users;

-- Create procedure to insert current usage for all users
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage(IN p_timestamp DATETIME)
BEGIN
    INSERT INTO UsageSnapshots (user_id, timestamp, total_usage)
    SELECT id, p_timestamp, COALESCE(used_traffic, 0)
    FROM v_users;
END //
DELIMITER ;

-- Create procedure to calculate usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE calculate_usage()
BEGIN
    DECLARE current_report_number INT;
    
    -- Get the current report number
    SELECT COALESCE(MAX(report_number), 0) + 1 INTO current_report_number FROM PeriodicUsage;
    
    INSERT INTO PeriodicUsage (user_id, username, usage_in_period, timestamp, report_number)
    SELECT 
        u.id AS user_id,
        u.username,
        COALESCE(new.total_usage - old.total_usage, 0) AS usage_in_period,
        new.timestamp AS timestamp,
        current_report_number AS report_number
    FROM 
        v_users u
    LEFT JOIN UsageSnapshots new ON u.id = new.user_id AND new.timestamp = (
        SELECT MAX(timestamp) FROM UsageSnapshots WHERE user_id = u.id
    )
    LEFT JOIN UsageSnapshots old ON u.id = old.user_id AND old.timestamp = (
        SELECT MAX(timestamp) FROM UsageSnapshots 
        WHERE user_id = u.id AND timestamp < new.timestamp
    )
    WHERE
        new.timestamp > (SELECT COALESCE(MAX(timestamp), '1970-01-01') FROM PeriodicUsage)
    ORDER BY u.id;

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE report_number = current_report_number
    ORDER BY user_id;
END //
DELIMITER ;

-- Create procedure to clean up old data
DELIMITER //
CREATE OR REPLACE PROCEDURE cleanup_old_data(IN p_current_time DATETIME)
BEGIN
    DELETE FROM UsageSnapshots
    WHERE timestamp < DATE_SUB(p_current_time, INTERVAL 1 YEAR);
    
    DELETE FROM PeriodicUsage
    WHERE timestamp < DATE_SUB(p_current_time, INTERVAL 1 YEAR);
    
    -- Reset auto-increment value
    ALTER TABLE PeriodicUsage AUTO_INCREMENT = 1;
    
    INSERT INTO CleanupLog (cleanup_time) VALUES (p_current_time);
END //
DELIMITER ;

-- Create procedure to retrieve historical usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE get_historical_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY user_id, report_number;
END //
DELIMITER ;
