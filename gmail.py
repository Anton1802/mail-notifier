import json
from config import GOOGLE_CREDENTIALS
from dotenv import set_key

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service():
    credentials = None

    print(repr(GOOGLE_CREDENTIALS))

    if GOOGLE_CREDENTIALS:
        info = json.loads(GOOGLE_CREDENTIALS)
        credentials = Credentials.from_authorized_user_info(info, SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            credentials = flow.run_local_server(port=0)
            set_key(".env", "GOOGLE_CREDENTIALS", credentials.to_json())

    return build("gmail", "v1", credentials=credentials)


def list_messages(service, max_results=30):
    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q="label:INBOX")
        .execute()
    )
    messages = results.get("messages", [])

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = msg_data["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(без темы)"
        )
        sender = next(
            (h["value"] for h in headers if h["name"] == "From"), "(неизвестно)"
        )
        print(f"От: {sender}\nТема: {subject}\n---")


if __name__ == "__main__":
    service = get_service()
    list_messages(service)
