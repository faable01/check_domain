"""
    ドメイン選別のため、Ahrefs, Moz, Majestic, Waybackで調査を行う.
    
    ---- 補足 ----

    結果をSSに書き込む際のURLパラメータ形式は：
    [“__a::値__”, “__b::値__”, “__c::値__”, …]

    ---- スプレッドシート調査構成 ----
    Ahrefs				
    UR	DR	Governmental	教育	目視確認用

    Moz			
    PA	DA	MozRank(! 廃止のためSSの列から削除)	目視確認用

    Majestic				
    TF	CF(被リンクの量)	4total	6total	目視確認用

    Wayback		
    運用開始	空白年	目視確認用
"""

import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
import chromedriver_binary
import threading
import urllib.parse
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
disable_warnings(InsecureRequestWarning)
import asyncio
import io 
import urllib.request
from PIL import Image
import os
import sys
from mozscape import Mozscape


def check_current():
    """
        cx-freezeの利用を考慮した階層チェック.
        参考：https://codeday.me/jp/qa/20190408/581468.html
        参考2：https://cx-freeze.readthedocs.io/en/latest/faq.html
    """
    dir_ = None
    if getattr(sys, 'frozen', False):
        # frozen
        dir_ = os.path.dirname(sys.executable)
        print("frozen")

    else:
        # unfrozen
        dir_ = os.path.dirname(os.path.realpath(__file__))
        print("unfrozen")

    print(f"current directory: {dir_}")
    return dir_


# このファイルの存在するパス（cx-freezeのビルド前、ビルド後のパスの差異を吸収する）
__current__ = check_current()

# ChromeとChromeDriverのパス
__chrome_driver_path__ = None
__chrome_exec_path__ = None
if os.name == "posix":  # mac or linux
    __chrome_driver_path__ = f"{__current__}/lib/chromedriver_binary/chromedriver"
    __chrome_exec_path__ = f"{__current__}/Google Chrome.app/Contents/MacOS/Google Chrome"

else:  # windows
    __chrome_driver_path__ = f"{__current__}/chromedriver_binary/chromedriver.exe"
    __chrome_exec_path__ = f"{__current__}/Google/Chrome/Application/chrome.exe"


def get_ssurl():
    """
        連携するスプレッドシートのURLを取得する.
        なお、URLはss_url.txtの１行目から取得する.
        また、ss_url.txtが2行以上ある場合、そのままだと行末に改行コードが含まれる.
        そのため正規表現でURLを抜き出している.
    """
    with open(f"{__current__}/ss_url.txt", encoding="utf-8") as f:
        first_line = f.readline()
        return re.search("http.+?exec", first_line).group(0)


# サーバとして機能させているGASのURL
__ssurl__ = get_ssurl()


def get_keys_for_moz_api():
    """
        Moz APIのためのキーをタプルで取得する
    """
    with open(f"{__current__}/moz_api.txt", encoding="utf-8") as f:
        id = f.readline().rstrip('\r\n')
        key = f.readline().rstrip('\r\n')
        return id, key


def open_png(img_read):
    """
        読み込み済みの画像データ（png）を保存せずに開く
    """
    img_bin = io.BytesIO(img_read) #メモリに保持してディレクトリ偽装みたいなことする
    pil_img = Image.open(img_bin) #PILで読み込む
    pil_img.show()


def plusStrToNum(*str):
    """
        引数の文字列すべてを小数に変換し、加算した結果を返却する.
        なおfloatに変換できない文字列は数値「0」とみなす
    """
    target = []
    for s in str:
        try:
            target.append(float(s))
        except:
            target.append(0)
            
    result = 0
    for t in target:
        result += t
    return result


class pycolor:
    """
        ターミナル用出力用.
        色つき文字列の取得: pycolor.paint(str, pycolor.RED), 
        色つきプリント；pycolor.print_red(str)
    """
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    PURPLE = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    END = '\033[0m'
    BOLD = '\038[1m'
    UNDERLINE = '\033[4m'
    INVISIBLE = '\033[08m'
    REVERCE = '\033[07m'
    
    @classmethod
    def paint(self, target: str, color: str) -> str:
        return f"{color}{target}{pycolor.END}"
    
    @classmethod
    def print_red(self, target: str):
        print(pycolor.paint(target, pycolor.RED))
    
    @classmethod
    def print_green(self, target: str):
        print(pycolor.paint(target, pycolor.GREEN))
    
    @classmethod
    def print_yellow(self, target: str):
        print(pycolor.paint(target, pycolor.YELLOW))
    
    @classmethod
    def print_blue(self, target: str):
        print(pycolor.paint(target, pycolor.BLUE))
    
    @classmethod
    def print_cyan(self, target: str):
        print(pycolor.paint(target, pycolor.CYAN))


