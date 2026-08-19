# Plano · Harness de desenvolvimento com agentes

**Data:** 2026-08-19 (rev. 2) · **Status:** Proposta, nada executado · **Repo alvo:** `~/git/harness` (vazio, greenfield)

Decisões já tomadas por Douglas: **todo o conteúdo do harness em inglês** (agentes, rules, templates, labels, commands — este plano é o último artefato em português); núcleo agnóstico de ferramenta, mas **alvo único por ora: Claude Code** (Cursor e outros vão para o roadmap); desenho multi-provider com **Azure DevOps primeiro**; gate por aprovação no upstream via label/tag; ADR global no repositório global do cliente (ex.: Confluence), ADR interna do repo em `docs/architecture/adrs`; do Notion vem só o conhecimento próprio (templates, notas, referências).

---

## 1 · Princípio estrutural: núcleo agnóstico + compiladores

A mesma regra da sua arquitetura de informação vale aqui: **um dono por dado**. O dono de toda definição — agente, regra, template, workflow — é o diretório `core/`, escrito em markdown puro com frontmatter YAML, **em inglês**, sem sintaxe de nenhuma ferramenta. O instalador **compila** o núcleo para o alvo:

| Alvo | O que o compilador gera | Status |
|---|---|---|
| Claude Code | `CLAUDE.md`, `.claude/agents/*.md`, `.claude/skills/`, commands, hooks | **Único alvo agora** |
| Cursor | `AGENTS.md`, `.cursor/rules/*.mdc` | Roadmap |
| Genérico (Codex, Windsurf, etc.) | `AGENTS.md` | Roadmap |

A separação core/compilador continua mesmo com um alvo só — é ela que torna o Cursor um item de roadmap barato em vez de uma reescrita. O custo de manter a separação agora é pequeno (o compilador claude-code é quase um passthrough com renomeação de campos); o custo de introduzi-la depois seria refatorar todo o core.

**Trade-off já conhecido para quando o roadmap chegar lá:** o fluxo orquestrado (orquestrador despachando engenheiro → reviewers → QA) só existe de verdade no Claude Code, porque subagentes e skills são primitivas dele. Nos demais alvos o harness degradará para *rules + templates + processo manual* — o núcleo é portável; a automação, não.

**Instalador:** CLI (`harness`) em Node ou Python — decisão de mecânica, fica para a execução. Comandos:

- `harness init` — cria `harness.yaml` no repo alvo (provider, org/projeto, stacks, comandos de build/test, sistema de toggle) e pergunta o essencial.
- `harness install --tool claude-code` — compila o core para o alvo, instala lefthook, valida auth do provider (gh/glab/az).
- `harness update` — recompila a partir do core novo; nunca toca no que é do repo (`harness.yaml`, overrides).
- `harness doctor` — diagnóstico: config, auth, labels criadas no upstream, hooks ativos.

**Overrides por repo:** um diretório `.harness/overrides/` opcional onde o projeto adiciona regras locais (convenções do cliente, comandos específicos). O compilador concatena core + override, override vence. Resolve o "depende do projeto" sem forcar divergência do núcleo.

---

## 2 · Camada de provider (GitHub · GitLab · Azure DevOps)

Interface neutra com verbos, três adapters. Cada adapter é um documento de receitas CLI (`gh`, `glab`, `az boards`) + tabela de vocabulário — os agentes falam a interface, o compilador injeta o adapter do `harness.yaml`.

| Conceito neutro | GitHub | GitLab | Azure DevOps |
|---|---|---|---|
| Item de trabalho | Issue | Issue | Work Item (Epic/Feature/PBI/Bug/Task) |
| Tipo | Label `type:*` | Label | Work Item Type nativo |
| Estado do gate | Label | Label | Tag (State fica intocado) |
| Hierarquia | Sub-issues / task list | Epic → Issue | Epic → Feature → PBI → Task |
| Revisão de código | Pull Request | Merge Request | Pull Request |
| Pipeline | Actions | GitLab CI | Azure Pipelines |

Verbos da interface: `create_item`, `update_item`, `comment`, `set_gate_state`, `link_items`, `list_by_gate_state`, `create_pr`, `request_changes`, `get_pr_diff`.

