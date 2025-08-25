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
    generate_coherent_post,
)

def pull_image():
    API_KEY = "REDACTED"
    query = random.choice(["sun", "great", "flower","machine", "hills"])
    save_path = "/tmp/random_flower.jpg"

    # Pick a random page within Pixabay's 500 max results
    page = random.randint(1, 25)  # 20 per page × 25 pages = 500

    url = f"https://pixabay.com/api/?key={API_KEY}&q={query}&image_type=photo&per_page=20&page={page}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    if data.get("hits"):
        choice = random.choice(data["hits"])
        img_url = choice.get("largeImageURL") or choice.get("webformatURL")
        print("Downloading:", img_url)

        img_data = requests.get(img_url).content
        with open(save_path, "wb") as f:
            f.write(img_data)
    return save_path

# --- AcademyGram Checker ---
class AcademyGramChecker(checkerlib.BaseChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 2750
        self.timeout = 30

    def get_base_url(self):
        return f"http://{self.ip}:{self.port}"

    def get_credentials(self):
        bot_usernames = get_bot_usernames()
        base_username = random.choice(bot_usernames)
        username = f"{base_username}_{random_string(6)}"
        password = random_string(12)
        return username, password

    def _get_or_create_user(self, session, base_url):
        username, password = self.get_credentials()

        register_data = {"username": username, "password": password}
        try:
            r_reg = session.post(
                f"{base_url}/register",
                data=register_data,
                allow_redirects=False,
                timeout=self.timeout,
            )

            if r_reg.status_code == 302 and r_reg.headers.get("Location", "").endswith(
                "/login"
            ):
                return username, password
        except Exception as e:
            print(f"Registration attempt failed for {username}: {e}")

        try:
            self._login(session, username, password)
            self._logout(session)
            return username, password
        except Exception as e:
            print(f"Login attempt failed for {username}: {e}")

        raise Exception(f"Failed to register or login as {username}")

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
        if r.status_code != 302 or not r.headers.get("Location", "").endswith("/"):
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

                if r_post.status_code != 302 or not r_post.headers.get(
                    "Location", ""
                ).endswith("/"):
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
                if r_post.status_code != 302 or not r_post.headers.get(
                    "Location", ""
                ).endswith("/"):
                    self._logout(session)
                    return checkerlib.CheckResult.FAULTY

            interests_data = {"interests": f"CTF Research,{flag},Binary Analysis"}
            r_interests = session.post(
                f"{base_url}/update_interests",
                data=interests_data,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if r_interests.status_code != 302 or not r_interests.headers.get(
                "Location", ""
            ).endswith("/interests"):
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

            username, password = self._get_or_create_user(session, base_url)

            self._login(session, username, password)

            test_content = generate_coherent_post()
            post_data = {"content": test_content}  # No "is_private" = public post
            r_post = session.post(
                f"{base_url}/add_post",
                data=post_data,
                timeout=self.timeout,
                allow_redirects=False,
            )

            if r_post.status_code != 302 or not r_post.headers.get(
                "Location", ""
            ).endswith("/"):
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            test_image_content = generate_coherent_post()
            image_path = pull_image()
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

                    if r_image_post.status_code != 302 or not r_image_post.headers.get(
                        "Location", ""
                    ).endswith("/"):
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

            unique_interest = random_string(8)
            test_interests = f"Service Testing,{unique_interest},Security Research"
            interests_data = {"interests": test_interests}
            r_update_interests = session.post(
                f"{base_url}/update_interests",
                data=interests_data,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if (
                r_update_interests.status_code != 302
                or not r_update_interests.headers.get("Location", "").endswith(
                    "/interests"
                )
            ):
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            r_interests_check = session.get(
                f"{base_url}/interests", timeout=self.timeout
            )
            if r_interests_check.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            if unique_interest not in r_interests_check.text:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            r_forgot = session.get(f"{base_url}/forgot_password", timeout=self.timeout)
            if r_forgot.status_code != 200 or "forgot" not in r_forgot.text.lower():
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            r_get_code = session.get(f"{base_url}/get_code", timeout=self.timeout)
            if r_get_code.status_code != 200:
                self._logout(session)
                return checkerlib.CheckResult.FAULTY

            try:
                code_data = r_get_code.json()
                if "current_code" not in code_data or "username" not in code_data:
                    self._logout(session)
                    return checkerlib.CheckResult.FAULTY
                if (
                    not code_data["current_code"].isdigit()
                    or len(code_data["current_code"]) != 4
                ):
                    self._logout(session)
                    return checkerlib.CheckResult.FAULTY
            except:
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

            if flag not in r_interests.text:
                self._logout(session)
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            self._logout(session)
            return checkerlib.CheckResult.OK

        except (ConnectionError, requests.exceptions.RequestException):
            return checkerlib.CheckResult.DOWN
        except (KeyError, TypeError):
            return checkerlib.CheckResult.FLAG_NOT_FOUND


if __name__ == "__main__":
    checkerlib.run_check(AcademyGramChecker)