def log(str, *, color=""):
    """
        ログ出力をターミナルに行う.
        キーワード引数colorの値により、出力時の文字色を変える
    """
    output = f"{datetime.now()} : {str}"
    if color == "blue":
        pycolor.print_blue(output)
    elif color == "green":
        pycolor.print_green(output)
    elif color == "cyan":
        pycolor.print_cyan(output)
    elif color == "yellow":
        pycolor.print_yellow(output)
    else:
        print(output)


def read():
    """
        スプレッドシートを読み取り、応答をdictで返却する.
        なお応答は以下の形式.
        {
            "ah_id":"xxxxx@gmail.com",
            "ah_pass":"xxxxx",
            "mz_id":"xxxxxx@gmail.com",
            "mz_pass":"xxxxx",
            "mj_id":"dodonpaxp@gmail.com",
            "mj_pass":"xxxxxx",
            "domain":{
                "row5":"xxxx.net",
            }
                "row6":"xxxxx.com"
        }
    """
    log("スプレッドシートから情報を取得します")
    url_body = __ssurl__
    url_param = "?mode=0"
    url = url_body + url_param
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"
    }
    log(f"通信先URL: {url}")
    res = requests.get(url, headers=headers, verify=True)

    if res.status_code is not 200:
        log("通信失敗")
        return None

    log("通信成功")
    log(f"取得情報：{res.text}")
    dictionary = json.loads(res.text)
    return dictionary


def get_target_list(res: dict) -> list:
    """
        調査対象の行番号とドメイン名のタプルをリストで取得する
        row, domain :: int, str
    """
    domain_list = res.get("domain")
    result_list = []
    for key in domain_list:
        row = key[3:]
        domain = domain_list.get(key)
        result_list.append((int(row), domain))
    return result_list


def write(row, domain, ahs_list, moz_list, maj_list, way_list):
    """
        Ahrefs, Moz, Majestic, Waybackで調査したドメインの情報をスプレッドシートに書き込むようGASサーバに命令する
        なお、書き込みを行うスプレッドシートの構成は以下の通り
                	Ahrefs					                  Moz			         	Majestic				                                                   	Wayback		
        DomainName	UR	DR	Governmental	教育	目視確認用	PA	DA	MozRank	目視確認用	TF	CF(被リンクの量)	4total	6total	目視確認用_Majestic_URL	 運用開始年月	空白年	目視確認用_wayback_URL
        
        ---- 補足 ----
        4total = UR + DR + TF + CF
        6total = 4total + PA + DA
    """
    url_body = __ssurl__

    # 4total, 6totalの算出
    total4 = plusStrToNum(ahs_list[0], ahs_list[1], maj_list[0], maj_list[1])
    total6 = total4 + plusStrToNum(moz_list[0], moz_list[1])

    url_param = f"?mode=1&row={row}&val=__a::{domain}__,__b::{ahs_list[0]}__,__c::{ahs_list[1]}__,__d::{ahs_list[2]}__,__e::{ahs_list[3]}__,__f::{ahs_list[4]}__,__g::{moz_list[0]}__,__h::{moz_list[1]}__,__i::{moz_list[2]}__,__j::{moz_list[3]}__,__k::{maj_list[0]}__l::{maj_list[1]}__,__m::{total4}__,__n::{total6}__,__o::{maj_list[2]}__,__p::{way_list[0]}__,__q::{way_list[1]}__,__r::{way_list[2]}__"
    url = url_body + url_param
    log(f"{domain}調査結果_ss連携URL：{url}")
    res = requests.get(url)
    log(f"書き込み完了：{res.text}")


