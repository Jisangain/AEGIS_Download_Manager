// Aegis Download Manager - Extension Service Worker
// Communicates with com.aegis.downloadmanager Native Messaging Host

const HOST_NAME = "com.aegis.downloadmanager";

chrome.runtime.onInstalled.addListener(() => {
  // Context menus
  chrome.contextMenus.create({
    id: "aegis-download-link",
    title: "Download with Aegis",
    contexts: ["link"]
  });

  chrome.contextMenus.create({
    id: "aegis-download-media",
    title: "Download Media with Aegis",
    contexts: ["image", "video", "audio"]
  });

  chrome.contextMenus.create({
    id: "aegis-download-page",
    title: "Download Page / Video with Aegis",
    contexts: ["page"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  let targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
  if (!targetUrl) return;

  sendToAegis({
    action: "download",
    url: targetUrl,
    page_url: tab ? tab.url : "",
    page_title: tab ? tab.title : ""
  });
});

// Optional: Intercept browser download requests if enabled
chrome.downloads.onCreated.addListener(async (downloadItem) => {
  const settings = await chrome.storage.local.get({ interceptDownloads: false });
  if (settings.interceptDownloads && downloadItem.url && !downloadItem.url.startsWith("blob:")) {
    // Cancel browser download and forward to Aegis
    chrome.downloads.cancel(downloadItem.id, () => {
      sendToAegis({
        action: "download",
        url: downloadItem.url,
        filename: downloadItem.filename || "",
        referrer: downloadItem.referrer || ""
      });
    });
  }
});

function sendToAegis(payload) {
  try {
    chrome.runtime.sendNativeMessage(HOST_NAME, payload, (response) => {
      if (chrome.runtime.lastError) {
        console.warn("Aegis Native Host communication failed:", chrome.runtime.lastError.message);
      } else {
        console.log("Aegis response:", response);
      }
    });
  } catch (err) {
    console.error("Error sending to Aegis:", err);
  }
}
