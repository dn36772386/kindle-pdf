"""Kindless UI - 統合版"""

import wx
import os
import os.path as osp
import subprocess
import sys
import configparser
import threading
import time

# 既存の設定ローダーを再利用
from dataclass import KindleSSConfig, read_config
from WindowInfo import GetWindowHandleWithName, GetWindowText

APP_NAME = "Kindless"
SECTION = "KINDLESS"

def ini_default_path() -> str:
    """デフォルトのINIファイルパス"""
    return osp.abspath("kindless.ini")

def ensure_ini_exists(path: str) -> None:
    """INIファイルが存在しない場合は作成"""
    if osp.exists(path):
        return
    
    cfg = KindleSSConfig()
    # 保存先フォルダを設定
    save_folder = "C:\\Users\\Public\\Documents\\KindleCaptures"
    
    config = configparser.ConfigParser()
    config[SECTION] = {
        "window_title": cfg.window_title,
        "execute_filename": cfg.execute_filename,
        "nextpage_key": cfg.nextpage_key,
        "fullscreen_key": cfg.fullscreen_key,
        "pagejump_key": " + ".join(cfg.pagejump_key),
        "pagejump": cfg.pagejump,
        "base_save_folder": save_folder,
        "overwrite": str(cfg.overwrite),
        "trim_after_capture": str(cfg.trim_after_capture),
        "force_move_first_page": str(cfg.force_move_first_page),
        "auto_title": str(cfg.auto_title),
        "file_extension": cfg.file_extension.lstrip('.'),
    }
    
    with open(path, "w", encoding="utf-8") as f:
        config.write(f)


