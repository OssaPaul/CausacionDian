import os
import imaplib
import email
import io
import zipfile
from email.header import decode_header
import requests
from typing import List, Tuple
from datetime import datetime, timezone
from supabase import Client


class DianImapIngestionEngine:
    """
    Motor de ingesta IMAP multitenant.
    Procesa casillas parametrizadas por empresa desde Supabase y actualiza su estado.
    """

    DIAN_KEYWORDS = [
        "factura electronica", "factura electrónica", "attacheddocument", 
        "documento soporte", "nota credito", "nota crédito", "dian", "fe_", "nc_"
    ]

    def __init__(
        self,
        integration_id: str,
        company_id: str,
        direction: str,
        server: str,
        port: int,
        user: str,
        password: str,
        folder_name: str,
        api_url: str,
        supabase_client: Client
    ):
        self.integration_id = integration_id
        self.company_id = company_id
        self.direction = direction
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.folder_name = folder_name or "INBOX"
        self.api_url = api_url
        self.supabase = supabase_client

    def _decode_str(self, header_value: str) -> str:
        if not header_value:
            return ""
        decoded_list = decode_header(header_value)
        text_parts = []
        for bytes_or_str, encoding in decoded_list:
            if isinstance(bytes_or_str, bytes):
                text_parts.append(bytes_or_str.decode(encoding or 'utf-8', errors='ignore'))
            else:
                text_parts.append(bytes_or_str)
        return "".join(text_parts)

    def connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.server, self.port)
        mail.login(self.user, self.password)
        return mail

    def _is_dian_subject(self, subject: str) -> bool:
        subject_lower = subject.lower()
        return any(kw in subject_lower for kw in self.DIAN_KEYWORDS)

    def _is_valid_dian_xml_bytes(self, content: bytes) -> bool:
        try:
            if content.startswith(b'PK\x03\x04'):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    xml_files = [f for f in z.namelist() if f.endswith('.xml')]
                    if not xml_files:
                        return False
                    content = z.read(xml_files[0])

            content_str = content[:2000].decode('utf-8', errors='ignore').lower()
            return ("dian.gov.co" in content_str or "attacheddocument" in content_str or "<invoice" in content_str or "<creditnote" in content_str)
        except Exception:
            return False

    def process_mailbox(self) -> int:
        print(f"[WORKER IMAP] Sincronizando {self.direction} - Empresa: {self.company_id} ({self.user})")
        
        try:
            mail = self.connect()
        except Exception as e:
            error_msg = f"Error conexión IMAP: {str(e)}"
            print(f"[WORKER ERROR] {error_msg}")
            self._update_sync_status("ERROR_CONEXION", error_msg)
            return 0

        status_select, _ = mail.select(f'"{self.folder_name}"')
        if status_select != 'OK':
            error_msg = f"No se pudo acceder a la carpeta '{self.folder_name}'"
            print(f"[WORKER ERROR] {error_msg}")
            mail.logout()
            self._update_sync_status("ERROR_CARPETA", error_msg)
            return 0

        status_code, response = mail.search(None, 'UNSEEN')
        if status_code != 'OK' or not response[0]:
            mail.logout()
            self._update_sync_status("OK", "Sin mensajes nuevos")
            return 0

        mail_ids = response[0].split()
        processed_count = 0

        for m_id in mail_ids:
            res_data, msg_data = mail.fetch(m_id, '(RFC822)')
            if res_data != 'OK':
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = self._decode_str(msg.get("Subject", ""))

                    if not self._is_dian_subject(subject):
                        continue

                    attachments = self._extract_dian_attachments(msg)
                    for filename, file_bytes in attachments:
                        if not self._is_valid_dian_xml_bytes(file_bytes):
                            continue

                        success = self._send_to_api(filename, file_bytes)
                        if success:
                            processed_count += 1

        mail.logout()
        status_text = f"Procesados {processed_count} documentos" if processed_count > 0 else "OK"
        self._update_sync_status("OK", status_text)
        return processed_count

    def _extract_dian_attachments(self, msg: email.message.Message) -> List[Tuple[str, bytes]]:
        attachments = []
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                filename = self._decode_str(filename)
                ext = filename.lower().split('.')[-1]
                if ext in ['xml', 'zip']:
                    file_data = part.get_payload(decode=True)
                    if file_data:
                        attachments.append((filename, file_data))
        return attachments

    def _send_to_api(self, filename: str, file_bytes: bytes) -> bool:
        files = {'file': (filename, file_bytes, 'application/octet-stream')}
        data = {'company_id': self.company_id, 'direction': self.direction}

        try:
            response = requests.post(self.api_url, data=data, files=files)
            return response.status_code in [201, 409]
        except Exception as e:
            print(f"[WORKER ERROR API] {str(e)}")
            return False

    def _update_sync_status(self, status: str, details: str):
        try:
            self.supabase.table("company_email_integrations").update({
                "last_sync_at": datetime.now(timezone.utc).isoformat(),
                "last_sync_status": f"{status}: {details}"[:100]
            }).eq("id", self.integration_id).execute()
        except Exception as e:
            print(f"[ERROR SUPABASE STATUS] {str(e)}")