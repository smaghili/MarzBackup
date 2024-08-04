-- Modify the PeriodicUsage table
DROP TABLE IF EXISTS PeriodicUsage;
CREATE TABLE PeriodicUsage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    usage_in_period BIGINT NOT NULL,
    timestamp DATETIME NOT NULL,
    report_number INT NOT NULL,
    INDEX idx_user_report (user_id, report_number)
);

-- Modify the calculate_usage procedure
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
        NOW() AS timestamp,
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

-- Add a procedure to reset the auto-increment value
DELIMITER //
CREATE OR REPLACE PROCEDURE reset_periodic_usage_auto_increment()
BEGIN
    SET @max_id = (SELECT COALESCE(MAX(id), 0) FROM PeriodicUsage);
    SET @sql = CONCAT('ALTER TABLE PeriodicUsage AUTO_INCREMENT = ', @max_id + 1);
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
END //
DELIMITER ;

-- Modify the cleanup procedure to reset auto-increment after cleanup
DELIMITER //
CREATE OR REPLACE PROCEDURE cleanup_old_data()
BEGIN
    DELETE FROM UsageSnapshots
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    DELETE FROM PeriodicUsage
    WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 2 MONTH);
    
    CALL reset_periodic_usage_auto_increment();
    
    INSERT INTO CleanupLog (cleanup_time) VALUES (NOW());
END //
DELIMITER ;
