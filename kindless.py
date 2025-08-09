"""Kindle キャプチャ本体."""

# HiDPI を最優先で有効化（wx / pyautogui 初期化前）
try:
    import ctypes  # noqa: F401
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # Per-Monitor v2
except Exception:
    try:
        import ctypes  # noqa: F401
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # Per-Monitor
    except Exception:
        try:
            import ctypes  # noqa: F401
            ctypes.windll.user32.SetProcessDPIAware()       # System DPI fallback
        except Exception:
            pass

from dataclass import KindleSSConfig, read_config
from WindowInfo import *

import threading, queue
import sys, os, os.path as osp, datetime , time
import shutil
import dataclasses

import cv2, numpy as np  # 既存
from PIL import ImageGrab
import pyautogui as pag
from wxdialog import SimpleDialog, Icon
import traceback

# --- 追加: ステータス/停止ファイル対応 ---
STATUS_FILE: str | None = None
STOP_FILE: str | None = None

def _parse_status_arg():
    global STATUS_FILE
    if "--status-file" in sys.argv:
        i = sys.argv.index("--status-file")
        if i + 1 < len(sys.argv):
            STATUS_FILE = sys.argv[i + 1]
    global STOP_FILE
    if "--stop-file" in sys.argv:
        i = sys.argv.index("--stop-file")
        if i + 1 < len(sys.argv):
            STOP_FILE = sys.argv[i + 1]

def _report(msg: str):
    if not STATUS_FILE:
        return
    try:
        with open(STATUS_FILE, "a", encoding="utf-8") as f:
            f.write(msg.strip() + "\n")
    except Exception:
        pass
# --- ここまで ---

def _norm_ext(ext: str) -> str:
    """拡張子を常に .付きに正規化（例: 'png' -> '.png'）。"""
    if not ext:
        return '.png'
    return '.' + ext.lstrip('.')

def _activate_and_fullscreen(hwnd, fullscreen_key: str | None):
    """前面化→最大化→全画面化。安定のため少し待機。"""
    try:
        import ctypes
        SW_SHOWMAXIMIZED = 3
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.2)
    try:
        if fullscreen_key:
            pag.press(fullscreen_key)
            time.sleep(0.3)
    except Exception:
        pass

rep_list = [['　',' '],[':','：'],[';','；'],['（','('],['）',')'],['［','['],['］',']'],
            ['&','＆'],['"','”'],['|','｜'],['?','？'],['!','！'],['*','＊'],['\\','￥'],
            ['<','＜'],['>','＞'],['/','／']]

@dataclasses.dataclass
class Margin:
    top : int
    bottom : int
    left : int
    right : int

@dataclasses.dataclass
class ThreadArgs:
    endflag : bool
    page : int
    filename : str
    image : np.ndarray

@dataclasses.dataclass
class ThreadResult:
    margin_left : int
    margin_right : int
    gray : bool
    filename : str


class CaptureWrapper:
    def __init__(self):
        pass
    def capture(self, bbox: tuple[int,int,int,int] | None = None) -> np.ndarray:
        """スクリーンショット (BGR)。bbox=(L,T,R,B) 指定でその矩形のみ。"""
        cap = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
        return cv2.cvtColor(np.array(cap), cv2.COLOR_RGB2BGR)


def imread(filename: str, flags=cv2.IMREAD_COLOR, dtype=np.uint8) -> np.ndarray:
    n = np.fromfile(filename, dtype)
    img = cv2.imdecode(n, flags)
    return img


def imwrite(filename: str, img : np.ndarray, params=None) -> bool:
    ext = os.path.splitext(filename)[1]
    result, n = cv2.imencode(ext, img, params)
    if result:
        with open(filename, mode='w+b') as f:
            n.tofile(f)
        return True
    else:
        return False


