		from decimal import Decimal, ROUND_HALF_UP

        if parsed_data.taxes:
            unique_taxes_map = {}
            for tax in parsed_data.taxes:
                if isinstance(tax, dict):
                    t_type = str(tax.get("tax_type") or tax.get("type", "")).upper()
                    t_percent = float(tax.get("percent", 0.0) or 0.0)
                    t_taxable = Decimal(str(tax.get("taxable_amount", "0.0") or "0.0"))
                    t_amount = Decimal(str(tax.get("tax_amount", "0.0") or "0.0"))
                else:
                    t_type = str(getattr(tax, "tax_type", getattr(tax, "type", ""))).upper()
                    t_percent = float(getattr(tax, "percent", 0.0) or 0.0)
                    t_taxable = Decimal(str(getattr(tax, "taxable_amount", "0.0") or "0.0"))
                    t_amount = Decimal(str(getattr(tax, "tax_amount", "0.0") or "0.0"))

                if not t_type:
                    continue

                # Llave única por concepto y tarifa global
                key = (t_type, t_percent)

                # Acumular de forma exacta usando aritmética Decimal
                if key in unique_taxes_map:
                    unique_taxes_map[key]["taxable_amount"] += t_taxable
                    unique_taxes_map[key]["tax_amount"] += t_amount
                else:
                    unique_taxes_map[key] = {
                        "invoice_id": invoice_id,
                        "type": t_type,
                        "percent": t_percent,
                        "taxable_amount": t_taxable,
                        "tax_amount": t_amount
                    }

            # --- FUERA DEL CICLO FOR (ESTO FALTABA) ---
            # Normalizar y redondear a 4 decimales exactos para la base de datos
            taxes_payload = []
            for item in unique_taxes_map.values():
                taxes_payload.append({
                    "invoice_id": item["invoice_id"],
                    "type": item["type"],
                    "percent": item["percent"],
                    "taxable_amount": float(item["taxable_amount"].quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)),
                    "tax_amount": float(item["tax_amount"].quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))
                })

            if taxes_payload:
                print(f"[UPLOAD XML] Insertando {len(taxes_payload)} impuestos consolidados de cabecera.")
                supabase.table("invoice_taxes").insert(taxes_payload).execute()