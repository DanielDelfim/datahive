
---

## Regras de Organização

1. **Domínios separados por pasta** em `app/utils/<dominio>/` (ex.: `vendas`, `publicidade`), espelhando a mesma convenção de nomes:  
   `filtros.py`, `metricas.py`, `preprocess.py` (quando existir), `agregador.py`, `service.py`.

2. **Clientes externos** agrupados em `app/utils/<provedor>/` (ex.: `meli/`), com `client.py`.  
   - Opcional: `auth.py`, `endpoints.py`, `schemas.py` se crescer.

3. **Core genérico** fica em `app/utils/core/` e **não importa domínios**.

4. **Páginas/dashboards** usam **apenas services** dos domínios.  
   - Compositores em `app/dashboard/<pagina>/compositor.py`.

5. **Scripts** (jobs/CLI) nunca implementam regra de negócio — **delegam** para domínios ou integrações.

6. **Dados RAW**: salvar em `data/marketplaces/meli/vendas/<loja>/raw/`  
   - **Atual** (para consumo do PP): `current/last_order.json`  
   - **Histórico por ID** (opcional): `by_id/order_<ORDER_ID>.json`

7. **Tokens** e segredos fora do git, sob `tokens/`.

---

## Convenções de Nomes

- **Módulos (arquivos .py)**: `snake_case` curto e específico.  
- **Classes**: `CapWords` (ex.: `MeliClient`).  
- **Funções públicas** em `service.py`: `verbo_objeto` (ex.: `obter_receita_por_periodo`).  
- **Helpers privados**: prefixo `_` (ex.: `_normalizar_datas`).  
- **Aliases de import** quando houver nomes iguais entre domínios (ex.: `import app.utils.vendas.service as vendas_svc`).

---

## Fronteiras e Dependências

- `dashboard/**` → **chama** `app/utils/*/service.py` (fachadas).  
- `service.py` → **chama** `agregador.py` do mesmo domínio.  
- `agregador.py` → **chama** `metricas.py`, `filtros.py`, `preprocess.py` (quando houver) e utilidades de `core/`.  
- **Nunca**: um domínio importar diretamente outro domínio (ex.: `publicidade` importar `vendas`).  
  - Para composições entre domínios, use o **compositor** no nível de página.

---

## Boas Práticas de Dados

- **Arquivos estáveis** (consumo por PP) não têm timestamp no nome.  
- Escrita **atômica** para JSON (gravar `.tmp` e `os.replace`) para evitar leituras corrompidas.  
- **Particionamento** por loja (`sp/`, `mg/`) e por escopo (`raw/current`, `raw/by_id`).  
- O **PP** não lê múltiplos lugares — sempre um **ponto único estável**.

---

## Próximos Passos (Backlog Estrutural)

- [ ] `01_conventions.md`: estilos de import, alias, docstrings, `__all__`, visibilidade (público/privado).  
- [ ] `03_module_map.md`: desenhar setas de dependência (quem importa quem).  
- [ ] `04_interfaces.md`: listar contratos públicos dos services de `vendas` e `publicidade`.  
- [ ] ADR: “Arquitetura por domínios com façade (service) + orquestrador (agregador)”.  
- [ ] Definir layout de `preprocess.py` (RAW → PP) para `vendas` (one e batch).

---

## Histórico de Alterações

- v1 (2025-09-18): Versão inicial conforme alinhamento do Architect Mode.
