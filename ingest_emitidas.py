import os
from dotenv import load_dotenv
from imap_ingestion import DianImapIngestionEngine

load_dotenv()

if __name__ == "__main__":
    engine = DianImapIngestionEngine(
        server=os.getenv("EMITIDAS_IMAP_SERVER"),
        port=int(os.getenv("EMITIDAS_IMAP_PORT", 993)),
        user=os.getenv("EMITIDAS_EMAIL_ACCOUNT"),
        password=os.getenv("EMITIDAS_EMAIL_PASSWORD"),
        company_id=os.getenv("COMPANY_ID"),
        api_url=os.getenv("API_UPLOAD_URL")
    )

    folder = os.getenv("EMITIDAS_FOLDER", "Sent")
    engine.process_folder(folder_name=folder, direction="EMITIDA")