from dataclasses import dataclass
from typing import List, Dict, Optional
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


class PucAccountingEngine:
    """
    Motor de causación contable inteligente e híbrido.
    Integra el maestro global UNSPSC, reglas por NIT y búsqueda flexible de impuestos.
    """

    def __init__(
        self,
        company_parameters: Dict[str, Dict[str, str]],
        provider_rules: Optional[Dict[str, str]] = None,
        unspsc_master: Optional[Dict[str, Dict[str, str]]] = None
    ):
        """
        :param company_parameters: Parámetros contables de la empresa ({ 'CONCEPT_CODE': {'account': '...', 'name': '...'} })
        :param provider_rules: Reglas de excepción por NIT ({NIT: cuenta_debit_puc})
        :param unspsc_master: Maestro global UNSPSC ({codigo: {'category_type': '...', 'suggested_puc_account': '...', 'description': '...'}})
        """
        self.params = company_parameters
        self.provider_rules = provider_rules or {}
        self.unspsc_master = unspsc_master or {}

    def _find_flexible_tax_info(self, tax_type: str, percent: float) -> Optional[Dict[str, str]]:
        """
        Busca de forma flexible (por aproximación) un concepto tributario en company_accounting_parameters.
        """
        exact_key = f"{tax_type}_{percent}"
        if exact_key in self.params:
            return self.params[exact_key]

        # Búsqueda flexible por subcadenas (ej. que contenga el tipo y el porcentaje)
        for code, info in self.params.items():
            code_upper = code.upper()
            if tax_type in code_upper and str(percent) in code_upper:
                return info

        # Búsqueda de respaldo solo por tipo de impuesto
        for code, info in self.params.items():
            if code.upper() == tax_type:
                return info

        return None

    def _resolve_item_account(self, item: dict, issuer_nit: str) -> Dict[str, str]:
        """
        Resuelve la cuenta contable y categoría para un ítem basándose en:
        1. Cuenta persistida en el ítem.
        2. Regla de excepción por NIT del proveedor.
        3. Código UNSPSC del ítem contra el maestro global.
        4. Parámetro general de compra por defecto.
        """
        # 1. Si ya tiene cuenta persistida
        if item.get('puc_account_debit') or item.get('puc_account'):
            acc = item.get('puc_account_debit') or item.get('puc_account')
            return {'account': acc, 'name': f"Cuenta asignada en ítem", 'source': 'PERSISTED'}

        # 2. Excepción por NIT del proveedor
        if issuer_nit in self.provider_rules:
            return {
                'account': self.provider_rules[issuer_nit],
                'name': f"Gasto/Compra por Excepción NIT {issuer_nit}",
                'source': 'NIT_RULE'
            }

        # 3. Maestro UNSPSC (¡La inteligencia por ítem que adoptamos!)
        unspsc_code = str(item.get('unspsc_code', '')).strip()
        if unspsc_code and unspsc_code in self.unspsc_master:
            unspsc_info = self.unspsc_master[unspsc_code]
            return {
                'account': unspsc_info['suggested_puc_account'],
                'name': f"UNSPSC {unspsc_code}: {unspsc_info.get('description', 'Inventario/Gasto')}",
                'source': f"UNSPSC_{unspsc_info['category_type']}"
            }

        # 4. Parámetros generales de compra / gasto
        for candidate in ['PURCHASE_DEFAULT', 'COMPRA', 'GASTO', 'GASTOS', 'COMPRAS']:
            if candidate in self.params:
                return {**self.params[candidate], 'source': 'COMPANY_PARAM'}

        for code, info in self.params.items():
            if info.get('account', '').startswith(('5', '6', '14')) and 'RETE' not in code.upper() and 'IVA' not in code.upper():
                return {**info, 'source': 'FALLBACK_CLASS'}

        raise ValueError(
            f"Falta parametrización contable: El ítem con código UNSPSC '{unspsc_code}' del NIT {issuer_nit} "
            f"no tiene cuenta asignada ni se encontró un parámetro de compra general."
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
        mode: GroupingMode = GroupingMode.CONSOLIDATED
    ) -> AccountingJournalEntry:
        lines: List[AccountingEntryLine] = []
        resolved_accounts_audit = []
        resolved_taxes_audit = []

        # -------------------------------------------------------------------
        # 1. DÉBITOS: Imputación de Ítems (Consolidado o Detallado)
        # -------------------------------------------------------------------
        if mode == GroupingMode.CONSOLIDATED:
            # En modo consolidado, evaluamos el primer ítem o un genérico para definir la cuenta principal
            sample_item = items[0] if items else {}
            item_info = self._resolve_item_account(sample_item, issuer_nit)
            resolved_accounts_audit.append(item_info)

            lines.append(AccountingEntryLine(
                account_puc=item_info['account'],
                account_name=item_info['name'],
                third_party_nit=issuer_nit,
                third_party_name=issuer_name,
                debit=round(line_extension_amount, 2),
                credit=0.0,
                description=f"Causación Factura {full_number}"
            ))
        else:
            # Modo Detallado: Cada ítem se imputa a su propia cuenta según su UNSPSC o regla
            for item in items:
                item_info = self._resolve_item_account(item, issuer_nit)
                resolved_accounts_audit.append(item_info)
                item_subtotal = round(float(item.get('subtotal', 0.0)), 2)
                
                if item_subtotal <= 0:
                    continue

                lines.append(AccountingEntryLine(
                    account_puc=item_info['account'],
                    account_name=f"{item_info['name'][:40]}",
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=item_subtotal,
                    credit=0.0,
                    description=f"Línea {item.get('line_number', 1)}: {item.get('description', '')[:60]}"
                ))

        # -------------------------------------------------------------------
        # 2. DÉBITOS / CRÉDITOS: Impuestos y Retenciones
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

            tax_info = self._find_flexible_tax_info(tax_type, percent)
            if not tax_info:
                raise ValueError(
                    f"Falta parámetro contable: El impuesto '{tax_type}' ({percent}%) "
                    f"no está configurado en company_accounting_parameters para esta organización."
                )

            account_code = tax_info['account']
            account_name = tax_info['name']

            resolved_taxes_audit.append({
                'type': tax_type,
                'percent': percent,
                'account': account_code,
                'amount': amount
            })

            # Naturaleza contable: Retenciones al Crédito, IVA Descontable al Débito
            if tax_type in ['RETEFUENTE', 'RETEIVA', 'RETEICA']:
                total_credit_retentions += amount
                lines.append(AccountingEntryLine(
                    account_puc=account_code,
                    account_name=account_name,
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=0.0,
                    credit=amount,
                    description=f"{tax_type} {percent}% Factura {full_number}"
                ))
            else:
                lines.append(AccountingEntryLine(
                    account_puc=account_code,
                    account_name=account_name,
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=amount,
                    credit=0.0,
                    description=f"{tax_type} {percent}% Factura {full_number}"
                ))
                
        # -------------------------------------------------------------------
        # 3. CRÉDITOS: Proveedor (Cuenta por Pagar - Valor Neto)
        # -------------------------------------------------------------------
        provider_info = None
        for candidate in ['PROVIDER_DEFAULT', 'PROVEEDOR', 'PROVEEDORES', 'CUENTA_POR_PAGAR']:
            if candidate in self.params:
                provider_info = self.params[candidate]
                break
        
        if not provider_info:
            for code, info in self.params.items():
                if info.get('account', '').startswith('2') and ('PROVEEDOR' in code.upper() or 'PAGAR' in code.upper()):
                    provider_info = info
                    break

        if not provider_info:
            raise ValueError(
                "Falta parametrización contable: No se encontró un concepto de Proveedor o Cuenta por Pagar (Clase 2) "
                "en company_accounting_parameters."
            )

        # EL SECRETO CONTABLE: El proveedor se registra por el Total Factura MENOS las retenciones practicadas
        net_payable_amount = round(payable_amount - total_credit_retentions, 2)

        lines.append(AccountingEntryLine(
            account_puc=provider_info['account'],
            account_name=provider_info['name'],
            third_party_nit=issuer_nit,
            third_party_name=issuer_name,
            debit=0.0,
            credit=net_payable_amount,
            description=f"Cuenta por pagar Proveedor Factura {full_number} (Neto)"
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
            resolved_taxes=resolved_taxes_audit
        )