**Ciclo do gate (labels/tags padronizadas, em inglês):**
`harness:proposed` → **[você aprova no upstream]** → `harness:approved` → `harness:in-dev` → `harness:in-review` → `harness:done`

O orquestrador só enxerga `harness:approved`. Rejeição é comentário seu no work item + tag `harness:needs-revision` — o issue-writer relê o comentário e reescreve. Assíncrono, auditável, funciona com você ausente.

**Ordem de validação: Azure DevOps primeiro.** A interface neutra nasce para os três, mas o ADO é o adapter validado de ponta a ponta na fase 2 — e é a escolha certa para forçar a interface a ser honesta: o ADO é o caso *mais rico* (hierarquia Epic→Feature→PBI nativa, Work Item Types em vez de labels, `az boards` como CLI). Interface que sobrevive ao ADO acomoda GitHub e GitLab com folga; o contrário não é verdade. GitHub e GitLab ficam para a fase 3.

---

## 3 · Os agentes

Dez agentes, cada um com arquivo próprio em `core/agents/`, referenciando as rules da sua disciplina (seção 4). Modelo mental: **o agente carrega o papel e o critério de pronto; a rule carrega a disciplina; o template carrega o formato.**

### 3.1 `issue-writer` — análise e estruturação
Transforma demanda em itens de trabalho completos o suficiente para outro agente desenvolver **sem acesso a esta conversa**. Esse é o critério de qualidade: a issue é o contrato de contexto.

- **Tipos e templates** (`core/templates/issues/`): *User Story* (narrativa + critérios de aceite em Gherkin `Dado/Quando/Então` — cada cenário vira spec BDD depois), *Bug* (repro numerada, esperado vs observado, evidência, severidade), *Dívida técnica* (custo atual de não pagar, proposta, critério de quitação), *Spike* (pergunta, timebox, entregável = decisão documentada).
- **Feature toggles:** decide se a entrega pede toggle e classifica pela taxonomia de Hodgson/Fowler — *Release* (esconde trabalho incompleto; vida curta), *Experiment* (A/B), *Ops* (kill-switch; pode ser longevo), *Permission* (por perfil). **Toda toggle nasce com issue de remoção vinculada e data-alvo** — exceto Ops/Permission, que nascem com dono e revisão periódica. Toggle sem plano de morte é dívida com juros.
- **Fontes de contexto:** docs do repo (README, `docs/architecture/`, código relevante) + **Notion como acervo seu**: templates, suas notas sobre o projeto, referências. Leitura apenas. Se a decisão global do cliente mora no Confluence/wiki do ADO, a issue **linka**, não copia.
- Cria tudo com `harness:proposed` e para. O gate é seu.

### 3.2 `orchestrator` — o maestro
Único agente que despacha outros. Fluxo na seção 5. Responsabilidades: puxar itens `harness:approved`, rotear por stack, decidir quando o arquiteto entra (issue marcada `arch-review` pelo issue-writer, ou mudança que toca fronteira de módulo/contrato público), garantir a ordem teste-antes-de-código, não deixar item sair sem os dois reviews e sem QA quando aplicável, atualizar o estado do gate no upstream a cada transição. Ele não escreve código nem opina em conteúdo — coordena e cobra critério de pronto.

### 3.3–3.5 `engineer-js` · `engineer-csharp` · `engineer-python`
Sêniores, um por stack, selecionados pelo orquestrador conforme `harness.yaml` + arquivos tocados. Comportamento comum (a rule de engenharia): decompor a issue em tasks pequenas (checklist na própria issue via provider — visível para você); **BDD por padrão** — cada cenário Gherkin da issue vira spec executável antes de qualquer implementação; onde BDD não faz sentido (código sem regra de negócio: util, adapter, infra) cai para **TDD** clássico; commits pequenos e convencionais; toggle implementada conforme o tipo definido na issue; nunca marca task de infra/pipeline como sua — devolve ao orquestrador para o secdevops.

