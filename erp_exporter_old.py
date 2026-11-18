import io
import pandas as pd
from typing import List, Dict, Tuple
from supabase import Client


class ErpExporterEngine:
    """
    Transforma asientos contables causados en Supabase a formatos de importación masiva
    para ERPs colombianos (Siigo, Helisa, Loggro, SysCafé, Alegra y World Office).
    """

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def _get_causation_data(self, company_id: str, invoice_ids: List[str] = None) -> List[Dict]:
        """Obtiene y construye las líneas de causación balanceadas para los ERPs."""
        query = self.supabase.table("invoices").select("*").eq("company_id", company_id).eq("status", "CAUSADO")
        if invoice_ids:
            query = query.in_("id", invoice_ids)
        
        inv_res = query.execute()
        if not inv_res.data:
            raise ValueError("No se encontraron facturas causadas para exportar.")

        params_res = self.supabase.table("company_accounting_parameters").select("*").eq("company_id", company_id).execute()
        company_params = {r["concept_code"]: r["account_puc"] for r in (params_res.data or [])}

        rules_res = self.supabase.table("accounting_rules").select("*").eq("company_id", company_id).execute()
        provider_rules = {r["match_value"]: r["debit_puc"] for r in (rules_res.data or []) if r.get("match_value") and r.get("debit_puc")}

        compiled_lines = []

        for invoice in inv_res.data:
            inv_id = invoice["id"]
            full_number = invoice["full_number"]
            number = invoice["number"]
            issue_date = invoice["issue_date"]  # YYYY-MM-DD
            issuer_nit = invoice["issuer_nit"]
            issuer_name = invoice["issuer_name"]
            line_extension_amount = float(invoice["line_extension_amount"])
            payable_amount = float(invoice["payable_amount"])

            taxes_res = self.supabase.table("invoice_taxes").select("*").eq("invoice_id", inv_id).execute()

            # 1. Débito (Gasto/Compra)
            debit_account = provider_rules.get(issuer_nit) or company_params.get("PURCHASE_DEFAULT", "51359501")
            compiled_lines.append({
                "invoice_id": inv_id,
                "full_number": full_number,
                "number": number,
                "date": issue_date,
                "nit": issuer_nit,
                "name": issuer_name,
                "account": debit_account,
                "debit": round(line_extension_amount, 2),
                "credit": 0.0,
                "description": f"Causación Factura {full_number}"
            })

            # 2. Impuestos
            tax_groups = {}
            for t in (taxes_res.data or []):
                key = (t.get("type"), t.get("percent", 0.0))
                tax_groups[key] = tax_groups.get(key, 0.0) + float(t.get("tax_amount", 0.0))

            for (tax_type, percent), amount in tax_groups.items():
                amount = round(amount, 2)
                if amount <= 0:
                    continue
                
                concept_key = f"{tax_type}_{percent}"
                tax_account = company_params.get(concept_key, "23659901")

                if tax_type in ['RETEFUENTE', 'RETEIVA', 'RETEICA']:
                    compiled_lines.append({
                        "invoice_id": inv_id,
                        "full_number": full_number,
                        "number": number,
                        "date": issue_date,
                        "nit": issuer_nit,
                        "name": issuer_name,
                        "account": tax_account,
                        "debit": 0.0,
                        "credit": amount,
                        "description": f"{tax_type} {percent}% Factura {full_number}"
                    })
                else:
                    compiled_lines.append({
                        "invoice_id": inv_id,
                        "full_number": full_number,
                        "number": number,
                        "date": issue_date,
                        "nit": issuer_nit,
                        "name": issuer_name,
                        "account": tax_account,
                        "debit": amount,
                        "credit": 0.0,
                        "description": f"{tax_type} {percent}% Factura {full_number}"
                    })

            # 3. Crédito (Proveedor)
            provider_account = company_params.get("PROVIDER_DEFAULT", "22050501")
            compiled_lines.append({
                "invoice_id": inv_id,
                "full_number": full_number,
                "number": number,
                "date": issue_date,
                "nit": issuer_nit,
                "name": issuer_name,
                "account": provider_account,
                "debit": 0.0,
                "credit": round(payable_amount, 2),
                "description": f"Cuenta por Pagar Factura {full_number}"
            })

        return compiled_lines

    # --- 1. Exportador SIIGO NUBE (Excel) ---
    def export_siigo(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            parts = line["date"].split("-")
            formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else line["date"]
            rows.append({
                "Código Cuenta PUC": line["account"],
                "Identificación Tercero": line["nit"],
                "Sucursal": "0",
                "Tipo Comprobante": "F-1",
                "Número Comprobante": line["number"],
                "Fecha Elaboración": formatted_date,
                "Débito": line["debit"],
                "Crédito": line["credit"],
                "Descripción": line["description"]
            })
        df = pd.DataFrame(rows)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Importacion_Siigo', index=False)
        return out.getvalue()

    # --- 2. Exportador HELISA (CSV / TXT Separado por punto y coma) ---
    def export_helisa(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            formatted_date = line["date"].replace("-", "")  # YYYYMMDD
            rows.append({
                "FECHA": formatted_date,
                "COMPROBANTE": "CE",
                "NUMERO": line["number"],
                "CUENTA": line["account"],
                "NIT": line["nit"],
                "DEBITO": line["debit"],
                "CREDITO": line["credit"],
                "CONCEPTO": line["description"]
            })
        df = pd.DataFrame(rows)
        csv_str = df.to_csv(index=False, sep=";", encoding="latin1")
        return csv_str.encode("latin1")

    # --- 3. Exportador LOGGRO NUBE (Excel) ---
    def export_loggro(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            rows.append({
                "Tipo Documento": "Comprobante de Egreso / Causacion",
                "Consecutivo": line["number"],
                "Fecha (AAAA-MM-DD)": line["date"],
                "Cuenta Contable": line["account"],
                "Tercero (NIT/CC)": line["nit"],
                "Razon Social": line["name"],
                "Valor Debito": line["debit"],
                "Valor Credito": line["credit"],
                "Observaciones": line["description"]
            })
        df = pd.DataFrame(rows)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Plantilla_Loggro', index=False)
        return out.getvalue()

    # --- 4. Exportador SYSCAFÉ (TXT plano con separador de barra vertical) ---
    def export_syscafe(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            rows.append({
                "COD_COMP": "COM",
                "NUM_COMP": line["number"],
                "FECHA": line["date"],
                "CUENTA": line["account"],
                "NIT": line["nit"],
                "DEBITO": line["debit"],
                "CREDITO": line["credit"],
                "DETALLE": line["description"]
            })
        df = pd.DataFrame(rows)
        csv_str = df.to_csv(index=False, sep="|", encoding="utf-8")
        return csv_str.encode("utf-8")

    # --- 5. Exportador ALEGRA (Excel) ---
    def export_alegra(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            rows.append({
                "Fecha": line["date"],
                "Cuenta Contable": line["account"],
                "Identificación Proveedor": line["nit"],
                "Nombre Proveedor": line["name"],
                "Débito": line["debit"],
                "Crédito": line["credit"],
                "Nota / Observación": line["description"]
            })
        df = pd.DataFrame(rows)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Importar_Alegra', index=False)
        return out.getvalue()

    # --- 6. Exportador WORLD OFFICE (Excel) ---
    def export_world_office(self, company_id: str, invoice_ids: List[str] = None) -> bytes:
        lines = self._get_causation_data(company_id, invoice_ids)
        rows = []
        for line in lines:
            parts = line["date"].split("-")
            formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else line["date"]
            rows.append({
                "Tipo de Documento": "Comprobante de Contabilidad",
                "Prefijo": "CC",
                "Documento Número": line["number"],
                "Fecha": formatted_date,
                "Tercero Identificación": line["nit"],
                "Código Cuenta": line["account"],
                "Debito": line["debit"],
                "Credito": line["credit"],
                "Concepto": line["description"]
            })
        df = pd.DataFrame(rows)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Captura_WorldOffice', index=False)
        return out.getvalue()