# ------------------------------------------------------------
# 安全なコンテンツ左右境界推定
# ------------------------------------------------------------
def _safe_bounds_by_content(bgr: np.ndarray, cfg) -> tuple[int, int]:
    """画像からコンテンツ領域左右境界を推定。空候補ならINIマージンでフォールバック。"""
    h, w = bgr.shape[:2]
    # 解析ROI設定
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    top = getattr(cfg, "grayscale_margin_top", 0)
    bot = getattr(cfg, "grayscale_margin_bottom", 0)
    lef = getattr(cfg, "grayscale_margin_left", 0)
    rig = getattr(cfg, "grayscale_margin_right", 0)
    roi = g[top: max(top, h - bot), lef: max(lef, w - rig)]
    if roi.size == 0:
        L = getattr(cfg, "left_margin", 0)
        R = max(L + 1, w - getattr(cfg, "right_margin", 0))
        return (L, R)
    thr = int(getattr(cfg, "grayscale_threshold", 180) or 180)
    try:
        _, bw = cv2.threshold(roi, thr, 255, cv2.THRESH_BINARY_INV)
    except Exception:
        bw = (roi < thr).astype("uint8") * 255
    colsum = bw.sum(axis=0)
    cols = np.where(colsum > 0)[0]
    if cols.size == 0:
        L = getattr(cfg, "left_margin", 0)
        R = max(L + 1, w - getattr(cfg, "right_margin", 0))
        return (L, R)
    L = int(cols[0] + lef)
    R = int(cols[-1] + lef + 1)
    L = max(L, getattr(cfg, "left_margin", 0))
    R = min(R, w - getattr(cfg, "right_margin", 0))
    if R - L < 16:
        L = getattr(cfg, "left_margin", 0)
        R = max(L + 1, w - getattr(cfg, "right_margin", 0))
    return (L, R)


def trim_check(img: np.ndarray, color, margin: Margin):
    """
    画面背景色（color）と異なるピクセルの左右端を探す。
    候補が無い場合は「マージンで切った全幅」にフォールバックする。
    """
    h, w = img.shape[:2]
    x0 = margin.left
    x1 = max(x0 + 1, w - margin.right)
    y0 = margin.top
    y1 = max(y0 + 1, h - margin.bottom)
    roi = img[y0:y1, x0:x1]
    if roi.size == 0:
        return (0, w)
    # BGR 全成分で color と異なる画素がある列だけ採用
    mask = (roi[:, :, 0] != color[0]) | (roi[:, :, 1] != color[1]) | (roi[:, :, 2] != color[2])
    cols = np.where(mask.any(axis=0))[0]
    if cols.size == 0:
        # 何も見つからない → 画像全幅
        return (0, w)
    lm = int(x0 + cols.min())
    rm = int(x0 + cols.max() + 1)
    # クランプ
    lm = max(0, min(lm, w - 1))
    rm = max(lm + 1, min(rm, w))
    return lm, rm


def color_check(img: np.ndarray, mg:Margin) -> int:
    # width / height を取り違えていたバグを修正
    imx = img.shape[1]  # width
    imy = img.shape[0]  # height
    img_blue, img_green, img_red = cv2.split(img[mg.top : imy - mg.bottom , mg.left : imx - mg.right])
    img_bg = np.abs(img_blue.astype(int) - img_green.astype(int))
    img_gr = np.abs(img_green.astype(int) - img_red.astype(int))
    img_rb = np.abs(img_red.astype(int) - img_blue.astype(int))
    return max(img_bg.max(),img_gr.max(),img_rb.max()) 


