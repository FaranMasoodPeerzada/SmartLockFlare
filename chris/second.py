import random
import requests
import pytz
from datetime import datetime, timedelta
import time

def generate_passcode(lock_id, start_date, end_date, coworker_name, max_retries=3, retry_delay=2):
    if not lock_id or not start_date or not end_date:
        app.logger.warning(f"Missing parameters for passcode generation: lock_id={lock_id}, start_date={start_date}, end_date={end_date}")
        return None
    
    for attempt in range(max_retries):
        try:
            passcode = random.randint(100000, 999999)
            url = f'{base_url}v3/keyboardPwd/add'
            selected_date_time = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
            start_date = selected_date_time - timedelta(minutes=15)
            end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
            reservation_date = datetime.now(tz=pytz.utc)
            
            app.logger.info(f"Attempt {attempt + 1}: Selected datetime: {selected_date_time}, adjusted start_date: {start_date}, end_date: {end_date}")
            
            data = {
                'clientId': app.config['CLIENT_ID'],
                'accessToken': get_access_token(),
                'lockId': lock_id,
                'keyboardPwd': passcode,
                'keyboardPwdName': coworker_name,
                'startDate': round(start_date.timestamp() * 1000),
                'endDate': round(end_date.timestamp() * 1000),
                'addType': 2,
                'date': round(reservation_date.timestamp() * 1000),
            }
            
            app.logger.info(f"Data payload for passcode generation: {data}")
            response = requests.post(url, data=data)
            response_data = response.json()
            
            app.logger.info(f"generate_passcode response: {response_data} for data: {data}")
            
            if 'keyboardPwdId' in response_data:
                return passcode
            else:
                app.logger.warning(f'Failed generating passcode from data {response_data}, and dates {start_date}, {end_date}, {reservation_date}')
            
        except Exception as e:
            app.logger.error(f"Exception during passcode generation attempt {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:
            app.logger.info(f"Retrying passcode generation after {retry_delay} seconds...")
            time.sleep(retry_delay)

    app.logger.error(f"Failed to generate passcode after {max_retries} attempts.")
    return None
