# Nexus AI

Nexus AI é um protótipo acadêmico de chatbot para estudos, escrita e exploração de ideias. O Flask serve a interface e envia as mensagens à Gemini API. O navegador recebe apenas a resposta em texto e mantém até seis pares de mensagens como contexto na conversa atual. O projeto usa Python 3.12, Flask, Google Gen AI SDK, HTML, CSS e JavaScript. Em produção, é servido pelo Gunicorn.

## Estrutura

```text
nexus_ai/
├── app.py                  # Página, rotas da API e integração Gemini
├── requirements.txt        # Dependências Python fixadas
├── render.yaml             # Blueprint de hospedagem no Render
├── .env.example            # Variáveis de ambiente de exemplo
├── .gitignore
├── README.md
├── templates/index.html
└── static/
    ├── css/                # style.css e chat.css
    └── js/app.js
```

## Executar localmente

Instale Python 3.12. Crie uma chave da Gemini API no [Google AI Studio](https://aistudio.google.com/apikey). No terminal, entre na pasta que contém `app.py`.

**macOS ou Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e preencha `GEMINI_API_KEY` com a chave real. No macOS ou Linux, execute `python app.py`. No Windows, execute `.\.venv\Scripts\python.exe app.py`. Abra [http://127.0.0.1:5000](http://127.0.0.1:5000) e envie uma mensagem. O servidor de desenvolvimento do Flask funciona nos três sistemas. O Gunicorn é usado no Render.

| Variável | Uso |
| --- | --- |
| `GEMINI_API_KEY` | Obrigatória para gerar respostas. O Flask lê a chave no servidor. |
| `GEMINI_MODEL` | Opcional. Padrão `gemini-3.5-flash-lite`. Use um modelo de texto disponível no seu projeto Google. |
| `CHAT_RATE_LIMIT` | Opcional. Padrão `20 per minute; 300 per day`, compartilhado por todos os visitantes da instância. |
| `PORT` | Opcional localmente, com padrão `5000`. O Render fornece a porta ao Gunicorn. |

Variáveis definidas no ambiente têm prioridade sobre `.env`. Mantenha a chave apenas no ambiente local ou nos segredos da hospedagem. Versione `.env.example` com o valor de exemplo.

## Publicar no Render

1. Envie o conteúdo de `nexus_ai/` para a raiz de um repositório no GitHub. Inclua os arquivos ocultos `.env.example` e `.gitignore`.
2. No painel do Render, escolha **New → Blueprint** e conecte o repositório. O Render lê `render.yaml` e solicita o valor de `GEMINI_API_KEY`.
3. Se precisar substituir o modelo ou os limites, defina `GEMINI_MODEL` ou `CHAT_RATE_LIMIT` em **Environment** no serviço.
4. Concluído o deploy, abra a URL HTTPS do serviço e envie uma mensagem para validar a integração com a conta Google.

O Render instala as dependências com `python -m pip install -r requirements.txt` e inicia o Gunicorn usando a variável `PORT`. O plano gratuito pode demorar no primeiro acesso após um período de inatividade.

## API e limites do protótipo

- `GET /` abre a interface. A interface e a API compartilham a mesma origem.
- `GET /api/status` retorna o modelo selecionado e indica se há uma chave configurada. O Render usa a rota para verificar se o servidor consegue responder.
- `POST /api/chat` aceita um objeto JSON com `message` e um `history` opcional. O histórico contém até seis pares alternados, no formato `{"role":"user","text":"..."}` e `{"role":"model","text":"..."}`. Cada texto tem limite de 4.000 caracteres. A resposta é `{"reply":"..."}` ou `{"error":"..."}`, com o status HTTP correspondente.

```bash
curl http://127.0.0.1:5000/api/chat \
  -H 'Content-Type: application/json' \
  --data '{"message":"Explique o que é uma API em duas frases."}'
```

A validação da chave, do modelo e da cota ocorre durante a geração de uma resposta. O chat público usa um limite global em memória. Ele é compartilhado pelos quatro threads do único worker configurado no Render e reiniciado quando o processo reinicia. Com múltiplos workers ou réplicas, cada processo teria sua própria cota. A interface envia o contexto recente ao Gemini a cada chamada. A aplicação não persiste o histórico.
