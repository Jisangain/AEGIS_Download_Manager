const status = document.getElementById("status");
const button = document.getElementById("check");

button.addEventListener("click", () => {
  button.disabled = true;
  status.className = "";
  status.textContent = "Checking native host…";
  chrome.runtime.sendMessage({ action: "check-connection" }, (result) => {
    const runtimeError = chrome.runtime.lastError;
    button.disabled = false;
    if (runtimeError || !result || result.status !== "ok") {
      status.className = "error";
      status.textContent = runtimeError?.message || result?.error || "Connection check failed.";
      return;
    }
    status.className = "ok";
    status.textContent = "Connected. The browser can reach the Aegis native host.";
  });
});
