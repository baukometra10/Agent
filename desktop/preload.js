const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("spixaDesktop", {
  product: "Spixa",
  company: "Suppix AI",
  isDesktop: true,
  platform: process.platform,
  pickFolder: () => ipcRenderer.invoke("spixa:pick-folder"),
});
