// Aegis Download Manager - Extension Service Worker & Stream Sniffer
// Communicates with com.aegis.downloadmanager Native Messaging Host

const HOST_NAME = "com.aegis.downloadmanager";

// Context menus setup
chrome.runtime.onInstalled.addListener(() => {
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

// Listener for messages from DOM content script (floating video download button)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request && request.action === "download") {
    try {
      chrome.runtime.sendNativeMessage(HOST_NAME, request, (response) => {
        if (chrome.runtime.lastError) {
          console.warn("Aegis Native Host communication failed:", chrome.runtime.lastError.message);
          sendResponse({ status: "error", error: chrome.runtime.lastError.message });
        } else {
          console.log("Aegis response:", response);
          sendResponse({ status: "ok", response: response });
        }
      });
    } catch (err) {
      console.error("Error sending to Aegis:", err);
      sendResponse({ status: "error", error: err.message });
    }
    return true; // Keep channel open for async response
  }
});

// Stream Sniffing via WebRequest
const MEDIA_EXTS = [".mp4", ".m4v", ".webm", ".m3u8", ".mpd", ".flv", ".ts", ".m4s", "videoplayback"];

if (chrome.webRequest && chrome.webRequest.onResponseStarted) {
  chrome.webRequest.onResponseStarted.addListener(
    (details) => {
      if (details.tabId < 0 || !details.url) return;
      const urlLower = details.url.toLowerCase();

      let detectedExt = "";
      for (const ext of MEDIA_EXTS) {
        if (urlLower.includes(ext)) {
          detectedExt = ext.replace(".", "");
          break;
        }
      }

      // Check content-type header
      if (!detectedExt && details.responseHeaders) {
        const ctHeader = details.responseHeaders.find(h => h.name.toLowerCase() === "content-type");
        if (ctHeader && ctHeader.value) {
          const val = ctHeader.value.toLowerCase();
          if (val.includes("video/mp4")) detectedExt = "mp4";
          else if (val.includes("video/webm")) detectedExt = "webm";
          else if (val.includes("mpegurl") || val.includes("m3u8")) detectedExt = "m3u8";
          else if (val.includes("dash+xml")) detectedExt = "mpd";
        }
      }

      if (detectedExt) {
        try {
          chrome.tabs.sendMessage(details.tabId, {
            type: "AEGIS_STREAM_DETECTED",
            url: details.url,
            ext: detectedExt
          }).catch(() => {});
        } catch (e) {}
      }
    },
    { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other"] },
    ["responseHeaders"]
  );
}

// Intercept browser download requests if enabled
if (chrome.downloads && chrome.downloads.onCreated) {
  chrome.downloads.onCreated.addListener(async (downloadItem) => {
    const settings = await chrome.storage.local.get({ interceptDownloads: false });
    if (settings.interceptDownloads && downloadItem.url && !downloadItem.url.startsWith("blob:")) {
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
}

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
