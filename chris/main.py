from flask import Flask, request, jsonify
import requests
import os, pathlib
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import pytz
import random
import uuid, logging
import multiprocessing as mp

app_path = pathlib.Path(os.path.abspath(__file__)).parent
load_dotenv(app_path / '.env')
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# note: main doors do not have a resouce associated with them
resource_to_lock_mapping = {
    1414843560:	"EC:75:5D:81:64:FF", # Fidiou 8pax
    1415078581:	"B1:48:81:51:79:B5", # Fidiou 6pax L
    1415084640:	"FA:37:8F:4B:3C:81", # Fidiou 6pax R
    1414925968:	"D7:2C:71:36:9C:C5", # Fidiou 3pax
    1414944050:	"54:6C:1D:21:CE:CE", # Fidiou Podcast Room
    1414957789: "D6:DB:F1:2E:24:54", # Fidiou Sleeping Pod
    1415083298:	"67:6C:FF:02:84:82", # Patmou Podcast
    1415083300:	"92:E8:46:4D:50:12", # Patmou BreakRoom
    1415079490:	"F9:73:37:A9:E1:E5", # Patmou MR3
    1415109087:	"96:3A:98:2D:24:18", # Patmou MR4
    1415109088:	"A0:FD:E4:9F:9A:14", # Patmou MR5
    1415083396:	"FE:74:91:79:FB:F2", # Patmou Board Room
    1415108987:	"0D:A9:BA:99:28:F6", # Test lock 6pax
    1415111440: "16:D7:E6:DD:23:34", # Test lock 8pax

}

my_session = {'modified': None, 'nexudus_modified': False, 'access_token': '', 'refresh_token': ''}


class Config:
    CLIENT_ID = os.environ.get('CLIENT_ID')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
    USERNAME = os.environ.get('SCIENER_USERNAME')
    PASSWORD = os.environ.get('SCIENER_PASSWORD')
    PASSCODE_LENGTH = os.environ.get('PASSCODE_LENGTH')
    NEXUDUS_USERNAME = os.environ.get('NEXUDUS_USERNAME')
    NEXUDUS_PASSWORD = os.environ.get('NEXUDUS_PASSWORD')
    NEXUDUS_CUSTOM_FIELD_NAME = os.environ.get('NEXUDUS_CUSTOM_FIELD_NAME')


app.config.from_object(Config)

base_url = "https://euapi.sciener.com/"


def get_access_token():
    if 'expires_at' in my_session and my_session['expires_at'].replace(tzinfo=pytz.utc) > datetime.now(tz=pytz.utc):
        return my_session['access_token']
    elif my_session['modified']:
        return refresh_token()
    else:
        return get_token()


def get_token():
    url = f'{base_url}oauth2/token'
    data = {
        'clientId': app.config['CLIENT_ID'],
        'clientSecret': app.config['CLIENT_SECRET'],
        'username': app.config['USERNAME'],
        'password': app.config['PASSWORD'],
    }

    response = requests.post(url, data=data)
    token_data = response.json()

    app.logger.info(f"token_data: {token_data}")

    if 'access_token' in token_data:
        my_session['access_token'] = token_data['access_token']
        my_session['refresh_token'] = token_data['refresh_token']
        my_session['expires_at'] = datetime.now(tz=pytz.utc) + timedelta(seconds=token_data['expires_in'])
        my_session['uid'] = token_data['uid']

    return token_data['access_token']


def refresh_token():
    url = f'{base_url}oauth2/token'

    data = {
        'clientId': app.config['CLIENT_ID'],
        'clientSecret': app.config['CLIENT_SECRET'],
        'grant_type': 'refresh_token',
        'refresh_token': my_session.get('refresh_token')
    }

    response = requests.post(url, data=data)
    token_data = response.json()

    if 'access_token' in token_data:
        my_session['access_token'] = token_data['access_token']
        my_session['expires_at'] = datetime.now(tz=pytz.utc) + timedelta(seconds=token_data['expires_in'])
        my_session['modified'] = True

    return my_session['access_token']


