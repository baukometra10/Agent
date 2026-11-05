/**
 * Spixa Desktop — Electron shell for the Spixa web IDE.
 */
const { app, BrowserWindow, shell, Menu, dialog, ipcMain } = require("electron");
const path = require("path");

const SPIXA_BASE =
  process.env.SPIXA_URL?.replace(/\/ide\/?$/, "") ||
  process.env.EVOLVE_URL?.replace(/\/ide\/?$/, "") ||
  "http://localhost:3000";
const SPIXA_IDE = `${SPIXA_BASE.replace(/\/$/, "")}/ide`;

function createWindow() {
  const win = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 960,
    minHeight: 640,
    title: "Spixa · Suppix AI",
    backgroundColor: "#0b1220",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadURL(SPIXA_IDE);

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  async function openFolderIntoIde() {
    const result = await dialog.showOpenDialog(win, {
      properties: ["openDirectory"],
      title: "Spixa — فتح مجلد",
    });
    if (result.canceled || !result.filePaths[0]) return;
    const folder = result.filePaths[0];
    const url = `${SPIXA_IDE}?open=${encodeURIComponent(folder)}`;
    win.loadURL(url);
  }

  ipcMain.removeHandler("spixa:pick-folder");
  ipcMain.handle("spixa:pick-folder", async () => {
    const result = await dialog.showOpenDialog(win, {
      properties: ["openDirectory"],
      title: "Spixa — فتح مجلد",
    });
    if (result.canceled || !result.filePaths[0]) return null;
    return result.filePaths[0];
  });

  const template = [
    {
      label: "Spixa",
      submenu: [
        { label: "مساحة العمل (IDE)", click: () => win.loadURL(SPIXA_IDE) },
        { label: "فتح مجلد…", accelerator: "CmdOrCtrl+O", click: () => void openFolderIntoIde() },
        { type: "separator" },
        {
          label: "الحساب والاستخدام",
          click: () => win.loadURL(`${SPIXA_BASE}/console`),
        },
        { label: "الخطط", click: () => win.loadURL(`${SPIXA_BASE}/pricing`) },
        { label: "تنزيل / تحديث", click: () => win.loadURL(`${SPIXA_BASE}/download`) },
        { type: "separator" },
        { role: "reload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "quit", label: "خروج" },
      ],
    },
    {
      label: "تحرير",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
