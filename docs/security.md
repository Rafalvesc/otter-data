# Segurança — fundação local

## Proteções implementadas

- PostgreSQL acessível pelo host apenas em `127.0.0.1`.
- Senhas locais distintas geradas com `secrets`; `.env` ignorado pelo Git e pelo build.
- Backend recebe apenas a senha analítica; não recebe senhas de administração ou seed.
- `analytics_agent` sem privilégios elevados ou associação com outros papéis.
- Conta analítica acessa somente seis views no schema `analytics`, sem acesso ao schema `core`.
- E-mail fictício existe apenas em `core.customers`, para testar a separação de dados sensíveis.
- Views usam direitos do proprietário para leitura das origens e não incluem campos sensíveis.
- Escrita, criação de tabelas, objetos temporários e alteração das views não são concedidas à conta analítica.
- Defaults de read-only, statement timeout de dez segundos e lock timeout de dois segundos.
- Conta de seed possui apenas SELECT/INSERT nas tabelas core e não é proprietária das relações.
- Novas relações não são liberadas automaticamente à conta analítica.
- Container da aplicação executa como usuário sem root.
- Validação AST com allowlist de nós, funções, casts, views, colunas e chaves de join.
- Resolução de aliases, CTEs e subconsultas pelo catálogo; referências desconhecidas são rejeitadas.
- Tabelas do catálogo escritas sem schema (`FROM orders`) são qualificadas com o schema aprovado antes da validação; o SQL executado sempre traz o schema, e nomes fora do catálogo continuam recusados.
- `SUM`, `AVG` e `COUNT` sem `DISTINCT` são recusados quando, a partir da tabela medida, a consulta segue uma chave estrangeira do pai para o filho (um para muitos), porque cada valor seria contado várias vezes (ex.: um pagamento somado uma vez por item do pedido). A recusa é corrigível e sugere usar a medida da tabela mais detalhada, `COUNT(DISTINCT ...)` ou filtrar com `IN (SELECT ...)`.
- Nas métricas versionadas, os valores dos parâmetros vêm sempre do plano, nunca do modelo; o SQL precisa usar todos eles, ou é recusado indicando os nomes que faltam ou sobram.
- SQL original não é executado diretamente: somente a consulta normalizada e aprovada entra no executor.
- Toda chamada ao executor valida novamente e não aceita uma aprovação fornecida pelo chamador.
- Parâmetros nomeados são vinculados pelo cursor raw do Psycopg, sem interpolação de valores.
- Transação read-only e configurações locais aplicadas pelo executor, independentemente dos defaults da conta.
- Cursor no servidor, teto de linhas e de tamanho do array JSON; truncamento explícito.
- Orçamento de execução aplicado às leituras; erros e registros operacionais sanitizados.

