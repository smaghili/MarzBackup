-- ... (بقیه کد بدون تغییر باقی می‌ماند)

-- Create or replace procedure to calculate usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE calculate_usage()
BEGIN
    DECLARE current_report_number INT;
    DECLARE last_report_time DATETIME;
    
    -- Get the current report number
    SELECT COALESCE(MAX(report_number), 0) + 1 INTO current_report_number FROM PeriodicUsage;
    
    -- Get the timestamp of the last report
    SELECT COALESCE(MAX(timestamp), DATE_SUB(get_tehran_time(), INTERVAL 5 MINUTE)) INTO last_report_time FROM PeriodicUsage;
    
    INSERT INTO PeriodicUsage (user_id, username, usage_in_period, timestamp, report_number)
    SELECT 
        u.id AS user_id,
        u.username,
        CASE
            WHEN current_report_number = 1 THEN 0
            ELSE COALESCE(new.total_usage - COALESCE(old.total_usage, 0), 0)
        END AS usage_in_period,
        get_tehran_time() AS timestamp,
        current_report_number AS report_number
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
    ORDER BY u.id
    ON DUPLICATE KEY UPDATE
        username = VALUES(username),
        usage_in_period = VALUES(usage_in_period),
        timestamp = VALUES(timestamp);

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE report_number = current_report_number
    ORDER BY report_number, user_id;
END //
DELIMITER ;

-- Create or replace procedure to retrieve historical usage data
DELIMITER //
CREATE OR REPLACE PROCEDURE get_historical_usage(IN p_start_time DATETIME, IN p_end_time DATETIME)
BEGIN
    SELECT user_id, username, usage_in_period, timestamp, report_number
    FROM PeriodicUsage
    WHERE timestamp BETWEEN p_start_time AND p_end_time
    ORDER BY report_number, user_id;
END //
DELIMITER ;
