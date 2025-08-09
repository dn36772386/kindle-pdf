import wx
import os
import os.path as osp
import subprocess
import sys
import configparser

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
        # 初期サイズを論理DIPで指定
        self.SetInitialSize(self.FromDIP(wx.Size(560, 420)))
        panel = wx.Panel(self)

        # 全体配色を控えめダーク寄りに
        bg = wx.Colour(30, 33, 36)
        fg = wx.Colour(235, 235, 235)
        panel.SetBackgroundColour(bg)
        self.SetBackgroundColour(bg)
        self.SetForegroundColour(fg)

        font = panel.GetFont()
        font.MakeSmaller()
        panel.SetFont(font)

        s = wx.BoxSizer(wx.VERTICAL)

        # INI パス
        self.ini_path = ini_default_path()
        ensure_ini_exists(self.ini_path)

        # 設定読み込み
        self.cfg = read_config(KindleSSConfig(), self.ini_path)

        # 保存先
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(wx.StaticText(panel, label="保存先フォルダ"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 8)
        self.dir_picker = wx.DirPickerCtrl(panel, path=self.cfg.base_save_folder, style=wx.DIRP_USE_TEXTCTRL)
        self.dir_picker.SetBackgroundColour(bg); self.dir_picker.SetForegroundColour(fg)
        row1.Add(self.dir_picker, 1, wx.EXPAND)
        s.Add(row1, 0, wx.EXPAND|wx.ALL, self.FromDIP(10))

        # トグル群
        toggles = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_trim = wx.CheckBox(panel, label="キャプチャ後にトリミング")
        self.chk_trim.SetValue(self.cfg.trim_after_capture)
        self.chk_overwrite = wx.CheckBox(panel, label="既存フォルダを上書き")
        self.chk_overwrite.SetValue(self.cfg.overwrite)
        self.chk_auto_title = wx.CheckBox(panel, label="タイトル自動取得")
        self.chk_auto_title.SetValue(self.cfg.auto_title)
        self.chk_force_first = wx.CheckBox(panel, label="開始前に1ページ目へ移動")
        self.chk_force_first.SetValue(self.cfg.force_move_first_page)
        for w in (self.chk_trim, self.chk_overwrite, self.chk_auto_title, self.chk_force_first):
            w.SetForegroundColour(fg)
            toggles.Add(w, 0, wx.RIGHT, 12)
        s.Add(toggles, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, self.FromDIP(10))

        # 拡張子
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(panel, label="保存形式"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 8)
        opts = ["png", "jpg", "webp"]
        curr = self.cfg.file_extension[1:] if self.cfg.file_extension.startswith(".") else self.cfg.file_extension
        if curr not in opts:
            opts.insert(0, curr)
        self.cmb_ext = wx.ComboBox(panel, value=curr, choices=opts, style=wx.CB_READONLY)
        row2.Add(self.cmb_ext, 0, wx.RIGHT, 16)

        # 実行ファイル名・ウィンドウタイトル
        row2.Add(wx.StaticText(panel, label="Kindle実行ファイル名"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, self.FromDIP(8))
        self.txt_exec = wx.TextCtrl(panel, value=self.cfg.execute_filename, size=self.FromDIP(wx.Size(140, -1)))
        row2.Add(self.txt_exec, 0, wx.RIGHT, 16)
        row2.Add(wx.StaticText(panel, label="Kindleウィンドウタイトル"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, self.FromDIP(8))
        self.txt_title = wx.TextCtrl(panel, value=self.cfg.window_title, size=self.FromDIP(wx.Size(120, -1)))
        row2.Add(self.txt_title, 0)
        s.Add(row2, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, self.FromDIP(10))

        # 詳細設定（折りたたみ）
        adv = Collapsible(panel, "詳細設定")
        adv.body.SetBackgroundColour(bg)
        adv.body.SetForegroundColour(fg)

        g = wx.FlexGridSizer(2, 4, 8, 8)
        g.AddGrowableCol(1, 1)
        g.AddGrowableCol(3, 1)

        self.txt_next = wx.TextCtrl(adv.body, value=self.cfg.nextpage_key)
        self.txt_full = wx.TextCtrl(adv.body, value=self.cfg.fullscreen_key)
        self.txt_pgkey = wx.TextCtrl(adv.body, value=" + ".join(self.cfg.pagejump_key))
        self.txt_pg = wx.TextCtrl(adv.body, value=self.cfg.pagejump)

        for w in (self.txt_next, self.txt_full, self.txt_pgkey, self.txt_pg):
            w.SetBackgroundColour(wx.Colour(45, 49, 53))
            w.SetForegroundColour(fg)

        g.Add(wx.StaticText(adv.body, label="次ページキー"), 0, wx.ALIGN_CENTER_VERTICAL)
        g.Add(self.txt_next, 1, wx.EXPAND)
        g.Add(wx.StaticText(adv.body, label="全画面化キー"), 0, wx.ALIGN_CENTER_VERTICAL)
        g.Add(self.txt_full, 1, wx.EXPAND)

        g.Add(wx.StaticText(adv.body, label="ページ移動キー"), 0, wx.ALIGN_CENTER_VERTICAL)
        g.Add(self.txt_pgkey, 1, wx.EXPAND)
        g.Add(wx.StaticText(adv.body, label="開始ページ"), 0, wx.ALIGN_CENTER_VERTICAL)
        g.Add(self.txt_pg, 1, wx.EXPAND)

        adv.body_sizer.Add(g, 0, wx.EXPAND|wx.ALL, 4)
        s.Add(adv, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, self.FromDIP(10))

        # ボタン
        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save = wx.Button(panel, label="設定を保存")
        self.btn_start = wx.Button(panel, label="キャプチャ開始")
        self.btn_exit = wx.Button(panel, label="閉じる")
        for b in (self.btn_save, self.btn_start, self.btn_exit):
            btns.Add(b, 0, wx.RIGHT, 8)
        s.Add(btns, 0, wx.ALIGN_RIGHT|wx.ALL, self.FromDIP(10))

        panel.SetSizer(s)

        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start)
        self.btn_exit.Bind(wx.EVT_BUTTON, lambda e: self.Close())

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
        # kindless.exe が同じフォルダにあればそれを使い、なければ python 実行
        here = osp.dirname(osp.abspath(__file__))
        exe = osp.join(here, "Kindless.exe")
        if osp.exists(exe):
            cmd = [exe, self.ini_path]
            creationflags = 0
        else:
            # 開発時: コンソールを出さないように STARTUPINFO を設定
            py = sys.executable
            target = osp.join(here, "kindless.py")
            cmd = [py, target, self.ini_path]
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        try:
            subprocess.Popen(cmd, creationflags=creationflags)
            wx.MessageBox("キャプチャを開始しました。Kindleが見つからない場合はエラーが表示されます。", APP_NAME, wx.OK|wx.ICON_INFORMATION)
            self.Close()
        except Exception as e:
            wx.MessageBox(f"起動に失敗しました: {e}", APP_NAME, wx.OK|wx.ICON_ERROR)

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
