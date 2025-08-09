from dataclass import KindleSSConfig, read_config
from wxdialog import SimpleDialog, Icon
from WindowInfo import *

import threading, queue
import sys, os, os.path as osp, datetime , time
import shutil
import dataclasses

import pyautogui as pag
import cv2, numpy as np
from PIL import ImageGrab

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
    def capture(self) -> np.ndarray:
        cap = ImageGrab.grab()
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


def trim_check(img: np.ndarray, color, margin: Margin):
    def cmps(img, xrange, yrange , color, xdef):
        rt = xdef
        for x in xrange:
            if (img[yrange[0]:yrange[1] , x] != color).any():
                rt = x
                break
        return rt
    
    sx, sy = img.shape[1], img.shape[0]
    nx, ny = margin.top, margin.bottom
    xx, xy = sx - margin.left, sy - margin.right
    lm = cmps(img, range(nx, xx), (ny, xy),color, sx)
    if lm == nx:
        lm = 0
    rm = cmps(img, reversed(range(nx, xx)), (ny, xy), color, 0)
    if rm == xx:
        rm = sx
    return lm,rm


def color_check(img: np.ndarray, mg:Margin) -> int:
    imx = img.shape[1]
    imy = img.shape[0]
    img_blue, img_green, img_red = cv2.split(img[mg.top : imx - mg.bottom , mg.left : imy - mg.right])
    img_bg = np.abs(img_blue.astype(int) - img_green.astype(int))
    img_gr = np.abs(img_green.astype(int) - img_red.astype(int))
    img_rb = np.abs(img_red.astype(int) - img_blue.astype(int))
    return max(img_bg.max(),img_gr.max(),img_rb.max()) 


def capture(cfg: KindleSSConfig, dir_title: str, page: int):
    # Kindle ウィンドウ取得（タイトルに依存しない）
    hwnd = GetWindowHandleWithName('', cfg.execute_filename)
    if hwnd is None:
        SimpleDialog.infomation(title="エラー", label="Kindleが見つかりません", icon=Icon.Exclamation)
        _report("ERROR: KINDLE_NOT_FOUND")
        return False
    # 念のため撮影前にも全画面状態を整える
    _activate_and_fullscreen(hwnd, cfg.fullscreen_key)
    print('Cap start')
    sc_w, sc_h = pag.size()

    cap = CaptureWrapper()
    imp = cap.capture()

    def cmps(img,rng):
        for i in rng:
            if np.all(img[20][i] != img[19][0]):
                return i

    lft = cmps(imp,range(cfg.left_margin, imp.shape[1] - cfg.right_margin))
    rht = cmps(imp,reversed(range(cfg.left_margin, imp.shape[1] - cfg.right_margin)))
    
    comic = True ##カスタム

    print(lft, sc_w - rht, imp[int(sc_h / 2) , lft +1])
    comic = True if lft < 60 and sc_w - rht < 60 and max(imp[int(sc_h / 2) , lft +1]) == 0 else False
    ext = '.png' if comic else cfg.file_extension

    old = np.zeros((sc_h , rht-lft, 3), np.uint8)

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
        if GetWindowHandleWithName('', cfg.execute_filename) is None:
            _report("ERROR: KINDLE_NOT_FOUND")
            return False
        filename = osp.join(dir_title , str(page).zfill(3) + ext)
        start = time.perf_counter()
        while True:
            time.sleep(cfg.capture_wait)
            ss = cap.capture()
            ss = ss[:, lft: rht]

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
            pag.press(cfg.nextpage_key)
            # 5ページごとに全画面再適用（外れる環境対策）
            if page % 5 == 0:
                _activate_and_fullscreen(hwnd, cfg.fullscreen_key)

    if comic and cfg.trim_after_capture:
        with cv:
            arg.put(ThreadArgs(True, 0, '', None))
            cv.notify()
        thr.join()

        r : list[ThreadResult] = []
        while not rslt.empty():
            r += [rslt.get()]
        ml = min([x.margin_left for x in r])
        mr = max([x.margin_right for x in r])
        print('trim =', ml, mr)
        for i in r:
            print(i.filename, end='')
            s = imread(i.filename)
            s = s[:,ml:mr]
            if i.gray:
                s = cv2.cvtColor(s, cv2.COLOR_RGB2GRAY)
                print(' is grayscale', end = '')
            fn = osp.splitext(i.filename)[0] + cfg.file_extension
            os.remove(i.filename)
            imwrite(fn,s)
            print()
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
                page = max([int(os.path.splitext(os.path.basename(i))[0]) for i in os.listdir(dir_title)]) + 1
            except ValueError:
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
        _report("START")
        ok_cap = capture(cfg, dir_title, page)
        if not ok_cap:
            _report("ERROR: CAPTURE_ABORTED")
        else:
            _report("DONE")
    except Exception as e:
        _report(f"ERROR: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
