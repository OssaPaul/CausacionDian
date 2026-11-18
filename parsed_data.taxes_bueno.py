        if parsed_data.taxes:
            taxes_payload = []
            invoice_base = float(getattr(parsed_data, 'line_extension_amount', 0.0) or getattr(parsed_data, 'tax_exclusive_amount', 0.0) or 0.0)
            
            from collections import defaultdict
            tax_groups = defaultdict(list)
            
            for tax in parsed_data.taxes:
                if isinstance(tax, dict):
                    t_type = str(tax.get("tax_type") or tax.get("type", "")).upper()
                    t_percent = float(tax.get("percent", 0.0) or 0.0)
                    t_taxable = float(tax.get("taxable_amount", 0.0) or 0.0)
                    t_amount = float(tax.get("tax_amount", 0.0) or 0.0)
                else:
                    t_type = str(getattr(tax, "tax_type", getattr(tax, "type", ""))).upper()
                    t_percent = float(getattr(tax, "percent", 0.0) or 0.0)
                    t_taxable = float(getattr(tax, "taxable_amount", 0.0) or 0.0)
                    t_amount = float(getattr(tax, "tax_amount", 0.0) or 0.0)

                if not t_type:
                    continue

                tax_groups[(t_type, t_percent)].append({
                    "invoice_id": invoice_id,
                    "type": t_type,
                    "percent": t_percent,
                    "taxable_amount": round(t_taxable, 4),
                    "tax_amount": round(t_amount, 4)
                })

            # Evaluar cada grupo de impuesto de forma inteligente
            for (t_type, t_percent), entries in tax_groups.items():
                # Buscar si alguna entrada cubre el total global de la factura (con tolerancia de 1 unidad por redondeo)
                header_entry = next((e for e in entries if invoice_base > 0 and abs(e["taxable_amount"] - invoice_base) < 1.0), None)
                
                if header_entry:
                    # Si existe el global de cabecera, usamos solo ese y descartamos el ruido de líneas
                    taxes_payload.append(header_entry)
                else:
                    # Si no hay uno global, conservamos los subtotales parciales independientes (ej. factura 37725)
                    seen_signatures = set()
                    for entry in entries:
                        sig = (entry["type"], entry["percent"], entry["taxable_amount"], entry["tax_amount"])
                        if sig not in seen_signatures:
                            seen_signatures.add(sig)
                            taxes_payload.append(entry)

            if taxes_payload:
                print(f"[UPLOAD XML] Insertando {len(taxes_payload)} impuestos optimizados de cabecera.")
                supabase.table("invoice_taxes").insert(taxes_payload).execute()