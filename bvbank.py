import requests
import json
import time
import datetime
from requests.cookies import RequestsCookieJar
import base64
import re
import urllib.parse
from bs4 import BeautifulSoup
import os 
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
from base64 import b64encode
from playwright.async_api import async_playwright
import asyncio
from itertools import cycle
import random
class BVBank:
    def __init__(self,username, password, account_number,proxy_list=None):
        self.proxy_list = proxy_list
        self.proxy_cycle = cycle(self.proxy_list) if self.proxy_list else None
        if self.proxy_list:
            self.proxy_info = random.choice(self.proxy_list)
            proxy_host, proxy_port, username_proxy, password_proxy = self.proxy_info.split(':')
            self.proxies = {
                'http': f'http://{username_proxy}:{password_proxy}@{proxy_host}:{proxy_port}',
                'https': f'http://{username_proxy}:{password_proxy}@{proxy_host}:{proxy_port}'
            }
        else:
            self.proxies = None
        self.keyanticaptcha = "b8246038ce1540888c4314a6c043dcae"
        self.base64_key = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDOMAicHDxAkPEBRp4RfMpDCbTQ16wZCFdS4Uw2E9S5NVIGIRdirdViOTsaNWmbk/pQQQeVIccsHHh9hvH6St6z0krxmIPeXs9NqYniVNcWOqxPDxcm4FuKc736RI6TVqXI4zA/yH/+2dA4uCF54ekOoPT3Akd1m13m0hNZHX/77wIDAQAB"
        self.public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{self.base64_key}\n-----END PUBLIC KEY-----"
        self.file = f"db/users/{account_number}.json"
        self.cookies_file = f"db/cookies/{account_number}.json"
        self.cookies = RequestsCookieJar()
        self.session = requests.Session()
        self.load_cookies()
        self.accounts_list = {}
        
        self.username = username
        self.password = password
        self.account_number = account_number
        if not os.path.exists(self.file) or os.path.getsize(self.file) == 0:
            self.username = username
            self.password = password
            self.account_number = account_number
            self.is_login = False
            self.time_login = time.time()
            self.save_data()
        else:
            self.parse_data()
            self.username = username
            self.password = password
            self.account_number = account_number
            self.save_data()
    def save_data(self):
        data = {
            'username': self.username,
            'password': self.password,
            'account_number': self.account_number,
            'time_login': self.time_login,
            'is_login': self.is_login
        }
        with open(f"db/users/{self.account_number}.json", 'w') as file:
            json.dump(data, file)
    def parse_data(self):
        with open(f"db/users/{self.account_number}.json", 'r') as file:
            data = json.load(file)
            self.username = data['username']
            self.password = data['password']
            self.account_number = data['account_number']
            self.time_login = data['time_login']
            self.is_login = data['is_login']

    def save_cookies(self,cookie_jar):
        with open(self.cookies_file, 'w') as f:
            json.dump(cookie_jar.get_dict(), f)
    def load_cookies(self):
        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)
                self.session.cookies.update(cookies)
                return
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            return requests.cookies.RequestsCookieJar()
    def encrypt_with_public_key(self, plaintext):
        try:
            # Tải khóa công khai
            public_key = RSA.import_key(self.public_key_pem)
            cipher = PKCS1_v1_5.new(public_key)
            encrypted_data = cipher.encrypt(plaintext.encode('utf-8'))
            return b64encode(encrypted_data).decode('utf-8')
        except Exception as ex:
            print(f"Encryption error: {ex}")
            return False
    async def get_cookies(self):
        cookie_dict = {}

        if self.proxies:
            http_proxy = self.proxies.get('http')
            https_proxy = self.proxies.get('https')
            proxy_url = http_proxy or https_proxy

            # Parse proxy
            proxy_parts = proxy_url.replace('http://', '').split('@')
            credentials, proxy_address = proxy_parts[0], proxy_parts[1]
            proxy_username, proxy_password = credentials.split(':')
            host, port = proxy_address.split(':')

            proxy_config = {
                "server": f"http://{host}:{port}",
                "username": proxy_username,
                "password": proxy_password
            }
        else:
            proxy_config = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_config  # None nếu không có proxy
            )

            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto('https://digibank.bvbank.net.vn/login')

                await page.wait_for_selector(
                    'body > div > main > div > section > div.content-wrap.sme-register-form > div > div > div:nth-child(1) > h2'
                )

                # Lấy cookie và chuyển sang dict
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

                # Cập nhật session
                self.session.cookies.update(cookie_dict)
                return cookie_dict

            finally:
                await browser.close()    

    def extract_text_from_td(self,td_string):
        return re.sub(r"<[^>]*>", "", td_string).strip()
    def extract_error_message(self,html_content):
        pattern = r'login\.on_load\("lock", "(.*?)"'
        match = re.search(pattern, html_content)
        return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else None
    
    def extract_csrf(self,html_content):
        pattern = r'<form class="form_style" id="loginForm" action="/login?type=dn" method="POST"><input type="hidden" name="_csrf" value="(.*)"/>'
        match = re.search(pattern, html_content)
        return match.group(1) if match else None
    def extract_accounts(self,html_string):
        """
        Extracts account numbers and balances from the given HTML string.

        Args:
            html_string (str): The input HTML string containing account details.

        Returns:
            list: A list of dictionaries, each containing 'account_number' and 'balance'.
        """
        soup = BeautifulSoup(html_string, "html.parser")

        # Find all account items
        list_items = soup.select(".CASA .item-li")
        
        accounts = []
        for item in list_items:
            account_number = item.select_one("a").text.strip()
            balance = item.select_one("span").text.strip()
            accounts.append({"account_number": account_number, "balance": balance})
        
        return accounts
    def extract_balance_from_td(self,td_string):
        balance_pattern = r"(\d{1,3}(?:,\d{3})*\.\d{2})"
        balances = re.findall(balance_pattern, td_string)
        formatted_balances = [balance.split('.')[0].replace(',', '') for balance in balances]
        return formatted_balances[0]
    def extract_account_number(self,html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        ac_element = soup.find('span', class_='me-2')
        if ac_element:
            ac_text = ac_element.get_text(strip=True)
        return (ac_text.strip()) if ac_element else None
    def extract_balance(self,html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        ac_element = soup.find('span', class_='me-2 text-blue')
        if ac_element:
            ac_text = ac_element.get_text(strip=True)
        return float(ac_text.strip().replace('.', '').replace(',','.')) if ac_element else None
    def extract_transaction_history(self,html_string):
        html_content = html_string.replace('undefined','').replace(' >','>').replace('< ','<')
        soup = BeautifulSoup(html_content, 'html.parser')
        transactions = []

        items = soup.find_all('div', class_='item-account-statement')
        for item in items:
            date_time = item.find('p', class_='mb-2 fs-small').text.strip()
            description = item.find('p', class_='fw-bold m-0 text-break').text.strip()
            transaction_code = item.find('span', class_='fw-bold').text.strip()
            amount_element = item.find('p', class_='text-danger m-0 text-end fw-bold') or item.find('p', class_='text-green m-0 text-end fw-bold')
            amount = amount_element.text.strip() if amount_element else 'N/A'
            
            transaction = {
                'date_time': date_time,
                'transaction_id': transaction_code,
                'remark': description,
                'amount': amount
            }
            transactions.append(transaction)

        return transactions
    def change_proxy(self):
            print('change_proxy')
            if not self.proxy_cycle:
                print("No proxies available. Setting self.proxies to None.")
                self.proxies = None
                return
            self.proxy_info = next(self.proxy_cycle)  # Lấy proxy kế tiếp từ vòng lặp
            proxy_host, proxy_port, username_proxy, password_proxy = self.proxy_info.split(':')
            self.proxies = {
                'http': f'http://{username_proxy}:{password_proxy}@{proxy_host}:{proxy_port}',
                'https': f'http://{username_proxy}:{password_proxy}@{proxy_host}:{proxy_port}'
            }
            print(f"New proxy: {self.proxies}")
    def base_request_get(self,url):
        headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'referer': 'https://digibank.bvbank.net.vn/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        }
        try:
            response = self.session.get(url, headers=headers,proxies=self.proxies)
        except Exception as e:
            print('reason change proxy',e)
            self.change_proxy()
            return None
        return response
    async def login(self,relogin=False):
        if not relogin:
            balance_response = await self.get_balance(self.account_number)
            if balance_response['code'] != 500:
                return balance_response
            
        self.session = requests.Session()
        await self.get_cookies()
        url = "https://digibank.bvbank.net.vn/login?type=dn"
        
        response = self.base_request_get(url)
        # with open("init_login.html", "w", encoding="utf-8") as file:
        #     file.write(response.text)
        _csrf_token = self.extract_csrf(response.text)
        # print(_csrf_token)
        
        
        url = "https://digibank.bvbank.net.vn/login?type=dn"

        payload = {
            '_csrf': _csrf_token,
            'infoForm': 'IP : 116.111.4.186;AGENT : Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0 DEVICE_NAME: Chrome 131',
            'username': self.encrypt_with_public_key(self.username),
            'password': self.encrypt_with_public_key(self.password),
        }

        # Convert the dictionary to a URL-encoded string
        encoded_payload = urllib.parse.urlencode(payload)
        # print(encoded_payload)        
        headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://digibank.bvbank.net.vn',
        'priority': 'u=0, i',
        'referer': 'https://digibank.bvbank.net.vn/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
        }
        try:
            response = self.session.post(url, headers=headers, data=encoded_payload,allow_redirects=True,proxies=self.proxies)
        except Exception as e:
            print('reason change proxy',e)
            self.change_proxy()
            return None
        # with open("login.html", "w", encoding="utf-8") as file:
        #     file.write(response.text)
        if 'https://digibank.bvbank.net.vn/home' in response.url:
            self.save_cookies(self.session.cookies)
            self.is_login = True
            self.time_login = time.time()
            self.save_data()
            return await self.get_balance(self.account_number)
        else:
            error_message = self.extract_error_message(response.text)
            print(error_message)
            if error_message:
                if 'vô hiệu hóa' in error_message:
                    return  {
                            "success": False,
                            "code": 449,
                            "message": "Blocked account!",
                            "details": error_message
                        }
                elif 'nhập sai tên đăng nhập hoặc mật khẩu' in error_message:
                    return {
                            'success': False,
                            'message': 'Đăng nhập không thành công!',
                            'code': 444,
                            "details": error_message
                        }
            else:
                return await self.login(relogin=True)

                
        return None

    async def get_balance(self,account_number,retry=False):
        if not self.is_login or time.time() - self.time_login > 9000:
            self.is_login = True
            self.save_data()
            login = await self.login(relogin=True)
            return login
        response = self.base_request_get('https://digibank.bvbank.net.vn/home')
        # with open("home.html", "w", encoding="utf-8") as file:
        #     file.write(response.text)
        account_list = self.extract_accounts(response.text)
        if account_list:
            for account in account_list:
                if account.get('account_number') == account_number:
                    return {'code':200,'success': True, 'message': 'Thành công',
                                    'data':{
                                        'account_number':account_number,
                                        'balance':int(account.get('balance').replace(' VND','').replace('.',''))
                            }}
            return {'code':404,'success': False, 'message': 'account_number not found!'} 
        else:
            self.is_login = False
            self.save_data()
            if not retry:
                return await self.get_balance(account_number,retry=True)

            return {'code':500 ,'success': False, 'message': 'Unknown Error!','data':response.text} 


    async def get_transactions(self,account_number,fromDate,toDate,latest=False,retry=False):
        if not self.is_login or time.time() - self.time_login > 9000:
            self.is_login = True
            self.save_data()
            login = await self.login()
            if not login['success']:
                return login
        if latest:
            url = f'https://digibank.bvbank.net.vn/account/quick-search/CASA/{account_number}/gdgn?_={str(int(time.time() * 1000))}'
        else:
            url = f'https://digibank.bvbank.net.vn/account/search-by-date/CASA/{account_number}/{fromDate}/{toDate}?_={str(int(time.time() * 1000))}'
        response = self.base_request_get(url)
        # with open("transaction.html", "w", encoding="utf-8") as file:
        #     file.write(response.text)
        try:
            response = response.json()
        except:
            self.is_login = False
            self.save_data()
            if not retry:
                return await self.get_transactions(account_number,fromDate,toDate,latest,retry=True)

            return {'code':500 ,'success': False, 'message': 'Unknown Error!','data':response.text} 
        # transactions =  self.extract_transaction_history(response.text)
        
        if  'response' in response:
            response['response'].reverse()
            
            return {'code':200,'success': True, 'message': 'Thành công',
                    'data':{
                        'transactions':response['response'],
            }}
        else:
            return {'code':200,'success': True, 'message': 'Thành công',
                    'data':{
                        'message': 'No data',
                        'transactions':[],
                        'response':response
            }}


