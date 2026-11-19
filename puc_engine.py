from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum


class GroupingMode(str, Enum):
    CONSOLIDATED = "CONSOLIDATED"  # Modo A: Agrupar ítems en una sola línea de gasto/compra
    DETAILED = "DETAILED"          # Modo B: Una línea por cada ítem (inventarios/centros de costo)


@dataclass
class AccountingEntryLine:
    account_puc: str
    account_name: str
    third_party_nit: str
    third_party_name: str
    debit: float
    credit: float
    description: str


@dataclass
class AccountingJournalEntry:
    invoice_id: str
    full_number: str
    grouping_mode: GroupingMode
    lines: List[AccountingEntryLine]
    total_debit: float
    total_credit: float
    is_balanced: bool
    resolved_purchase_accounts_audit: List[Dict]
    resolved_taxes: List[Dict]
    tipo_documento: str = "01"
    document_type: str = "01"


class PucAccountingEngine:
    """
    Motor de causación contable inteligente e híbrido.
    Integra el maestro global UNSPSC, reglas por NIT, búsqueda flexible de impuestos
    y soporte para Facturas (01), Notas Crédito (91) y Notas Débito (92)
    consultando el campo `tipo_documento`.
    """

    def __init__(
        self,
        company_parameters: Dict[str, Dict[str, Any]],
        provider_rules: Optional[Dict[str, Any]] = None,
        unspsc_master: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        self.params = company_parameters or {}
        self.provider_rules = provider_rules or {}
        self.unspsc_master = unspsc_master or {}

    @staticmethod
    def _normalize_doc_type(tipo_documento: Optional[str]) -> str:
        doc = str(tipo_documento or "01").strip()
        if doc in ("91", "NC", "NOTA_CREDITO", "CREDIT_NOTE"):
            return "91"
        if doc in ("92", "ND", "NOTA_DEBITO", "DEBIT_NOTE"):
            return "92"
        return "01"

    def _matches_tipo_documento(self, key: str, info: Any, doc_type: str) -> bool:
        if isinstance(info, dict):
            row_doc = str(info.get("tipo_documento") or "").strip()
            if row_doc:
                return self._normalize_doc_type(row_doc) == doc_type
        key_upper = str(key).upper()
        return key_upper.endswith(f"_{doc_type}") or f"_{doc_type}_" in key_upper

    def _find_flexible_tax_info(
        self,
        tax_type: str,
        percent: float,
        tipo_documento: str = "01"
    ) -> Optional[Dict[str, Any]]:
        """
        Busca de forma flexible un concepto tributario en company_accounting_parameters,
        priorizando el campo `tipo_documento` y manteniendo la cascada flexible original.
        """
        doc_type = self._normalize_doc_type(tipo_documento)
        tax_upper = str(tax_type).upper().strip()
        pct_str = str(percent)

        # 1. Coincidencias exactas con tipo_documento
        exact_doc_keys = [
            f"{tax_upper}_{pct_str}_{doc_type}",
            f"{tax_upper}_{int(percent)}_{doc_type}" if float(percent).is_integer() else "",
            f"{tax_upper}_{doc_type}",
        ]
        for k in exact_doc_keys:
            if k and k in self.params:
                return self.params[k]

        # 2. Coincidencias flexibles filtrando por tipo_documento
        for code, info in self.params.items():
            code_upper = code.upper()
            if self._matches_tipo_documento(code, info, doc_type) and tax_upper in code_upper and pct_str in code_upper:
                return info

        for code, info in self.params.items():
            code_upper = code.upper()
            if self._matches_tipo_documento(code, info, doc_type) and code_upper.startswith(tax_upper):
                return info

        # 3. Cascada flexible original sin filtrar por tipo_documento
        exact_key = f"{tax_upper}_{pct_str}"
        if exact_key in self.params:
            return self.params[exact_key]

        for code, info in self.params.items():
            code_upper = code.upper()
            if tax_upper in code_upper and pct_str in code_upper:
                return info

        for code, info in self.params.items():
            if code.upper() == tax_upper:
                return info

        return None

    def _lookup_unspsc_entry(self, unspsc_code: str, doc_type: str) -> Optional[Dict[str, Any]]:
        """
        Busca en unspsc_master consultando primero `tipo_documento` y cayendo
        al código base si no existe registro específico para ese tipo_documento.
        """
        code = str(unspsc_code or "").strip()
        if not code:
            return None

        candidate_keys = [
            f"{code}_{doc_type}",
            f"{code}:{doc_type}",
            f"{code}-{doc_type}",
            code,
        ]
        for key in candidate_keys:
            entry = self.unspsc_master.get(key)
            if isinstance(entry, dict):
                entry_doc = str(entry.get("tipo_documento") or "").strip()
                if not entry_doc or self._normalize_doc_type(entry_doc) == doc_type or key == code:
                    return entry

        for key, entry in self.unspsc_master.items():
            if not isinstance(entry, dict):
                continue
            entry_code = str(entry.get("code") or key).split("_")[0].strip()
            entry_doc = str(entry.get("tipo_documento") or "").strip()
            if entry_code == code and entry_doc and self._normalize_doc_type(entry_doc) == doc_type:
                return entry

        for key, entry in self.unspsc_master.items():
            if not isinstance(entry, dict):
                continue
            entry_code = str(entry.get("code") or key).split("_")[0].strip()
            if entry_code == code:
                return entry

        return None

    def _resolve_item_account(
        self,
        item: dict,
        issuer_nit: str,
        tipo_documento: str = "01"
    ) -> Dict[str, Any]:
        """
        Resuelve la cuenta contable y categoría para un ítem manteniendo la cascada
        de puc_engine_old.py y consultando `tipo_documento` (01, 91, 92):
        1. Cuenta persistida en el ítem.
        2. Regla por NIT del proveedor (provider_rules).
        3. Código UNSPSC en el ítem y en el maestro global (unspsc_master).
        4. Cascada contra parámetros de la empresa (Compra / Gasto / Costo).
        5. Respaldo definitivo por clase PUC (5, 6, 14).
        """
        doc_type = self._normalize_doc_type(tipo_documento)
        clean_nit = str(issuer_nit or "").strip()

        # 1. Si ya tiene cuenta persistida
        if item.get("puc_account_debit") or item.get("puc_account"):
            acc = item.get("puc_account_debit") or item.get("puc_account")
            return {
                "account": acc,
                "name": "Cuenta asignada en ítem",
                "source": "PERSISTED",
                "tipo_documento": doc_type,
            }

        # 2. Regla por NIT del proveedor
        raw_rule = self.provider_rules.get(clean_nit)
        has_provider_rule = False
        unspsc_code = ""

        if isinstance(raw_rule, dict):
            rule_doc = str(raw_rule.get("tipo_documento") or "").strip()
            if not rule_doc or self._normalize_doc_type(rule_doc) == doc_type:
                rule_val = str(raw_rule.get("unspsc_code") or raw_rule.get("unspsc") or raw_rule.get("account") or "").strip()
                if rule_val:
                    has_provider_rule = True
                    unspsc_code = rule_val
        elif raw_rule is not None and str(raw_rule).strip():
            has_provider_rule = True
            unspsc_code = str(raw_rule).strip()

        if has_provider_rule and unspsc_code.isdigit() and len(unspsc_code) >= 6 and not self._lookup_unspsc_entry(unspsc_code, doc_type):
            return {
                "account": unspsc_code,
                "name": f"Excepción NIT {clean_nit} ({unspsc_code})",
                "source": "NIT_DIRECT_RULE",
                "tipo_documento": doc_type,
            }

        # 3. Si el NIT no tiene regla propia, tomamos el UNSPSC del ítem
        if not unspsc_code:
            unspsc_code = str(item.get("unspsc_code") or item.get("unspsc") or "").strip()

        # 4. Buscamos ese código en unspsc_master consultando tipo_documento
        if unspsc_code:
            unspsc_info = self._lookup_unspsc_entry(unspsc_code, doc_type)
            if unspsc_info:
                suggested_acc = unspsc_info.get("suggested_puc_account") or unspsc_info.get("puc_account")
                if suggested_acc:
                    source_label = (
                        "NIT_UNSPSC_RULE"
                        if has_provider_rule
                        else f"UNSPSC_{unspsc_info.get('category_type', 'GENERAL')}"
                    )
                    return {
                        "account": suggested_acc,
                        "name": f"UNSPSC {unspsc_code}: {unspsc_info.get('description', 'Inventario/Gasto')}",
                        "source": source_label,
                        "tipo_documento": doc_type,
                    }

        # 5. Cascada contra parámetros de la empresa (priorizando tipo_documento)
        base_candidates = [
            "COMPRA", "COMPRAS", "MERCANCIA", "INVENTARIO",
            "GASTO", "GASTOS", "COSTO", "COSTOS", "PURCHASE_DEFAULT"
        ]
        doc_candidates = [f"{c}_{doc_type}" for c in base_candidates]

        for candidate in doc_candidates + base_candidates:
            if candidate in self.params:
                return {
                    **self.params[candidate],
                    "source": f"COMPANY_PARAM_{candidate}",
                    "tipo_documento": doc_type,
                }

        # 6. Respaldo definitivo buscando cualquier cuenta de clase 5, 6 o 14
        for code, info in self.params.items():
            if self._matches_tipo_documento(code, info, doc_type):
                account_str = str(info.get("account", ""))
                if account_str.startswith(("5", "6", "14")) and "RETE" not in code.upper() and "IVA" not in code.upper():
                    return {**info, "source": "FALLBACK_PUC_CLASS_DOC", "tipo_documento": doc_type}

        for code, info in self.params.items():
            account_str = str(info.get("account", ""))
            if account_str.startswith(("5", "6", "14")) and "RETE" not in code.upper() and "IVA" not in code.upper():
                return {**info, "source": "FALLBACK_PUC_CLASS", "tipo_documento": doc_type}

        raise ValueError(
            f"Falta parametrización contable: El ítem (Descripción: '{item.get('description', 'Sin descripción')}', "
            f"UNSPSC: '{unspsc_code}', tipo_documento: '{doc_type}') del NIT {clean_nit} no pudo ser clasificado "
            f"porque la organización no tiene cuentas configuradas para Compras, Gastos o Costos en sus Parámetros Contables."
        )

    def _resolve_provider_account(self, tipo_documento: str) -> Dict[str, Any]:
        """
        Resuelve la cuenta por pagar del proveedor (Clase 2) consultando primero
        `tipo_documento` y luego los respaldos generales.
        """
        doc_type = self._normalize_doc_type(tipo_documento)
        base_candidates = ["PROVIDER_DEFAULT", "PROVEEDOR", "PROVEEDORES", "CUENTA_POR_PAGAR"]
        doc_candidates = [f"{c}_{doc_type}" for c in base_candidates]

        for candidate in doc_candidates + base_candidates:
            if candidate in self.params:
                return self.params[candidate]

        for code, info in self.params.items():
            if self._matches_tipo_documento(code, info, doc_type):
                if str(info.get("account", "")).startswith("2") and (
                    "PROVEEDOR" in code.upper() or "PAGAR" in code.upper()
                ):
                    return info

        for code, info in self.params.items():
            if str(info.get("account", "")).startswith("2") and (
                "PROVEEDOR" in code.upper() or "PAGAR" in code.upper()
            ):
                return info

        raise ValueError(
            "Falta parametrización contable: No se encontró un concepto de Proveedor o Cuenta por Pagar (Clase 2) "
            "en company_accounting_parameters."
        )

    def generate_journal_entry(
        self,
        invoice_id: str,
        full_number: str,
        issuer_nit: str,
        issuer_name: str,
        line_extension_amount: float,
        payable_amount: float,
        items: List[dict],
        taxes: List[dict],
        mode: GroupingMode = GroupingMode.CONSOLIDATED,
        tipo_documento: str = "01",
        document_type: Optional[str] = None
    ) -> AccountingJournalEntry:
        raw_doc = document_type if document_type is not None else tipo_documento
        doc_type = self._normalize_doc_type(raw_doc)
        is_credit_note = (doc_type == "91")
        doc_label = "Nota Crédito" if doc_type == "91" else ("Nota Débito" if doc_type == "92" else "Factura")

        lines: List[AccountingEntryLine] = []
        resolved_accounts_audit = []
        resolved_taxes_audit = []

        # -------------------------------------------------------------------
        # 1. IMPUTACIÓN DE ÍTEMS (Débito en 01/92; Crédito en Nota Crédito 91)
        # -------------------------------------------------------------------
        if mode == GroupingMode.CONSOLIDATED:
            sample_item = items[0] if items else {}
            item_info = self._resolve_item_account(sample_item, issuer_nit, doc_type)
            resolved_accounts_audit.append(item_info)

            amount_val = round(float(line_extension_amount or 0.0), 2)
            lines.append(AccountingEntryLine(
                account_puc=item_info["account"],
                account_name=item_info["name"],
                third_party_nit=issuer_nit,
                third_party_name=issuer_name,
                debit=0.0 if is_credit_note else amount_val,
                credit=amount_val if is_credit_note else 0.0,
                description=f"Causación {doc_label} {full_number}"
            ))
        else:
            for item in items:
                item_info = self._resolve_item_account(item, issuer_nit, doc_type)
                resolved_accounts_audit.append(item_info)
                item_subtotal = round(float(item.get("subtotal", 0.0)), 2)

                if item_subtotal <= 0:
                    continue

                lines.append(AccountingEntryLine(
                    account_puc=item_info["account"],
                    account_name=f"{item_info['name'][:40]}",
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=0.0 if is_credit_note else item_subtotal,
                    credit=item_subtotal if is_credit_note else 0.0,
                    description=f"Línea {item.get('line_number', 1)}: {item.get('description', '')[:60]}"
                ))

        # -------------------------------------------------------------------
        # 2. IMPUESTOS Y RETENCIONES
        # -------------------------------------------------------------------
        tax_groups: Dict[tuple, float] = {}
        for tax in taxes:
            t_type = str(tax.get("type", "")).upper()
            t_percent = float(tax.get("percent", 0.0))
            key = (t_type, t_percent)
            tax_groups[key] = tax_groups.get(key, 0.0) + float(tax.get("tax_amount", 0.0))

        total_retention_adjustment = 0.0

        for (tax_type, percent), amount in tax_groups.items():
            amount = round(amount, 2)
            if amount <= 0:
                continue

            tax_info = self._find_flexible_tax_info(tax_type, percent, doc_type)
            if not tax_info:
                raise ValueError(
                    f"Falta parámetro contable: El impuesto '{tax_type}' ({percent}%) "
                    f"no está configurado en company_accounting_parameters para esta organización."
                )

            account_code = tax_info["account"]
            account_name = tax_info["name"]

            resolved_taxes_audit.append({
                "type": tax_type,
                "percent": percent,
                "account": account_code,
                "amount": amount,
                "tipo_documento": doc_type
            })

            if tax_type in ["RETEFUENTE", "RETEIVA", "RETEICA"]:
                debit_val = amount if is_credit_note else 0.0
                credit_val = 0.0 if is_credit_note else amount
                if not is_credit_note:
                    total_retention_adjustment += credit_val
                else:
                    total_retention_adjustment -= debit_val

                lines.append(AccountingEntryLine(
                    account_puc=account_code,
                    account_name=account_name,
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=debit_val,
                    credit=credit_val,
                    description=f"{tax_type} {percent}% {doc_label} {full_number}"
                ))
            else:
                debit_val = 0.0 if is_credit_note else amount
                credit_val = amount if is_credit_note else 0.0
                lines.append(AccountingEntryLine(
                    account_puc=account_code,
                    account_name=account_name,
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=debit_val,
                    credit=credit_val,
                    description=f"{tax_type} {percent}% {doc_label} {full_number}"
                ))

        # -------------------------------------------------------------------
        # 3. PROVEEDOR / CUENTA POR PAGAR (Crédito en 01/92; Débito en 91)
        # -------------------------------------------------------------------
        provider_info = self._resolve_provider_account(doc_type)

        net_payable_amount = round(float(payable_amount or 0.0) - total_retention_adjustment, 2)

        lines.append(AccountingEntryLine(
            account_puc=provider_info["account"],
            account_name=provider_info["name"],
            third_party_nit=issuer_nit,
            third_party_name=issuer_name,
            debit=net_payable_amount if is_credit_note else 0.0,
            credit=0.0 if is_credit_note else net_payable_amount,
            description=f"Cuenta por pagar Proveedor {doc_label} {full_number} (Neto)"
        ))

        # -------------------------------------------------------------------
        # 4. Validar Balance de Partida Doble
        # -------------------------------------------------------------------
        total_debit = round(sum(line.debit for line in lines), 2)
        total_credit = round(sum(line.credit for line in lines), 2)
        is_balanced = abs(total_debit - total_credit) < 0.01

        return AccountingJournalEntry(
            invoice_id=invoice_id,
            full_number=full_number,
            grouping_mode=mode,
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=is_balanced,
            resolved_purchase_accounts_audit=resolved_accounts_audit,
            resolved_taxes=resolved_taxes_audit,
            tipo_documento=doc_type,
            document_type=doc_type
        )