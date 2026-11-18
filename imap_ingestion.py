import imaplib
import email
from email.header import decode_header
import requests
from supabase import Client

class DianImapIngestionEngine:
    def __init__(self, integration_id: str, organization_id: str, direction: str, 
                 server: str, port: int, user: str, password: str, 
                 folder_name: str, api_url: str, supabase_client: Client):
        self.integration_id = integration_id
        self.organization_id = organization_id  # Multi-tenant key
        self.direction = direction
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.folder_name = folder_name
        self.api_url = api_url
        self.supabase = supabase_client

    def process_mailbox(self):
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.user, self.password)
            mail.select(self.folder_name)

            status, messages = mail.search(None, '(UNSEEN)')
            if status != 'OK' or not messages[0]:
                return

            for num in messages[0].split():
                res, msg_data = mail.fetch(num, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        self._process_attachments(msg)

        except Exception as e:
            print(f"[IMAP ERROR] Org {self.organization_id}: {str(e)}")

    def _process_attachments(self, msg):
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename and (filename.endswith('.xml') or filename.endswith('.zip')):
                file_content = part.get_payload(decode=True)
                
                # Enviar al endpoint con la nueva llave de organización
                files = {'file': (filename, file_content, 'application/octet-stream')}
                data = {
                    'organization_id': self.organization_id, 
                    'direction': self.direction
                }
                
                try:
                    r = requests.post(self.api_url, files=files, data=data)
                    print(f"[IMAP UPLOAD] {filename}: {r.status_code}")
                except Exception as e:
                    print(f"[IMAP API ERROR] {str(e)}")