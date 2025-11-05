import os
import sys
import django
import uuid
import time
import threading
import requests
from datetime import datetime
from zk import ZK
sys.path.append('/home/kalosh/projects/kiswate_digital')  # your project root
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.settings')  # replace with your actual settings module

django.setup()
from userauths.models import User  # adjust path to your app
from school.models import ScanLog, School, SmartID, Student  # adjust path to your app
from django.utils import timezone
from django.db import IntegrityError

# -------------------------------
# Configuration
# -------------------------------


DEVICES = [
    {"ip": "192.168.100.201", "id": "Device-A", "location": "Main Gate"},
    {"ip": "192.168.100.202", "id": "Device-B", "location": "Back Gate"},
    {"ip": "192.168.100.303", "id": "Device-C", "location": "Office Entrance"},
]

POLL_INTERVAL = 5   

# EUJIM SMS setup
SMS_API_KEY = ''
SMS_PARTNERID =''
SMS_SHORTCODE = ''
SMS_API_URL = ''
ALERT_PHONE = ""


# -------------------------------
# Django Setup
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "src")  # Adjust if needed
sys.path.append(PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
django.setup()

# -------------------------------
# Import Models
# -------------------------------


# -------------------------------
# Helper: Send SMS via EUJIM
# -------------------------------
def _send_sms_via_eujim(to_phone_number: str, message: str) -> bool:
    if not to_phone_number:
        print("⚠️ Empty phone number — skipping SMS.")
        return False

    phone_str = str(to_phone_number)
    if phone_str.startswith("0"):
        phone_str = "254" + phone_str[1:]
    elif phone_str.startswith("+254"):
        phone_str = phone_str[1:]
    elif not phone_str.startswith("254"):
        phone_str = "254" + phone_str

    payload = {
        "apikey": SMS_API_KEY,
        "partnerID": SMS_PARTNERID,
        "message": message,
        "shortcode": SMS_SHORTCODE,
        "mobile": phone_str,
    }

    try:
        response = requests.post(SMS_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "responses" in data and len(data["responses"]) > 0:
                r = data["responses"][0]
                if r.get("response-code") == 200 and "Success" in r.get(
                    "response-description", ""
                ):
                    print(f"📩 SMS sent successfully to {phone_str}")
                    return True
        print(f"❌ SMS sending failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ SMS Exception: {e}")
    return False


# -------------------------------
# Helper: Save Scan to Database
# -------------------------------
def save_scan_to_db(user_id, scan_time, device_id, location="Main Gate"):
    """
    Creates a ScanLog and links it with the correct SmartID and Profile.
    """
    try:
        # Match ZKTeco's scanned ID to SmartID.user_f18_id
        smart_id = SmartID.objects.select_related("profile", "school").filter(user_f18_id=str(user_id)).first()

        if not smart_id:
            print(f"⚠️ No SmartID found for scanned ID: {user_id}")
            return None

        # Prevent duplicate scans in 10 seconds for same smart_id
        existing = ScanLog.objects.filter(
            smart_id=smart_id,
            scanned_at__gte=timezone.now() - timezone.timedelta(seconds=10),
        ).exists()
        if existing:
            print(f"⏳ Duplicate scan ignored for SmartID {smart_id.card_id}")
            return None

        scan_log = ScanLog.objects.create(
            smart_id=smart_id,
            scan_id=str(uuid.uuid4()),
            device_id=device_id,
            location=location,
            scanned_at=scan_time,
        )

        print(f"📝 New ScanLog created for {smart_id.profile} at {scan_time}")
        return scan_log

    except IntegrityError:
        print(f"⚠️ Duplicate ScanLog entry detected for SmartID {user_id}")
    except Exception as e:
        print(f"❌ Error saving ScanLog: {e}")
    return None



# -------------------------------
# Main: Poll ZKTeco Device
# -------------------------------
def poll_device_and_send_sms_for_device(ip, device_id, location):
    zk = ZK(ip, port=4370, timeout=5)
    try:
        conn = zk.connect()
        print(f" Connected to ZKTeco device {device_id} at {ip}")

        last_scan_time = None

        while True:
            try:
                logs = conn.get_attendance()
                if not logs:
                    time.sleep(POLL_INTERVAL)
                    continue

                latest_log = logs[-1]
                log_time = latest_log.timestamp

                # Only act if new scan detected
                if last_scan_time and log_time <= last_scan_time:
                    time.sleep(POLL_INTERVAL)
                    continue

                # Save scan to DB
                scan_record = save_scan_to_db(
                    user_id=latest_log.user_id,
                    scan_time=log_time,
                    device_id=device_id,
                    location=location,
                )

                if scan_record:
                    profile = scan_record.smart_id.profile

                    #  If the scanned user is a student
                    if profile.is_student:
                        print(f"📚 Student scan detected: {profile}")

                        # Find the corresponding Student object
                        student = Student.objects.filter(
                            profile=profile,
                            school=scan_record.smart_id.school
                        ).first()

                        if student:
                            # Get all parents linked to this student
                            parents = student.parent.all()
                            full_name = f"{profile.first_name} {profile.last_name}"
                            message = (
                                f"New Scan: {full_name} at {location} "
                                f"({log_time.strftime('%Y-%m-%d %H:%M:%S')})"
                            )

                            # Send SMS to each parent
                            for parent in parents:
                                if parent.profile.phone_number:
                                    _send_sms_via_eujim(parent.profile.phone_number, message)
                                    print(f"📩 SMS sent to parent: {parent.profile.phone_number}")
                                else:
                                    print(f"⚠️ Parent {parent} has no phone number.")

                        else:
                            print(f"⚠️ No student record found for {profile}")

                    else:
                        # For non-students, send SMS directly to the user's own phone
                        full_name = f"{profile.first_name} {profile.last_name}"
                        message = f"New Scan: {full_name} at {location} ({log_time.strftime('%Y-%m-%d %H:%M:%S')})"
                        _send_sms_via_eujim(profile.phone_number, message)
                        print(f"📩 SMS sent to user: {profile.phone_number}")

                    last_scan_time = log_time

                else:
                    print(f"⚠️ No scan saved for {device_id} this round.")

                time.sleep(POLL_INTERVAL)

            except Exception as inner_e:
                print(f"⚠️ Polling error on {device_id}: {inner_e}")
                time.sleep(POLL_INTERVAL)

    except Exception as e:
        print(f"❌ Could not connect to device {device_id} ({ip}): {e}")
    finally:
        try:
            conn.disconnect()
        except:
            pass
        print(f"🔌 Disconnected from {device_id}")


def poll_all_devices_parallel():
    threads = []
    for device in DEVICES:
        t = threading.Thread(
            target=poll_device_and_send_sms_for_device,
            args=(device["ip"], device["id"], device["location"]),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Keep main thread alive
    for t in threads:
        t.join()
# -------------------------------
# Run Script
# -------------------------------
if __name__ == "__main__":
    poll_all_devices_parallel()
