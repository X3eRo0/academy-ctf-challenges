#!/usr/bin/env python3
import os
import random
import string
import tempfile
import json
from PIL import Image, ImageDraw, ImageFont


def random_string(length=12):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_bot_usernames():
    return [
        "Gluncho",
        "brightprogrammer",
        "Saan",
        "InkaDinka",
        "CROWNPRINCE",
        "Ze:R0",
        "Alchemy1729",
        "kobush",
        "LE_THOG",
        "AAAA",
        "mistertoenails",
        "emi",
        "hs",
        "hanto",
        "RenegadePenguin",
        "aturt13",
        "Platinum",
        "nendo",
        "antiriad7",
        "0xVul",
        "razzledazzle",
        "Leo",
        "Snowy",
        "thairog",
        "x3ero0",
        "k1R4",
        "VessaX",
        "Newtons4thLaw",
        "rxgel",
        "ordinary",
        "NopNopGoose",
        "amateurhour",
        "SMCxDeathBurger",
        "TUNISIA_ALBERT",
        "ThatGuySteve",
        "prosdkr",
        "George",
        "Gus",
        "stevie",
        "HackOlympus",
        "Elvis",
        "Shunt",
        "slowman",
        "Canlex",
        "Flipout50",
        "0xcosmos",
        "beaver",
        "xuesu",
        "j88001",
        "Tedan Vosin",
        "HAL50000",
        "cyx",
        "Gh05t-1337",
        "kaal",
        "j3r3mias",
        "/bin/cat",
        "Jared",
        "profl@¥",
        "Sylvie",
        "「」",
        "nucko",
        "Adical",
        "Ron",
        "fatalynk",
        "F4_U57",
        "A1.exe",
        "0xFFFFFF",
        "e-.",
        "ch0mp4",
        "Sammy",
    ]


def create_placeholder_image(text, output_path, image_size=(1280, 720), font_size=40):
    """Create a placeholder image with text, similar to bots.py"""
    try:
        img = Image.new("RGB", image_size, color="black")
        draw = ImageDraw.Draw(img)
        font_size = int((image_size[0] // len(text)) * 1.6)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size
            )
        except IOError:
            font = ImageFont.load_default(size=font_size)

        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(
                text, font=font
            )  # For older versions

        position = (
            (image_size[0] - text_width) // 2,
            (image_size[1] - text_height) // 2,
        )
        draw.text(position, text, fill=(0, 255, 0), font=font)
        fd = os.open(output_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o400)
        with os.fdopen(fd, "wb") as f:
            img.save(f, "jpeg")
    except Exception as e:
        print(f"Could not create image {output_path}: {e}")


def create_temp_image(text):
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_file.close()
        create_placeholder_image(text, temp_file.name)
        return temp_file.name
    except Exception as e:
        print(f"Could not create temp image: {e}")
        return None


def load_credentials():
    try:
        with open("creds.txt", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_credentials(creds):
    with open("creds.txt", "w") as f:
        json.dump(creds, f, indent=2)


def generate_coherent_post():
    templates = [
        "Just finished a great CTF challenge on {topic}! #CTF #{hashtag}",
        "Exploring the world of {topic}. The possibilities are endless. #infosec #{hashtag}",
        "Deep dive into {topic} today. Learned so much! #cybersecurity #{hashtag}",
        "Working on a new project involving {topic}. Wish me luck! #coding #{hashtag}",
        "Anyone have good resources for learning {topic}? #askingtweeps #{hashtag}",
        "That moment when your {topic} exploit finally works. #pwned #{hashtag}",
        "Late night debugging session with {topic}. Coffee is my best friend. #dev #{hashtag}",
        "Discovered an interesting {topic} technique today. Mind blown! #learning #{hashtag}",
        "Shoutout to the amazing {topic} community for all the help! #grateful #{hashtag}",
        "Building something cool with {topic} this weekend. Stay tuned! #weekend #{hashtag}",
        "Finally understand {topic} concepts. Feeling accomplished! #progress #{hashtag}",
        "Reading papers about {topic} and my brain hurts. Worth it though! #research #{hashtag}",
        "Deployed my first {topic} solution to production. Nervous but excited! #milestone #{hashtag}",
        "Teaching someone {topic} today. Best way to solidify knowledge! #teaching #{hashtag}",
        "Found a nasty bug in my {topic} implementation. Back to the drawing board. #debugging #{hashtag}",
        "Conference talk on {topic} was incredible. So much inspiration! #conference #{hashtag}",
        "Open source {topic} project needs contributors. Who's interested? #opensource #{hashtag}",
        "Three weeks into learning {topic} and loving every challenge! #journey #{hashtag}",
        "Refactoring legacy {topic} code. It's therapeutic somehow. #refactoring #{hashtag}",
        "Built a simple {topic} tool for my team. Small wins matter! #productivity #{hashtag}",
        "Attending {topic} workshop next week. Can't wait to level up! #workshop #{hashtag}",
        "Documentation for {topic} is actually good for once. Rare find! #documentation #{hashtag}",
        "Mentoring junior devs in {topic}. Seeing their progress is rewarding! #mentoring #{hashtag}",
        "Experimenting with {topic} on my homelab. Breaking things safely! #homelab #{hashtag}",
        "Community meetup about {topic} was fantastic. Great networking! #community #{hashtag}",
    ]

    topics = [
        "reverse engineering",
        "web security",
        "binary exploitation",
        "cryptography",
        "forensics",
        "OSINT",
        "malware analysis",
        "penetration testing",
        "network security",
        "incident response",
        "threat hunting",
        "vulnerability research",
        "red teaming",
        "blue teaming",
        "digital forensics",
        "mobile security",
        "cloud security",
        "DevSecOps",
        "secure coding",
        "risk assessment",
    ]

    hashtags = [
        "hacking",
        "dev",
        "security",
        "100daysofcode",
        "bugbounty",
        "infosec",
        "cybersec",
        "ethicalhacking",
        "pentesting",
        "redteam",
        "blueteam",
        "ctf",
        "oscp",
        "cissp",
        "sans",
        "netsec",
        "appsec",
        "cloudsec",
        "devsecops",
        "zerotrust",
    ]

    template = random.choice(templates)
    topic = random.choice(topics)
    hashtag = random.choice(hashtags)

    return template.format(topic=topic, hashtag=hashtag)