A definição de privilégios segue a [documentação oficial do PostgreSQL](https://www.postgresql.org/docs/17/sql-grant.html). Valores da carga usam parâmetros vinculados e identificadores estáticos são compostos com `psycopg.sql`, conforme a [documentação do Psycopg](https://www.psycopg.org/psycopg3/docs/basic/params.html).

## Limites desta entrega

O default read-only e os timeouts de sessão podem ser alterados pelo próprio usuário em certas situações. Os testes comprovam separadamente que os privilégios de escrita continuam ausentes. O executor já aplica transação read-only, política SQL e timeout local independentemente do modelo.

PostgreSQL disponibiliza funções e metadados de sistema a usuários comuns. A conta de leitura, isoladamente, não impede todo consumo de recursos nem toda chamada a funções. O validador bloqueia funções não autorizadas e acesso ao catálogo; o executor fixa a resolução de funções em `pg_catalog`. Esta proteção exige usar o executor: um cliente externo com a senha analítica não passa pela política AST.

Esta versão possui integração LLM, mas ainda não possui autenticação, autorização por usuário, TLS ou isolamento entre tenants. O endpoint aceita perguntas, não SQL direto. Usar somente localmente, com dados sintéticos. Acesso a dados reais exige implementar e validar as fronteiras empresariais antes da implantação.

Limites de retorno não garantem baixo custo de processamento. `EXPLAIN` e controle de custo estimado continuam pendentes. O limite em bytes mede as linhas serializadas; o envelope e os buffers do driver têm overhead separado. A consulta ainda pode produzir uma métrica incorreta ou uma junção que duplique valores: segurança SQL não prova acurácia analítica.

O subconjunto autorizado admite CTEs não recursivas e subconsultas, mas joins em fontes derivadas, unions e funções fora da lista permanecem bloqueados. Nenhuma forma desconhecida é liberada por heurística ou por justificativa do modelo.

A allowlist inclui funções estatísticas e de janela puramente de leitura (desvio padrão, variância, raiz, potência, percentis com `WITHIN GROUP`, mediana, `FILTER`, `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `NTILE`, `PERCENT_RANK`, `CUME_DIST`, `LAG`, `LEAD` e agregados com `OVER`). Os argumentos passam pelas mesmas regras de colunas, então um campo sensível dentro de uma janela ou percentil continua bloqueado. `LN`, `EXP` e funções desconhecidas seguem fora.

Quando a validação recusa uma consulta corrigível, o motivo (texto fixo da política e, no caso de função, apenas o nome que o próprio modelo escreveu) volta ao modelo para uma única reescrita, que passa pelo validador do zero. Escrita, múltiplas instruções e campos sensíveis são marcados como não corrigíveis e encerram o pedido. Nenhum dado da base entra nessa mensagem.

## Verificação

`python -m pytest --run-integration` verifica leitura permitida, campos sensíveis indisponíveis, ausência de papéis elevados, bloqueio de escrita mesmo sem o default read-only, timeout real e correção das cinco consultas de referência.

A segunda etapa acrescenta ataques com aliases, CTEs, subconsultas, funções, múltiplas instruções e parâmetros; verifica que rejeições não abrem conexão. Testes reais do executor conferem limites de linhas/bytes, precisão decimal, dados vazios, tratamento de falhas e timeout. Um teste usa credenciais de administração apenas para segurar um lock temporário em dados sintéticos, verificando cancelamento e recuperação; a aplicação nunca recebe essas credenciais.

A resolução de referências usa a API de [qualificação do sqlglot](https://github.com/tobymao/sqlglot/blob/main/sqlglot/optimizer/qualify.py). A execução usa [cursores no servidor do Psycopg](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html#server-side-cursors) e [configurações locais de transação do PostgreSQL](https://www.postgresql.org/docs/17/sql-set.html).

A carga usa uma transação e um lock para serializar tentativas de seed. Reexecuções comparam os dados completos. Não existe reset automático nem privilégio de DELETE/TRUNCATE para o seeder.

## Bases de dados próprias

O usuário pode conectar PostgreSQL, MySQL ou MongoDB e importar CSV (DuckDB local). Isso permite dados reais; os controles abaixo valem para essas bases e não substituem uma conta de banco com permissão só de leitura, que a interface pede explicitamente.

- **Credenciais:** recebidas uma única vez pela API, guardadas no Cofre de Credenciais do Windows via `keyring` e nunca persistidas em arquivo, devolvidas pela API, registradas em log ou enviadas ao modelo. O campo de senha é limpo na página logo após o envio. Remover a base apaga a credencial do cofre.
- **Somente leitura em camadas:** validador determinístico no dialeto da base (`postgres`, `mysql` ou `duckdb`), tabelas qualificadas no schema/banco configurado, joins apenas por chaves descobertas; sessão PostgreSQL com `default_transaction_read_only`, `SET TRANSACTION READ ONLY`, `statement_timeout` e `lock_timeout`; sessão MySQL com `SET SESSION TRANSACTION READ ONLY`, `START TRANSACTION READ ONLY` e `max_execution_time`; DuckDB aberto com `read_only=True` e interrompido pelo tempo limite. Testes de integração provam que uma conta PostgreSQL com permissão de escrita e uma conta MySQL não conseguem escrever pela sessão, mesmo sem o validador.
- **Parâmetros:** sempre vinculados pelo driver (`$n` no PostgreSQL e DuckDB, `%s` no MySQL com `%` literal escapado no SQL renderizado).
- **Privacidade:** a estrutura (nomes de tabelas e colunas) vai para o modelo para gerar SQL. Colunas com nomes que sugerem dado pessoal ou segredo ficam fora do catálogo e são rejeitadas pelo validador. A detecção é por nome; dados pessoais em colunas com nomes neutros não são detectados, por isso a escolha da conta e do schema continua sendo do usuário.
- **Linhas para a IA:** desligado por padrão em bases próprias; o usuário liga por base. Com ele desligado, nenhuma linha sai da aplicação.
- **API local:** requisições que alteram estado (`POST`, `PATCH`, `DELETE`) vindas de outra origem (`Origin` diferente ou `Sec-Fetch-Site: cross-site`) são recusadas com 403. Uploads de CSV têm limite de tamanho (`CSV_MAX_MB`) aplicado durante o recebimento.
- **Moeda:** símbolos monetários são exibidos apenas na base de exemplo, cuja moeda é documentada.

## Conversa geral

- O modo `chat` responde mensagens sem consultar o banco: não gera SQL, não usa o executor e não recebe linhas de resultado. O modelo recebe a mensagem, a data de referência e as capacidades (nomes de views, colunas e descrições de métricas).
- As instruções proíbem inventar números sobre a empresa e revelar instruções, credenciais ou configurações. O guarda textual de escrita e dados pessoais roda antes, como nas demais rotas.
- O texto é exibido com `textContent`. Por ser conversa geral, não há conferência numérica; respostas sobre dados devem vir dos modos de métrica ou exploração.

## Perguntas exploratórias

- O modo `explore` permite SQL gerado livremente pelo modelo, mas apenas um `SELECT` por pergunta, sempre submetido ao validador determinístico e ao executor com a conta `analytics_agent` (somente leitura, `statement_timeout`, limite de linhas e bytes).
- O contexto enviado ao modelo é o catálogo das views `analytics`; tabelas `core` e campos sensíveis não são listados. O guarda textual de escrita e dados pessoais continua antes do modelo.
- Parâmetros propostos pelo modelo são aceitos apenas como valores vinculados (`$n`), com tipos e tamanhos verificados pelo validador; nunca são concatenados ao SQL.
- A resposta determinística é montada a partir das linhas retornadas. Título e premissas vêm do modelo e são exibidos como declarações dele, não como fatos verificados.
- Respostas exploratórias levam limitação explícita de que não são métricas versionadas. O modo pode ser desativado com `EXPLORATION_ENABLED=false`.

## Resposta em linguagem natural

- Dados enviados: pergunta, premissas, definição e período da métrica (quando houver), colunas e até `NARRATIVE_MAX_ROWS` linhas. Não são enviados SQL, credenciais, tabelas `core` nem campos sensíveis (já bloqueados pelo validador).
- Usar somente com dados sintéticos ou com autorização explícita para enviar resultados ao provedor: com modelos Ollama `-cloud`, as linhas saem para o ollama.com; com modelos locais, ficam na máquina.
- O texto do modelo é tratado como não confiável: inserido com `textContent`, sem ferramentas, e com números conferidos de forma determinística contra os resultados. Divergências ficam visíveis, não são escondidas.
- A conferência cobre valores, totais, médias, diferenças e percentuais simples. Ela não prova que a interpretação ou a recomendação estão corretas; afirmações qualitativas continuam sendo responsabilidade do leitor.
- Falhas da redação não descartam a resposta determinística nem repetem consultas.

## Interface web

- Servida pela API em `/` e `/static`, com Content-Security-Policy restrita (`default-src 'none'`, scripts, estilos, imagens, fontes e conexões somente da própria origem, sem inline). Fontes são hospedadas localmente; nenhum recurso externo é carregado e `X-Content-Type-Options: nosniff`.
- Texto vindo do modelo ou do banco é inserido com `textContent`; o código não usa `innerHTML`. Um teste verifica a ausência dessas APIs e o cabeçalho.
- O histórico fica apenas no `localStorage` do navegador (perguntas e status, sem resultados). A exportação CSV é gerada no próprio navegador a partir das linhas já exibidas. Não há autenticação: manter o uso local.

## Fluxo do modelo (Ollama) e LangGraph

- A aplicação não recebe chave de API: o daemon local do Ollama guarda o login do ollama.com e encaminha os modelos `-cloud`. Modelos locais não enviam nada para fora da máquina.
- O modelo recebe pergunta, conversa recente, definições documentadas, schema selecionado e plano. Com `NARRATIVE_ENABLED=true`, recebe também até `NARRATIVE_MAX_ROWS` linhas do resultado (só em bases que permitem); com `false`, nenhum resultado sai da aplicação.
- Como os modelos de nuvem do Ollama ignoram o parâmetro `format`, o contrato JSON vai nas instruções e é imposto pela validação Pydantic e, para SQL, pelo validador determinístico.
- Datas e região de métricas versionadas são vinculadas pelo plano; parâmetros produzidos pelo modelo devem coincidir com esses valores.
- No máximo quatro chamadas ao modelo por pergunta (interpretação, SQL, uma reescrita, redação). Escrita, múltiplas instruções e campos sensíveis encerram o pedido sem reescrita.
- O adaptador não segue redirecionamentos, não faz retries e não expõe corpos de erro; há timeout por chamada e por fluxo. A execução Psycopg assíncrona permite cancelamento e fechamento da conexão.
- Evidência de consulta iniciada é preservada mesmo quando o prazo total encerra o grafo.
- Tracing LangSmith é desativado no fluxo, inclusive se houver configuração herdada no ambiente. Não há exportação automática de prompts ou resultados.
- O modo `demo` (respostas programadas, sem modelo) precisa ser escolhido expressamente e identifica seus resultados como programados.

Referência: [execução assíncrona Psycopg, incluindo restrição de event loop no Windows](https://www.psycopg.org/psycopg3/docs/advanced/async.html).

A limitação de concorrência é por processo e não equivale a autenticação ou rate limiting empresarial. Interpretação e SQL de um modelo real ainda precisam de avaliação. Uma consulta aprovada pode usar uma fórmula de negócio incorreta; o catálogo e os testes de demonstração não provam a acurácia da geração real.

## Memória da conversa

O cliente envia até 8 trocas anteriores (`history`), validadas como texto sem caracteres de controle e com limites de tamanho; o servidor usa no máximo `HISTORY_TURNS` (padrão 6). O histórico é tratado como dado não confiável, como a própria pergunta: não muda regras, ferramentas nem permissões, e todo SQL gerado com ele passa pelo mesmo validador. Respostas anteriores podem conter valores da base, por isso só são enviadas ao modelo quando a base permite que a IA leia resultados (`allow_rows_to_llm`); caso contrário vão apenas as perguntas. Nada do histórico é registrado em log.

## Progresso em tempo real

`POST /api/v1/ask/stream` executa a mesma análise de `/ask`, com as mesmas validações, e envia uma linha por nó concluído do grafo contendo apenas o nome do nó (`interpret`, `validate`...). Nenhum dado, SQL, prompt ou resultado parcial sai antes da resposta final, que é idêntica à de `/ask`. Se o cliente desconectar, a análise em andamento é cancelada.

## Gráficos pedidos ao modelo

O modelo nunca gera código, SVG ou HTML de gráfico. Ele só pode devolver `chart = {type, x, y}`, com tipo de uma lista fechada e nomes de colunas validados por padrão de identificador. Depois da execução, `backend/agents/charts.py` confere a especificação contra as colunas e valores reais; especificações que não cabem são descartadas com uma nota. O desenho é feito pelo frontend com `textContent` e atributos SVG numéricos, sem interpretar texto do modelo como marcação.

## Reescrita após erro do banco

Quando uma consulta aprovada falha na execução, a mensagem do driver nunca vai ao modelo nem ao log, porque pode citar valores da base. Apenas a classe do erro (SQLSTATE no PostgreSQL, número do erro no MySQL, tipo da exceção no DuckDB) é convertida em uma dica fixa de `backend/tools/execution_hints.py` (ex.: "proteja o divisor com NULLIF"). Com dica conhecida e dentro do limite de tentativas, o modelo reescreve uma vez e o novo SQL passa pelo validador do zero; sem dica conhecida, o pedido termina com erro.

## Base de exemplo embutida (app instalado)

Sem credenciais do PostgreSQL configuradas, a base de exemplo é gerada localmente em DuckDB (`%LOCALAPPDATA%\OtterData\sample-ecommerce-v2.duckdb`), a partir do mesmo gerador determinístico, sem a coluna `email`. Ela é aberta somente para leitura, passa pelo mesmo validador (dialeto DuckDB) e funciona em modo exploração; as definições das métricas vão ao modelo como documentação, sem a vinculação de parâmetros das métricas versionadas.

## MongoDB (cópia local)

O MongoDB não usa SQL, então não é consultado diretamente: ao conectar (e a cada "Atualizar"), o app lê as coleções com `find` e copia os documentos para um arquivo DuckDB local, e todas as perguntas rodam como SQL validado sobre essa cópia, com as mesmas regras das outras bases. Contra o MongoDB só são usados `ping`, `list_collection_names` e `find`, com tempo limite e no máximo 100 mil documentos por coleção (o limite é registrado na estrutura da base). Subdocumentos viram colunas (`endereco.cidade` → `endereco_cidade`), listas de subdocumentos viram tabelas filhas ligadas ao documento pai (`orders.items` → `orders_items.orders_id`) e outras listas ficam como texto JSON. A cópia nova é montada num arquivo temporário e só substitui a anterior se der certo. Recomenda-se um usuário com o papel `read`; a senha vai para o Cofre de Credenciais do Windows, e servidores sem autenticação não guardam senha. Mensagens de erro do MongoDB nunca são repassadas: só textos fixos (conexão, acesso recusado, tempo esgotado).

## Valores de colunas de categoria

O modelo escreve filtros de texto (ex.: `status = 'cancelled'`) sem ver os dados, então pode errar a grafia e devolver zero com confiança. Nas bases em que o usuário permite que a IA leia resultados, o app envia os valores distintos de colunas de texto curtas (até 12 valores, até 60 caracteres, nunca colunas ocultas, identificadores, datas ou listas JSON), obtidos por consultas `SELECT DISTINCT` que passam pelo validador; os valores ficam só em memória. Sem essa permissão, o modelo é instruído a não filtrar por texto adivinhado e agrupar pela coluna, e o validador recusa um `GROUP BY` principal cuja coluna não aparece no resultado, para que cada linha diga a que grupo pertence.
