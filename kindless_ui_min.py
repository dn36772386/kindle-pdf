import wx
import os, os.path as osp, sys, subprocess

APP_NAME = "Kindless Launcher (min)"

def _enable_hi_dpi():
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # Per-Monitor v2
    except Exception:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

def _abs(p: str) -> str:
    return osp.abspath(p)

_enable_hi_dpi()

class Main(wx.Frame):
    def __init__(self):
        super().__init__(None, title=APP_NAME)
        self.SetInitialSize(self.FromDIP(wx.Size(420, 160)))

        p = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="INI"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(8))
        self.txt_ini = wx.TextCtrl(p, value="kindless.ini")
        row.Add(self.txt_ini, 1, wx.EXPAND)
        s.Add(row, 0, wx.EXPAND | wx.ALL, self.FromDIP(10))

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(p, label="開始")
        self.btn_exit = wx.Button(p, label="閉じる")
        btns.AddStretchSpacer()
        btns.Add(self.btn_start, 0, wx.RIGHT, self.FromDIP(8))
        btns.Add(self.btn_exit, 0)
        s.Add(btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(10))

        p.SetSizer(s)

        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start)
        self.btn_exit.Bind(wx.EVT_BUTTON, lambda e: self.Close())

        self.Centre()

    def on_start(self, _):
        here = _abs(osp.dirname(__file__))
        ini = _abs(self.txt_ini.GetValue().strip() or "kindless.ini")
        target = osp.join(here, "kindless.py")
        if not osp.exists(target):
            wx.MessageBox(f"kindless.py が見つかりません。\n{target}", APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        if not osp.exists(ini):
            wx.MessageBox(f"INI が見つかりません。\n{ini}", APP_NAME, wx.OK | wx.ICON_ERROR)
            return

        py = sys.executable
        cmd = [py, target, ini]
        try:
            subprocess.Popen(cmd)
            wx.MessageBox("起動しました。エラーはコンソールに出ます。", APP_NAME, wx.OK | wx.ICON_INFORMATION)
            self.Close()
        except Exception as e:
            wx.MessageBox(f"起動失敗: {e}", APP_NAME, wx.OK | wx.ICON_ERROR)

class App(wx.App):
    def OnInit(self):
        f = Main()
        f.Show()
        return True

if __name__ == "__main__":
    App(False).MainLoop()