**Sobre o subagente de testes (você pediu para eu verificar):** recomendo **dividir por camada, não por completo**. Os *specs de aceite BDD* (a tradução Gherkin → teste executável que falha) devem ser escritos pelo `test-engineer` **antes** do engenheiro tocar em implementação — separar quem escreve o teste de quem o faz passar elimina o viés de escrever teste que confirma a implementação, e é barato porque o Gherkin já existe na issue. Já o *ciclo unitário de TDD* (red-green-refactor) deve ficar com o próprio engenheiro: o ciclo é interativo demais para atravessar fronteira de agente — cada micro-iteração viraria um handoff, e o custo mata o pragmatismo. Então: **3.6 existe, mas opera no nível de aceite/spec, não no unitário.**

### 3.6 `test-engineer`
Recebe a issue aprovada antes do engenheiro. Escreve os specs BDD executáveis (falhando) a partir dos cenários Gherkin, na ferramenta da stack (Cucumber/Vitest+gherkin para JS, SpecFlow/Reqnroll para C#, pytest-bdd para Python — decisão por repo no `harness.yaml`). Entrega: branch com specs vermelhos + mapa cenário→spec comentado na issue. Não implementa nada.

### 3.7 `code-reviewer`
Sênior, revisa o diff do PR/MR contra a rule de review: desenho (coesão, acoplamento, nome), correção, cobertura dos cenários da issue, legibilidade, consistência com o padrão do repo. **Comenta no upstream** (review com request changes ou approve) — nunca edita código. Loop: engenheiro responde/corrige, reviewer re-revisa. Duas rodadas sem convergência → escala para você via comentário mencionando-o.

### 3.8 `security-reviewer`
Roda em paralelo ao code-reviewer, no mesmo PR. Checklist ancorado em **OWASP Top 10 + ASVS** (nível 1 por padrão, 2 quando o `harness.yaml` marcar o repo como sensível): injeção, authz/authn, exposição de dado, segredo em código, dependência vulnerável, SSRF, logging de dado sensível. Também revisa a issue na origem quando marcada `security-review` (desenho, não só código). Mesmo protocolo: comenta no upstream, não edita.

### 3.9 `secdevops`
Dono do caminho até produção: pipelines (Actions/GitLab CI/Azure Pipelines — adapter do provider), **lefthook** (pre-commit: lint+format+segredo-scan; pre-push: testes rápidos), políticas (branch protection, conventional commits, SAST/dep-scan no pipeline), **CDK para AWS** como padrão de IaC (CDKTF/Bicep quando o cliente for GCP/Azure — decisão do solutions-architect). Instala a base via `harness install`; evolui via issues como qualquer trabalho.

### 3.10 `software-architect`
Guardião do **Haiku**, das **ADRs** e dos **diagramas C4** — templates de Haiku e ADR vêm do seu Notion (Modelo de Haiku de Arquitetura e Modelo de ADR formato Nygard, ambos em References). Papéis: (a) na entrada, quando o issue-writer marca `arch-review`, valida a proposta contra o ranking de atributos de qualidade do Haiku — o de cima ganha; (b) produz ADR quando há decisão (imutável depois de aceita; mudança = ADR nova que substitui); (c) mantém os **diagramas C4** (Context, Container, Component; Code só quando pagar o custo) em **draw.io preferencialmente** ou **Mermaid** quando o diagrama for simples o bastante para viver como texto diffável; (d) audita desvio: implementação que contradiz ADR aceita é bloqueio de review.

**Convenção de formato de diagrama (vale para 3.10 e 3.11):** no repo, o formato canônico é **`.drawio.svg`** — um arquivo só, editável no draw.io e renderizado nativamente no PR e no browser; `.drawio` puro é proibido no repo porque é XML opaco em review. Um diagrama por arquivo, nome com escopo e nível (`c4-container-payments.drawio.svg`). No repositório global (Confluence), o diagrama vive na **integração nativa draw.io do Confluence** — editável na página, sem arquivo órfão — e a página linka o repo quando o diagrama nasce de lá. Mermaid é aceito só para C4 de escopo do repo em nível Component para baixo, onde o diff textual vale mais que a estética. O `harness doctor` valida a convenção (extensão, nome, um diagrama por arquivo).

**Regra de localização (vale para ADR e C4 igualmente):** escopo global do cliente → repositório global de conhecimento dele (ex.: Confluence, wiki do ADO), configurado no `harness.yaml`; escopo interno do repo → `docs/architecture/adrs/` para ADRs e `docs/architecture/diagrams/` para C4. O critério é o alcance da decisão/visão, não a preferência de quem escreve: se outro repo precisa conhecer, é global.

### 3.11 `solutions-architect`
Cloud (AWS primeiro — sua praia — GCP e Azure quando o cliente pedir). Papéis: desenho de infra para issues com componente de nuvem, revisão Well-Architected (custo, resiliência, segurança de infra), escolha de serviço com trade-off explícito (tabela ganhamos/pagamos, mesmo formato do Haiku), par do secdevops na definição do CDK. **Diagramas de arquitetura de solução sempre em draw.io, com a iconografia oficial da nuvem em uso** (AWS Architecture Icons, Azure architecture icons, Google Cloud icons — bibliotecas nativas do draw.io, selecionadas pelo `harness.yaml` do repo). Mesma regra de localização do 3.10. Distinção com o 3.10: o software-architect decide *dentro* do sistema; o solutions-architect decide *onde e sobre o quê* o sistema roda. Issues que tocam os dois passam pelos dois.

### 3.12 `qa`
**Constrói** os testes caros; **quem valida é o pipeline.** O QA escreve e mantém: **integration tests** (fronteiras reais: banco, fila, API externa com testcontainers onde couber), **acceptance tests** end-to-end com **Cypress**, **smoke suite** mínima (Cypress, tag `@smoke`). A execução é responsabilidade do CI/CD: o contrato QA↔secdevops (formalizado na rule de QA e na de pipelines) define em qual estágio cada suite roda — integration no CI de PR ou pós-merge conforme custo, acceptance no ambiente de teste, smoke no deploy — e **um teste que o pipeline não executa não existe**: entregar suite nova sem o estágio correspondente no pipeline é entrega incompleta, e o orquestrador não fecha o item.

**Mecânica do contrato (para não virar prosa):** o `harness.yaml` ganha uma seção `test-suites` — cada suite declara caminho, comando e o estágio do pipeline que a executa (`integration → ci-post-merge`, `acceptance → test-env`, `smoke → deploy`). O QA entrega suite **junto com a entrada no manifesto**; o secdevops materializa o estágio; um check no CI (e no `harness doctor`) falha se existir suite no repo sem entrada no manifesto ou entrada sem estágio real no pipeline — drift entre teste e pipeline vira quebra visível, não acordo esquecido. O orquestrador só fecha o item com o check verde. O QA não repete o que o test-engineer cobriu: test-engineer prova a regra de negócio; QA prova o sistema montado.

---

## 4 · Rules por disciplina (`core/rules/`)

Uma rule por disciplina, curta, **em inglês**, referenciada pelos agentes — nunca duplicada dentro deles (mesma razão do seu "não repita a lógica das skills no prompt"). Essência de cada uma:

| Rule | Essência |
|---|---|
| `engineering.md` | Task pequena; teste antes de código; conventional commits; nada de toggle sem tipo e sem plano de remoção; nada de TODO sem issue |
| `bdd.md` | Gherkin da issue é a fonte; cenário sem spec é issue incompleta; spec sem cenário é escopo não aprovado |
| `review.md` | Review comenta, não edita; bloqueio só com justificativa e sugestão; duas rodadas sem acordo escala para Douglas |
| `security.md` | OWASP Top 10 + ASVS L1/L2; segredo em código é bloqueio imediato; dependência crítica vulnerável bloqueia merge |
| `pipelines.md` | Todo repo tem lefthook + CI com lint, teste, SAST, dep-scan; pipeline quebrado bloqueia despacho de nova issue do repo; estágios de teste do QA são parte do contrato do pipeline |
| `architecture.md` | Ranking do Haiku é critério de desempate; decisão gera ADR (Nygard, imutável); regra de localização: alcance global → repo global do cliente, alcance do repo → `docs/architecture/`; C4 em draw.io (preferencial) ou Mermaid; desvio aceito tem dono, validade e controle compensatório |
| `toggles.md` | Taxonomia Release/Experiment/Ops/Permission; Release e Experiment nascem com issue de remoção; Ops e Permission com dono e data de revisão |
| `qa.md` | Fronteira test-engineer vs QA; QA constrói, pipeline valida — suite sem estágio no CI/CD é entrega incompleta; smoke é pequena e rápida por definição; teste flaky se conserta ou se apaga, não se ignora |

---

## 5 · O fluxo orquestrado

```
você (demanda)
   │
   ▼
issue-writer ──── contexto: repo docs + Notion (seu acervo) + repo global do cliente (link)
   │  cria itens com harness:proposed
   ▼
━━━ GATE: você aprova no upstream (label/tag → harness:approved) ━━━
   │
   ▼
orchestrator ── puxa aprovadas, roteia
   │
   ├─► software-architect / solutions-architect   (se arch-review / cloud)
   │        └─ ADR + C4/diagrama de solução no local certo (global vs docs/architecture)
   ▼
test-engineer ── specs BDD vermelhos a partir do Gherkin
   ▼
engineer-{js|csharp|python} ── tasks pequenas; faz os specs passarem; TDD no unitário
   ▼
PR ──► code-reviewer ─┬─ paralelo ─┬─ security-reviewer
   │        (loop de request changes no upstream)
   ▼
merge
   ▼
qa ── CONSTRÓI integration + acceptance (Cypress) + smoke
   ▼
secdevops ── pluga cada suite no estágio acordado do CI/CD; pipeline VALIDA
   ▼
harness:done ── comentário final no item com resumo do que foi entregue
```

Regras do orquestrador que evitam os modos comuns de falha: um item de cada vez por repo (sem paralelismo de issues que tocam o mesmo código); transição de gate sempre refletida no upstream (o estado mora lá, nunca só na sessão — de novo, um dono por dado); qualquer bloqueio vira comentário na issue mencionando você, nunca falha silenciosa.

---

## 6 · Notion no harness

Papel estrito, coerente com a sua arquitetura: **Notion é acervo de conhecimento seu, leitura apenas.**

- O que os agentes leem: templates (Haiku, ADR — já localizados em References, ambos `Revisada`), suas notas e referências sobre o projeto/cliente, atas de reunião quando a issue nasce de uma decisão em reunião (e aí vale sua regra: resumo no Notion, fato dito na transcrição do Plaud).
- O que o harness **nunca** faz no Notion: escrever, criar relação, inferir vínculo. Nada muda nas suas guardas atuais.
- **Um problema real a resolver:** Cursor e o pipeline de CI não têm o MCP do Notion. Proposta: `harness update` faz *snapshot* dos templates para `core/templates/architecture/` com link e data da fonte no cabeçalho — artefato de build, não segunda fonte de verdade; divergência se resolve rodando `harness update`. É o mesmo padrão do seu `gerar-system-prompt`. Alternativa mais pura (agente sempre lê do Notion ao vivo) funciona só no Claude Code — aceitável se você topar que os outros alvos usem o snapshot. A proposta cobre os dois.
- Fica fora do escopo do harness (e continua com as skills existentes): tarefas no Todoist, atas, time blocks. **Uma fronteira a decidir depois, não agora:** se issue aprovada deve gerar rastro no Todoist. Minha posição: não — o upstream é o dono do estado da issue, e espelhar issue em tarefa violaria "nunca estado duplicado". No máximo, uma tarefa avulsa "revisar propostas do harness" quando houver itens em `harness:proposta` parados há N dias.

---

## 7 · Layout do repo `~/git/harness`

Tudo em inglês, inclusive nomes de arquivo e conteúdo:

```
harness/
├── core/
│   ├── agents/            # 10 definições agnósticas (md + frontmatter)
│   ├── rules/             # 8 rules de disciplina
│   ├── templates/
│   │   ├── issues/        # user-story, bug, tech-debt, spike
│   │   ├── architecture/  # snapshot haiku + adr (fonte: Notion, com link/data) + esqueletos C4
│   │   └── toggles/       # registro de toggle (tipo, dono, expiração)
│   └── workflows/         # fluxo orquestrado (seção 5) em formato neutro
├── providers/
│   ├── interface.md       # verbos neutros
│   ├── azure-devops.md    # receitas az boards + mapeamento Work Item Types  ← primeiro
│   ├── github.md          # receitas gh                                      (fase 3)
│   └── gitlab.md          # receitas glab                                    (fase 3)
├── compilers/
│   └── claude-code/       # gera CLAUDE.md, .claude/agents, skills, commands
│                          # (cursor/ e agents-md/ entram via roadmap)
├── installer/             # CLI: init, install, update, doctor
├── schema/harness.yaml    # schema comentado da config por repo
└── README.md
```

No repo de cada projeto, depois do `harness install`: `harness.yaml`, `.harness/overrides/` (opcional), `lefthook.yml`, os artefatos compilados do Claude Code, e a convenção de docs — `docs/architecture/adrs/` e `docs/architecture/diagrams/` para o que for de alcance do repo (o global mora no repositório de conhecimento do cliente, apontado no `harness.yaml`).

### Commands (alvo Claude Code)

| Command | Faz |
|---|---|
| `/issue <demanda>` | issue-writer: estrutura e cria com `harness:proposed` |
| `/triage` | lista propostas aguardando você + aprovadas na fila |
| `/dev [id]` | orquestrador: ciclo completo de um item aprovado |
| `/review [pr]` | code + security review de um PR existente (uso avulso) |
| `/qa [escopo]` | constrói/atualiza as suites caras sob demanda |
| `/adr <decisão>` · `/haiku` · `/c4 [nível]` | software-architect com seus templates e diagramas |
| `/solution-diagram` | solutions-architect: diagrama draw.io com iconografia da nuvem |
| `/pipeline` | secdevops: cria/atualiza CI, hooks, políticas, estágios das suites do QA |

---

## 8 · Fases de execução (quando você autorizar) e roadmap

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 1 | `core/` completo em inglês: agentes, rules, templates, workflow + snapshot dos templates do Notion | Revisão sua do conteúdo dos 10 agentes e 8 rules |
| 2 | Interface de provider + **adapter Azure DevOps** + compilador claude-code + instalador mínimo (`init`, `install`) | Ciclo `/issue` → gate → `/dev` → PR revisado rodando num projeto ADO seu |
| 3 | Adapters GitHub e GitLab | Mesmo ciclo num repo GitHub |
| 4 | `doctor`, `update`, lefthook empacotado, smoke do próprio harness | `harness doctor` verde nos três providers |

Validar no ADO primeiro força a interface neutra a ser honesta desde o começo (é o provider mais rico); GitHub e GitLab viram casos simples depois.

**Roadmap (fora das fases, sem data):**

- Compilador **Cursor** (`AGENTS.md` + `.cursor/rules`) e alvo genérico `agents-md` — degradação já desenhada na seção 1.
- Outras ferramentas conforme aparecerem (Windsurf, Codex, etc.) — cada uma é só um compilador novo sobre o mesmo core.
- Integração opcional issue parada → aviso (ver seção 6, fronteira Todoist).

---

## 9 · O que você não perguntou, mas importa

1. **Autenticação é o atrito real do multi-provider — e o `az` do ADO é o pior dos três.** PAT ou Entra ID, expiração, escopo por organização. O `doctor` precisa verificar auth antes de qualquer fluxo, senão o erro aparece no meio do ciclo. Vale resolver isso na fase 2, não na 4.
2. **O gate protege você de issue ruim, não de código ruim.** Entre `aprovada` e `pronta` não há olho humano obrigatório — os reviewers são agentes. Se quiser um segundo olho seu, o ponto barato é aprovar o merge do PR no upstream (branch protection exigindo sua aprovação), que o secdevops pode configurar por repo. Recomendo isso pelo menos nos repos de cliente.
3. **Dez agentes têm custo de manutenção.** Cada um é um prompt que envelhece. O antídoto é o que já está no desenho: agente magro, disciplina na rule — mas vale aceitar desde já que engineer-js/csharp/python são 90% idênticos e o compilador deve gerá-los de um template único + bloco de stack, senão você mantém três cópias do mesmo texto.
4. **`harness update` nos repos é o elo fraco do modelo compilado.** Core evolui, repos ficam para trás. Sugestão barata: o `doctor` compara versão instalada vs core e o orquestrador avisa quando o repo está defasado. Nada de auto-update silencioso.
