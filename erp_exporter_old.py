import io
import pandas as pd
from supabase import Client

class ErpExporterEngine:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def _get_journal_data(self, organization_id: str) -> pd.DataFrame:
        """
        Consulta las líneas del libro diario (journal_lines) y su factura asociada
        para la organización, extrayendo las imputaciones contables reales y descripciones.
        """
        res = self.supabase.table("journal_lines")\
            .select("*, invoices(full_number, issue_date, issuer_nit, issuer_name)")\
            .eq("organization_id", organization_id)\
            .execute()
        
        data = res.data if res and res.data else []
        if not data:
            raise ValueError("No se encontraron movimientos contables causados en 'journal_lines' para la organización.")
        
        rows = []
        for item in data:
            inv = item.get("invoices") or {}
            rows.append({
                "comprobante": "FC",
                "consecutivo": str(inv.get("full_number") or "S/N").strip(),
                "fecha": str(inv.get("issue_date") or "2026-01-01")[:10],
                "cuenta": str(item.get("account_code") or "").strip(),
                "tercero": str(item.get("third_party_nit") or inv.get("issuer_nit") or "0").strip(),
                "debito": float(item.get("debit") or 0.0),
                "credito": float(item.get("credit") or 0.0),
                "descripcion": str(item.get("description") or f"Causación Factura {inv.get('full_number', '')}").strip()
            })
        
        return pd.DataFrame(rows)

    def export_siigo(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Siigo_Import', index=False)
        return output.getvalue()

    def export_helisa(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        return export_df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

    def export_loggro(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Loggro_Import', index=False)
        return output.getvalue()

    def export_syscafe(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito"]]
        return export_df.to_csv(index=False, sep='\t', header=False).encode('utf-8')

    def export_alegra(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["fecha", "comprobante", "consecutivo", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Alegra_Import', index=False)
        return output.getvalue()

    def export_world_office(self, organization_id: str) -> bytes:
        df = self._get_journal_data(organization_id)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='WorldOffice_Import', index=False)
        return output.getvalue()