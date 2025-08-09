import wx
import wx.adv
import os
import os.path as osp
import subprocess
import sys
import configparser
import tempfile
import time
import uuid

# --- 追加: HiDPI 対応 (Per-Monitor v2 優先) ---
def _enable_hi_dpi():
    try:
        import ctypes  # noqa: F401
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2 (-4)
    except Exception:
        try:
            import ctypes  # noqa: F401
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE (2)
        except Exception:
            try:
                import ctypes  # noqa: F401
                ctypes.windll.user32.SetProcessDPIAware()  # Legacy API
            except Exception:
                pass
# --- ここまで ---

# 既存の設定ローダーを再利用
from dataclass import KindleSSConfig, read_config  # type: ignore

APP_NAME = "Kindless"
SECTION = "KINDLESS"

def ini_default_path() -> str:
    # 初回はカレント配下に kindless.ini を作る
    return osp.abspath("kindless.ini")

def ensure_ini_exists(path: str) -> None:
    if osp.exists(path):
        return
    # 最小限のキーだけを書いたシンプルINIを作成
    cfg = KindleSSConfig()
    config = configparser.ConfigParser()
    config[SECTION] = {
        "window_title": cfg.window_title,
        "execute_filename": cfg.execute_filename,
        "nextpage_key": cfg.nextpage_key,
        "fullscreen_key": cfg.fullscreen_key,
        "pagejump_key": " + ".join(cfg.pagejump_key),
        "pagejump": cfg.pagejump,
        "base_save_folder": cfg.base_save_folder,
        "overwrite": str(cfg.overwrite),
        "trim_after_capture": str(cfg.trim_after_capture),
        "force_move_first_page": str(cfg.force_move_first_page),
        "auto_title": str(cfg.auto_title),
        "file_extension": (cfg.file_extension[1:] if cfg.file_extension.startswith(".") else cfg.file_extension),
    }
    with open(path, "w", encoding="utf-8") as f:
        config.write(f)

class Collapsible(wx.Panel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.toggle = wx.ToggleButton(self, label=f"▼ {title}")
        self.body = wx.Panel(self)
        self.body_sizer = wx.BoxSizer(wx.VERTICAL)
        self.body.SetSizer(self.body_sizer)
        self.sizer.Add(self.toggle, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 6)
        self.sizer.Add(self.body, 0, wx.EXPAND|wx.ALL, 0)
        self.SetSizer(self.sizer)
        self.toggle.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)
        self.body.Hide()

    def on_toggle(self, evt):
        if self.toggle.GetValue():
            self.toggle.SetLabel(self.toggle.GetLabel().replace("▼", "▲"))
            self.body.Show()
        else:
            self.toggle.SetLabel(self.toggle.GetLabel().replace("▲", "▼"))
            self.body.Hide()
        self.GetParent().Layout()

