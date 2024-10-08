def generate_passcode(lock_id, start_date, end_date, coworker_name, max_retries=3, initial_retry_delay=10):
    if not lock_id or not start_date or not end_date:
        app.logger.warning(f"Missing parameters for passcode generation: lock_id={lock_id}, start_date={start_date}, end_date={end_date}")
        return None

    attempt = 0
    retry_delay = initial_retry_delay  # Start with the initial retry delay
    
    while attempt < max_retries:
        try:
            passcode = random.randint(100000, 999999)
            url = f'{base_url}v3/keyboardPwd/add'
            
            # Convert start_date and end_date to datetime objects if they are not already
            if isinstance(start_date, str):
                selected_date_time = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
            else:
                selected_date_time = start_date

            start_date = selected_date_time - timedelta(minutes=15)

            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
            else:
                end_date = end_date

            reservation_date = datetime.now(tz=pytz.utc)
            app.logger.info(f"Selected datetime: {selected_date_time}, adjusted start_date: {start_date}, end_date: {end_date}")
            
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
            elif response_data.get('errcode') == -3003:  # Gateway busy
                attempt += 1
                app.logger.warning(f"Gateway is busy, Attempt {attempt}/{max_retries}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff: double the retry delay
            else:
                app.logger.warning(f"Failed generating passcode: {response_data}. Start date: {start_date}, End date: {end_date}, Reservation date: {reservation_date}")
                return None
        
        except Exception as e:
            app.logger.error(f"Exception during passcode generation: {e}")
            return None
    
    app.logger.error(f"Failed to generate passcode after {max_retries} attempts due to gateway being busy.")
    return None
