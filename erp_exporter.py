import io
from typing import Optional
import pandas as pd
from supabase import Client


class ErpExporterEngine:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def _get_journal_data(
        self,
        organization_id: str,
        tipo_documento: str,
        comprobante: str
    ) -> pd.DataFrame:
        """
        Consulta las líneas del libro diario (journal_lines) y su documento asociado
        para la organización, filtrando estrictamente por `tipo_documento` (01, 91, 92)
        y asignando el código de `comprobante` indicado por el usuario.
        """
        doc_type = str(tipo_documento or "").strip()
        voucher = str(comprobante or "").strip()

        if doc_type not in ("01", "91", "92"):
            raise ValueError("Tipo de documento inválido para exportación. Use '01', '91' o '92'.")

        if not voucher:
            raise ValueError("El número o código de comprobante es obligatorio para exportar.")

        res = self.supabase.table("journal_lines")\
            .select("*, invoices(full_number, issue_date, issuer_nit, issuer_name, document_type)")\
            .eq("organization_id", organization_id)\
            .execute()

        data = res.data if res and res.data else []
        if not data:
            raise ValueError("No se encontraron movimientos contables causados en 'journal_lines' para la organización.")

        rows = []
        for item in data:
            inv = item.get("invoices") or {}
            inv_doc_type = str(inv.get("document_type") or "01").strip()
            if inv_doc_type != doc_type:
                continue

            full_num = str(inv.get("full_number") or "S/N").strip()
            rows.append({
                "comprobante": voucher,
                "consecutivo": full_num,
                "fecha": str(inv.get("issue_date") or "2026-01-01")[:10],
                "cuenta": str(item.get("account_code") or "").strip(),
                "tercero": str(item.get("third_party_nit") or inv.get("issuer_nit") or "0").strip(),
                "debito": float(item.get("debit") or 0.0),
                "credito": float(item.get("credit") or 0.0),
                "descripcion": str(item.get("description") or f"Causación {full_num}").strip()
            })

        if not rows:
            raise ValueError(
                f"No se encontraron movimientos causados para el tipo de documento '{doc_type}' en la organización."
            )

        return pd.DataFrame(rows)

    def export_siigo(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Siigo_Import', index=False)
        return output.getvalue()

    def export_helisa(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]
        return export_df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

    def export_loggro(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Loggro_Import', index=False)
        return output.getvalue()

    def export_syscafe(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito"]]
        return export_df.to_csv(index=False, sep='\t', header=False).encode('utf-8')

    def export_alegra(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["fecha", "comprobante", "consecutivo", "cuenta", "tercero", "debito", "credito", "descripcion"]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Alegra_Import', index=False)
        return output.getvalue()

    def export_world_office(self, organization_id: str, tipo_documento: str = "01", comprobante: str = "") -> bytes:
        df = self._get_journal_data(organization_id, tipo_documento=tipo_documento, comprobante=comprobante)
        export_df = df[["comprobante", "consecutivo", "fecha", "cuenta", "tercero", "debito", "credito", "descripcion"]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='WorldOffice_Import', index=False)
        return output.getvalue()