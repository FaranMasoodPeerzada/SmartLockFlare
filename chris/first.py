import time

def generate_passcode_with_retry(door_id, from_time, to_time, coworker_name, max_retries=3, retry_delay=2):
    retries = 0
    passcode = None

    while retries < max_retries:
        passcode = generate_passcode(door_id, from_time, to_time, coworker_name)
        
        if passcode is not None:
            break
        
        retries += 1
        app.logger.warning(f"Failed to generate passcode. Attempt {retries}/{max_retries}. Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
    
    if passcode is None:
        app.logger.error(f"Failed to generate passcode after {max_retries} attempts.")
        # Handle the fallback here, e.g., by notifying the user, logging the incident, or generating a default passcode.
    
    return passcode

wellness_door_passcode = generate_passcode_with_retry(wellness_door_id, from_time, to_time, coworker_name)
if wellness_door_passcode is not None:
    app.logger.info(f"Generated passcode for main door: {wellness_door_passcode}")
    passcodes.append(wellness_door_passcode)
else:
    app.logger.error("Unable to generate a passcode for the wellness door. Please check the system.")
