#!/usr/bin/env python3
import requests
import random
import sys
import os
import string
import json
from contextlib import contextmanager

import checkerlib
from PIL import Image, ImageDraw, ImageFont
import tempfile

# --- AcademyGram Checker ---


class AcademyGramChecker(checkerlib.BaseChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 3333
        self.timeout = 30

    def get_base_url(self):
        """Get base URL for the service"""
        return f"http://{self.ip}:{self.port}"

    def _random_string(self, length=12):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @contextmanager
    def _login(self, session, username, password):
        try:
            base_url = self.get_base_url()
            login_data = {"username": username, "password": password}
            r = session.post(
                f"{base_url}/login",
                data=login_data,
                timeout=self.timeout,
                allow_redirects=False,
            )
            r.raise_for_status()
            if r.status_code != 302 or "/login" in r.headers.get("Location", ""):
                raise ConnectionError(f"Login failed for {username}")
            yield session
        finally:
            session.get(f"{base_url}/logout")

    def _create_flag_image(self, flag_text):
        """Creates a placeholder image with flag text, similar to bots.py"""
        try:
            width, height = 600, 400
            img = Image.new('RGB', (width, height), color=(25, 25, 25))
            d = ImageDraw.Draw(img)
            
            # Use default font
            try:
                font = ImageFont.load_default()
            except:
                font = None

            # Text wrapping
            lines = []
            words = flag_text.split()
            line = ''
            for word in words:
                test_line = line + word + ' '
                if font and d.textlength(test_line, font=font) <= width - 40:
                    line = test_line
                elif len(test_line) <= 60:  # fallback if no font
                    line = test_line
                else:
                    lines.append(line)
                    line = word + ' '
            lines.append(line)

            # Draw text
            y_text = (height - len(lines) * 25) / 2
            for line in lines:
                d.text((20, y_text), line, fill=(220, 220, 220), font=font)
                y_text += 25
                
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            img.save(temp_file.name)
            return temp_file.name
        except Exception as e:
            print(f"Could not create image: {e}")
            return None

    def place_flag(self, tick):
        flag = checkerlib.get_flag(tick)
        base_url = self.get_base_url()
        session = requests.Session()
        
        # Get admin credentials from environment
        admin_password = os.environ.get("ADMIN_PASSWORD", "CHANGEME_password123")

        # Generate random credentials for this tick
        username = self._random_string(8)
        password = self._random_string(12)

        try:
            # 1. Register new user for private post
            register_data = {"username": username, "password": password}
            r_reg = session.post(
                f"{base_url}/register",
                data=register_data,
                allow_redirects=False,
                timeout=self.timeout,
            )
            if r_reg.status_code != 302:
                return checkerlib.CheckResult.FAULTY

            # 2. Login as the new user and create private post with flag
            with self._login(session, username, password):
                # Flag Storage 1: Private image post with flag as caption
                flag_image_path = self._create_flag_image(flag)
                if flag_image_path:
                    with open(flag_image_path, 'rb') as img_file:
                        files = {'image': ('flag_post.png', img_file, 'image/png')}
                        post_data = {'content': flag, 'is_private': 'on'}
                        r_post = session.post(
                            f"{base_url}/add_post",
                            data=post_data,
                            files=files,
                            timeout=self.timeout
                        )
                    # Clean up temp file
                    os.unlink(flag_image_path)
                    
                    if r_post.status_code != 302:
                        return checkerlib.CheckResult.FAULTY
                else:
                    # Fallback: text-only private post
                    post_data = {'content': flag, 'is_private': 'on'}
                    r_post = session.post(
                        f"{base_url}/add_post",
                        data=post_data,
                        timeout=self.timeout
                    )
                    if r_post.status_code != 302:
                        return checkerlib.CheckResult.FAULTY

            # 3. Flag Storage 2: Login as admin and update interests
            with self._login(session, "admin", admin_password):
                interests_data = {
                    "interests": f"Top Secret Research,{flag},Zero-Day Hunting"
                }
                r_interests = session.post(
                    f"{base_url}/update_interests",
                    data=interests_data,
                    timeout=self.timeout
                )
                if r_interests.status_code != 302:
                    return checkerlib.CheckResult.FAULTY

            # Store credentials for later retrieval
            flag_info = {
                "username": username,
                "password": password
            }

            checkerlib.store_state(str(tick), flag_info)
            checkerlib.set_flagid(username)

            return checkerlib.CheckResult.OK

        except (ConnectionError, requests.exceptions.RequestException):
            return checkerlib.CheckResult.DOWN
        except Exception:
            return checkerlib.CheckResult.FAULTY

    def check_service(self):
        try:
            base_url = self.get_base_url()
            session = requests.Session()
            
            # Check main page
            r = session.get(base_url, timeout=self.timeout)
            if r.status_code != 200:
                return checkerlib.CheckResult.DOWN

            # Check login page
            r_login = session.get(f"{base_url}/login", timeout=self.timeout)
            if r_login.status_code != 200 or "login" not in r_login.text.lower():
                return checkerlib.CheckResult.FAULTY

            # Check basic functionality - register and login
            username = self._random_string()
            password = self._random_string()

            register_data = {"username": username, "password": password}
            r_reg = session.post(
                f"{base_url}/register",
                data=register_data,
                allow_redirects=False,
                timeout=self.timeout,
            )
            if r_reg.status_code != 302:
                return checkerlib.CheckResult.FAULTY

            # Test login works
            with self._login(session, username, password):
                pass

            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException:
            return checkerlib.CheckResult.DOWN

    def check_flag(self, tick):
        flag = checkerlib.get_flag(tick)
        base_url = self.get_base_url()
        session = requests.Session()

        try:
            # Retrieve stored credentials
            flag_info = checkerlib.load_state(str(tick))
            if not flag_info:
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            username = flag_info["username"]
            password = flag_info["password"]
            
            # Check Flag Storage 1: Private post on user's profile
            with self._login(session, username, password):
                r_profile = session.get(
                    f"{base_url}/profile/{username}", timeout=self.timeout
                )
                if r_profile.status_code != 200:
                    return checkerlib.CheckResult.FLAG_NOT_FOUND
                    
                # Check if flag is in private posts
                if flag not in r_profile.text:
                    return checkerlib.CheckResult.FLAG_NOT_FOUND
            
            # Check Flag Storage 2: Admin interests via IDOR vulnerability
            with self._login(session, username, password):
                # Exploit IDOR to access admin interests
                r_interests = session.get(
                    f"{base_url}/interests?user_id=1", timeout=self.timeout
                )
                if r_interests.status_code != 200:
                    return checkerlib.CheckResult.FLAG_NOT_FOUND
                    
                # Check if flag is in admin interests
                if flag not in r_interests.text:
                    return checkerlib.CheckResult.FLAG_NOT_FOUND
            
            # Both flag storage locations verified
            return checkerlib.CheckResult.OK

        except (ConnectionError, requests.exceptions.RequestException):
            return checkerlib.CheckResult.DOWN
        except (KeyError, TypeError):
            return checkerlib.CheckResult.FLAG_NOT_FOUND


if __name__ == "__main__":
    checkerlib.run_check(AcademyGramChecker)
