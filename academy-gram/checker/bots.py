import sqlite3
import random
import os
import string
from PIL import Image, ImageDraw, ImageFont


def generate_coherent_post():
    """Generates more realistic post content."""
    templates = [
        "Just finished a great CTF challenge on {topic}! #CTF #{hashtag}",
        "Exploring the world of {topic}. The possibilities are endless. #infosec #{hashtag}",
        "Deep dive into {topic} today. Learned so much! #cybersecurity #{hashtag}",
        "Working on a new project involving {topic}. Wish me luck! #coding #{hashtag}",
        "Anyone have good resources for learning {topic}? #askingtweeps #{hashtag}",
        "That moment when your {topic} exploit finally works. #pwned #{hashtag}",
    ]
    topics = [
        "reverse engineering",
        "web security",
        "binary exploitation",
        "cryptography",
        "forensics",
        "OSINT",
    ]
    hashtags = ["hacking", "dev", "security", "100daysofcode", "bugbounty"]

    template = random.choice(templates)
    topic = random.choice(topics)
    hashtag = random.choice(hashtags)

    return template.format(topic=topic, hashtag=hashtag)


def create_placeholder_image(text, output_path, image_size=(1280, 720), font_size=40):
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


def main():
    usernames = [
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

    # Create directory for post images
    if not os.path.exists("static/posts"):
        os.makedirs("static/posts")

    conn = sqlite3.connect("academygram.db")
    cur = conn.cursor()

    # Get all users or create them if they don't exist
    user_ids = []
    for username in usernames:
        cur.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user:
            user_ids.append(user[0])
        else:
            password = "".join(
                random.choices(string.ascii_letters + string.digits, k=12)
            )
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password),
            )
            user_ids.append(cur.lastrowid)

    # Create posts in a more mixed-up order
    posts_to_create = []
    for user_id in user_ids:
        for _ in range(random.randint(2, 5)):
            posts_to_create.append(user_id)
    random.shuffle(posts_to_create)

    for i, user_id in enumerate(posts_to_create):
        content = generate_coherent_post()
        image_name = f"post_{i}_{user_id}.png"
        image_path = os.path.join("static/posts", image_name)

        create_placeholder_image(image_path, content)

        is_private = random.choice([True, False])

        cur.execute(
            "INSERT INTO posts (user_id, content, image_path, is_private) VALUES (?, ?, ?, ?)",
            (user_id, content, image_path, is_private),
        )

    conn.commit()
    conn.close()
    print(f"Database populated with {len(posts_to_create)} image posts.")


if __name__ == "__main__":
    main()
