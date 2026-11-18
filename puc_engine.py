from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


class GroupingMode(str, Enum):
    CONSOLIDATED = "CONSOLIDATED"
    DETAILED = "DETAILED"


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
    document_type: str
    grouping_mode: GroupingMode
    lines: List[AccountingEntryLine]
    total_debit: float
    total_credit: float
    is_balanced: bool
    resolved_purchase_accounts_audit: List[Dict]
    resolved_taxes: List[Dict]


class PucAccountingEngine:
    """
    Motor de causación contable inteligente e híbrido.
    Soporta Facturas (01), Notas Crédito (91) y Notas Débito (92) guiado por datos.
    """

    def __init__(
        self,
        company_parameters: Dict[str, Dict[str, str]],
        provider_rules: Optional[Dict[str, str]] = None,
        unspsc_master: Optional[Dict[str, Dict[str, any]]] = None
    ):
        self.params = company_parameters
        self.provider_rules = provider_rules or {}
        self.unspsc_master = unspsc_master or {}

    def _resolve_item_account(self, item: dict, issuer_nit: str, document_type: str) -> Dict[str, any]:
        unspsc_code = ""
        if issuer_nit in self.provider_rules:
            unspsc_code = str(self.provider_rules[issuer_nit]).strip()

        if not unspsc_code:
            unspsc_code = str(item.get('unspsc_code', '')).strip()

        # Búsqueda en maestro UNSPSC considerando el tipo de documento (o comodín '01')
        if unspsc_code:
            key_doc = f"{unspsc_code}_{document_type}"
            key_default = f"{unspsc_code}_01"
            unspsc_info = self.unspsc_master.get(key_doc) or self.unspsc_master.get(unspsc_code) or self.unspsc_master.get(key_default)
            
            if unspsc_info:
                suggested_acc = unspsc_info.get('suggested_puc_account')
                suggested_tipmov = unspsc_info.get('suggested_tipmov', 'D')
                if suggested_acc:
                    return {
                        'account': suggested_acc,
                        'name': f"UNSPSC {unspsc_code}: {unspsc_info.get('description', 'Inventario/Gasto')}",
                        'tipmov': suggested_tipmov,
                        'source': f'UNSPSC_{document_type}'
                    }

        # Respaldo contra parámetros de la empresa buscando por tipo de documento
        for candidate in [f'COMPRA_{document_type}', 'COMPRA', 'COMPRAS', 'GASTO', 'COSTO']:
            if candidate in self.params:
                return {**self.params[candidate], 'tipmov': 'C' if document_type == '91' else 'D', 'source': f'COMPANY_PARAM_{candidate}'}

        raise ValueError(
            f"Falta parametrización contable: El ítem (Descripción: '{item.get('description', 'Sin descripción')}', "
            f"UNSPSC: '{unspsc_code}') para el documento tipo {document_type} no pudo ser clasificado."
        )

    def generate_journal_entry(
        self,
        invoice_id: str,
        full_number: str,
        document_type: str,
        issuer_nit: str,
        issuer_name: str,
        line_extension_amount: float,
        payable_amount: float,
        items: List[dict],
        taxes: List[dict],
        mode: GroupingMode = GroupingMode.CONSOLIDATED
    ) -> AccountingJournalEntry:
        lines: List[AccountingEntryLine] = []
        resolved_accounts_audit = []
        resolved_taxes_audit = []

        # -------------------------------------------------------------------
        # 1. IMPUTACIÓN DE ÍTEMS (Débito o Crédito según documento y tipmov)
        # -------------------------------------------------------------------
        if mode == GroupingMode.CONSOLIDATED:
            sample_item = items[0] if items else {}
            item_info = self._resolve_item_account(sample_item, issuer_nit, document_type)
            resolved_accounts_audit.append(item_info)

            is_credit_mov = (item_info.get('tipmov') == 'C') or (document_type == '91')
            
            lines.append(AccountingEntryLine(
                account_puc=item_info['account'],
                account_name=item_info['name'],
                third_party_nit=issuer_nit,
                third_party_name=issuer_name,
                debit=0.0 if is_credit_mov else round(line_extension_amount, 2),
                credit=round(line_extension_amount, 2) if is_credit_mov else 0.0,
                description=f"Ajuste / Causación Doc {full_number} (Tipo {document_type})"
            ))
        else:
            for item in items:
                item_info = self._resolve_item_account(item, issuer_nit, document_type)
                resolved_accounts_audit.append(item_info)
                item_subtotal = round(float(item.get('subtotal', 0.0)), 2)
                
                if item_subtotal <= 0:
                    continue

                is_credit_mov = (item_info.get('tipmov') == 'C') or (document_type == '91')

                lines.append(AccountingEntryLine(
                    account_puc=item_info['account'],
                    account_name=item_info['name'][:40],
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=0.0 if is_credit_mov else item_subtotal,
                    credit=item_subtotal if is_credit_mov else 0.0,
                    description=f"Línea {item.get('line_number', 1)}: {item.get('description', '')[:60]}"
                ))

        # -------------------------------------------------------------------
        # 2. IMPUESTOS Y RETENCIONES (Inversión automática para Notas Crédito)
        # -------------------------------------------------------------------
        tax_groups: Dict[tuple, float] = {}
        for tax in taxes:
            t_type = str(tax.get('type', '')).upper()
            t_percent = float(tax.get('percent', 0.0))
            key = (t_type, t_percent)
            tax_groups[key] = tax_groups.get(key, 0.0) + float(tax.get('tax_amount', 0.0))

        total_credit_retentions = 0.0

        for (tax_type, percent), amount in tax_groups.items():
            amount = round(amount, 2)
            if amount <= 0:
                continue

            # Buscar parámetro para el impuesto cruzando tipo de documento
            tax_info = self.params.get(f"{tax_type}_{percent}_{document_type}") or self.params.get(f"{tax_type}_{percent}") or self.params.get(tax_type)
            if not tax_info:
                raise ValueError(f"Falta parámetro contable: El impuesto '{tax_type}' ({percent}%) para doc tipo {document_type} no está configurado.")

            account_code = tax_info['account']
            account_name = tax_info['name']

            resolved_taxes_audit.append({'type': tax_type, 'percent': percent, 'account': account_code, 'amount': amount})

            # Si es Nota Crédito (91), invertimos el efecto del impuesto
            if tax_type in ['RETEFUENTE', 'RETEIVA', 'RETEICA']:
                # En NC, la retención va al Débito para revertir la retención inicial
                debit_val = amount if document_type == '91' else 0.0
                credit_val = 0.0 if document_type == '91' else amount
                if credit_val > 0:
                    total_credit_retentions += credit_val
                
                lines.append(AccountingEntryLine(
                    account_puc=account_code, account_name=account_name,
                    third_party_nit=issuer_nit, third_party_name=issuer_name,
                    debit=debit_val, credit=credit_val,
                    description=f"Reversión/Ajuste {tax_type} {percent}% Doc {full_number}"
                ))
            else:
                debit_val = 0.0 if document_type == '91' else amount
                credit_val = amount if document_type == '91' else 0.0
                lines.append(AccountingEntryLine(
                    account_puc=account_code, account_name=account_name,
                    third_party_nit=issuer_nit, third_party_name=issuer_name,
                    debit=debit_val, credit=credit_val,
                    description=f"IVA/Impuesto {tax_type} {percent}% Doc {full_number}"
                ))

        # -------------------------------------------------------------------
        # 3. PROVEEDOR / CUENTA POR PAGAR (El núcleo del ajuste)
        # -------------------------------------------------------------------
        provider_info = self.params.get(f"PROVIDER_DEFAULT_{document_type}") or self.params.get("PROVIDER_DEFAULT")
        if not provider_info:
            for code, info in self.params.items():
                if info.get('account', '').startswith('2') and ('PROVEEDOR' in code.upper() or 'PAGAR' in code.upper()):
                    provider_info = info
                    break

        if not provider_info:
            raise ValueError("Falta parametrización contable: No se encontró cuenta por Pagar (Clase 2).")

        # Regla contable clave:
        # - Factura (01) o Nota Débito (92): Proveedor al CRÉDITO (Aumenta la deuda).
        # - Nota Crédito (91): Proveedor al DÉBITO (Disminuye la deuda / devolución).
        net_amount = round(payable_amount - total_credit_retentions, 2)

        if document_type == '91':
            debit_prov = net_amount
            credit_prov = 0.0
        else:
            debit_prov = 0.0
            credit_prov = net_amount

        lines.append(AccountingEntryLine(
            account_puc=provider_info['account'],
            account_name=provider_info['name'],
            third_party_nit=issuer_nit,
            third_party_name=issuer_name,
            debit=debit_prov,
            credit=credit_prov,
            description=f"Cuenta por pagar Proveedor Doc {full_number} (Tipo {document_type})"
        ))

        total_debit = round(sum(line.debit for line in lines), 2)
        total_credit = round(sum(line.credit for line in lines), 2)
        is_balanced = abs(total_debit - total_credit) < 0.01

        return AccountingJournalEntry(
            invoice_id=invoice_id,
            full_number=full_number,
            document_type=document_type,
            grouping_mode=mode,
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=is_balanced,
            resolved_purchase_accounts_audit=resolved_accounts_audit,
            resolved_taxes=resolved_taxes_audit
        )