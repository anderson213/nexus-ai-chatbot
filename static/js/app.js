const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const sendButton = document.getElementById("sendButton");
const sidebar = document.getElementById("sidebar");
const mobileMenu = document.getElementById("mobileMenu");
const history = [];
let activeRequest = null;

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

function addMessage(role, text, state = "") {
  welcome.hidden = true;
  messages.classList.add("visible");

  const isUser = role === "user";
  const item = document.createElement("article");
  item.className = `message ${isUser ? "user" : "assistant"}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = isUser ? "V" : "N";

  const body = document.createElement("div");
  body.className = "message-body";
  const name = document.createElement("div");
  name.className = "message-name";
  name.textContent = isUser ? "Você" : "Nexus AI";

  const content = document.createElement("div");
  content.className = "message-text";
  content.textContent = text;
  if (state) content.classList.add(state);

  body.append(name, content);
  if (state === "typing-status") {
    const dots = document.createElement("div");
    dots.className = "typing";
    dots.setAttribute("aria-hidden", "true");
    dots.append(...Array.from({length: 3}, () => document.createElement("span")));
    body.appendChild(dots);
  }
  item.append(avatar, body);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || activeRequest) return;

  const controller = new AbortController();
  activeRequest = controller;
  const timeout = setTimeout(() => controller.abort(), 60_000);
  sendButton.disabled = true;
  addMessage("user", message);
  input.value = "";
  resizeInput();
  const typing = addMessage("assistant", "Digitando…", "typing-status");

  try {
    const response = await fetch(form.dataset.chatUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message, history}),
      signal: controller.signal,
    });
    const data = response.headers.get("content-type")?.includes("application/json")
      ? await response.json()
      : null;
    if (activeRequest !== controller) return;

    typing.remove();
    if (!response.ok) {
      addMessage("assistant", data?.error || "O chat está indisponível no momento.", "error");
      return;
    }
    if (typeof data?.reply !== "string" || !data.reply.trim()) {
      addMessage("assistant", "O servidor retornou uma resposta inválida.", "error");
      return;
    }

    addMessage("assistant", data.reply);
    const contextReply = Array.from(data.reply).slice(0, 4000).join("");
    history.push({role: "user", text: message}, {role: "model", text: contextReply});
    if (history.length > 12) history.splice(0, 2);
  } catch {
    if (activeRequest !== controller) return;
    typing.remove();
    const error = controller.signal.aborted
      ? "A resposta demorou demais. Tente novamente."
      : "Não foi possível receber a resposta. Tente novamente.";
    addMessage("assistant", error, "error");
  } finally {
    clearTimeout(timeout);
    if (activeRequest === controller) {
      activeRequest = null;
      sendButton.disabled = false;
    }
  }
}

function setMobileMenu(open) {
  sidebar.classList.toggle("open", open);
  mobileMenu.setAttribute("aria-expanded", String(open));
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});
input.addEventListener("input", resizeInput);
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll(".suggestion").forEach(button => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});
document.getElementById("newChat").addEventListener("click", () => {
  activeRequest?.abort();
  activeRequest = null;
  sendButton.disabled = false;
  history.length = 0;
  messages.replaceChildren();
  messages.classList.remove("visible");
  welcome.hidden = false;
  input.value = "";
  resizeInput();
  setMobileMenu(false);
  input.focus();
});
mobileMenu.addEventListener("click", () => setMobileMenu(!sidebar.classList.contains("open")));

fetch(form.dataset.statusUrl, {signal: AbortSignal.timeout(10_000)})
  .then(response => {
    if (!response.ok) throw new Error();
    return response.json();
  })
  .then(data => {
    const dot = document.getElementById("statusDot");
    const label = document.getElementById("statusText");
    dot.classList.toggle("online", data.configured);
    dot.classList.toggle("offline", !data.configured);
    label.textContent = data.configured ? "Chave de IA configurada" : "Chave de IA pendente";
  })
  .catch(() => {
    document.getElementById("statusText").textContent = "Status indisponível";
    document.getElementById("statusDot").classList.add("offline");
  });
