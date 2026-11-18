import io
import zipfile
from dataclasses import dataclass
from typing import List, Optional, Union
from lxml import etree


@dataclass
class InvoiceItem:
    line_number: int
    seller_item_id: Optional[str]
    unspsc_code: Optional[str]
    description: str
    quantity: float
    unit_price: float
    subtotal: float


@dataclass
class InvoiceTax:
    tax_type: str
    percent: float
    taxable_amount: float
    tax_amount: float


@dataclass
class ParsedInvoice:
    cufe: str
    document_type: str  # '01'=Factura, '91'=Nota Crédito, '92'=Nota Débito
    billing_reference: Optional[str]  # Número o CUFE del documento afectado
    prefix: Optional[str]
    number: str
    full_number: str
    issue_date: str
    issue_time: Optional[str]
    issuer_nit: str
    issuer_name: str
    receiver_nit: str
    receiver_name: str
    currency: str
    line_extension_amount: float
    tax_exclusive_amount: float
    tax_inclusive_amount: float
    payable_amount: float
    items: List[InvoiceItem]
    taxes: List[InvoiceTax]


class DianXmlParser:
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'fe': 'http://www.dian.gov.co/contratos/facturaelectronica/v1',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    }

    TAX_SCHEME_MAP = {
        '01': 'IVA', '02': 'IC_CIGARRILLOS', '03': 'ICA', '04': 'INC',
        '05': 'RETEIVA', '06': 'RETEFUENTE', '07': 'RETEICA', '08': 'IC_LICORES',
        '20': 'FSD', '22': 'INC_BOLSAS', '30': 'IC_DATOS', '34': 'IBUA', '35': 'ICUI', 'ZZ': 'OTROS_TRIBUTOS',
    }

    def __init__(self, xml_content: Union[str, bytes]):
        self.tree = self._load_xml_tree(xml_content)

    def _load_xml_tree(self, content: Union[str, bytes]) -> etree._ElementTree:
        if isinstance(content, str):
            content = content.encode('utf-8')

        if content.startswith(b'PK\x03\x04'):
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                xml_files = [f for f in z.namelist() if f.endswith('.xml')]
                if not xml_files:
                    raise ValueError("El archivo ZIP no contiene ningún archivo .xml")
                target_xml = next((f for f in xml_files if not f.startswith('ad')), xml_files[0])
                content = z.read(target_xml)

        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(content, parser=parser)

        if root.tag.endswith('AttachedDocument'):
            descriptions = root.xpath('//cac:Attachment/cac:ExternalReference/cbc:Description/text()', namespaces=self.NAMESPACES)
            invoice_xml = next((desc for desc in descriptions if '<Invoice' in desc or '<CreditNote' in desc or '<DebitNote' in desc), descriptions[0] if descriptions else None)
            if invoice_xml:
                root = etree.fromstring(invoice_xml.strip().encode('utf-8'), parser=parser)

        return etree.ElementTree(root)

    def _xpath_text(self, query: str, default: Optional[str] = None) -> Optional[str]:
        results = self.tree.xpath(query, namespaces=self.NAMESPACES)
        if results:
            if isinstance(results[0], etree._Element):
                return results[0].text.strip() if results[0].text else default
            return str(results[0]).strip()
        return default

    def _xpath_float(self, query: str, default: float = 0.0) -> float:
        val = self._xpath_text(query)
        if val:
            try:
                return float(val)
            except ValueError:
                return default
        return default

    def parse(self) -> ParsedInvoice:
        root_tag = self.tree.getroot().tag
        
        # Identificación robusta del tipo de documento DIAN
        doc_type = "01"
        if "CreditNote" in root_tag:
            doc_type = "91"
        elif "DebitNote" in root_tag:
            doc_type = "92"
        else:
            doc_type = self._xpath_text('//cbc:InvoiceTypeCode/text()') or "01"

        cufe = self._xpath_text('//cbc:UUID/text()') or ""
        full_number = self._xpath_text('//cbc:ID/text()') or ""
        issue_date = self._xpath_text('//cbc:IssueDate/text()') or ""
        issue_time = self._xpath_text('//cbc:IssueTime/text()')

        # Referencia al documento afectado (para Notas Crédito / Débito)
        billing_ref = self._xpath_text('//cac:BillingReference//cac:InvoiceDocumentReference/cbc:ID/text()')

        prefix = None
        number = full_number
        prefix_val = self._xpath_text('//sts:Prefix/text()')
        if prefix_val and full_number.startswith(prefix_val):
            prefix = prefix_val
            number = full_number[len(prefix_val):]

        issuer_nit = self._xpath_text('//cac:AccountingSupplierParty//cbc:CompanyID/text()') or ""
        issuer_name = self._xpath_text('//cac:AccountingSupplierParty//cac:PartyLegalEntity/cbc:RegistrationName/text()') or ""

        receiver_nit = self._xpath_text('//cac:AccountingCustomerParty//cbc:CompanyID/text()') or ""
        receiver_name = self._xpath_text('//cac:AccountingCustomerParty//cac:PartyLegalEntity/cbc:RegistrationName/text()') or ""

        currency = self._xpath_text('//cbc:DocumentCurrencyCode/text()') or "COP"
        line_ext = round(self._xpath_float('//cac:LegalMonetaryTotal/cbc:LineExtensionAmount/text()'), 2)
        tax_excl = round(self._xpath_float('//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount/text()'), 2)
        tax_incl = round(self._xpath_float('//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount/text()'), 2)
        payable = round(self._xpath_float('//cac:LegalMonetaryTotal/cbc:PayableAmount/text()'), 2)

        items = self._parse_items()
        taxes = self._parse_taxes()

        return ParsedInvoice(
            cufe=cufe,
            document_type=doc_type,
            billing_reference=billing_ref,
            prefix=prefix,
            number=number,
            full_number=full_number,
            issue_date=issue_date,
            issue_time=issue_time,
            issuer_nit=issuer_nit,
            issuer_name=issuer_name,
            receiver_nit=receiver_nit,
            receiver_name=receiver_name,
            currency=currency,
            line_extension_amount=line_ext,
            tax_exclusive_amount=tax_excl,
            tax_inclusive_amount=tax_incl,
            payable_amount=payable,
            items=items,
            taxes=taxes
        )

    def _parse_items(self) -> List[InvoiceItem]:
        items = []
        lines = self.tree.xpath('//cac:InvoiceLine | //cac:CreditNoteLine | //cac:DebitNoteLine', namespaces=self.NAMESPACES)

        for line in lines:
            line_num_str = line.xpath('./cbc:ID/text()', namespaces=self.NAMESPACES)
            line_num = int(line_num_str[0]) if line_num_str else len(items) + 1

            seller_id = line.xpath('./cac:Item/cac:SellersItemIdentification/cbc:ID/text()', namespaces=self.NAMESPACES)
            unspsc_id = line.xpath('./cac:Item/cac:StandardItemIdentification/cbc:ID/text()', namespaces=self.NAMESPACES)
            description = line.xpath('./cac:Item/cbc:Description/text()', namespaces=self.NAMESPACES)
            qty = line.xpath('./cbc:InvoicedQuantity/text() | ./cbc:CreditedQuantity/text() | ./cbc:DebitedQuantity/text()', namespaces=self.NAMESPACES)
            price = line.xpath('./cac:Price/cbc:PriceAmount/text()', namespaces=self.NAMESPACES)
            subtotal = line.xpath('./cbc:LineExtensionAmount/text()', namespaces=self.NAMESPACES)

            items.append(InvoiceItem(
                line_number=line_num,
                seller_item_id=seller_id[0] if seller_id else None,
                unspsc_code=unspsc_id[0] if unspsc_id else None,
                description=description[0] if description else "",
                quantity=float(qty[0]) if qty else 1.0,
                unit_price=round(float(price[0]), 2) if price else 0.0,
                subtotal=round(float(subtotal[0]), 2) if subtotal else 0.0
            ))

        return items

    def _parse_taxes(self) -> List[InvoiceTax]:
        taxes = []
        tax_nodes = self.tree.xpath('//cac:TaxTotal | //cac:WithholdingTaxTotal', namespaces=self.NAMESPACES)

        for tax_node in tax_nodes:
            subtotals = tax_node.xpath('./cac:TaxSubtotal', namespaces=self.NAMESPACES)
            for sub in subtotals:
                tax_code_list = sub.xpath('./cac:TaxCategory/cac:TaxScheme/cbc:ID/text()', namespaces=self.NAMESPACES)
                tax_code = tax_code_list[0] if tax_code_list else ""
                tax_name = self.TAX_SCHEME_MAP.get(tax_code, f"IMPUESTO_{tax_code}" if tax_code else "OTROS")

                percent = sub.xpath('./cac:TaxCategory/cbc:Percent/text()', namespaces=self.NAMESPACES)
                taxable = sub.xpath('./cbc:TaxableAmount/text()', namespaces=self.NAMESPACES)
                amount = sub.xpath('./cbc:TaxAmount/text()', namespaces=self.NAMESPACES)

                taxes.append(InvoiceTax(
                    tax_type=tax_name,
                    percent=float(percent[0]) if percent else 0.0,
                    taxable_amount=round(float(taxable[0]), 2) if taxable else 0.0,
                    tax_amount=round(float(amount[0]), 2) if amount else 0.0
                ))

        return taxes