def capture(cfg: KindleSSConfig, dir_title: str, page: int):
    """Kindle キャプチャメインループ.
    戻り値: True=正常完了 / False=中断・エラー
    """
    # Kindle ウィンドウ（プロセス名のみで検出）
    hwnd = GetWindowHandleWithName('', cfg.execute_filename)
    if hwnd is None:
        SimpleDialog.infomation(title="エラー", label="Kindleが見つかりません", icon=Icon.Exclamation)
        _report("ERROR: KINDLE_NOT_FOUND")
        return False
    _activate_and_fullscreen(hwnd, cfg.fullscreen_key)
    print('Cap start')

    cap = CaptureWrapper()
    left, top, right, bottom = GetWindowRect(hwnd)
    imp = cap.capture((left, top, right, bottom))
    # 安全な境界検出（空の場合はマージンフォールバック）
    lft, rht = _safe_bounds_by_content(imp, cfg)
    
    comic = True ##カスタム

    win_w = imp.shape[1]
    win_h = imp.shape[0]
    print(lft, win_w - rht, imp[int(win_h / 2) , lft +1])
    comic = True if lft < 60 and win_w - rht < 60 and max(imp[int(win_h / 2) , lft +1]) == 0 else False
    ext = '.png' if comic else _norm_ext(cfg.file_extension)

    ss0 = imp[:, lft:rht]
    old = np.zeros_like(ss0)

    _report("START")

    comic = True ##カスタム

    if comic and cfg.trim_after_capture:
        arg = queue.Queue()
        rslt = queue.Queue()
        cv = threading.Condition()
        trim = Margin(cfg.trim_margin_top, cfg.trim_margin_bottom, cfg.trim_margin_left, cfg.trim_margin_right)
        gray = Margin(cfg.grayscale_margin_top, cfg.grayscale_margin_bottom, cfg.grayscale_margin_left, cfg.grayscale_margin_right)
        thr = threading.Thread(args=(cv, arg, trim, gray, rslt, cfg.grayscale_threshold),target=thread)
        thr.start()
  
    loop = True
    while loop:
        # 停止要求
        if STOP_FILE and os.path.exists(STOP_FILE):
            _report("ERROR: STOPPED")
            return False
        # Kindle消失
        hwnd_now = GetWindowHandleWithName('', cfg.execute_filename)
        if hwnd_now is None:
            _report("ERROR: KINDLE_NOT_FOUND")
            return False
        filename = osp.join(dir_title , str(page).zfill(3) + ext)
        start = time.perf_counter()
        while True:
            time.sleep(cfg.capture_wait)
            # 毎回ウィンドウ矩形を再取得しクロップ
            left, top, right, bottom = GetWindowRect(hwnd_now)
            ss = cap.capture((left, top, right, bottom))
            # ページ遷移直後は未描画で空幅になることがあるので毎回検証
            cur_l, cur_r = lft, rht
            if ss.shape[1] <= 0 or cur_r - cur_l < 2:
                cur_l, cur_r = _safe_bounds_by_content(ss, cfg)
            ss = ss[:, cur_l:cur_r]
            if ss.size == 0:
                # まだ描画されていない。再トライ。
                continue

            if not np.array_equal(old, ss):
                break
            if time.perf_counter()- start > cfg.timeout_wait:
                pag.press(cfg.fullscreen_key)
                loop = False
                break
        if loop:
            old = ss.copy()
            if not comic and cfg.trim_after_capture:
                if color_check(ss, Margin(0,0,0,0)) <= cfg.grayscale_threshold:
                    imwrite(filename,ss[:,:,1])
                else:
                    imwrite(filename,ss)
            else:
                with cv:
                    arg.put(ThreadArgs( False, page, filename, ss ))
                    cv.notify()

            print('Page:', page, ' ', ss.shape, time.perf_counter() - start, 'sec')
            page += 1
            _report(f"PAGE {page}")
            print(f"Pressing next page key: {cfg.nextpage_key}")
            pag.press(cfg.nextpage_key)  # 押しっぱなし防止
            if page % 5 == 0:
                _activate_and_fullscreen(hwnd_now, cfg.fullscreen_key)

    if comic and cfg.trim_after_capture:
        with cv:
            arg.put(ThreadArgs(True, 0, '', None))
            cv.notify()
        thr.join()

        r : list[ThreadResult] = []
        while not rslt.empty():
            r.append(rslt.get())
        if r:
            left_candidates = [x.margin_left for x in r]
            right_candidates = [x.margin_right for x in r]
            if left_candidates and right_candidates:
                ml = min(left_candidates)
                mr = max(right_candidates)
                print('trim =', ml, mr)
                for i in r:
                    print(i.filename, end='')
                    s = imread(i.filename)
                    s = s[:, ml:mr]
                    if i.gray:
                        s = cv2.cvtColor(s, cv2.COLOR_RGB2GRAY)
                        print(' is grayscale', end='')
                    fn = osp.splitext(i.filename)[0] + _norm_ext(cfg.file_extension)
                    os.remove(i.filename)
                    imwrite(fn, s)
                    print()
            else:
                print('trim skipped: empty candidates')
        else:
            print('trim skipped: no results collected')
    _report("DONE")
    return True

