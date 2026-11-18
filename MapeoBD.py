# Ejemplo de prueba y mapeo directo hacia la Base de Datos en Supabase
if __name__ == "__main__":
    with open("factura_ejemplo.xml", "rb") as f:
        xml_bytes = f.read()

    parser = DianXmlParser(xml_bytes)
    invoice_data = parser.parse()

    # Convertir a Diccionario listo para insertar en Supabase (tabla 'invoices')
    print("CUFE Extraído:", invoice_data.cufe)
    print("Proveedor:", invoice_data.issuer_name, "NIT:", invoice_data.issuer_nit)
    print("Total a pagar:", invoice_data.payable_amount)
    print("Ítems procesados:", len(invoice_data.items))
    print("Impuestos encontrados:", invoice_data.taxes)