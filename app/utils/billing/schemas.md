# Schemas — Billing (XML & Excel)

## 1) XML — NotaResumo (auditoria)
- id_unico: string
- modelo: "NFe" | "NFSe"
- chave: string | null
- numero: string
- serie: string | null
- data_emissao: ISO-8601 (com timezone)
- mes_competencia: "YYYY-MM"
- emitente: { documento, razao_social, uf, municipio, inscricao_estadual? }
- destinatario: { documento, razao_social, uf, municipio, inscricao_estadual? }
- natureza_operacao: string
- cfops: string[]
- itens: ItemResumo[]
- totais: Totais { valor_produtos, descontos, frete, outras_despesas, base_icms, icms, ipi, pis, cofins, valor_total_nfe }
- regiao: "sp" | "mg"
- market: "meli"
- tipo_documento: "entrada" | "saida" | null
- status_parse: "ok" | "warning" | "error"
- mensagem_erro?: string
- origem_arquivo: string

### ItemResumo
- sku?, gtin?, descricao, ncm?, cfop, cst_icms?, cst_pis?, cst_cofins?, quantidade, valor_unitario, valor_total, desconto?, aliquotas?

### Deduplicação
- NFe: `chave`
- NFSe: `(emitente.documento, numero, serie, data_emissao.date())`
- Fallback: `(emitente.doc, destinatario.doc, numero, serie, data.date(), totais.valor_total_nfe)`

---

## 2) Excel — Linhas normalizadas (fechamento rápido)
Campos base:
- __id__ (string) — chave por relatório (`tarifa_id` ou `pagamento_id`)
- __data__ (datetime) — data da tarifa/pagamento
- __conceito__ (string) — descrição bruta
- __valor__ (float) — valor da tarifa (positivo); estornos serão bucketizados como “Cancelamentos”
- __valor_mes__ (float) — para `Pagamento de Faturas`
- __categoria__ (string) — bucket canônico (vide mappers/excel_concepts_map.yaml)
- __file__, __sheet__ — origem

---

## 3) Saídas consolidadas
### FaturaPorCategoria (tela “Sua fatura inclui”)
Objeto `dict[str, number]` com chaves:
- Tarifas de venda
- Tarifas de envios no Mercado Livre
- Tarifas por campanha de publicidade
- Taxas de parcelamento
- Tarifas de envios Full
- Tarifas dos serviços do Mercado Pago
- Tarifas da Minha página
- Cancelamentos de tarifas

### Reconciliacao
- total_cobrancas: number
- total_pagamentos: number
- diferenca: number
- parametros: { market, ano, mes, regioes[] }
