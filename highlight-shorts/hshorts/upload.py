"""YouTube upload. Always private; the owner publishes by hand in YouTube Studio."""
import os

from . import store

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _paths():
    root = store.data_dir()
    return os.path.join(root, "client_secret.json"), os.path.join(root, "youtube_token.json")


def has_client():
    return os.path.isfile(_paths()[0])


def connected():
    return os.path.isfile(_paths()[1])


def describe(text, channel, url):
    """The description always ends with credit to the source."""
    credit = "เครดิตวิดีโอต้นฉบับ: %s" % channel
    if url:
        credit += "\n%s" % url
    credit += "\nใช้โดยได้รับอนุญาตจากเจ้าของ"
    return ((text or "").strip() + "\n\n" + credit).strip()[:4900]


def connect():
    """Open the Google sign-in page in the browser and store the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    secret, token = _paths()
    if not os.path.isfile(secret):
        raise FileNotFoundError("ยังไม่มีไฟล์ client_secret.json ใน %s (ดูวิธีทำใน README)"
                                % store.data_dir())
    creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
    with open(token, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    token = _paths()[1]
    creds = Credentials.from_authorized_user_file(token, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def body(title, description, tags):
    return {
        "snippet": {"title": (title or "Shorts").strip()[:100], "description": description,
                    "tags": [t for t in (tags or []) if t][:30], "categoryId": "20"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def send(path, title, description, tags, service=None):
    """Upload one file as a private video. Returns the YouTube video id."""
    from googleapiclient.http import MediaFileUpload
    service = service or _service()
    request = service.videos().insert(
        part="snippet,status", body=body(title, description, tags),
        media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]