class MainFrame(wx.Frame):
    def __init__(self, parent=None, title="Kindless UI"):
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER))
        self.SetInitialSize(self.FromDIP(wx.Size(640, 520)))
        panel = wx.Panel(self)

        # 配色
        bg = wx.Colour(30, 33, 36)
        fg = wx.Colour(235, 235, 235)
        panel.SetBackgroundColour(bg)
        self.SetBackgroundColour(bg)
        self.SetForegroundColour(fg)

        s = wx.BoxSizer(wx.VERTICAL)

        # INI 読み込み
        self.ini_path = ini_default_path()
        ensure_ini_exists(self.ini_path)
        self.cfg = read_config(KindleSSConfig(), self.ini_path)

        # 保存先
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(wx.StaticText(panel, label="保存先フォルダ"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.dir_picker = wx.DirPickerCtrl(panel, path=self.cfg.base_save_folder, style=wx.DIRP_USE_TEXTCTRL)
        self.dir_picker.SetBackgroundColour(bg); self.dir_picker.SetForegroundColour(fg)
        row1.Add(self.dir_picker, 1, wx.EXPAND)
        s.Add(row1, 0, wx.EXPAND | wx.ALL, self.FromDIP(10))

        # トグル
        toggles = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_trim = wx.CheckBox(panel, label="キャプチャ後にトリミング"); self.chk_trim.SetValue(self.cfg.trim_after_capture)
        self.chk_overwrite = wx.CheckBox(panel, label="既存フォルダを上書き"); self.chk_overwrite.SetValue(self.cfg.overwrite)
        self.chk_auto_title = wx.CheckBox(panel, label="タイトル自動取得"); self.chk_auto_title.SetValue(self.cfg.auto_title)
        self.chk_force_first = wx.CheckBox(panel, label="開始前に1ページ目へ移動"); self.chk_force_first.SetValue(self.cfg.force_move_first_page)
        for w in (self.chk_trim, self.chk_overwrite, self.chk_auto_title, self.chk_force_first):
            w.SetForegroundColour(fg)
            toggles.Add(w, 0, wx.RIGHT, 12)
        s.Add(toggles, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(10))

        # 基本設定行
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(panel, label="保存形式"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        opts = ["png", "jpg", "webp"]
        curr = self.cfg.file_extension[1:] if self.cfg.file_extension.startswith('.') else self.cfg.file_extension
        if curr not in opts:
            opts.insert(0, curr)
        self.cmb_ext = wx.ComboBox(panel, value=curr, choices=opts, style=wx.CB_READONLY)
        row2.Add(self.cmb_ext, 0, wx.RIGHT, 16)
        row2.Add(wx.StaticText(panel, label="Kindle実行ファイル名"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(8))
        self.txt_exec = wx.TextCtrl(panel, value=self.cfg.execute_filename, size=self.FromDIP(wx.Size(140, -1)))
        row2.Add(self.txt_exec, 0, wx.RIGHT, 16)
        row2.Add(wx.StaticText(panel, label="Kindleウィンドウタイトル"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(8))
        self.txt_title = wx.TextCtrl(panel, value=self.cfg.window_title, size=self.FromDIP(wx.Size(120, -1)))
        row2.Add(self.txt_title, 0)
        s.Add(row2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, self.FromDIP(10))

        # ログ + ゲージ
        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log.SetBackgroundColour(wx.Colour(25, 27, 30))
        self.log.SetForegroundColour(fg)
        self.log.SetMinSize(self.FromDIP(wx.Size(-1, 140)))
        self.gauge = wx.Gauge(panel, range=100)
        s.Add(self.log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(10))
        s.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(10))

        # 詳細設定
        adv = Collapsible(panel, "詳細設定")
        adv.body.SetBackgroundColour(bg); adv.body.SetForegroundColour(fg)
        g = wx.FlexGridSizer(2, 4, 8, 8)
        g.AddGrowableCol(1, 1); g.AddGrowableCol(3, 1)
        self.txt_next = wx.TextCtrl(adv.body, value=self.cfg.nextpage_key)
        self.txt_full = wx.TextCtrl(adv.body, value=self.cfg.fullscreen_key)
        self.txt_pgkey = wx.TextCtrl(adv.body, value=" + ".join(self.cfg.pagejump_key))
        self.txt_pg = wx.TextCtrl(adv.body, value=self.cfg.pagejump)
        for w in (self.txt_next, self.txt_full, self.txt_pgkey, self.txt_pg):
            w.SetBackgroundColour(wx.Colour(45, 49, 53)); w.SetForegroundColour(fg)
        g.Add(wx.StaticText(adv.body, label="次ページキー"), 0, wx.ALIGN_CENTER_VERTICAL); g.Add(self.txt_next, 1, wx.EXPAND)
        g.Add(wx.StaticText(adv.body, label="全画面化キー"), 0, wx.ALIGN_CENTER_VERTICAL); g.Add(self.txt_full, 1, wx.EXPAND)
        g.Add(wx.StaticText(adv.body, label="ページ移動キー"), 0, wx.ALIGN_CENTER_VERTICAL); g.Add(self.txt_pgkey, 1, wx.EXPAND)
        g.Add(wx.StaticText(adv.body, label="開始ページ"), 0, wx.ALIGN_CENTER_VERTICAL); g.Add(self.txt_pg, 1, wx.EXPAND)
        adv.body_sizer.Add(g, 0, wx.EXPAND | wx.ALL, 4)
        s.Add(adv, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, self.FromDIP(10))

        # ボタン
        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save = wx.Button(panel, label="設定を保存")
        self.btn_start = wx.Button(panel, label="キャプチャ開始")
        self.btn_stop = wx.Button(panel, label="中止")
        self.btn_exit = wx.Button(panel, label="閉じる")
        for b in (self.btn_save, self.btn_start, self.btn_stop, self.btn_exit):
            btns.Add(b, 0, wx.RIGHT, 8)
        s.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, self.FromDIP(10))

        panel.SetSizer(s)

        # 実行管理
        self.proc = None  # type: ignore
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_tick, self.timer)
        self.status_path = None  # type: ignore
        self.stop_path = None  # type: ignore
        self._last_size = 0

        # イベント
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start)
        self.btn_stop.Bind(wx.EVT_BUTTON, self.on_stop)
        self.btn_exit.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        self.btn_stop.Enable(False)

        self.Centre()

    def collect_to_config(self) -> configparser.ConfigParser:
        cfg = configparser.ConfigParser()
        ext = self.cmb_ext.GetValue()
        if ext.startswith("."):
            ext = ext[1:]
        cfg[SECTION] = {
            "window_title": self.txt_title.GetValue().strip() or "Kindle",
            "execute_filename": self.txt_exec.GetValue().strip() or "KINDLE.EXE",
            "nextpage_key": self.txt_next.GetValue().strip() or "left",
            "fullscreen_key": self.txt_full.GetValue().strip() or "f11",
            "pagejump_key": self.txt_pgkey.GetValue().strip() or "ctrl + g",
            "pagejump": self.txt_pg.GetValue().strip() or "1",
            "base_save_folder": self.dir_picker.GetPath(),
            "overwrite": str(self.chk_overwrite.GetValue()),
            "trim_after_capture": str(self.chk_trim.GetValue()),
            "force_move_first_page": str(self.chk_force_first.GetValue()),
            "auto_title": str(self.chk_auto_title.GetValue()),
            "file_extension": ext
        }
        return cfg

    def on_save(self, evt):
        cfg = self.collect_to_config()
        with open(self.ini_path, "w", encoding="utf-8") as f:
            cfg.write(f)
        wx.MessageBox("設定を保存しました。", APP_NAME, wx.OK|wx.ICON_INFORMATION)

    def on_start(self, evt):
        # 保存してから起動
        self.on_save(evt)
        # ステータスファイル準備
        uid = uuid.uuid4().hex
        self.status_path = osp.join(tempfile.gettempdir(), f"kindless_status_{uid}.log")
        self.stop_path = osp.join(tempfile.gettempdir(), f"kindless_stop_{uid}.flag")
        try:
            if osp.exists(self.status_path):
                os.remove(self.status_path)
        except Exception:
            pass
        try:
            if self.stop_path and osp.exists(self.stop_path):
                os.remove(self.stop_path)
        except Exception:
            pass

        here = osp.dirname(osp.abspath(__file__))
        exe = osp.join(here, "Kindless.exe")
        if osp.exists(exe):
            cmd = [exe, self.ini_path, "--status-file", self.status_path, "--stop-file", self.stop_path]
            creationflags = 0
        else:
            py = sys.executable
            target = osp.join(here, "kindless.py")
            cmd = [py, target, self.ini_path, "--status-file", self.status_path, "--stop-file", self.stop_path]
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        try:
            self.proc = subprocess.Popen(cmd, creationflags=creationflags)
            self.append_log("開始: ステータスを表示します。")
            self.timer.Start(300)
            self.Iconize(True)
            self.btn_start.Enable(False)
            self.btn_stop.Enable(True)
        except Exception as e:
            wx.MessageBox(f"起動に失敗しました: {e}", APP_NAME, wx.OK|wx.ICON_ERROR)

    def append_log(self, text: str):
        if not text:
            return
        self.log.AppendText(text.rstrip() + "\n")

    def on_tick(self, evt):
        self.gauge.Pulse()
        if self.status_path and osp.exists(self.status_path):
            try:
                sz = osp.getsize(self.status_path)
                if sz > self._last_size:
                    with open(self.status_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(self._last_size)
                        chunk = f.read()
                        self._last_size = sz
                    for line in chunk.splitlines():
                        self.append_log(line)
                        if line.strip() == "DONE":
                            self.on_done()
                            return
                        if line.startswith("ERROR"):
                            self.on_error(line)
                            return
            except Exception:
                pass
        if self.proc and (self.proc.poll() is not None):
            code = self.proc.returncode or 0
            if code == 0:
                self.on_done()
            else:
                self.on_error(f"ERROR: PROCESS_EXIT_CODE {code}")

    def on_done(self):
        self.timer.Stop()
        note = wx.adv.NotificationMessage(APP_NAME, "完了しました")
        try:
            note.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
        except Exception:
            pass
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        wx.MessageBox("完了しました", APP_NAME, wx.OK|wx.ICON_INFORMATION)
        self.btn_start.Enable(True)
        self.btn_stop.Enable(False)

    def on_error(self, msg: str):
        self.timer.Stop()
        self.append_log(msg)
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        wx.MessageBox(f"エラーで終了しました:\n{msg}", APP_NAME, wx.OK|wx.ICON_ERROR)
        self.btn_start.Enable(True)
        self.btn_stop.Enable(False)

    def on_stop(self, evt):
        # stop-file を作成して穏当な停止を要求
        try:
            if self.stop_path:
                open(self.stop_path, "w").close()
        except Exception:
            pass
        # 最大2秒待機
        deadline = time.time() + 2.0
        while self.proc and (self.proc.poll() is None) and time.time() < deadline:
            time.sleep(0.1)
        # まだ生きていれば terminate
        if self.proc and (self.proc.poll() is None):
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.append_log("中止要求を送信しました。")
        self.btn_start.Enable(True)
        self.btn_stop.Enable(False)

class App(wx.App):
    def OnInit(self):
        self.SetAppName(APP_NAME)
        f = MainFrame(title="Kindless 設定と起動")
        f.Show()
        return True

if __name__ == "__main__":
    _enable_hi_dpi()
    app = App(False)
    app.MainLoop()
