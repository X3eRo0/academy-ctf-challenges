#!/usr/bin/env python3
import requests
import random
import sys
import os
import json

from ctf_gameserver import checkerlib
from utils import (
    random_string,
    get_bot_usernames,
    create_temp_image,
    load_credentials,
    save_credentials,
    generate_coherent_post,
)


# --- AcademyGram Checker ---
class AcademyGramChecker(checkerlib.BaseChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 2750
        self.timeout = 30

    def get_base_url(self):
        return f"http://{self.ip}:{self.port}"

    def _get_or_create_user(self, session, base_url):
        creds = load_credentials()
        bot_usernames = get_bot_usernames()

        if not creds:
            print("Initializing credentials for all bot usernames...")
            for username in bot_usernames:
                password = random_string(12)
                creds[username] = password
            save_credentials(creds)
            print(f"Initialized {len(creds)} bot accounts in creds.txt")

        username = random.choice(list(creds.keys()))
        password = creds[username]
        return username, password

    def _login(self, session, username, password):
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
        return True

    def _logout(self, session):
        base_url = self.get_base_url()
        session.get(f"{base_url}/logout")

    def place_flag(self, tick):
        flag = checkerlib.get_flag(tick)
        base_url = self.get_base_url()
        session = requests.Session()

        try:
            username, password = self._get_or_create_user(session, base_url)
            self._login(session, username, password)

            flag_image_path = create_temp_image(flag)
            if flag_image_path:
                with open(flag_image_path, "rb") as img_file:
                    files = {"image": ("flag_post.png", img_file, "image/png")}
                    post_data = {"content": flag, "is_private": "on"}
                    r_post = session.post(
                        f"{base_url}/add_post",
                        data=post_data,
                        files=files,
                        timeout=self.timeout,
                        allow_redirects=False,
                    )
                os.unlink(flag_image_path)

                if r_post.status_code != 302:
                    self._logout(session)
                    return checkerlib.CheckResult.FAULTY
            else:
                post_data = {"content": flag, "is_private": "on"}
                r_post = session.post(
                    f"{base_url}/add_post",
                    data=post_data,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
                if r_post.status_code != 302:
                    self._logout(session)
                    return checkerlib.CheckResult.FAULTY

            interests_data = {"interests": f"CTF Research,{flag},Binary Analysis"}
            r_interests = session.post(
                f"{base_url}/update_interests",
                data=interests_data,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if r_interests.status_code != 302:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            self._logout(session)

            flag_info = {"username": username, "password": password}

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

            r = session.get(base_url, timeout=self.timeout)
            if r.status_code != 200:
                return checkerlib.CheckResult.DOWN

            r_login = session.get(f"{base_url}/login", timeout=self.timeout)
            if r_login.status_code != 200 or "login" not in r_login.text.lower():
                return checkerlib.CheckResult.FAULTY

            # username = random_string()
            # password = random_string()
            username, password = self._get_or_create_user(session, base_url)

            register_data = {"username": username, "password": password}
            r_reg = session.post(
                f"{base_url}/register",
                data=register_data,
                allow_redirects=False,
                timeout=self.timeout,
            )
            if r_reg.status_code != 302:
                return checkerlib.CheckResult.FAULTY

            self._login(session, username, password)

            test_content = generate_coherent_post()
            post_data = {"content": test_content}  # No "is_private" = public post
            r_post = session.post(
                f"{base_url}/add_post",
                data=post_data,
                timeout=self.timeout,
                allow_redirects=False,
            )

            if r_post.status_code != 302:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            test_image_content = generate_coherent_post()
            image_path = create_temp_image(test_image_content)
            if image_path:
                try:
                    with open(image_path, "rb") as img_file:
                        files = {"image": ("service_check.jpg", img_file, "image/jpeg")}
                        post_data = {"content": test_image_content}  # Public post
                        r_image_post = session.post(
                            f"{base_url}/add_post",
                            data=post_data,
                            files=files,
                            timeout=self.timeout,
                            allow_redirects=False,
                        )
                    os.unlink(image_path)  # Clean up temp file

                    if r_image_post.status_code != 302:
                        self._logout(session)
                        return checkerlib.CheckResult.FAULTY
                except Exception:
                    if os.path.exists(image_path):
                        os.unlink(image_path)

            r_profile = session.get(f"{base_url}/profile", timeout=self.timeout)
            if r_profile.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            r_interests = session.get(f"{base_url}/interests", timeout=self.timeout)
            if r_interests.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            test_interests = f"Service Testing,{random_string(6)},Security Research"
            interests_data = {"interests": test_interests}
            r_update_interests = session.post(
                f"{base_url}/update_interests",
                data=interests_data,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if r_update_interests.status_code != 302:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            r_timeline_check = session.get(f"{base_url}/", timeout=self.timeout)
            if r_timeline_check.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            timeline_has_content = test_content in r_timeline_check.text or (
                image_path and test_image_content in r_timeline_check.text
            )
            if not timeline_has_content:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            self._logout(session)

            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException:
            return checkerlib.CheckResult.DOWN

    def check_flag(self, tick):
        flag = checkerlib.get_flag(tick)
        base_url = self.get_base_url()
        session = requests.Session()

        try:
            flag_info = checkerlib.load_state(str(tick))
            if not flag_info:
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            username = flag_info["username"]
            password = flag_info["password"]

            self._login(session, username, password)

            r_profile = session.get(f"{base_url}/profile", timeout=self.timeout)
            if r_profile.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            if flag not in r_profile.text:
                self._logout(session)
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            r_interests = session.get(f"{base_url}/interests", timeout=self.timeout)
            if r_interests.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Check if flag is in user's interests
            if flag not in r_interests.text:
                self._logout(session)
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            self._logout(session)

            # Both flag storage locations verified
            return checkerlib.CheckResult.OK

        except (ConnectionError, requests.exceptions.RequestException):
            return checkerlib.CheckResult.DOWN
        except (KeyError, TypeError):
            return checkerlib.CheckResult.FLAG_NOT_FOUND


if __name__ == "__main__":
    checkerlib.run_check(AcademyGramChecker)
