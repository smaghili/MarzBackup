-- Update the insert_current_usage procedure to accept a timestamp parameter
DELIMITER //
CREATE OR REPLACE PROCEDURE insert_current_usage(IN current_timestamp DATETIME)
BEGIN
    INSERT INTO user_usage_snapshots (user_id, timestamp, total_usage)
    SELECT id, current_timestamp, COALESCE(used_traffic, 0)
    FROM v_users;
END //

-- Update the calculate_hourly_usage procedure to accept a timestamp parameter
CREATE OR REPLACE PROCEDURE calculate_hourly_usage(IN current_timestamp DATETIME)
BEGIN
    INSERT INTO user_hourly_usage (user_id, username, usage_in_last_hour, timestamp)
    SELECT 
        u.id AS user_id,
        u.username,
        COALESCE(new.total_usage - old.total_usage, 0) AS usage_in_last_hour,
        current_timestamp AS timestamp
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
        new.timestamp > DATE_SUB(current_timestamp, INTERVAL 1 HOUR);

    -- Return the inserted data for display
    SELECT user_id, username, usage_in_last_hour, timestamp
    FROM user_hourly_usage
    WHERE timestamp = current_timestamp;
END //

DELIMITER ;