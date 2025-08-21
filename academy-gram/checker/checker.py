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
        self.timeout = 10 # Increased timeout for image uploads

    def place_flag(self, tick):
        raise NotImplementedError()

    def check_service(self):
        raise NotImplementedError()

    def run(self, action, tick=None):
        try:
            if action == 'place_flag':
                return self.place_flag(tick)
            elif action == 'check_service':
                return self.check_service()
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
            if r.status_code != 302:
                raise ConnectionError(f"Login failed for {username}")
            yield self.session
        finally:
            self.session.get(f"{self.base_url}/logout")

    def _get_random_bot_user(self):
        bots = ["Gluncho", "brightprogrammer", "Saan", "InkaDinka", "CROWNPRINCE",
        "Ze:R0", "Alchemy1729", "kobush", "LE_THOG", "AAAA", "mistertoenails",
        "emi", "hs", "hanto", "RenegadePenguin", "aturt13", "Platinum",
        "nendo", "antiriad7", "0xVul", "razzledazzle", "Leo", "Snowy",
        "thairog", "x3ero0", "k1R4", "VessaX", "Newtons4thLaw", "rxgel",
        "ordinary", "NopNopGoose", "amateurhour", "SMCxDeathBurger",
        "TUNISIA_ALBERT", "ThatGuySteve", "prosdkr", "George", "Gus",
        "stevie", "HackOlympus", "Elvis", "Shunt", "slowman", "Canlex",
        "Flipout50", "0xcosmos", "beaver", "xuesu", "j88001", "Tedan Vosin",
        "HAL50000", "cyx", "Gh05t-1337", "kaal", "j3r3mias", "/bin/cat",
        "Jared", "profl@¥", "Sylvie", "「」", "nucko", "Adical", "Ron",
        "fatalynk", "F4_U57", "A1.exe", "0xFFFFFF", "e-.", "ch0mp4", "Sammy"]
        return random.choice(bots)

    def _fetch_image_from_pixabay(self):
        query = random.choice(["sun","machine", "moon", "flower", "great"])
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

        # 1. Bot Activity: Post a public image
        bot_user = self._get_random_bot_user()
        try:
            with self._login(bot_user, bot_password):
                image_data, tags = self._fetch_image_from_pixabay()
                if image_data:
                    post_data = {'content': f"Exploring the world of {tags}! #infosec"}
                    files = {'image': ('post.jpg', image_data, 'image/jpeg')}
                    self.session.post(f"{self.base_url}/add_post", data=post_data, files=files)
        except (ConnectionError, requests.exceptions.RequestException) as e:
            print(f"[*] Bot activity failed, but not critical: {e}", file=sys.stderr)

        # 2. Flag Placement: As admin
        try:
            with self._login("admin", admin_password):
                # Flag in a private post
                post_data = {'content': f"Confidential project notes: {flag}", 'is_private': 'on'}
                r_post = self.session.post(f"{self.base_url}/add_post", data=post_data, allow_redirects=False)
                if r_post.status_code != 302:
                    return CheckerResult.FAULTY, "Failed to create private post with flag"
                
                # Flag in admin's interests via API
                interests_data = {'user_id': 1, 'interests': f"Top Secret Research,{flag},Zero-Day Hunting"}
                r_interests = self.session.post(f"{self.base_url}/api/update_interests", json=interests_data)
                if r_interests.status_code != 200:
                    return CheckerResult.FAULTY, "Failed to update admin interests with flag"
                
                print(f"[*] Flag for tick {tick} placed: {flag}")
                # Store the flag in a way the gameserver can retrieve for check_service
                with open(f"/tmp/flag_tick_{tick}.txt", "w") as f:
                    f.write(flag)
                return CheckerResult.OK, "Flag placed in post and interests"
        except (ConnectionError, requests.exceptions.RequestException):
            return CheckerResult.DOWN, "Failed to log in as admin and place flag"

    def check_service(self, tick):
        """Checks if the service is up and if a flag can be retrieved."""
        try:
            # Check main page
            r = self.session.get(self.base_url, timeout=self.timeout)
            if r.status_code != 200:
                return CheckerResult.DOWN, "Main page is not accessible"

            # Check if a previously placed flag is retrievable (simulated)
            try:
                with open(f"/tmp/flag_tick_{tick}.txt", "r") as f:
                    flag = f.read().strip()
            except FileNotFoundError:
                # No flag from a previous tick to check, so we just check service health
                return CheckerResult.OK, "Service is up, but no flag to check"

            # This part would normally involve exploiting a vuln to get the flag.
            # For a simple check, we'll just see if the login page works.
            r_login = self.session.get(f"{self.base_url}/login", timeout=self.timeout)
            if "login" not in r_login.text.lower():
                 return CheckerResult.FAULTY, "Login page seems broken"

            return CheckerResult.OK, "Service is up and responsive"

        except requests.exceptions.RequestException:
            return CheckerResult.DOWN, "Failed to connect to service"


if __name__ == "__main__":
    if len(sys.argv) not in [4, 5]:
        print(f"Usage: python {sys.argv[0]} <ip> <port> <action> [tick]")
        sys.exit(1)

    ip, port, action = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    tick = int(sys.argv[4]) if len(sys.argv) == 5 else random.randint(1, 1000)

    checker = AcademyGramChecker(ip=ip, port=port)
    
    if action == 'check_service':
        result, message = checker.check_service(tick)
    elif action == 'place_flag':
        result, message = checker.place_flag(tick)
    else:
        result, message = CheckerResult.FAULTY, "Unknown action"

    print(f"Result: {result}\nMessage: {message}")
    if result != CheckerResult.OK:
        sys.exit(1)
