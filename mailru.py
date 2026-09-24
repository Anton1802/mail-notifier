import email
import imaplib
from email.header import decode_header

from config import MAILRU_EMAIL, MAILRU_APP_PASSWORD

IMAP_HOST = "imap.mail.ru"
IMAP_PORT = 993


def get_service():
    """
    Аналог get_service() из gmail_api.py — открывает IMAP-сессию.
    """
    if not MAILRU_EMAIL or not MAILRU_APP_PASSWORD:
        raise RuntimeError("MAILRU_EMAIL / MAILRU_APP_PASSWORD не заданы в .env")

    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(MAILRU_EMAIL, MAILRU_APP_PASSWORD)
    imap.select("INBOX")
    return imap


def _decode_str(value):
    """
    Декодирует MIME-заголовок (тема, имя отправителя) в обычную строку.
    """
    if not value:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded += text.decode(encoding or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def _get_body(msg):
    """
    Достаёт текстовое тело письма (plain приоритетнее html).
    """
    plain_body = None
    html_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")

            if "attachment" in disposition:
                continue

            if content_type == "text/plain" and plain_body is None:
                charset = part.get_content_charset() or "utf-8"
                plain_body = part.get_payload(decode=True).decode(
                    charset, errors="replace"
                )
            elif content_type == "text/html" and html_body is None:
                charset = part.get_content_charset() or "utf-8"
                html_body = part.get_payload(decode=True).decode(
                    charset, errors="replace"
                )
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            plain_body = payload.decode(charset, errors="replace")

    return plain_body or html_body or ""


def get_last_uid_current(imap):
    """
    Возвращает текущий максимальный UID в INBOX (для инициализации состояния).
    """
    status, data = imap.uid("search", None, "ALL")
    if status != "OK" or not data or not data[0]:
        return 0
    uids = data[0].split()
    return int(uids[-1]) if uids else 0


def get_new_messages(imap, last_uid, mark_read=True):
    """
    Возвращает новые письма с UID > last_uid и новый last_uid.

    Аналог get_new_messages() из gmail_api.py.
    """
    status, data = imap.uid("search", None, f"UID {last_uid + 1}:*")
    if status != "OK" or not data or not data[0]:
        return [], last_uid

    uids = data[0].split()
    # UID-диапазон может вернуть last_uid ещё раз, если новых писем нет — отфильтруем
    uids = [uid for uid in uids if int(uid) > last_uid]

    if not uids:
        return [], last_uid

    messages = []
    max_uid = last_uid

    for uid in uids:
        fetch_mode = "(RFC822)" if mark_read else "(BODY.PEEK[])"
        status, msg_data = imap.uid("fetch", uid, fetch_mode)
        if status != "OK" or not msg_data or msg_data[0] is None:
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        messages.append(
            {
                "uid": int(uid),
                "subject": _decode_str(msg.get("Subject")),
                "from": _decode_str(msg.get("From")),
                "to": _decode_str(msg.get("To")),
                "date": msg.get("Date"),
                "body": _get_body(msg),
            }
        )

        max_uid = max(max_uid, int(uid))

    return messages, max_uid


def close_service(imap):
    try:
        imap.close()
    except Exception:
        pass
    imap.logout()