class AhrefsScraper:
    """
        指定ドメインについてAhrefsにアクセスして以下を取得する.
        UR, DR, Governmental, 教育, 目視確認用リンク
    """
    def __init__(self, id, password, *, posi_y=0, headless=False):
        self.id = id
        self.password = password
        self._options = Options()
        self._options.binary_location = __chrome_exec_path__
        headless and self._options.add_argument("--headless")
        self._options.add_argument('--user-agent=Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30')
        self.driver = webdriver.Chrome(options=self._options, executable_path=__chrome_driver_path__)
        self.driver.set_window_position(0, 0+posi_y)
        self.driver.set_window_size(200, 400)
        self.wait = WebDriverWait(self.driver, 10)

    def _waitAndGo(self, css, index, send=None):
        """
           対象が表示されるまで待機し、キーを送信する.
           対象はCSSセレクタとインデックスで指定し、キー送信後これを返却する.
           なお、sendが存在しない場合はsend_keys()を実行しない.
        """
        target = self.wait.until(
            expected_conditions.visibility_of_all_elements_located(
                (By.CSS_SELECTOR, css)
            )
        )[index]
        send and target.send_keys(send)
        return target

    def login(self):
        url = "https://ahrefs.com/user/login"
        self.driver.get(url)
        time.sleep(5)
        self.driver.find_element_by_id("email_input").send_keys(self.id)
        self.driver.find_element_by_css_selector("[name=password]").send_keys(self.password)
        self.driver.find_element_by_css_selector("[value='Sign in']").send_keys(Keys.ENTER)
        time.sleep(1)

    def scrape(self, domain):
        before = time.time()
        log(f"ahrefsスクレイピング開始（{domain}）", color="blue")
        self.driver.get(f"https://ahrefs.com/site-explorer/overview/v2/subdomains/live?target={domain}")
        self._waitAndGo(
            "#UrlRatingContainer span, "
            "#DomainRatingContainer span, "
            "#ReferringDomainsStatsContainer tr+tr+tr a, "
            "#ReferringDomainsStatsContainer tr+tr+tr+tr a", 
            0)
        time.sleep(0.5)

        ur = None
        try:
            ur = self.driver.find_element_by_css_selector("#UrlRatingContainer span").text
        except:
            ur = "-"       
        dr = None
        try:
            dr = self.driver.find_element_by_css_selector("#DomainRatingContainer span").text
        except:
            dr = "-"
        gov = None
        try:
            gov = self.driver.find_element_by_css_selector("#ReferringDomainsStatsContainer tr+tr+tr a").text
        except:
            gov = "-"
        edu = None
        try:
            edu = self.driver.find_element_by_css_selector("#ReferringDomainsStatsContainer tr+tr+tr+tr a").text
        except:
            edu = "-"

        link_on_sheet = urllib.parse.quote(f'=HYPERLINK("{self.driver.current_url}", "Ahrefs")')
        after = time.time()
        log(f"ahrefsスクレイピング終了（{domain}）", color="blue")
        log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="blue")
        log("---- 取得結果 ----", color="blue")
        log(f"UR: {ur}, DR: {dr}, 教育: {gov}", color="blue")
        return [ur, dr, gov, edu, link_on_sheet]

    def close(self):
        self.driver.get("https://ahrefs.com/user/logout")
        self.driver.close()
        log("Ahrefs用Chromeをクローズしました.")


