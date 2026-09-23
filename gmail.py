import json
from config import GOOGLE_CREDENTIALS
from dotenv import set_key

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_service():
    credentials = None

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


def get_last_history_google(service):
    profile = service.users().getProfile(userId="me").execute()
    return profile["historyId"]


def get_changes(service, start_history_id):
    response = (
        service.users()
        .history()
        .list(userId="me", startHistoryId=start_history_id)
        .execute()
    )
    return response


def mark_as_read_batch(service, msg_ids):
    if not msg_ids:
        return
    service.users().messages().batchModify(
        userId="me", body={"ids": msg_ids, "removeLabelIds": ["UNREAD"]}
    ).execute()


def get_new_messages(service, start_history_id, mark_read=True):
    response = (
        service.users()
        .history()
        .list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],  # фильтр, чтобы не тащить лишнее
        )
        .execute()
    )

    new_message_ids = []
    for record in response.get("history", []):
        for msg_added in record.get("messagesAdded", []):
            new_message_ids.append(msg_added["message"]["id"])

    messages = []
    for msg_id in new_message_ids:
        full_message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="full",  # или 'metadata', 'raw', 'minimal'
            )
            .execute()
        )
        messages.append(full_message)

    if mark_read and new_message_ids:
        service.users().messages().batchModify(
            userId="me", body={"ids": new_message_ids, "removeLabelIds": ["UNREAD"]}
        ).execute()

    return messages, response["historyId"]
