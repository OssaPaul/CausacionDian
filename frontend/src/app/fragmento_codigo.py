					<thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3.5 w-10">
                          <input
                            type="checkbox"
                            checked={
                              invoicesList.filter(i => i.status === "PARSEADO").length > 0 &&
                              selectedInvoiceIds.length === invoicesList.filter(i => i.status === "PARSEADO").length
                            }
                            onChange={(e) => {
                              if (e.target.checked) {
                                const parseadasIds = invoicesList
                                  .filter(i => i.status === "PARSEADO")
                                  .map(i => i.id);
                                setSelectedInvoiceIds(parseadasIds);
                              } else {
                                setSelectedInvoiceIds([]);
                              }
                            }}
                            className="w-4 h-4 rounded bg-slate-950 border-slate-700 cursor-pointer text-blue-600 focus:ring-blue-500"
                            title="Seleccionar todas las parseadas"
                          />
                        </th>
                        <th className="px-4 py-3.5">Número</th>    
						<th className="px-4 py-3.5">Fecha</th>
                        <th className="px-4 py-3.5">Emisor / Tercero</th>
                        <th className="px-4 py-3.5 text-right">Subtotal</th>
                        <th className="px-4 py-3.5 text-right">Total a Pagar</th>
                        <th className="px-4 py-3.5 text-center">Estado</th>
                        <th className="px-4 py-3.5 text-right">Acción</th>
                      </tr>
                    </thead>
                    
					<tbody className="divide-y divide-slate-800/60">
                      {invoicesList.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-6 py-8 text-center text-slate-500">
                            No hay facturas registradas en esta organización.
                          </td>
                        </tr>
                      ) : (
                        invoicesList.map((inv) => (
                          <tr key={inv.id} className="hover:bg-slate-800/30">
                            <td className="px-4 py-3.5">
                              <input
                                type="checkbox"
                                checked={selectedInvoiceIds.includes(inv.id)}
                                onChange={() => toggleSelectInvoice(inv.id)}
                                className="rounded bg-slate-950 border-slate-700"
                              />
                            </td>
                            <td className="px-4 py-3.5 font-mono font-bold text-white">
                              {inv.full_number}
                            </td>
                            <td className="px-4 py-3.5 font-mono text-slate-400">
                              {inv.issue_date}
                            </td>
                            <td className="px-4 py-3.5">
                              <div className="font-semibold text-white">{inv.issuer_name}</div>
                              <div className="text-[10px] font-mono text-slate-400">
                                NIT: {inv.issuer_nit}
                              </div>
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono">
                              ${Number(inv.line_extension_amount || 0).toLocaleString("es-CO")}
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono font-bold text-indigo-300">
                              ${Number(inv.payable_amount || 0).toLocaleString("es-CO")}
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  inv.status === "CAUSADO"
                                    ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                                    : "bg-amber-950 text-amber-400 border border-amber-800/50"
                                }`}
                              >
                                {inv.status}
                              </span>
                            </td>
                     		<td className="px-4 py-3.5 text-right space-x-2 whitespace-nowrap">
							  <button
								type="button"
								disabled={isCausing}
								onClick={() => handleCausarSingle(inv.id, inv.status)}
								className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-[11px] font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
							  >
								<Eye className="w-3.5 h-3.5" />
							    <span>{inv.status === "CAUSADO" ? "Ver Asiento" : "Causar"}</span>
							  </button>
							  <button
							    type="button"
								onClick={() => handleOpenInvoiceDetails(inv.id)}
								title="Ver Detalle y Validar DIAN"
								className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-[11px] font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
							  >
								<Receipt className="w-3.5 h-3.5 text-amber-400" />
								<span>Ver DIAN</span>
							  </button>
							</td>
						 </tr>
                        ))
                      )}
                    </tbody>