class KindlessFrame(wx.Frame):
    """統合UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent, title="Kindless", 
                         style=wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER)
        
        self.SetSize(450, 350)
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        
        # プロセス管理
        self.process = None
        self.monitor_thread = None
        
        # INI読み込み
        self.ini_path = ini_default_path()
        ensure_ini_exists(self.ini_path)
        self.cfg = read_config(KindleSSConfig(), self.ini_path)
        
        # レイアウト
        self.init_ui()
        self.Center()
        
        # ウィンドウクローズイベント
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Kindleから自動でタイトルを取得
        self.auto_get_title()
    
    def init_ui(self):
        """UI要素の配置"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # タイトル入力
        title_label = wx.StaticText(self.panel, label="書籍タイトル:")
        self.title_input = wx.TextCtrl(self.panel, size=(400, -1))
        self.title_input.SetHint("タイトルを入力（フォルダ名になります）")
        
        # ページ送り方向選択
        page_label = wx.StaticText(self.panel, label="ページ送り方向:")
        self.page_direction = wx.RadioBox(
            self.panel,
            choices=["右送り（→）", "左送り（←）"],
            majorDimension=2,
            style=wx.RA_SPECIFY_COLS
        )
        self.page_direction.SetSelection(0)  # デフォルトは右送り
        
        # ステータス表示
        self.status = wx.StaticText(self.panel, label="準備完了")
        self.gauge = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL)
        self.gauge.Hide()
        
        # ボタン
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_button = wx.Button(self.panel, label="キャプチャ開始")
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        
        self.close_button = wx.Button(self.panel, label="終了")
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        
        button_sizer.Add(self.start_button, 0, wx.ALL, 5)
        button_sizer.Add(self.close_button, 0, wx.ALL, 5)
        
        # レイアウト設定
        main_sizer.Add(title_label, 0, wx.ALL, 5)
        main_sizer.Add(self.title_input, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(page_label, 0, wx.ALL, 5)
        main_sizer.Add(self.page_direction, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(self.status, 0, wx.ALL | wx.CENTER, 10)
        main_sizer.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
    
    def auto_get_title(self):
        """Kindleウィンドウからタイトルを自動取得"""
        try:
            ghwnd = GetWindowHandleWithName(self.cfg.window_title, self.cfg.execute_filename)
            if ghwnd:
                title = GetWindowText(ghwnd)
                if title and ' - ' in title:
                    # Kindleのタイトル部分を抽出
                    title = title.split(' - ', 1)[1]
                    # 無効な文字を置換
                    rep_list = [['　',' '],[':','：'],[';','；'],['（','('],['）',')'],
                               ['［','['],['］',']'],['&','＆'],['"','"'],['|','｜'],
                               ['?','？'],['!','！'],['*','＊'],['\\','￥'],
                               ['<','＜'],['>','＞'],['/','／']]
                    for old, new in rep_list:
                        title = title.replace(old, new)
                    self.title_input.SetValue(title)
        except Exception as e:
            print(f"Error getting title: {e}")
    
    def on_start(self, event):
        """キャプチャ開始"""
        title = self.title_input.GetValue().strip()
        
        if not title:
            wx.MessageBox("タイトルを入力してください", "エラー", 
                         wx.OK | wx.ICON_ERROR)
            return
        
        # ページ送り方向を取得
        direction = "right" if self.page_direction.GetSelection() == 0 else "left"
        
        # 設定を更新
        self.update_config(direction)
        
        # kindless.pyを実行
        self.run_kindless(title)
    
    def update_config(self, direction):
        """設定ファイルを更新"""
        try:
            config = configparser.ConfigParser()
            config.read(self.ini_path, encoding='utf-8')
            
            if SECTION not in config:
                config[SECTION] = {}
            
            # ページ送り方向を更新
            config[SECTION]['nextpage_key'] = direction
            config[SECTION]['auto_title'] = 'False'  # UIでタイトルを指定するのでFalse
            
            with open(self.ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
                
        except Exception as e:
            print(f"Error updating config: {e}")
    
    def run_kindless(self, title):
        """kindless.pyを実行"""
        try:
            # UIを無効化
            self.start_button.Enable(False)
            self.title_input.Enable(False)
            self.page_direction.Enable(False)
            
            # ステータス更新
            self.status.SetLabel("キャプチャ実行中...")
            self.gauge.Show()
            self.gauge.Pulse()
            self.panel.Layout()
            
            # kindless.pyのパスを探す
            current_dir = osp.dirname(osp.abspath(__file__))
            kindless_py = osp.join(current_dir, 'kindless.py')
            
            if not osp.exists(kindless_py):
                wx.MessageBox("kindless.pyが見つかりません", "エラー", 
                            wx.OK | wx.ICON_ERROR)
                self.reset_ui()
                return
            
            # コマンド作成（タイトルを環境変数で渡す）
            env = os.environ.copy()
            env['KINDLE_TITLE'] = title
            
            cmd = [sys.executable, kindless_py, self.ini_path]
            
            # プロセスを起動
            if sys.platform == 'win32':
                self.process = subprocess.Popen(cmd, 
                                               env=env,
                                               creationflags=subprocess.CREATE_NEW_CONSOLE,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            else:
                self.process = subprocess.Popen(cmd,
                                               env=env,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            
            # モニタースレッド開始
            self.monitor_thread = threading.Thread(target=self.monitor_process, args=(title,))
            self.monitor_thread.start()
            
        except Exception as e:
            wx.MessageBox(f"実行エラー: {e}", "エラー", wx.OK | wx.ICON_ERROR)
            self.reset_ui()
    
    def monitor_process(self, title):
        """プロセス監視"""
        try:
            # プロセスの出力を読み取りながら監視
            while True:
                # プロセスが終了したかチェック
                poll = self.process.poll()
                if poll is not None:
                    # プロセス終了
                    return_code = poll
                    break
                
                # 出力を読み取る（ブロックしないように）
                try:
                    line = self.process.stdout.readline()
                    if line:
                        line = line.decode('utf-8', errors='ignore').strip()
                        print(f"[kindless.py] {line}")
                        
                        # トリミング処理の検知
                        if 'Trimming complete!' in line:
                            wx.CallAfter(self.update_status, "トリミング処理完了...")
                        elif 'Waiting for trimming' in line:
                            wx.CallAfter(self.update_status, "トリミング処理中...")
                        elif 'Exiting fullscreen' in line:
                            wx.CallAfter(self.update_status, "終了処理中...")
                except:
                    pass
                
                time.sleep(0.1)
            
            # UIスレッドで更新
            wx.CallAfter(self.on_capture_complete, return_code, title)
            
        except Exception as e:
            wx.CallAfter(self.on_capture_error, str(e))
    
    def update_status(self, message):
        """ステータス更新（UIスレッドから呼ばれる）"""
        self.status.SetLabel(message)
        self.panel.Layout()
    
    def on_capture_complete(self, return_code, title):
        """キャプチャ完了時の処理"""
        if return_code == 0:
            # 正常終了
            self.status.SetLabel("処理完了！")
            self.gauge.SetRange(100)
            self.gauge.SetValue(100)
            
            save_path = osp.join(self.cfg.base_save_folder, title)
            wx.MessageBox(f"キャプチャが完了しました。\n\n保存先:\n{save_path}", 
                         "完了", wx.OK | wx.ICON_INFORMATION)
        else:
            # エラー終了
            self.status.SetLabel("エラーが発生しました")
            wx.MessageBox(f"キャプチャ中にエラーが発生しました。\nエラーコード: {return_code}", 
                         "エラー", wx.OK | wx.ICON_ERROR)
        
        self.reset_ui()
    
    def on_capture_error(self, error_msg):
        """エラー時の処理"""
        self.status.SetLabel("エラーが発生しました")
        wx.MessageBox(f"キャプチャ中にエラーが発生しました。\n{error_msg}", 
                     "エラー", wx.OK | wx.ICON_ERROR)
        self.reset_ui()
    
    def reset_ui(self):
        """UI初期化"""
        self.start_button.Enable(True)
        self.title_input.Enable(True)
        self.page_direction.Enable(True)
        self.gauge.Hide()
        self.gauge.SetValue(0)
        self.status.SetLabel("準備完了")
        self.panel.Layout()
        self.process = None  # プロセス参照をクリア
        self.monitor_thread = None  # スレッド参照をクリア
    
    def on_close(self, event):
        """終了処理"""
        if self.process and self.process.poll() is None:
            wx.MessageBox("キャプチャ実行中は終了できません", "警告", 
                         wx.OK | wx.ICON_WARNING)
            return
        
        self.Destroy()


class App(wx.App):
    def OnInit(self):
        self.SetAppName(APP_NAME)
        frame = KindlessFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = App(False)
    app.MainLoop()