def thread(cv: threading.Condition, que: queue.Queue, trm: Margin, gray: Margin, out: queue.Queue,gs : int):
    end_flag = False
    sc_w, sc_h = pag.size()
    ml = sc_w
    mr = 0
    while not end_flag:
        while not que.empty():
            arg : ThreadArgs = que.get()
            if arg.endflag:
                end_flag = True
                break
            tm = trim_check(arg.image, arg.image[1, 1],trm)
            ml = min(ml, tm[0])
            mr = max(mr, tm[1])
            gst = Margin(gray.top, gray.bottom, gray.left + ml, mr - gray.right)
            gr = (color_check(arg.image, gst) <= gs)
            imwrite(arg.filename, arg.image)
            rslt = ThreadResult(tm[0], tm[1], gr, arg.filename)
            out.put(rslt)
        else:
            with cv:
                cv.wait()


def main():
    _parse_status_arg()
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        ini = sys.argv[1]
    else:
        ini = 'kindless.ini'

    cfg: KindleSSConfig = read_config(KindleSSConfig(), ini)
    # タイトルに依存せず、プロセス名で検出
    ghwnd = GetWindowHandleWithName('', cfg.execute_filename)
    if ghwnd is None:
        SimpleDialog.infomation(title="エラー", label="Kindleが見つかりません", icon=Icon.Exclamation)
        _report("ERROR: KINDLE_NOT_FOUND")
        return

    # 先に最大化 / 前面化 / 全画面化
    _activate_and_fullscreen(ghwnd, cfg.fullscreen_key)

    t = GetWindowText(ghwnd)
    if (idx := t.find(' - ')) != -1:
        t = t[idx + 3:]
        for i in rep_list:
            t = t.replace(i[0], i[1])
    else:
        t = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    if not cfg.auto_title:
        t = ''
    SetForeWindow(ghwnd)
    time.sleep(cfg.short_wait)
    if cfg.force_move_first_page:
        pag.hotkey(*cfg.pagejump_key)
        time.sleep(cfg.short_wait)
        pag.press(cfg.pagejump)
        pag.press('enter')
        time.sleep(cfg.capture_wait)

    # 再度念押し
    _activate_and_fullscreen(ghwnd, cfg.fullscreen_key)

    sc_w, sc_h = pag.size()
    pag.moveTo(sc_w / 2, sc_h / 2)
    ok, book_title = SimpleDialog.askstring(title="タイトル入力", label="タイトルを入れてね", value=t, width=400)
    if not ok:
        _activate_and_fullscreen(ghwnd, cfg.fullscreen_key)
        _report("ERROR: CAPTURE_ABORTED")
        return
    append = False
    if book_title and book_title[0] == '+':
        append = True
        book_title = book_title[1:]
    dir_title = osp.join(cfg.base_save_folder, book_title)
    print(dir_title)
    page = 1
    if osp.exists(dir_title):
        if append:
            try:
                existing_pages = [int(os.path.splitext(os.path.basename(i))[0]) for i in os.listdir(dir_title) if os.path.splitext(i)[0].isdigit()]
                if existing_pages:
                    page = max(existing_pages) + 1
                else:
                    page = 1
            except Exception:
                page = 1
        elif cfg.overwrite:
            shutil.rmtree(dir_title)
            os.makedirs(dir_title)
        else:
            pag.press(cfg.fullscreen_key)
            time.sleep(cfg.long_wait)
            SimpleDialog.infomation(title="エラー", label="ディレクトリが存在します", icon=Icon.Exclamation)
            _report("ERROR: DIR_EXISTS")
            return
    else:
        try:
            os.makedirs(dir_title)
        except OSError:
            pag.press(cfg.fullscreen_key)
            time.sleep(cfg.long_wait)
            SimpleDialog.infomation(title="エラー", label="ディレクトリが作成できませんでした", icon=Icon.Exclamation)
            _report("ERROR: MKDIR_FAILED")
            return
    time.sleep(cfg.fullscreen_wait)
    try:
        ok_cap = capture(cfg, dir_title, page)
        if not ok_cap:
            _report("ERROR: CAPTURE_ABORTED")
    except Exception as e:
        tb = traceback.format_exc()
        _report(f"ERROR: {type(e).__name__}: {e}")
        try:
            with open("kindless_error.log", "a", encoding="utf-8") as f:
                f.write(tb + "\n")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
