"use strict";

// Interface language. Texts are written in Portuguese in app.js and index.html; EN gives the
// English for each one. Fixed server messages are translated with the same table (exact text),
// and PATTERNS cover the ones that carry a name or a number. Model-written text already comes in
// the chosen language, because the request carries it.

const I18N = (() => {
  const KEY = "otterdata.language";
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(KEY));
  } catch {
    /* storage unavailable */
  }
  const lang = saved === "pt" ? "pt" : "en"; // English unless Portuguese was chosen
  const locale = lang === "en" ? "en-US" : "pt-BR";
  document.documentElement.lang = locale;

  const EN = {
    // ---------- Page and sidebar ----------
    "Otter Data: analista de dados com IA, SQL validado e evidências auditáveis.":
      "Otter Data: an AI data analyst with validated SQL and auditable evidence.",
    "Navegação": "Navigation",
    "Otter Data, início": "Otter Data, home",
    "Nova conversa": "New conversation",
    "Conversas": "Conversations",
    "Limpar": "Clear",
    "Suas conversas ficam guardadas só neste aparelho.": "Your conversations are stored only on this device.",
    "Estado do sistema": "System status",
    "Modelo": "Model",
    "Base": "Source",
    "verificando": "checking",
    "Bases de dados e ajustes": "Databases and settings",
    "Configurações": "Settings",
    "Alternar tema claro/escuro": "Toggle light/dark theme",
    "Tema": "Theme",
    "Idioma": "Language",
    "Idioma da interface e das respostas": "Language of the interface and the answers",
    "Abrir menu": "Open menu",
    "Exemplo: e-commerce sintético": "Sample: synthetic e-commerce",
    "Status": "Status",
    "Pronto": "Ready",
    "Sua pergunta": "Your question",
    "Converse ou pergunte sobre os dados…": "Chat or ask about the data…",
    "Enviar pergunta": "Send question",
    "Perguntar": "Ask",
    "Base para datas relativas como 'este mês'": "Reference for relative dates like 'this month'",
    "Ref. hoje": "Ref. today",
    "Escolher data de referência": "Choose reference date",
    "Modelo de IA usado nas próximas perguntas": "AI model used for the next questions",
    "envia,": "sends,",
    "quebra a linha": "new line",
    "As respostas podem conter erros. Confira premissas, SQL e números em “Como chegamos aqui?”. As últimas mensagens desta conversa servem de contexto.":
      "Answers can contain mistakes. Check assumptions, SQL and numbers in “How did we get here?”. The latest messages of this conversation are used as context.",
    "Otter Data / área de trabalho": "Otter Data / workspace",
    "Pergunte aos seus dados.": "Ask your data.",
    "Conecte seus dados e pergunte.": "Connect your data and ask.",
    "Ligue um banco PostgreSQL ou MySQL ou importe planilhas CSV. Cada pergunta vira uma consulta só de leitura, validada antes de executar, com as evidências de cada número.":
      "Connect a PostgreSQL or MySQL database or import CSV spreadsheets. Every question becomes a read-only query, validated before it runs, with the evidence behind each number.",
    "Conversando com {name}. Cada pergunta vira uma consulta só de leitura, validada antes de executar, com as evidências de cada número.":
      "Talking to {name}. Every question becomes a read-only query, validated before it runs, with the evidence behind each number.",
    "Sem dados à mão? Teste com a base de exemplo": "No data at hand? Try the sample data",
    "Exemplo gravado": "Recorded example",
    "Conversa real na base sintética de e-commerce, registrada em 03/10/2026.":
      "Real conversation on the synthetic e-commerce data, recorded on Oct 3, 2026.",

    // ---------- Settings ----------
    "Bases de dados": "Databases",
    "Converse com a base de exemplo, conecte o seu PostgreSQL ou MySQL, ou importe planilhas CSV.":
      "Chat with the sample data, connect your PostgreSQL or MySQL, or import CSV spreadsheets.",
    "Fechar configurações": "Close settings",
    "Suas bases": "Your data sources",
    "Adicionar base": "Add a data source",
    "Tipo de base": "Source type",
    "Conectar banco": "Connect database",
    "Importar CSV": "Import CSV",
    "Tipo de banco": "Database type",
    "Nome para identificar": "Display name",
    "Ex.: Loja — réplica de leitura": "E.g.: Store — read replica",
    "Servidor": "Host",
    "localhost ou db.empresa.com": "localhost or db.company.com",
    "Porta": "Port",
    "Banco": "Database",
    "(opcional)": "(optional)",
    "Usuário": "User",
    "Senha": "Password",
    "Permitir que a IA leia os resultados para escrever a resposta": "Let the AI read the results to write the answer",
    "Use um usuário com permissão": "Use a user with",
    "só de leitura": "read-only",
    ". A senha fica no Cofre de Credenciais do Windows, nunca em arquivo nem na IA. No app desktop,":
      " permission. The password stays in the Windows Credential Manager, never in a file or with the AI. In the desktop app,",
    "é este computador.": "is this computer.",
    "Testar e conectar": "Test and connect",
    "Ex.: Vendas 2026": "E.g.: Sales 2026",
    "Escolha um ou mais arquivos CSV": "Choose one or more CSV files",
    "Cada arquivo vira uma tabela. A primeira linha deve ter os nomes das colunas. Até 50 MB por arquivo.":
      "Each file becomes a table. The first row must hold the column names. Up to 50 MB per file.",
    "Importar": "Import",
    "A IA recebe só nomes de tabelas e colunas para escrever o SQL. Colunas com cara de dado pessoal (e-mail, CPF, telefone, senha…) ficam ocultas e bloqueadas. Linhas do resultado só vão para a IA nas bases em que você permitir. Toda consulta roda em transação somente leitura, com tempo limite.":
      "The AI only receives table and column names to write the SQL. Columns that look like personal data (email, tax ID, phone, password…) are hidden and blocked. Result rows only reach the AI for sources where you allow it. Every query runs in a read-only transaction with a time limit.",
    "Confirmação": "Confirmation",
    "Cancelar": "Cancel",
    "Confirmar": "Confirm",

    // ---------- app.js: status, models, calendar ----------
    "Demonstração": "Demo",
    "Sem configuração": "Not configured",
    "não informado": "not reported",
    "Sem resposta": "No response",
    "Na nuvem (Ollama)": "In the cloud (Ollama)",
    "Neste computador (Ollama)": "On this computer (Ollama)",
    "Pronto, local": "Ready, local",
    "Pronto, na nuvem": "Ready, cloud",
    "Modelo local: mais lento e, se for pequeno, erra mais SQL": "Local model: slower and, if small, gets more SQL wrong",
    "Modelo: {name}": "Model: {name}",
    "padrão": "default",
    "roda nesta máquina": "runs on this machine",
    "Modelos locais aparecem aqui depois de ": "Local models show up here after ",
    "ollama pull <modelo>": "ollama pull <model>",
    ". Modelos pequenos (até ~7B) costumam errar mais o SQL; o validador bloqueia o que estiver fora da política.":
      ". Small models (up to ~7B) tend to get SQL wrong more often; the validator blocks anything outside the policy.",
    "Ref. {date}": "Ref. {date}",
    "Mês anterior": "Previous month",
    "Próximo mês": "Next month",
    "Usar hoje": "Use today",
    "Base para “este mês”, “ontem”…": "Reference for “this month”, “yesterday”…",
    "{start} a {end}": "{start} to {end}",

    // ---------- Loading ----------
    "Interpretação": "Interpretation",
    "Catálogo": "Catalog",
    "Consulta": "Query",
    "Validação": "Validation",
    "Execução": "Execution",
    "Evidência": "Evidence",
    "aguardando": "waiting",
    "analisando": "working",
    "ok": "ok",
    "não necessária": "not needed",
    "Respondendo": "Replying",
    "Consulta (reescrita)": "Query (rewritten)",

    // ---------- Sources ----------
    "Exemplo": "Sample",
    "Confira os campos preenchidos.": "Check the fields you filled in.",
    "Não foi possível concluir (erro {status}).": "Could not complete the request (error {status}).",
    "Base indisponível": "Source unavailable",
    "Esta base foi removida": "This source was removed",
    "Indisponível": "Unavailable",
    "{kind}, {count} tabelas": "{kind}, {count} tables",
    "removida": "removed",
    "Conversando com: {name}": "Talking to: {name}",
    "base": "source",
    "{kind} · {count} tabelas": "{kind} · {count} tables",
    "Gerenciar bases…": "Manage sources…",
    "A IA poderá ler os resultados desta base": "The AI will be able to read results from this source",
    "A IA não lerá os resultados desta base": "The AI will not read results from this source",
    "{count} tabelas": "{count} tables",
    "{count} colunas": "{count} columns",
    "{count} ocultas por privacidade": "{count} hidden for privacy",
    "métricas versionadas": "versioned metrics",
    "Nesta conversa": "In this conversation",
    "IA pode ler os resultados (dados sintéticos)": "AI can read the results (synthetic data)",
    "IA pode ler os resultados": "AI can read the results",
    "Usar nesta conversa": "Use in this conversation",
    "Ver estrutura": "View structure",
    "Atualizar": "Refresh",
    "Remover": "Remove",
    "Carregando estrutura…": "Loading structure…",
    "Ocultas: {columns}": "Hidden: {columns}",
    "Ignorados (nomes fora do padrão): {items}": "Skipped (unsupported names): {items}",
    "Estrutura atualizada": "Structure refreshed",
    "Bases de dados / remover": "Databases / remove",
    "Remover a base \"{name}\"?": "Remove the source \"{name}\"?",
    "A conexão e a senha salva serão apagadas deste aparelho. Os dados no seu banco não são alterados.":
      "The connection and the saved password will be deleted from this device. The data in your database is not changed.",
    "Remover base": "Remove source",
    "Base removida": "Source removed",
    "Preencha nome, servidor, banco e usuário.": "Fill in name, host, database and user.",
    "Conectando e lendo a estrutura do banco…": "Connecting and reading the database structure…",
    "Conectado: {count} tabelas encontradas.": "Connected: {count} tables found.",
    "Dê um nome e escolha pelo menos um arquivo CSV.": "Give it a name and choose at least one CSV file.",
    "Importando {file} ({index} de {total})…": "Importing {file} ({index} of {total})…",
    "Importado: {tables} tabela(s), {columns} colunas.": "Imported: {tables} table(s), {columns} columns.",
    "{message} (os arquivos anteriores foram importados)": "{message} (the previous files were imported)",
    "mesmo nome do banco": "same as the database name",

    // ---------- Conversations ----------
    "agora": "now",
    "há {minutes} min": "{minutes} min ago",
    "hoje, {time}": "today, {time}",
    "ontem": "yesterday",
    "Pergunta {number}": "Question {number}",
    "Base própria": "Own source",
    "perg.": "q.",
    "pergs.": "qs.",
    "Apagar a conversa \"{title}\"": "Delete the conversation \"{title}\"",
    "Conversas / limpar": "Conversations / clear",
    "Apagar a conversa salva?": "Delete the saved conversation?",
    "Apagar as {count} conversas salvas?": "Delete the {count} saved conversations?",
    "Elas ficam guardadas só neste aparelho e não poderão ser recuperadas. As bases de dados não são afetadas.":
      "They are stored only on this device and cannot be recovered. Your data sources are not affected.",
    "Apagar conversas": "Delete conversations",
    "Conversas apagadas": "Conversations deleted",

    // ---------- Starter questions ----------
    "Qual foi a receita recebida em setembro de 2026?": "What was the received revenue in September 2026?",
    "Quais regiões tiveram maior receita recebida em setembro de 2026?":
      "Which regions had the highest received revenue in September 2026?",
    "Como a receita recebida evoluiu de janeiro a setembro de 2026?":
      "How did received revenue evolve from January to September 2026?",
    "Qual produto mais vale a pena vender?": "Which product is most worth selling?",
    "Como estão as vendas?": "How are sales going?",
    "Quantos pedidos existem por status?": "How many orders are there per status?",

    // ---------- Answers ----------
    "Receita recebida": "Received revenue",
    "Novos clientes": "New customers",
    "Pedidos cancelados": "Cancelled orders",
    "Conversa": "Chat",
    "Validada": "Validated",
    "Aguardando detalhes": "Needs details",
    "Recusada": "Refused",
    "Erro": "Error",
    "Investigando": "Investigating",
    "Analisando": "Analyzing",
    "Offline": "Offline",
    "Online": "Online",
    "Não foi possível enviar a pergunta": "The question could not be sent",
    "Confira o texto e a data de referência e tente novamente.": "Check the text and the reference date and try again.",
    "Sem conexão com a API": "No connection to the API",
    "O backend não respondeu. Verifique se ele está em execução e tente de novo.":
      "The backend did not respond. Check that it is running and try again.",
    "Faltam detalhes para responder": "More details are needed",
    "Pedido não permitido": "Request not allowed",
    "Números do texto que não aparecem nem derivam das linhas retornadas":
      "Numbers in the text that neither appear in nor derive from the returned rows",
    "{count} número(s) do texto não conferem com o resultado: {numbers}. Veja \"Como chegamos aqui?\".":
      "{count} number(s) in the text do not match the result: {numbers}. See \"How did we get here?\".",
    "por região": "by region",
    "por mês": "by month",
    "Período {period}": "Period {period}",
    "Você pode perguntar": "You can ask",
    "Continue a investigação": "Keep investigating",
    "Tentar novamente": "Try again",
    "Não foi possível concluir a consulta": "The query could not be completed",
    "Aviso": "Notice",
    "Você pode tentar": "You can try",

    // ---------- "Como chegamos aqui?" ----------
    "total do período": "period total",
    "Recusado antes de chegar ao modelo: o pedido envolve escrita ou dados pessoais.":
      "Refused before reaching the model: the request involves writing or personal data.",
    "A pergunta não chegou a ser interpretada.": "The question was not interpreted.",
    "Exploração livre: {title}.": "Free exploration: {title}.",
    "consulta descritiva": "descriptive query",
    "Critério escolhido:": "Chosen criteria:",
    "Métrica versionada {metric}": "Versioned metric {metric}",
    "de {period}": "from {period}",
    "somente a região {region}": "only the {region} region",
    "Pedido recusado pela política de leitura.": "Request refused by the read-only policy.",
    "Faltou informação para escolher a métrica ou o período.": "Information was missing to choose the metric or the period.",
    "A pergunta depende de dados ou análises fora do alcance desta base.":
      "The question depends on data or analyses beyond this source.",
    "Interpretação concluída.": "Interpretation complete.",
    "Definição usada: {description} Versão {version}, unidade {unit}.":
      "Definition used: {description} Version {version}, unit {unit}.",
    "Nenhum campo do catálogo foi consultado.": "No catalog field was queried.",
    "Copiar SQL": "Copy SQL",
    "Copiado ✓": "Copied ✓",
    "Não foi possível copiar": "Could not copy",
    "Pergunta": "Question",
    "Referência": "Reference",
    "Demonstração programada": "Scripted demo",
    "Consulta preparada": "Prepared query",
    "A primeira versão não passou na validação; a consulta foi reescrita uma vez.":
      "The first version did not pass validation; the query was rewritten once.",
    "Valores enviados à parte, como parâmetros: {names}.": "Values sent separately, as parameters: {names}.",
    "Nenhuma consulta foi preparada.": "No query was prepared.",
    "Aprovada: um único SELECT, apenas tabelas do catálogo, junções pelas chaves documentadas e nenhuma coluna pessoal.":
      "Approved: a single SELECT, catalog tables only, joins on documented keys and no personal columns.",
    "Recusada: {reason}": "Refused: {reason}",
    "Código {code}. Nada foi executado.": "Code {code}. Nothing was executed.",
    "Não houve consulta para validar.": "There was no query to validate.",
    "{rows} linha(s) em {ms} ms, em transação somente leitura{truncated}.":
      "{rows} row(s) in {ms} ms, in a read-only transaction{truncated}.",
    "; resultado truncado pelo limite": "; result truncated by the limit",
    "Nada foi executado no banco.": "Nothing was executed in the database.",
    "A IA leu {rows} linha(s) do resultado para escrever a resposta. {check}":
      "The AI read {rows} row(s) of the result to write the answer. {check}",
    "{count} número(s) do texto não conferem: {numbers}.": "{count} number(s) in the text do not match: {numbers}.",
    "{count} número(s) do texto conferem com o resultado.": "{count} number(s) in the text match the result.",
    "A resposta usa apenas os valores calculados pela consulta.": "The answer uses only the values computed by the query.",
    "Para considerar:": "Worth considering:",
    "Limites da base:": "Source limitations:",
    "parou aqui": "stopped here",
    "interrompida": "interrupted",
    "não executada": "not run",
    "sem leitura da IA": "no AI reading",
    "recusada": "refused",
    "Campos": "Fields",
    "Linhas": "Rows",
    "Total": "Total",
    "Etapa": "Stage",
    "interpretação": "interpretation",
    "não concluída": "not completed",
    "SQL": "SQL",
    "Caminho da consulta": "Query path",
    "Rastro da consulta {number}": "Query trace {number}",
    "Como chegamos aqui?": "How did we get here?",
    "Requisição": "Request",
    "Chamadas ao modelo": "Model calls",
    "Tokens": "Tokens",

    // ---------- Figures ----------
    "sim": "yes",
    "não": "no",
    "Resultado": "Result",
    "Período de {period}": "Period {period}",
    "consulta exploratória validada": "validated exploratory query",
    "métrica {name}, versão {version}": "metric {name}, version {version}",
    "base {name}": "source {name}",
    "lista truncada pelo limite de retorno": "list truncated by the return limit",
    "Gráfico": "Chart",
    "Tabela": "Table",
    "A consulta não retornou registros.": "The query returned no records.",
    "CSV baixado ✓": "CSV downloaded ✓",
    "CSV exportado": "CSV exported",
    "Fig. {number}": "Fig. {number}",
    "Fonte: {tables}": "Source: {tables}",
    "Mês": "Month",
    "Região": "Region",
    "Participação": "Share",
    "{label} por categoria": "{label} by category",
    "{share} do total": "{share} of total",
    "{label} ao longo do tempo": "{label} over time",
    "{change} vs. mês anterior": "{change} vs. previous month",
    "Dispersão de {label} por {x}, {count} pontos": "Scatter of {label} by {x}, {count} points",
    "{label}: partes do total": "{label}: parts of the total",

    // ---------- Server: sources ----------
    "Arquivo local (DuckDB) gerado no primeiro uso, somente leitura": "Local file (DuckDB) created on first use, read-only",
    "PostgreSQL local (Docker), conta somente leitura": "Local PostgreSQL (Docker), read-only account",
    "arquivo CSV importado": "imported CSV file",
    "O arquivo está vazio.": "The file is empty.",
    "Origem não permitida.": "Origin not allowed.",
    "Base de dados não encontrada.": "Data source not found.",
    "Estrutura da base não encontrada; atualize a base.": "Source structure not found; refresh the source.",
    "A senha desta base não está no cofre; remova e conecte de novo.":
      "This source's password is not in the vault; remove it and connect again.",
    "Só é possível adicionar CSV a uma base de CSV.": "CSV files can only be added to a CSV source.",
    "O CSV não tem linhas de dados abaixo do cabeçalho.": "The CSV has no data rows below the header.",
    "Não foi possível ler o CSV; confira se a primeira linha tem os nomes das colunas.":
      "Could not read the CSV; check that the first row holds the column names.",
    "O cofre de credenciais não está disponível aqui; conecte bancos pelo app desktop.":
      "The credential vault is not available here; connect databases from the desktop app.",
    "O cofre de credenciais do sistema não está disponível; use o app no Windows.":
      "The system credential vault is not available; use the app on Windows.",
    "Não foi possível conectar ao PostgreSQL; confira host, porta, usuário e senha.":
      "Could not connect to PostgreSQL; check host, port, user and password.",
    "Não foi possível conectar ao MySQL; confira host, porta, usuário e senha.":
      "Could not connect to MySQL; check host, port, user and password.",
    "Conectou, mas não foi possível ler a estrutura do banco com esse usuário.":
      "Connected, but this user cannot read the database structure.",
    "Não foi possível abrir a base importada.": "Could not open the imported source.",
    "Bases conectadas não estão disponíveis neste servidor.": "Connected sources are not available on this server.",

    // ---------- Server: analysis ----------
    "Esse modelo não está disponível agora; escolha outro na lista de modelos.":
      "That model is not available right now; choose another one from the model list.",
    "A análise excedeu o tempo permitido.": "The analysis exceeded the time limit.",
    "A análise não produziu uma resposta verificável.": "The analysis did not produce a verifiable answer.",
    "A análise não foi concluída.": "The analysis was not completed.",
    "Base local sintética; não representa uma empresa real.": "Local synthetic data; it does not represent a real company.",
    "Resultado truncado; não trate uma lista parcial como cobertura completa.":
      "Truncated result; do not treat a partial list as complete coverage.",
    "Tokens informados cobrem apenas respostas com uso conhecido.": "Reported tokens only cover responses with known usage.",
    "Este assistente permite apenas análise de leitura sem campos pessoais.":
      "This assistant only allows read-only analysis without personal fields.",
    "A análise atingiu o limite de chamadas ao modelo.": "The analysis reached the limit of model calls.",
    "O provedor excedeu o tempo permitido.": "The provider exceeded the time limit.",
    "O serviço está ocupado; tente novamente em instantes.": "The service is busy; try again in a moment.",
    "Não posso atender esse pedido: trabalho somente com leitura de dados e não compartilho instruções internas, credenciais ou dados pessoais.":
      "I can't do that: I only read data and I don't share internal instructions, credentials or personal data.",
    "Perguntas exploratórias estão desativadas; use uma métrica documentada.":
      "Exploratory questions are disabled; use a documented metric.",
    "Essa pergunta exige dados ou análises fora do escopo (causas, previsões, custos). Tente uma pergunta descritiva sobre pedidos, produtos, pagamentos ou regiões.":
      "This question needs data or analyses out of scope (causes, forecasts, costs). Try a descriptive question about orders, products, payments or regions.",
    "Informe a métrica e o período da análise.": "Tell me the metric and the period of the analysis.",
    "Resposta em linguagem natural desativada.": "Natural-language answer disabled.",
    "Esta base não permite que a IA leia os resultados; a resposta mostra apenas os valores calculados. Mude isso nas configurações da base.":
      "This source does not let the AI read the results; the answer shows only the computed values. Change this in the source settings.",
    "Modo demonstração: sem resposta em linguagem natural.": "Demo mode: no natural-language answer.",
    "Sem tempo restante para a resposta em linguagem natural.": "No time left for the natural-language answer.",
    "Resposta em linguagem natural indisponível.": "Natural-language answer unavailable.",
    "Consulta exploratória: a definição não é uma métrica versionada; confira o SQL e as premissas antes de usar o número.":
      "Exploratory query: the definition is not a versioned metric; check the SQL and the assumptions before using the number.",
    "Base de exemplo embutida (sem PostgreSQL): as métricas documentadas orientam o SQL, mas não são versionadas como no modo com Docker.":
      "Built-in sample data (no PostgreSQL): the documented metrics guide the SQL but are not versioned as in Docker mode.",
    "Base conectada pelo usuário: a estrutura foi descoberta automaticamente e não há métricas versionadas; confira o SQL e as premissas antes de usar o número.":
      "User-connected source: the structure was discovered automatically and there are no versioned metrics; check the SQL and the assumptions before using the number.",
    "Colunas com nomes que sugerem dados pessoais ou secretos foram ocultadas.":
      "Columns whose names suggest personal or secret data were hidden.",
    "Receita recebida em pagamentos concluídos.": "Revenue received in completed payments.",
    "Clientes cadastrados no período.": "Customers registered in the period.",
    "Pedidos cujo cancelamento ocorreu no período.": "Orders cancelled in the period.",
    "Não representa receita líquida; estornos não são modelados nesta seed.":
      "Not net revenue; refunds are not modeled in this seed.",
    "Não juntar pagamentos a itens diretamente para somar valores; isso duplica pagamentos.":
      "Do not join payments to items directly to sum values; that duplicates payments.",
    "Cancelamento de pedido não é churn de cliente.": "An order cancellation is not customer churn.",
    "O resultado foi truncado pelo limite de retorno; a lista está incompleta.":
      "The result was truncated by the return limit; the list is incomplete.",

    // ---------- Server: execution and validation ----------
    "A consulta excedeu o tempo permitido.": "The query exceeded the time limit.",
    "A consulta aprovada falhou durante a execução.": "The approved query failed during execution.",
    "Não foi possível acessar o banco analítico.": "Could not reach the analytics database.",
    "Execução cancelada pelo prazo ou cancelamento da solicitação.": "Execution cancelled by the deadline or by the request being cancelled.",
    "Consulta iniciada; execução ainda não concluída.": "Query started; execution not finished yet.",
    "Não foi possível conectar ao Ollama; confira se ele está em execução e o valor de OLLAMA_BASE_URL.":
      "Could not connect to Ollama; check that it is running and the value of OLLAMA_BASE_URL.",
    "O modelo configurado não está disponível no Ollama; confira OLLAMA_MODEL.":
      "The configured model is not available in Ollama; check OLLAMA_MODEL.",
    "O Ollama rejeitou o formato da solicitação; a integração precisa de revisão.":
      "Ollama rejected the request format; the integration needs review.",
    "O Ollama está indisponível; tente novamente mais tarde.": "Ollama is unavailable; try again later.",
    "O modelo retornou uma saída inválida.": "The model returned an invalid output.",
    "Informe uma consulta SQL não vazia.": "Provide a non-empty SQL query.",
    "SQL excede o limite de tamanho.": "SQL exceeds the size limit.",
    "SQL excede a complexidade permitida.": "SQL exceeds the allowed complexity.",
    "Permita exatamente uma instrução.": "Exactly one statement is allowed.",
    "Apenas SELECT é permitido.": "Only SELECT is allowed.",
    "SQL inválido ou não suportado pelo parser.": "Invalid SQL or not supported by the parser.",
    "Forma SQL não suportada pela política atual.": "SQL form not supported by the current policy.",
    "UNION, INTERSECT e EXCEPT não são permitidos. Traga os valores como colunas lado a lado num único SELECT (ex.: SUM(CASE WHEN ... THEN 1 ELSE 0 END) por coluna) ou agrupe com GROUP BY.":
      "UNION, INTERSECT and EXCEPT are not allowed. Bring the values as side-by-side columns in a single SELECT (e.g. SUM(CASE WHEN ... THEN 1 ELSE 0 END) per column) or group with GROUP BY.",
    "Junção por vírgula ou CROSS JOIN não é permitida. Para comparar grupos, agregue numa única subconsulta com GROUP BY e compare na consulta externa com MAX(CASE WHEN ... THEN ... END).":
      "Comma joins and CROSS JOIN are not allowed. To compare groups, aggregate in a single subquery with GROUP BY and compare in the outer query with MAX(CASE WHEN ... THEN ... END).",
    "Agregações aninhadas (ex.: CORR(SUM(...)) ou AVG(COUNT(...))) não são permitidas: calcule a primeira agregação numa subconsulta com GROUP BY e aplique a segunda na consulta externa.":
      "Nested aggregations (e.g. CORR(SUM(...)) or AVG(COUNT(...))) are not allowed: compute the first aggregation in a subquery with GROUP BY and apply the second in the outer query.",
    "Colunas ou aliases não puderam ser resolvidos no catálogo autorizado.":
      "Columns or aliases could not be resolved in the authorized catalog.",
    "Use nomes de saída distintos.": "Use distinct output names.",
    "Escrita e bloqueios são proibidos.": "Writes and locks are forbidden.",
    "Construção SQL não autorizada.": "SQL construct not authorized.",
    "Identificador não suportado.": "Identifier not supported.",
    "Campo sensível bloqueado.": "Sensitive field blocked.",
    "Liste as colunas explicitamente.": "List the columns explicitly.",
    "CTEs recursivas não são permitidas.": "Recursive CTEs are not allowed.",
    "Colunas de saída em excesso.": "Too many output columns.",
    "Literal excede o limite de tamanho.": "Literal exceeds the size limit.",
    "Tipo de cast não autorizado.": "Cast type not authorized.",
    "Precisão de cast inválida.": "Invalid cast precision.",
    "Precisão de cast excessiva.": "Cast precision too large.",
    "Unidade temporal não autorizada.": "Time unit not authorized.",
    "Fuso horário não autorizado.": "Time zone not authorized.",
    "Aliases de listas de colunas não suportados.": "Column-list aliases are not supported.",
    "Fonte não autorizada.": "Source not authorized.",
    "A consulta deve usar uma view aprovada.": "The query must use an approved view.",
    "Join sem relação explícita autorizada.": "Join without an explicit authorized relationship.",
    "Join deve comparar chaves documentadas.": "Joins must compare documented keys.",
    "Join em fonte derivada não suportado.": "Join on a derived source is not supported.",
    "Join não conecta a fonte adicionada.": "Join does not connect the added source.",
    "Relacionamento fora do catálogo.": "Relationship outside the catalog.",
    "Parâmetros ausentes ou excedentes.": "Missing or extra parameters.",
    "Use parâmetros nomeados como :start_date.": "Use named parameters such as :start_date.",
    "Tipo de parâmetro não suportado.": "Parameter type not supported.",
    "Parâmetro excede o limite de tamanho.": "Parameter exceeds the size limit.",
    "Parâmetro numérico deve ser finito.": "Numeric parameter must be finite.",
    "Parâmetro decimal inválido.": "Invalid decimal parameter.",
    "Inteiro fora do intervalo permitido.": "Integer out of the allowed range.",
    "Informe uma pergunta válida.": "Enter a valid question.",
  };

  // Server messages with a name or a number inside. Applied to the whole text.
  const PATTERNS = [
    [/^O arquivo passa de (\d+) MB\.$/, "The file is larger than $1 MB."],
    [/^Conectou, mas não há tabelas legíveis em “(.+)” com esse usuário\.$/, "Connected, but this user has no readable tables in “$1”."],
    [/^Base conectada pelo usuário: (.+)\.$/, "User-connected source: $1."],
    [/^tabela (\S+) \(limite de (\d+) tabelas\)$/, "table $1 (limit of $2 tables)"],
    [/^coluna (\S+) \(limite de (\d+) colunas\)$/, "column $1 (limit of $2 columns)"],
    [/^tabela (\S+)$/, "table $1"],
    [/^coluna (\S+)$/, "column $1"],
    [/^Resposta em linguagem natural indisponível \((\w+)\)\.$/, "Natural-language answer unavailable ($1)."],
    [/^O gráfico de (barras|linha|dispersão|pizza) pedido não foi desenhado: (.+)\. Os dados aparecem em tabela\.$/,
      (_, name, reason) => `The requested ${{ barras: "bar", linha: "line", "dispersão": "scatter", pizza: "pie" }[name]} chart was not drawn: ${chartReason(reason)}. The data is shown as a table.`],
    [/^(SUM|AVG|COUNT) de (\S+) contaria valores repetidos: o join com (\S+) traz várias linhas para cada linha de (\S+)\. .*$/,
      "$1 of $2 would count repeated values: the join with $3 brings several rows for each row of $4. Use the measure from the most detailed table, COUNT(DISTINCT ...) to count, or filter with IN (SELECT ...) instead of joining (e.g. WHERE x.order_id IN (SELECT order_id FROM ... WHERE ...))."],
    [/^Parâmetros ausentes ou excedentes\.(?: Sem valor: ([^.]+)\.)?(?: Não usados no SQL: ([^.]+)\.)? Cada :nome .*$/,
      (_, missing, extra) => `Missing or extra parameters.${missing ? ` No value: ${missing}.` : ""}${extra ? ` Not used in the SQL: ${extra}.` : ""} Every :name in the SQL needs a value in parameters, with the same name.`],
    [/^Use somente tabelas aprovadas, qualificadas como (\S+)\.$/, "Use only approved tables, qualified as $1."],
    [/^Função (.+) não permitida; use só as funções autorizadas\.$/, "Function $1 is not allowed; use only authorized functions."],
    [/^Consulta grande demais \((\d+) SELECTs, (\d+) joins; máximo 8 e 6\)\. Simplifique: faça os joins uma vez só e agregue com GROUP BY\.$/,
      "Query too large ($1 SELECTs, $2 joins; at most 8 and 6). Simplify: join once and aggregate with GROUP BY."],
    [/^A coluna (\S+) não existe(?: em (\S+))? neste ponto da consulta\. Na consulta externa, use os nomes de saída da subconsulta, não os aliases de tabelas internas\.$/,
      (_, column, table) => `Column ${column} does not exist${table ? ` in ${table}` : ""} at this point of the query. In the outer query, use the subquery's output names, not the aliases of inner tables.`],
    // Deterministic answers (shown when there is no natural-language answer).
    [/^(.+): a consulta não retornou registros\.$/, "$1: the query returned no records."],
    [/^(.+): (\d+) linha\(s\) retornada\(s\)( \(lista truncada pelo limite de retorno\))?; veja a tabela\.$/,
      (_, title, count, truncated) => `${title}: ${count} row(s) returned${truncated ? " (list truncated by the return limit)" : ""}; see the table.`],
    [/^(Modo demonstração, sem LLM\. )?(Receita recebida|Clientes cadastrados|Pedidos cancelados) de (\S+) a (\S+)(, por (região|mês))?:/,
      (_, demo, metric, start, end, by, dimension) => `${demo ? "Demo mode, no LLM. " : ""}${{
        "Receita recebida": "Received revenue", "Clientes cadastrados": "Registered customers", "Pedidos cancelados": "Cancelled orders",
      }[metric]} from ${start} to ${end}${by ? ` by ${dimension === "mês" ? "month" : "region"}` : ""}:`],
    [/^(Modo demonstração, sem LLM\. )?Não foram retornados registros para os filtros de (\S+) a (\S+)\.$/,
      (_, demo, start, end) => `${demo ? "Demo mode, no LLM. " : ""}No records were returned for the filters from ${start} to ${end}.`],
    [/Exibidos cinco de (\d+) grupos; consulte os demais nas evidências\./, "Showing five of $1 groups; see the rest in the evidence."],
    [/O resultado foi truncado pelo limite de retorno; a lista está incompleta\./, "The result was truncated by the return limit; the list is incomplete."],
  ];

  function chartReason(reason) {
    const fixed = {
      "as colunas indicadas não estão no resultado": "the given columns are not in the result",
      "o eixo e o valor precisam ser colunas diferentes": "the axis and the value must be different columns",
      "a pizza só representa partes positivas de um total": "a pie only shows positive parts of a total",
    };
    if (fixed[reason]) return fixed[reason];
    let match = reason.match(/^esse tipo funciona com (\d+) a (\d+) linhas e o resultado tem (\d+)$/);
    if (match) return `this type works with ${match[1]} to ${match[2]} rows and the result has ${match[3]}`;
    match = reason.match(/^a coluna (\S+) não é numérica em todas as linhas$/);
    if (match) return `column ${match[1]} is not numeric in every row`;
    match = reason.match(/^a dispersão precisa de duas colunas numéricas e (\S+) não é$/);
    if (match) return `a scatter needs two numeric columns and ${match[1]} is not one`;
    return reason;
  }

  const fill = (text, vars) => (vars
    ? text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? String(vars[name]) : whole))
    : text);

  // Interface text, written in Portuguese with {named} slots.
  function t(text, vars) {
    return fill(lang === "en" ? EN[text] ?? text : text, vars);
  }

  // A message that came from the server: exact entries, then patterns, else unchanged.
  function tm(text) {
    if (lang !== "en" || typeof text !== "string" || !text) return text;
    if (EN[text]) return EN[text];
    let result = text;
    for (const [pattern, replacement] of PATTERNS) {
      if (pattern.test(result)) result = result.replace(pattern, replacement);
    }
    return result;
  }

  const ATTRIBUTES = ["placeholder", "title", "aria-label", "content"];

  // Static markup: text nodes and labelling attributes whose whole text has an entry.
  function translateTree(root) {
    if (lang !== "en") return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.nodeValue.replace(/\s+/g, " ").trim();
      if (!text || !EN[text]) continue;
      const [lead] = node.nodeValue.match(/^\s*/);
      const [trail] = node.nodeValue.match(/\s*$/);
      node.nodeValue = `${lead}${EN[text]}${trail}`;
    }
    for (const node of root.querySelectorAll(ATTRIBUTES.map((name) => `[${name}]`).join(","))) {
      for (const name of ATTRIBUTES) {
        const value = node.getAttribute(name);
        if (value && EN[value]) node.setAttribute(name, EN[value]);
      }
    }
  }

  function setLanguage(next) {
    if (next === lang) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: the choice lasts until the page reloads */
    }
    location.reload();
  }

  // Deferred scripts run after parsing, so the markup (and its templates) is already here.
  translateTree(document);
  for (const template of document.querySelectorAll("template")) translateTree(template.content);

  return { lang, locale, t, tm, translateTree, setLanguage };
})();

const { t, tm } = I18N;