def get_lock_id_by_mac(lock_mac):
    if not lock_mac:
        return None

    page_no = 1
    found_lock = None

    url = f'{base_url}v3/lock/list'

    while True:
        params = {
            'clientId': app.config['CLIENT_ID'],
            'accessToken': get_access_token(),
            'pageNo': page_no,
            'pageSize': 20,
            'date': int(time.time() * 1000)
        }
        response = requests.get(url, params=params)
        response_data = response.json()

        # Check each lock in the current page
        if 'list' not in response_data or not response_data['list']:
            app.logger.warning(f"No locks found on page {page_no}")
            break

        for lock in response_data['list']:
            app.logger.info(f"Checking lock: {lock}")
            if lock.get('lockMac') == lock_mac:
                found_lock = lock
                break

        if found_lock:
            app.logger.info(f"Found lock with lock_mac: {lock_mac}, lock_id: {found_lock['lockId']}")
            break

        page_no += 1

    if found_lock:
        return found_lock['lockId']
    else:
        app.logger.warning(f"Can't get lockId, lockMac address is probably wrong: {lock_mac}")
        return None


def list_passcodes(lock_id, page_no):
    url = f"{base_url}v3/lock/listKeyboardPwd"
    params = {
        'clientId': app.config['CLIENT_ID'],
        'accessToken': get_access_token(),
        'lockId': lock_id,
        'date': int(time.time() * 1000),
        'pageNo': page_no,
        'pageSize': 20  # Adjust pageSize according to expected number of passcodes
    }
    response = requests.get(url, params=params)
    response_data = response.json()

    return response_data


def delete_passcode(lock_id, keyboard_pwd_id):
    current_time = int(time.time() * 1000)

    # API request to delete a passcode
    url = f"{base_url}v3/keyboardPwd/delete"
    data = {
        'clientId': app.config['CLIENT_ID'],
        'accessToken': get_access_token(),
        'lockId': lock_id,
        'keyboardPwdId': keyboard_pwd_id,
        'deleteType': 2,  # Assuming deletion via Wi-Fi or gateway
        'date': current_time
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return True
    else:
        return False

def generate_passcode(lock_id, start_date, end_date, coworker_name):
    if not lock_id or not start_date or not end_date:
        app.logger.warning(f"Missing parameters for passcode generation: lock_id={lock_id}, start_date={start_date}, end_date={end_date}")
        return None
    try:
        passcode = random.randint(100000, 999999)
        url = f'{base_url}v3/keyboardPwd/add'
        selected_date_time = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)# Subtract 15 minutes using timedelta
        start_date = selected_date_time - timedelta(minutes=15)
        end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
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
        else:
            app.logger.warning(f'Failed generating passcode from data {response_data}, and dates {start_date}, {end_date}, {reservation_date}')
            return None
            
    except Exception as e:
        app.logger.error(f"Exception during passcode generation: {e}")
        return None



# Define the mapping of MAC addresses to door names
door_names = {
    "EC:75:5D:81:64:FF": "Fidiou 8pax",
    "B1:48:81:51:79:B5": "Fidiou 6pax L",
    "FA:37:8F:4B:3C:81": "Fidiou 6pax R",
    "D7:2C:71:36:9C:C5": "Fidiou 3pax",
    "54:6C:1D:21:CE:CE": "Fidiou Podcast Room",
    "D6:DB:F1:2E:24:54": "Fidiou Sleeping Pod",
    "FD:64:42:39:E5:54": "Fidiou Wellness Entrance",
    "67:6C:FF:02:84:82": "Patmou Podcast",
    "92:E8:46:4D:50:12": "Patmou BreakRoom",
    "F9:73:37:A9:E1:E5": "Patmou MR3",
    "96:3A:98:2D:24:18": "Patmou MR4",
    "A0:FD:E4:9F:9A:14": "Patmou MR5",
    "FE:74:91:79:FB:F2": "Patmou 12pax",
    "E0:61:DA:79:64:45": "Patmou Staircase Access",
    "EE:4F:8C:5A:BE:97": "Patmou Lower Ground Floor Entrance",
    "0D:A9:BA:99:28:F6": "6 pax secondary", #test secondary 6pax
    "16:D7:E6:DD:23:34": "8 pax secondary", #test secondary 8pax
    "C2:DA:2B:DC:32:7D": "Main Door 1", # Main Door 1
    "C6:4A:85:44:B0:A8": "Main Door 2", # Main Door 2
    
    
}


