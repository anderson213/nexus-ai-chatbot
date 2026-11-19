import os
from pathlib import Path

import httpx2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from google import genai
from google.genai import errors, types
from werkzeug.exceptions import HTTPException

load_dotenv(Path(__file__).with_name(".env"), override=False)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 640 * 1024

MODEL_NAME = os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_ITEMS = 12
SYSTEM_INSTRUCTION = """
Você é Nexus, um assistente de inteligência artificial educado, claro e útil.
Responda em português do Brasil por padrão, a menos que a pessoa peça outro idioma.
Explique assuntos com linguagem acessível e admita quando não souber algo.
Não invente fontes, fatos ou capacidades. Use texto simples e listas quando necessário.
"""

limiter = Limiter(
    key_func=lambda: "chat",
    app=app,
    storage_uri="memory://",
    strategy="moving-window",
    headers_enabled=True,
)


def get_api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return "" if key == "sua_chave_aqui" else key


def valid_text(value):
    return (
        isinstance(value, str)
        and len(value) <= MAX_MESSAGE_LENGTH
        and bool(value.strip())
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
    )


@app.after_request
def set_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(HTTPException)
def handle_http_error(error):
    if not request.path.startswith("/api/"):
        return error

    messages = {
        400: "A requisição contém JSON inválido.",
        404: "Rota de API não encontrada.",
        405: "Método HTTP não permitido.",
        413: "A requisição excede 640 KiB.",
        415: "Envie a requisição como application/json.",
        429: "O chat atingiu o limite de solicitações. Tente novamente mais tarde.",
    }
    response = error.get_response()
    response.set_data(app.json.dumps({"error": messages.get(error.code, "Falha na requisição.")}))
    response.mimetype = "application/json"
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(configured=bool(get_api_key()), model=MODEL_NAME)


@app.post("/api/chat")
@limiter.limit(os.getenv("CHAT_RATE_LIMIT", "20 per minute; 300 per day"))
def chat():
    try:
        data = request.get_json()
    except RecursionError:
        return jsonify(error="A requisição contém JSON aninhado demais."), 400
    if not isinstance(data, dict):
        return jsonify(error="Envie um objeto JSON com o campo message."), 400

    message = data.get("message")
    if not valid_text(message):
        return jsonify(error="Envie uma mensagem de texto com até 4.000 caracteres."), 400

    history = data.get("history", [])
    if (
        not isinstance(history, list)
        or len(history) > MAX_HISTORY_ITEMS
        or len(history) % 2 != 0
    ):
        return jsonify(error="Envie até seis pares de mensagens no histórico."), 400

    contents = []
    for index, item in enumerate(history):
        expected_role = "model" if index % 2 else "user"
        if (
            not isinstance(item, dict)
            or item.get("role") != expected_role
            or not valid_text(item.get("text"))
        ):
            return jsonify(error="O histórico deve alternar mensagens de usuário e da IA."), 400
        contents.append(
            types.Content(
                role=expected_role,
                parts=[types.Part.from_text(text=item["text"].strip())],
            )
        )

    api_key = get_api_key()
    if not api_key:
        return jsonify(error="O chat está indisponível. Configure GEMINI_API_KEY no servidor."), 503

    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message.strip())])
    )

    try:
        with genai.Client(
            api_key=api_key,
            vertexai=False,
            http_options=types.HttpOptions(
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ) as client:
            result = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    max_output_tokens=2048,
                ),
            )
        answer = (result.text or "").strip()
    except httpx2.TimeoutException:
        return jsonify(error="A IA demorou para responder. Tente novamente."), 504
    except errors.APIError as error:
        app.logger.warning("A API Gemini retornou HTTP %s.", error.code)
        if error.code == 429:
            return jsonify(error="A cota do serviço de IA foi atingida. Tente mais tarde."), 429
        if error.code == 504:
            return jsonify(error="A IA demorou para responder. Tente novamente."), 504
        return jsonify(error="Não foi possível obter uma resposta da IA agora."), 502
    except Exception as error:
        app.logger.error("Falha ao consultar Gemini (%s).", type(error).__name__)
        return jsonify(error="Não foi possível obter uma resposta da IA agora."), 502

    if not answer:
        return jsonify(error="A IA não retornou texto. Tente reformular sua mensagem."), 502
    return jsonify(reply=answer)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