class MozScraper:
    """
        Mozで指定のドメインを調査する
        調査対象：PA, DA, MozRank, 目視確認用
    """
    def __init__(self, id, password, *, posi_y=0, headless=False):
        self.api_id, self.api_key = get_keys_for_moz_api()
        if self.api_id and self.api_key:
            """
                Moz APIで調査する場合は初期処理ここまで
            """
            return
        self.id = id
        self.password = password
        self._options = Options()
        self._options.binary_location = __chrome_exec_path__
        self.__isHeadless__ = headless
        # mozbarの導入(非ヘッドレスモード時のみ)
        headless or self._options.add_extension(f"{__current__}/mozbar.crx")
        # ヘッドレスモード
        headless and self._options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=self._options, executable_path=__chrome_driver_path__)
        self.driver.set_window_position(200, 0+posi_y)
        self.driver.set_window_size(200, 400)
        self.wait = WebDriverWait(self.driver, 10)

    def _is_ok(self, url):
        """
            urlの通信結果を判定する
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"
        }
        res = None
        try:
            res = requests.head(url, headers=headers, verify=False)
        except requests.exceptions.ConnectionError as e:
            log("通信失敗（該当ページが存在しない可能性があります）", color="yellow")
            log(f"エラー詳細：{e}", color="yellow")
            return False
        else:
            if res.status_code is not 200:
                log(f"通信異常（{res.status_code}）", color="yellow")
                return False
            else:
                log("通信成功", color="yellow")
                return True

    def _waitAndGo(self, css, index, send=None):
        """
           対象が表示されるまで待機し、キーを送信する.
           対象はCSSセレクタとインデックスで指定し、キー送信後これを返却する.
           なお、sendが存在しない場合はsend_keys()を実行しない.
        """
        target = self.wait.until(
            expected_conditions.visibility_of_all_elements_located(
                (By.CSS_SELECTOR, css)
            )
        )[index]
        send and target.send_keys(send)
        return target

    def login(self):
        if self.api_id and self.api_key:
            """
                Moz APIで調査する場合はログイン不要
            """
            return
        
        url = "https://moz.com/login"
        
        self.driver.get(url)
        if self.driver.current_url == url:
            self._waitAndGo(".forge-form-control", 0, self.id)
            self.driver.find_elements_by_css_selector(".forge-form-control")[1].send_keys(self.password)
            self._waitAndGo("[data-fieldname=submit]", 0, Keys.ENTER)
            time.sleep(1)
        self.driver.get("https://analytics.moz.com/link-explorer")
        time.sleep(1)
        try:
            self._waitAndGo(".indented a", 1).click()
        except:
            pass
        r = re.search("link-explorer", self.driver.current_url)
        if not (r and r.group(0)):
            self.login()

    def scrape(self, domain, *, non_mozbar=False):
        before = time.time()
        log(f"mozスクレイピング開始（{domain}）", color="yellow")
        url = f"https://{domain}"
        link_on_sheet = urllib.parse.quote(f'=HYPERLINK("https://analytics.moz.com/pro/link-explorer/overview?site={domain}&target=domain","Moz")')
        mozRank = "-" #現在取得不可のため未実装
        if self.api_id and self.api_key:
            """
                Moz APIでの調査を行う.
                PA: upa
                DA: pda
            """
            log("MozAPIで調査を行います.", color="yellow")
            moz_id = self.api_id
            moz_key = self.api_key
            client = Mozscape(moz_id, moz_key)
            mozMetrics = client.urlMetrics(domain)
            PA = mozMetrics.get("upa")
            DA = mozMetrics.get("pda")

            if PA:
                PA = f"{PA}"
            else:
                PA = "-"
            if DA:
                DA = f"{DA}"
            else:
                DA = "-"

            after = time.time()
            log(f"mozスクレイピング終了（{domain}）", color="yellow")
            log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="yellow")
            log("---- 取得結果 ----", color="yellow")
            log(f"DA: {DA}, PA: {PA}", color="yellow")
            return [PA, DA, mozRank, link_on_sheet]

        elif not non_mozbar and not self.__isHeadless__ and self._is_ok(url):
            log("moz_api.txtを読み取れませんでした。MozBarで調査を行います.", color="yellow")
            self.driver.execute_script("window.open()") #make new tab
            self.driver.switch_to.window(self.driver.window_handles[1]) #switch new tab
            self.driver.get(url)
            iframe = self._waitAndGo("#mozbar-wGA7MhRhQ3WS", 0)
            self.driver.switch_to_frame(iframe)
            PA = self._waitAndGo(".title", 0).text[4:]
            DA = self._waitAndGo(".title", 1).text[4:]
            self.driver.switch_to_default_content()
            after = time.time()
            log(f"mozスクレイピング終了（{domain}）", color="yellow")
            log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="yellow")
            log("---- 取得結果 ----", color="yellow")
            log(f"DA: {DA}, PA: {PA}", color="yellow")
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0]) #switch original tab
            return [PA, DA, mozRank, link_on_sheet]

        else:
            log("linkExplorerで調査を行います.", color="yellow")
            search_input = self._waitAndGo(".search-input", 0)

            for i in range(len(search_input.get_attribute("value"))):
                search_input.send_keys(Keys.BACK_SPACE)

            search_input.send_keys(domain)
            search_input.send_keys(Keys.ENTER)
            DA = self._waitAndGo(".animation-value", 0).text
            PA = self.driver.find_elements_by_css_selector(".animation-value")[1].text
            after = time.time()
            log(f"mozスクレイピング終了（{domain}）", color="yellow")
            log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="yellow")
            log("---- 取得結果 ----", color="yellow")
            log(f"DA: {DA}, PA: {PA}", color="yellow")
            return [PA, DA, mozRank, link_on_sheet]

    def close(self):
        if self.api_id and self.api_key:
            """
                Moz APIで調査する場合はクローズ不要
            """
            return
        
        self.driver.get("https://moz.com/logout")
        self.driver.close()
        log("Moz用Chromeをクローズしました.")


class MajesticScraper:
    """
        Majesticで指定のドメインを調査する
        調査対象：TF(10以上ぐらい）	CF(被リンクの量) 目視確認用リンク
    """
    def __init__(self, id, password, *, posi_y=0, headless=False):
        self.id = id
        self.password = password
        self._options = Options()
        self._options.binary_location = __chrome_exec_path__
        headless and self._options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=self._options, executable_path=__chrome_driver_path__)
        self.driver.set_window_position(400, 0+posi_y)
        self.driver.set_window_size(200, 400)
        self.wait = WebDriverWait(self.driver, 5)

    def _waitAndGo(self, css, index, send=None):
        """
           対象が表示されるまで待機し、キーを送信する.
           対象はCSSセレクタとインデックスで指定し、キー送信後これを返却する.
           なお、sendが存在しない場合はsend_keys()を実行しない.
        """
        target = self.wait.until(
            expected_conditions.visibility_of_all_elements_located(
                (By.CSS_SELECTOR, css)
            )
        )[index]
        send and target.send_keys(send)
        return target

    def login(self):
        """
            ログインを行い、以下のURLに遷移する.
            https://ja.majestic.com/account#my-campaigns-tab
        """
        url = "https://ja.majestic.com/account/login"
        self.driver.get(url)

        code = ""
        if os.name == "posix":  # Mac or Linuxの場合
            ActionChains(self.driver).move_to_element(
                self.driver.find_element_by_css_selector("[alt=captcha]")
            )
            png = self.driver.find_element_by_css_selector('[alt="captcha"]').screenshot_as_png
            open_png(png)
            code = input("表示された認証コードをターミナルに入力してください（入力後、画像ウィンドウは閉じて大丈夫です.） >>> ")

        else:  # Windowsの場合
            code = input("Majesticのログイン画面に表示された認証コードをターミナルに入力してください（入力後、画像ウィンドウは閉じて大丈夫です.） >>> ")

        self.driver.find_element_by_css_selector("[name=EmailAddress]").send_keys(self.id)
        self.driver.find_element_by_css_selector("[name=Password]").send_keys(self.password)
        self.driver.find_element_by_css_selector("[name=Captcha]").send_keys(code)
        self.driver.find_element_by_css_selector("[type=submit]").send_keys(Keys.ENTER)
        time.sleep(1)

        if self.driver.current_url == "https://ja.majestic.com/account/login":
            self.driver.find_element_by_css_selector('[name="Password"]').send_keys(self.password)
            self.driver.find_element_by_css_selector('[name="Password"]').send_keys(Keys.ENTER)

    def scrape(self, domain):
        before = time.time()
        log(f"majesticスクレイピング開始（{domain}）", color="green")
        search = self._waitAndGo("#search_text", 0)
        
        for i in range(len(search.get_attribute("value"))):
            search.send_keys(Keys.BACK_SPACE)

        search.send_keys(domain)
        search.send_keys(Keys.ENTER)
        TF = None
        CF = None
        self._waitAndGo(".citation_flow_innertext", 0)
        citation_flow_list = self.driver.find_elements_by_css_selector(".citation_flow_innertext")

        if len(citation_flow_list) > 1:
            """
                TFがゼロのとき.
                TF, CF共にクラス名「citation_flow_innertext」になっている.
            """
            TF = citation_flow_list[0].text
            CF = citation_flow_list[1].text

        else:
            """
                TFが1以上のとき.
                TF, CFのクラス名が別
            """
            TF = self._waitAndGo(".trust_flow_innertext", 0).text
            CF = citation_flow_list[0].text

        link_on_sheet = urllib.parse.quote(f'=HYPERLINK("{self.driver.current_url}", "Majestic")')
        after = time.time()
        log(f"majesticスクレイピング終了（{domain}）", color="green")
        log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="green")
        log("---- 取得結果 ----", color="green")
        log(f"TF: {TF}, CF: {CF}", color="green")
        return [TF, CF, link_on_sheet]

    def close(self):
        self.driver.get("https://ja.majestic.com/?logout=1")
        self.driver.close()
        log("Majestic用Chromeをクローズしました.")


def scrape_wayback(domain):
    """
        Wayback Machineでの調査を行う.
        調査対象：運用開始, 空白年, 目視確認用のwayback_URL
    """
    before = time.time()
    log(f"waybackスクレイピング開始（{domain}）", color="cyan")
    start_check_url = f"https://archive.org/wayback/available?url={domain}&timestamp=19700101"
    last_check_url = f"https://archive.org/wayback/available?url={domain}"
    headers = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"
    }
    g1 = re.search('"archived_snapshots":.+?"timestamp": "([0-9]+?)"', requests.get(start_check_url, headers=headers).text)
    g2 = re.search('"archived_snapshots":.+?"timestamp": "([0-9]+?)"', requests.get(last_check_url, headers=headers).text)
    start = g1 and g1.group(1)[:6] or "-" 
    end = g2 and f"{g2.group(1)[:6]}-" or "-"
    link_on_sheet = start and urllib.parse.quote(f'=HYPERLINK("https://web.archive.org/web/*/{domain}","WayBack")') or "-"
    after = time.time()
    log(f"waybackスクレイピング終了（{domain}）", color="cyan")
    log(f"所要時間：{'{:.3}'.format(after-before)}秒", color="cyan")
    log("---- 取得結果 ----", color="cyan")
    log(f"運用開始: {start}, 空白年: {end}", color="cyan")
    return [start, end, link_on_sheet]


def all_login(ahs_scraper, moz_scraper, maj_scraper):
    """
        各スクレイパのログインを行う
    """
    log("全サービスログイン処理開始")
    t1 = threading.Thread(target=maj_scraper.login)
    t2 = threading.Thread(target=ahs_scraper.login)
    t3 = threading.Thread(target=moz_scraper.login)
    t1.start()
    t2.start()
    t3.start()
    t1.join()
    t2.join()
    t3.join()
    log("全サービスログイン完了")


def all_login_for_multi(ahs_scraper, moz_scraper, maj_scraper):
    """
        各スクレイパのログインを行う（Moz用スクレイパを除く ※MozAPIによる調査用）
    """
    log("全サービスログイン処理開始")
    maj_scraper.login()
    t2 = threading.Thread(target=ahs_scraper.login)
    t3 = threading.Thread(target=moz_scraper.login)
    t2.start()
    t3.start()
    t2.join()
    t3.join()
    log("全サービスログイン完了")


def scrape_by_domain(row, domain, ahs_scraper, moz_scraper, maj_scraper):
    """
        指定したドメインについてAhrefs, Moz, Majestic, WaybackMachineでの調査結果を返却する
    """
    r1 = []
    r2 = []
    r3 = []
    r4 = []
    thread1 = threading.Thread(target=lambda:r1.extend(ahs_scraper.scrape(domain)))
    thread2 = threading.Thread(target=lambda:r2.extend(moz_scraper.scrape(domain, non_mozbar=True)))
    thread3 = threading.Thread(target=lambda:r3.extend(maj_scraper.scrape(domain)))
    thread4 = threading.Thread(target=lambda:r4.extend(scrape_wayback(domain)))
    thread1.start()
    thread2.start()
    thread3.start()
    thread4.start()
    thread1.join()
    thread2.join()
    thread3.join()
    thread4.join()
    return row, domain, r1, r2, r3, r4


def app(headless=False):
    """
        メイン処理を実行する.
        （スプレッドシートから調査対象ドメインを読み取り、各ドメインについての調査を行う）
    """
    ss_dict = read()
    target_list = get_target_list(ss_dict)
    if len(target_list) is 0:
        input("調査対象が存在しません.ツールの実行を終了します(click Enter.) >>> ")
        return

    ahsS = AhrefsScraper(ss_dict.get("ah_id"), ss_dict.get("ah_pass"), headless=headless)
    mozS = MozScraper(ss_dict.get("mz_id"), ss_dict.get("mz_pass"), headless=headless)
    majS = MajesticScraper(ss_dict.get("mj_id"), ss_dict.get("mj_pass"), headless=headless)

    all_login(ahsS, mozS, majS)

    before = time.time()

    for tuple in target_list:
        row, domain = tuple
        (
            row, 
            domain, 
            ahs_list, 
            moz_list, 
            maj_list, 
            way_list
        ) = scrape_by_domain(row, domain, ahsS, mozS, majS)
        threading.Thread(target=lambda:write(
            row, domain, ahs_list, moz_list, maj_list, way_list
        )).start()

    after = time.time()
    e = '{:.3}'.format(int(after-before)/len(target_list))
    log("====== スクレイピングに要した時間 ======")
    log(f"{int(after-before)}秒 / {len(target_list)}ドメイン")
    log(f"1ドメインにつき、およそ{e}秒")

    ahsS.close()
    mozS.close()
    majS.close()

    input("ツールの実行が完了しました")


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        print(e)
        input("error occured.")