def send_message(coworker_id, passcodes, coworker_name, lock_macs, from_time, to_time, resource_name, booking_number):
    # from_time_eet = datetime.strptime(from_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(
    #     pytz.timezone('Europe/Helsinki')).strftime("%Y-%m-%d %H:%M:%S")
    # to_time_eet = datetime.strptime(to_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(
    #     pytz.timezone('Europe/Helsinki')).strftime("%Y-%m-%d %H:%M:%S")

    # # Format the passcode information with door names instead of MAC addresses
    # passcode_info = '\n'.join([f'{door_names.get(lock_macs[i], "Unknown Door")}: {passcodes[i]}' for i in range(len(passcodes))])
    from_time_dt = datetime.strptime(from_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    to_time_dt = datetime.strptime(to_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    
    # Add 15 minutes to the from_time
    from_time_dt_adjusted = from_time_dt - timedelta(minutes=15)

    # Convert both times to EET timezone
    from_time_eet = from_time_dt_adjusted.astimezone(pytz.timezone('Europe/Helsinki')).strftime("%Y-%m-%d %H:%M:%S")
    to_time_eet = to_time_dt.astimezone(pytz.timezone('Europe/Helsinki')).strftime("%Y-%m-%d %H:%M:%S")

    # Format the passcode information with door names instead of MAC addresses
    #passcode_info = ' \n'.join([f'{door_names.get(lock_macs[i], "Unknown Door")}: {passcodes[i]}' for i in range(len(passcodes) - 1, -1, -1)])
    # added a hashtag after passcode
    passcode_info = ' \n '.join([f'{door_names.get(lock_macs[i], "Unknown Door")}: {passcodes[i]} #' for i in range(len(passcodes) - 1, -1, -1)])

    url = f'https://spaces.nexudus.com/api/spaces/coworkermessages'

    data = {
        'CoworkerId': coworker_id,
        'Subject': f'Passcode for your Booking for {resource_name} - #{booking_number}',
        'Body': (f'<!DOCTYPE html>'
                 f'<html>'
                 f'<head>'
                 f'<style>'
                 f'body {{ font-family: Arial, sans-serif; }}'
                 f'p {{ margin: 0; padding: 5px 0; }}'
                 f'.passcode-info {{ font-weight: bold; white-space: pre-line; }}'
                 f'</style>'
                 f'</head>'
                 f'<body>'
                 f'<p>Hello {coworker_name},</p>'
                 f'<p>Here are your access passcodes:</p>'
                 f'<p class="passcode-info">{passcode_info} </p>'
                 f'<p>Valid From: {from_time_eet}</p>'
                 f'<p>Valid To: {to_time_eet}</p>'
                 f'<p>Thank you,</p>'
                 f'<p>Your ViOS Team</p>'
                 f'<p><img src="https://cdn.shopify.com/s/files/1/0526/4670/7372/files/passcode-unlock_480x480.gif?v=1642520983" alt="Your GIF"></p>'
                 f'</body>'
                 f'</html>')
    }

    headers = {
        'Authorization': 'Bearer ' + get_nexudus_access_token()
    }

    response = requests.post(url, headers=headers, data=data)
    message_data = response.json()

    if response.status_code == 200:
        return True

    app.logger.warning(f'Failed adding coworker message to {coworker_name}')
    return False

# Define specific door IDs
single_passcode_door_ids = [
    1414843560,  # Fidiou 8pax
    1415117567,  # Fidiou 6pax L
    1415117471, # Fidiou 6pax RY
    1414925968, # Fidiou 3pax
    1414837599, # Fidiou 10 pax roof top
#    1415108987, # Test 6pax
#    1415111440, # Test 8pax 


    
#testing case 1 main door and 2 secondary doors
]
secondary_door_passcodes_ids_case1 = [ 1414944050, #Podcast Room
                                       1414957789, #Sleeping Pod
                                    #   1415108987, # Test1 6pax
                                    #   1415111440, # Test2 8pax
                                       
                                      ]
# the assumption is that the following may be made available to non-residents, hence passcode to two main doors
secondary_door_passcodes_ids_case2 = [ 1415083298, # Patmou Podcast
                                      1415083300, # Patmou BreakRoom
                                      1415079490, # Patmou MR3
                                      1415109087, # Patmou MR4
                                      1415109088, # Patmou MR5
                                      1415083396, # Patmou Board Room
                                      1415105546, # Patmou Meditation
                                      1415083399, # Patmou Massage Chair
                                      1415108987, # Test 6 pax resource as secondary
                                      1415111440, # Test 8pax resource as secondary
                                    
                                      ]

def handle_request(data):
    resource_id = data['ResourceId']
    app.logger.info(f"test Requested Resource id {resource_id}")
     
    from_time = data['FromTime']
    app.logger.info(f"from_time data: {from_time}")
    to_time = data['ToTime']
    coworker_name = data['CoworkerFullName']

    if resource_id is None:
        app.logger.warning("ResourceId missing")
        return jsonify({'error': 'ResourceId missing'}), 400

    contacts_booking = data['CancelIfNotPaid']
    tentative = data['Tentative']
    online = data['Online']

    app.logger.info(f"handle_request data: {data}")

    if tentative:
        app.logger.warning("Generating passcode is cancelled because the booking is not yet confirmed.")
        return

    if contacts_booking:
        invoice_paid = data['CoworkerInvoicePaid']
        if not invoice_paid and online:
            app.logger.warning("Generating passcode is cancelled because the booking from contacts is not yet paid.")
            return
        if not invoice_paid and data['InvoiceDate'] is None:
            invoice_paid = True

    lock_mac = resource_to_lock_mapping.get(resource_id)                                           
    lock_id = get_lock_id_by_mac(lock_mac)


    if not lock_id:
        app.logger.warning("No lock id")
        return

    passcodes = []
    lock_macs = []

    # Check if the resource ID is in the list of specific door IDs
    if resource_id in single_passcode_door_ids:
        # Generate a single passcode for the specific door
        app.logger.info(f"Single Resource id {resource_id}")
        
        single_passcode = generate_passcode(lock_id, from_time, to_time, coworker_name)
        app.logger.info(f"Generated single passcode for specific door: {single_passcode}")
        passcodes.append(single_passcode)
        lock_macs.append(lock_mac)
    elif resource_id in secondary_door_passcodes_ids_case1:
            app.logger.info(f"Requested Secondary door Resource id {resource_id}")
            requested_door_passcode = generate_passcode(lock_id, from_time, to_time, coworker_name)
            app.logger.info(f"Generated passcode for requested secondary door: {requested_door_passcode}")
            passcodes.append(requested_door_passcode)
            lock_macs.append(lock_mac)

            wellness_door_mac = "C2:DA:2B:DC:32:7D"  # Replace with the actual main door MAC
            wellness_door_id = get_lock_id_by_mac(wellness_door_mac)
            
            # Issue passcode for the main door
            wellness_door_passcode = generate_passcode(wellness_door_id, from_time, to_time, coworker_name)
            app.logger.info(f"Generated passcode for main door: {wellness_door_passcode}")
            passcodes.append(wellness_door_passcode)
            lock_macs.append(wellness_door_mac)
    elif resource_id in secondary_door_passcodes_ids_case2:
            app.logger.info(f"Requested Secondary door Resource id {resource_id}")
            requested_door_passcode = generate_passcode(lock_id, from_time, to_time, coworker_name)
            app.logger.info(f"Generated passcode for requested secondary door 1: {requested_door_passcode}")
            passcodes.append(requested_door_passcode)
            lock_macs.append(lock_mac)

            # Issue passcode for main door 1 - one main door too many?
          #  lower_gf_entrance_door_mac = "0D:A9:BA:99:28:F6"  # Replace with the actual main door MAC
           # lower_gf_entrance_door_id = get_lock_id_by_mac(lower_gf_entrance_door_mac)
          #  lower_gf_entrance_passcode = generate_passcode(lower_gf_entrance_door_id, from_time, to_time, coworker_name)
         #   app.logger.info(f"Generated passcode for Lower GF: {lower_gf_entrance_passcode}")
         #   passcodes.append(lower_gf_entrance_passcode)
         #   lock_macs.append(lower_gf_entrance_door_mac)
            
        # Issue passcode for a main door 2
            main_door_1_mac = "C2:DA:2B:DC:32:7D"  # Replace with the actual main door MAC
            main_door_1_door_id = get_lock_id_by_mac(main_door_1_mac)
            main_door_1_passcode = generate_passcode(main_door_1_door_id, from_time, to_time, coworker_name)
            app.logger.info(f"Generated passcode for main door 1: {main_door_1_passcode}")
            passcodes.append(main_door_1_passcode)
            lock_macs.append(main_door_1_mac) # Issue passcode for the Parking In
            # Issue passcode for a main door 3
            main_door_2_mac = "C6:4A:85:44:B0:A8"  # Replace with the actual main door MAC
            main_door_2_door_id = get_lock_id_by_mac(main_door_2_mac)
            main_door_2_passcode = generate_passcode(main_door_2_door_id, from_time, to_time, coworker_name)
            app.logger.info(f"Generated passcode for Main door 2: {main_door_2_passcode}")
            passcodes.append(main_door_2_passcode)
            lock_macs.append(main_door_2_mac)
        
        
    else:
         app.logger.info(f"Invalid Input value")
        

        
            

    coworker_id = data['CoworkerId']

    if send_message(coworker_id, passcodes, coworker_name, lock_macs, from_time, to_time,
                    data["ResourceName"], data["BookingNumber"]):
        app.logger.info(f"Successfully added coworker message {coworker_name}, {passcodes}")

def handle_cancel_request(data):
    resource_id = data[0]['ResourceId']
    from_time_str = data[0]['FromTime']

    app.logger.info(f"Cancel request data timee: {from_time_str}")

    # Convert 'FromTime' string to a datetime object
    from_time_dt = datetime.strptime(from_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    
    # Subtract 15 minutes
    from_time_adjusted = from_time_dt - timedelta(minutes=15)

    from_time = from_time_adjusted.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Log the adjusted time
    app.logger.info(f"Adjusted request data timee: {from_time}")
    
    to_time = data[0]['ToTime']

    if resource_id is None:
        app.logger.warning("ResourceId missing")
        return jsonify({'error': 'ResourceId missing'}), 400

    app.logger.info(f"Cancel request data: {data}")

    

    # List of all locks for the resource_id
    lock_ids_to_cancel = []
    
    if resource_id in single_passcode_door_ids:
        lock_mac = resource_to_lock_mapping.get(resource_id)
        lock_id = get_lock_id_by_mac(lock_mac)
        # Generate a single passcode for the specific door
        app.logger.info(f"Single Lock id to be deleted: {lock_id}")
        lock_ids_to_cancel.append(lock_id)
    elif resource_id in secondary_door_passcodes_ids_case1:
        lock_mac = resource_to_lock_mapping.get(resource_id)
        lock_id = get_lock_id_by_mac(lock_mac)
        app.logger.info(f"Requested Secondary door Lock id {lock_id}")
        lock_ids_to_cancel.append(lock_id)
        wellness_door_mac = "C2:DA:2B:DC:32:7D"  # Replace with the actual main door MAC
        wellness_door_id = get_lock_id_by_mac(wellness_door_mac)
        app.logger.info(f"Requested Secondary door  Lock id {wellness_door_id}")
        lock_ids_to_cancel.append(wellness_door_id)
    elif resource_id in secondary_door_passcodes_ids_case2:
        lock_mac = resource_to_lock_mapping.get(resource_id)
        lock_id = get_lock_id_by_mac(lock_mac)
        app.logger.info(f"Requested Secondary door Lock id {lock_id}")
        lock_ids_to_cancel.append(lock_id)
      #  lower_gf_entrance_door_mac = "0D:A9:BA:99:28:F6"  # Replace with the actual main door MAC
      #  lower_gf_entrance_door_id = get_lock_id_by_mac(lower_gf_entrance_door_mac)
      #  app.logger.info(f"Lower GF door Lock id {lower_gf_entrance_door_id}")
      #  lock_ids_to_cancel.append(lower_gf_entrance_door_id)
        
        main_door_1_mac = "C2:DA:2B:DC:32:7D"  # Replace with the actual main door MAC
        main_door_1_door_id = get_lock_id_by_mac(main_door_1_mac)
        app.logger.info(f"Main Door 1 Lock id {main_door_1_door_id}")
        lock_ids_to_cancel.append(main_door_1_door_id)
        main_door_2_mac = "C6:4A:85:44:B0:A8"  # Replace with the actual main door MAC
        main_door_2_door_id = get_lock_id_by_mac(main_door_2_mac)
        app.logger.info(f"Main door 2 Lock id {main_door_2_door_id}")
        lock_ids_to_cancel.append(main_door_2_door_id)
    
    else:
         app.logger.info(f"Invalid Resource ID")
          
    print(f"lock ids to cancel {lock_ids_to_cancel}")

    for lock_id_to_cancel in lock_ids_to_cancel:
        print(f'id {lock_id_to_cancel}')
        passcode = find_passcode(lock_id_to_cancel, from_time, to_time)
       

        if passcode:
            if delete_passcode(lock_id=lock_id_to_cancel, keyboard_pwd_id=passcode['keyboardPwdId']):
                app.logger.info(f'Success deleting passcode on lock on lock {lock_id_to_cancel} for resource {resource_id}.')
            else:
                app.logger.warning(f'Failed deleting passcode on lock on lock {lock_id_to_cancel} for resource {resource_id}.')
        else:
            app.logger.warning(f'Passcode not found on lock on lock {lock_id_to_cancel} for resource {resource_id}.')


@app.route('/booking-webhook', methods=['POST'])
def booking_webhook():
    datas = request.get_json()
    rid = None

    if not datas:
        app.logger.warning("Invalid booking data")
        return jsonify({'error': 'Invalid data'}), 200

    if isinstance(datas, list) and len(datas) > 0:
        for data in datas:
            rid = str(uuid.uuid4())[:12]
            process = mp.Process(target=handle_request, args=(data,))
            process.start()
    elif isinstance(datas, dict):
        rid = str(uuid.uuid4())[:12]
        process = mp.Process(target=handle_request, args=(datas,))
        process.start()

    return jsonify({"request_id": rid}), 200


def find_passcode(lock_id, from_time, to_time):
    page_no = 1
    passcode_to_delete = None

    while True:
        # API request to list passcodes
        passcodes = list_passcodes(lock_id=lock_id, page_no=page_no)

        # Check each passcode in the current page
        for passcode in passcodes.get('list', []):
            if passcode['startDate'] == int(
                    datetime.strptime(from_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).timestamp() * 1000) and \
                    passcode['endDate'] == int(
                    datetime.strptime(to_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).timestamp() * 1000):
                passcode_to_delete = passcode
                break

        if passcode_to_delete or not passcodes.get('list'):
            break

        page_no += 1

    return passcode_to_delete


@app.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'API is working'}), 200


@app.route('/booking-cancelled', methods=['POST'])
def cancel_booking_webhook():
    data = request.get_json()

    if not data:
        app.logger.warning("Invalid booking data")
        return jsonify({'error': 'Invalid data'}), 400

    rid = str(uuid.uuid4())[:12]
    process = mp.Process(target=handle_cancel_request, args=(data,))
    process.start()

    return jsonify({"request_id": rid}), 200


@app.route('/add-resource', methods=['POST'])
def add_resource():
    data = request.get_json()
    resource_id = data.get('resource_id')
    lock_mac = data.get('lock_mac')

    if not resource_id or not lock_mac:
        return jsonify({'error': 'Missing resource_id or lock_mac'}), 400

    [resource_id] = lock_mac
    return jsonify({'message': 'Resource added successfully'}), 200


@app.route('/delete-resource', methods=['POST'])
def delete_resource():
    data = request.get_json()
    resource_id = data.get('resource_id')

    if not resource_id or resource_id not in resource_to_lock_mapping:
        return jsonify({'error': 'Invalid or missing resource_id'}), 400

    del [resource_id]
    return jsonify({'message': 'Resource deleted successfully'}), 200

def get_nexudus_access_token():
    if 'expires_in' in my_session and my_session['expires_in'].replace(tzinfo=pytz.utc) > datetime.now(tz=pytz.utc):
        return my_session['access_nexudus_token']
    elif 'nexudus_modified' in my_session and my_session['nexudus_modified'] == True:
        return refresh_nexudus_token()
    else:
        return get_nexudus_token()


def get_nexudus_token():
    url = 'https://spaces.nexudus.com/api/token'
    data = {
        'grant_type': 'password',
        'username': app.config['NEXUDUS_USERNAME'],
        'password': app.config['NEXUDUS_PASSWORD'],
    }

    response = requests.post(url, data=data)
    token_data = response.json()

    if 'access_token' in token_data:
        my_session['access_nexudus_token'] = token_data['access_token']
        my_session['refresh_nexudus_token'] = token_data['refresh_token']
        my_session['expires_in'] = datetime.now(tz=pytz.utc) + timedelta(seconds=token_data['expires_in'])

    return token_data['access_token']


def refresh_nexudus_token():
    url = 'https://spaces.nexudus.com/api/token'

    headers = {
        'client_id': app.config["NEXUDUS_USERNAME"]
    }

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': my_session['refresh_nexudus_token']
    }

    response = requests.post(url, data=data, headers=headers)
    token_data = response.json()

    if 'access_token' in token_data:
        my_session['access_nexudus_token'] = token_data['access_token']
        my_session['refresh_nexudus_token'] = token_data['refresh_token']
        my_session['expires_in'] = datetime.now(tz=pytz.utc) + timedelta(seconds=token_data['expires_in'])
        my_session.nexudus_modified = True

    return my_session['access_token']


if __name__ == '__main__':
    app.run(debug=True)
