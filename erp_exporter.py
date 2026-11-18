import pandas as pd
import io
from supabase import Client
from typing import List, Dict

class ErpExporterEngine:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def _get_invoices_for_export(self, organization_id: str) -> List[Dict]:
        """Obtiene todas las facturas causadas de la organización."""
        res = self.supabase.table("invoices").select(
            "id, full_number, issue_date, issuer_nit, issuer_name, payable_amount, status"
        ).eq("organization_id", organization_id).eq("status", "CAUSADO").execute()
        return res.data or []

    def _get_journal_lines(self, invoice_id: str) -> List[Dict]:
        """Aquí consultarías tu tabla de asientos contables (journal_entries). Por ahora simulamos la data."""
        return [
            {"account": "5135", "debit": 1000, "credit": 0, "nit": "900"},
            {"account": "2205", "debit": 0, "credit": 1000, "nit": "900"}
        ]

    def export_siigo(self, organization_id: str) -> bytes:
        invoices = self._get_invoices_for_export(organization_id)
        if not invoices:
            raise ValueError("No hay facturas causadas para exportar en esta organización.")
            
        data = []
        for inv in invoices:
            lines = self._get_journal_lines(inv["id"])
            for line in lines:
                data.append({
                    "Comprobante": "FC",
                    "Consecutivo": inv["full_number"],
                    "Fecha": inv["issue_date"],
                    "Cuenta": line["account"],
                    "Tercero": line["nit"],
                    "Debito": line["debit"],
                    "Credito": line["credit"]
                })
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Siigo_Import', index=False)
        return output.getvalue()

    # (Puedes replicar esta lógica exacta filtrando por organization_id para export_helisa, export_loggro, export_syscafe, etc.)
    def export_helisa(self, organization_id: str) -> bytes:
        invoices = self._get_invoices_for_export(organization_id)
        # Lógica Helisa...
        return b"Estructura CSV Helisa"
        
    def export_loggro(self, organization_id: str) -> bytes:
        return b"Estructura Excel Loggro"
        
    def export_syscafe(self, organization_id: str) -> bytes:
        return b"Estructura TXT SysCafe"
        
    def export_alegra(self, organization_id: str) -> bytes:
        return b"Estructura Excel Alegra"
        
    def export_world_office(self, organization_id: str) -> bytes:
        return b"Estructura Excel WorldOffice" 