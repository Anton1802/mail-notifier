import email
import imaplib
from email.header import decode_header

import html2text
import re

_html_converter = html2text.HTML2Text()
_html_converter.ignore_links = False
_html_converter.ignore_images = True
_html_converter.body_width = 0
_html_converter


def _truncate_snippet(text, limit=500):
    text = text.strip()
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0]
    return truncated + "…"


def _clean_markdown_headers(text):
    # убираем ведущие # у заголовков, оставляя только текст
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # схлопываем более двух подряд пустых строк в одну
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_service(host, port, login, password, mailbox="INBOX"):
    """
    Открывает IMAP-сессию для произвольного провайдера.
    """
    if not login or not password:
        raise RuntimeError(f"Логин/пароль не заданы для {host}")

    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(login, password)
    imap.select(mailbox)
    return imap


def _decode_str(value):
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


def _get_body(msg, limit=500):
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
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = decoded
            else:
                plain_body = decoded

    if html_body:
        result = _clean_markdown_headers(_html_converter.handle(html_body)).strip()
    elif plain_body:
        result = plain_body.strip()
    else:
        result = ""

    return _truncate_snippet(result, limit)


def get_last_uid_current(imap):
    status, data = imap.uid("search", None, "ALL")
    if status != "OK" or not data or not data[0]:
        return 0
    uids = data[0].split()
    return int(uids[-1]) if uids else 0


def get_new_messages(imap, last_uid, mark_read=True):
    status, data = imap.uid("search", None, f"UID {last_uid + 1}:*")
    if status != "OK" or not data or not data[0]:
        return [], last_uid

    uids = data[0].split()
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
                "body": _get_body(msg, 4000),
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
