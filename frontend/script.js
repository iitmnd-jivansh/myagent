const messagesDiv = document.getElementById("messages");
const input = document.getElementById("messageInput");

function addMessage(text, type) {

  const div = document.createElement("div");

  div.className = `message ${type}`;

  div.textContent = text;

  messagesDiv.appendChild(div);

  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  return div;
}

async function sendMessage() {

  const message = input.value.trim();

  if (!message) return;

  addMessage(message, "user");

  input.value = "";

  const typing = addMessage("AI is thinking...", "ai typing");

  try {

    const response = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: message
      })
    });

    const data = await response.json();

    typing.remove();

    addMessage(data.response, "ai");

  } catch (error) {

    typing.remove();

    addMessage(
      "Error connecting to backend. Make sure FastAPI is running.",
      "ai"
    );

    console.error(error);
  }
}

input.addEventListener("keydown", function(event) {

  if (event.key === "Enter") {
    sendMessage();
  }
});
