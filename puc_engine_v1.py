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


class PucAccountingEngine:
    """
    Motor de causación contable según el Plan Único de Cuentas (PUC) de Colombia.
    Maneja la imputación de débitos y créditos con soporte para agrupación de impuestos
    y parametrización de detalle por ítems (Modo A vs Modo B).
    """

    # Mapeo por defecto de Cuentas PUC para Impuestos y Retenciones
    TAX_ACCOUNT_MAP = {
        'IVA': {'account': '240810', 'name': 'IVA Descontable en Compras y Servicios'},
        'INC': {'account': '511595', 'name': 'Impuesto Nacional al Consumo (Mayor valor del gasto)'},
        'RETEFUENTE': {'account': '236540', 'name': 'Retención en la Fuente por Compras/Servicios'},
        'RETEIVA': {'account': '236701', 'name': 'Retención de IVA (ReteIVA)'},
        'RETEICA': {'account': '236801', 'name': 'Retención de Industria y Comercio (ReteICA)'},
        'IC_LICORES': {'account': '143505', 'name': 'Impuesto al Consumo Licores (Mayor valor inventario)'},
        'IC_CIGARRILLOS': {'account': '143505', 'name': 'Impuesto al Consumo Cigarrillos (Mayor valor inventario)'},
        'INC_BOLSAS': {'account': '511595', 'name': 'Impuesto al Consumo de Bolsas Plásticas'},
        'IBUA': {'account': '511595', 'name': 'Impuesto Bebidas Azucaradas'},
        'ICUI': {'account': '511595', 'name': 'Impuesto Alimentos Ultraprocesados'},
    }

    # Cuentas PUC predeterminadas para Compras y Proveedores
    DEFAULT_PURCHASE_ACCOUNT = "513595"  # Gastos Diversos / Compras Generales
    DEFAULT_PROVIDER_ACCOUNT = "220505"  # Proveedores Nacionales

    def __init__(
        self,
        default_purchase_account: Optional[str] = None,
        default_provider_account: Optional[str] = None,
        custom_tax_accounts: Optional[Dict[str, Dict[str, str]]] = None
    ):
        if default_purchase_account:
            self.DEFAULT_PURCHASE_ACCOUNT = default_purchase_account
        if default_provider_account:
            self.DEFAULT_PROVIDER_ACCOUNT = default_provider_account
        if custom_tax_accounts:
            self.TAX_ACCOUNT_MAP.update(custom_tax_accounts)

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

        # -------------------------------------------------------------------
        # 1. DEBITOS: Imputación de Ítems (Modo A vs Modo B)
        # -------------------------------------------------------------------
        if mode == GroupingMode.CONSOLIDATED:
            # Modo A: Sumar subtotales de ítems en una sola línea
            lines.append(AccountingEntryLine(
                account_puc=self.DEFAULT_PURCHASE_ACCOUNT,
                account_name="Gastos / Compras Factura " + full_number,
                third_party_nit=issuer_nit,
                third_party_name=issuer_name,
                debit=round(line_extension_amount, 2),
                credit=0.0,
                description=f"Causación consolidada Factura {full_number}"
            ))
        else:
            # Modo B: Generar una línea por cada ítem de la factura
            for item in items:
                lines.append(AccountingEntryLine(
                    account_puc=self.DEFAULT_PURCHASE_ACCOUNT,
                    account_name=f"Ítem: {item.get('description', 'Producto/Servicio')[:40]}",
                    third_party_nit=issuer_nit,
                    third_party_name=issuer_name,
                    debit=round(float(item.get('subtotal', 0.0)), 2),
                    credit=0.0,
                    description=f"Línea {item.get('line_number', 1)} - {item.get('description', '')}"
                ))

        # -------------------------------------------------------------------
        # 2. DEBITOS / CREDITOS: Agrupación Consolidada de Impuestos
        # -------------------------------------------------------------------
        # Agrupar impuestos por (tax_type, percent)
        tax_groups: Dict[tuple, float] = {}
        for tax in taxes:
            key = (tax.get('type'), tax.get('percent', 0.0))
            tax_groups[key] = tax_groups.get(key, 0.0) + float(tax.get('tax_amount', 0.0))

        for (tax_type, percent), amount in tax_groups.items():
            amount = round(amount, 2)
            if amount <= 0:
                continue

            tax_info = self.TAX_ACCOUNT_MAP.get(tax_type, {
                'account': '236599',
                'name': f'Otros Impuestos ({tax_type})'
            })
            account_code = tax_info['account']
            account_name = f"{tax_info['name']} ({percent}%)"

            # Determinar la naturaleza contable (Retenciones son Crédito, IVA/INC son Débito)
            if tax_type in ['RETEFUENTE', 'RETEIVA', 'RETEICA']:
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
        # 3. CREDITOS: Cuentas por Pagar a Proveedores
        # -------------------------------------------------------------------
        lines.append(AccountingEntryLine(
            account_puc=self.DEFAULT_PROVIDER_ACCOUNT,
            account_name="Proveedores Nacionales",
            third_party_nit=issuer_nit,
            third_party_name=issuer_name,
            debit=0.0,
            credit=round(payable_amount, 2),
            description=f"Cuenta por pagar Proveedor Factura {full_number}"
        ))

        # -------------------------------------------------------------------
        # 4. Validar Balance de Partida Doble (Débitos = Créditos)
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
            is_balanced=is_balanced
        )