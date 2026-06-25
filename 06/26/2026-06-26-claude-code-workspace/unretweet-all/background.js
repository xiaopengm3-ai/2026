chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "start") {
    chrome.storage.local.set({ unretweetEnabled: true }, () => sendResponse({ status: "Started" }));
    return true;
  }
  if (message.action === "stop") {
    chrome.storage.local.set({ unretweetEnabled: false }, () => sendResponse({ status: "Stopped" }));
    return true;
  }
  return true;
});
