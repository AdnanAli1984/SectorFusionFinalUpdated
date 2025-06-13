from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import base58
import json
from datetime import datetime
import os

LICENSE_FILE_PATH = "License/license.bin"
SECRET_KEY = "yFanS37kbWnBTZRW" 
SECRET_KEY = bytes(SECRET_KEY, 'utf-8')  

def get_valid_days(licenses_data):
    try:
        if not licenses_data:
            return None
            
        category_days = {}
        current_date = datetime.now()
        
        for license in licenses_data:
            expiry = license.get("expiry_date")
            categories = license.get("categories", [])
            
            if not expiry or not categories:
                continue
                
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
                
                if current_date >= expiry_date:
                    print(f"License {license.get('id', 'Unknown')} has expired!")
                    continue
                    
                remaining_days = (expiry_date - current_date).days
                
                for category in categories:
                    if not isinstance(category, int):
                        category_days[category] = max(
                            category_days.get(category, 0),
                            remaining_days
                        )
                    
            except Exception as e:
                print(f"Error processing license {license.get('id', 'Unknown')}: {str(e)}")
                continue
        
        if not category_days:
            print("No valid licenses found!")
            return None
            
        print("Valid licenses found!")
        print("Remaining days per category:")
        for category, days in category_days.items():
            print(f"{category}: {days} days")
            
        return category_days
    except Exception as e:
        print(f"Error in get_valid_days: {str(e)}")
        return None

def get_days_for_feature(licenses_data, feature_name):
    try:
        category_days = get_valid_days(licenses_data)
        if category_days:
            return category_days.get(feature_name, 0)
        return 0
    except Exception as e:
        print(f"Error getting days for feature {feature_name}: {str(e)}")
        return 0

def validate_license_key(license_key: str, device_address: str, file_path: str = "License/license.bin"):
    try:
        encrypted = base58.b58decode(license_key)

        cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
        decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        license_data = json.loads(decrypted.decode('utf-8'))

        if license_data["device_address"] != device_address:
            print("Device address does not match!")
            return False, "License key is invalid"

        expiry_date = datetime.strptime(license_data["expiry_date"], "%Y-%m-%d")
        current_date = datetime.now()
        
        if current_date > expiry_date:
            print("License has expired!")
            return False, "License has expired!"
        
        save_encrypted_license(license_data, file_path)
        licenses = read_encrypted_license(file_path)
        valid_licenses = []
        current_date = datetime.now()
        
        for license_data in licenses:
            if license_data["device_address"] == device_address:
                expiry_date = datetime.strptime(license_data["expiry_date"], "%Y-%m-%d")
                if current_date < expiry_date:
                    remaining_days = (expiry_date - current_date).days
                    license_data["remaining_days"] = remaining_days
                    license_data["status"] = "Valid"
                    valid_licenses.append(license_data)
                    
                else:
                    remaining_days = 0
                    license_data["remaining_days"] = remaining_days
                    license_data["status"] = "Expired"
                    valid_licenses.append(license_data)
        
        if not valid_licenses:
            print("No valid licenses found for this device!")
            return False, "No valid licenses found"
            
        print(f"Found {len(valid_licenses)} valid licenses!")
        return True, valid_licenses
    except Exception as e:
        print(f"Error validating license: {str(e)}")
        return False, "License could not be validated"
    
def save_encrypted_license(license_data: dict, file_path: str):
    try:
        existing_licenses = []
        sites = None
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                content = file.read()
                if content: 
                    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
                    decrypted = unpad(cipher.decrypt(base58.b58decode(content)), AES.block_size)
                    existing_licenses_data = json.loads(decrypted.decode('utf-8'))
                    existing_licenses = existing_licenses_data["licenses"]
                    sites = existing_licenses_data.get("sites", None)
        
        existing_licenses.append(license_data)
        dir_name = os.path.dirname(file_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        licenses_json = json.dumps({"sites":sites, "licenses":existing_licenses})
        cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(licenses_json.encode(), AES.block_size))
        encrypted_data = base58.b58encode(encrypted).decode()
        
        with open(file_path, 'wb') as file:
            file.write(encrypted_data.encode('utf-8'))
            
        print(f"Encrypted license saved to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving encrypted license: {str(e)}")
        return False

def get_sites(file_path:str):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                content = file.read()
                if content: 
                    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
                    decrypted = unpad(cipher.decrypt(base58.b58decode(content)), AES.block_size)
                    license_data = json.loads(decrypted.decode('utf-8'))
                    sites = license_data.get("sites", False)
                    return sites
                else:
                    print("No content found in license file")
                    return None
        else:
            print("License file doesn't exist")
            return None
    except Exception as e:
        print(f"Error saving encrypted license: {str(e)}")
        return None
    
def save_sites(file_path:str, sites):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                content = file.read()
                if content: 
                    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
                    decrypted = unpad(cipher.decrypt(base58.b58decode(content)), AES.block_size)
                    license_data = json.loads(decrypted.decode('utf-8'))
                    license_data["sites"] = sites
                    licenses_json = json.dumps(license_data)
                    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
                    encrypted = cipher.encrypt(pad(licenses_json.encode(), AES.block_size))
                    encrypted_data = base58.b58encode(encrypted).decode()
                    
                    with open(file_path, 'wb') as file:
                        file.write(encrypted_data.encode('utf-8'))
                        return True
                else:
                    print("No content found in license file")
                    return None
        else:
            print("License file doesn't exist")
            return None
    except Exception as e:
        print(f"Error saving encrypted license: {str(e)}")
        return None

def read_encrypted_license(file_path: str):
    try:
        if not os.path.exists(file_path):
            print("No license file found")
            return []
            
        with open(file_path, 'rb') as file:
            content = file.read()
            if not content:  
                return []
        
        cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
        decrypted = unpad(cipher.decrypt(base58.b58decode(content)), AES.block_size)
        licenses = json.loads(decrypted.decode('utf-8'))
        
        print(f"Successfully extracted {len(licenses)} licenses!")
        return licenses["licenses"]
    except Exception as e:
        print(f"Error reading licenses: {str(e)}")
        return []
    
def get_license_info():
        try:
            data = read_encrypted_license(file_path=LICENSE_FILE_PATH)
            if isinstance(data, list) and len(data) == 0:
                return "No license information found"
            else:
                info_text = ""
                for item in data:
                    expiry_date = datetime.strptime(item["expiry_date"], "%Y-%m-%d")
                    current_date = datetime.now()
                    remaining_days = (expiry_date - current_date).days
                    if remaining_days <= 0:
                        validity = "Expired"
                        remaining_days = 0
                    else:
                        validity = "Valid"
                    categories = item["categories"]
                    category_list = []
                    site_limit = 50
                    for category in categories:
                        if isinstance(category, int):
                            site_limit = category
                        else:
                            category_list.append(category.replace("_", " "))
                        
                    text = f"""
                    License ID: {item["id"]}
                    License Status: {validity}
                    Device Address: {item["device_address"]}
                    Expiration Date: {item["expiry_date"]}
                    Days Remaining: {remaining_days}
                    Enabled Features: {", ".join(category_list)}
                    Number of allowed sites: {site_limit}"""
                    info_text = info_text+"\n"+text+"\n"
                return info_text
        except Exception as e:
            print(str(e))
            return None