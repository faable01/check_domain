/**
 * 以下の２機能をもったサーバとしてGASを機能させる。
 * 1. ユーザ情報、調査対象ドメインの読み取り
 * 2. 調査結果の書き込み
 * 
 * 本ツールのメイン機能である「ドメインの調査」はPython側で行う.
 * GAS側では、Python側の調査結果をもとにスプレッドシートに書き込みを行う
 */

var ss = SpreadsheetApp.getActiveSpreadsheet()
var main = ss.getSheetByName("main")
var idpass = ss.getSheetByName("ID_PASS")

// リクエストの格納場所
var REQ = {}

/**
 * modeパラメータ：書き込み（1）か読み取り(0)かを指定する
 *　rowパラメータ：書き込み行を指定、無ければデータの存在する末尾の次の行に書き込む
 * valパラメータ：書き込み列を以下の記法で指定
 * -- val記法 --
 * [“__a：:値__”, “__b:：値__”, “__c:：：値__”, …]
 */
function doGet(e) {

    // リクエストパラメータの取得
    REQ.mode = e.parameter.mode
    REQ.row = e.parameter.row || main.getDataRange().getValues().length + 1
    REQ.val = e.parameter.val

    if (REQ.mode == "0") { // 読み取りモード
        return this.read()
    } else if (REQ.mode == "1") { // 書き込みモード
        return this.write()
    }
}

/**
 * 返却値の形式：
 * {"ah_id":"aaaa@aaa.co.jp","ah_pass":"bbbbbb","mz_id":"cccc@gmail.com","mz_pass":"dddddd","mj_id":"eeee@gmail.com","mj_pass":"fffff","domain":{"row5":"foo.com","row6":"hooo.net"}}
 */
function read() {

    var range = idpass.getRange(1, 1, 13, 2)
    var values = range.getValues()

    Logger.log(values)

    var result = {}

    // Ahrefsのid, pass
    result.ah_id = values[1][1]
    result.ah_pass = values[2][1]

    // Mozのid, pass
    result.mz_id = values[6][1]
    result.mz_pass = values[7][1]

    // Majesticのid, pass
    result.mj_id = values[11][1]
    result.mj_pass = values[12][1]

    // 未調査ドメインの取得(1列目に値があり、かつ2列目に値がない行の1列目を取得)
    result.domain = {}
    var d_values = main.getDataRange().getValues()
    var row_number = 0
    d_values.forEach(function (row) {
        row_number++
        if (row[0] && !row[1]) {
            result.domain["row" + row_number] = row[0]
        }
    })

    var out = ContentService.createTextOutput();

    //Mime TypeをJSONに設定
    out.setMimeType(ContentService.MimeType.JSON);

    //JSONテキストをセットする
    out.setContent(JSON.stringify(result));

    return out;
}

function write() {
    // 各列に書き込む値の取得
    VAL = {}
    VAL.a = REQ.val.match(/__a::(.*?)__/)[1]
    VAL.b = REQ.val.match(/__b::(.*?)__/)[1]
    VAL.c = REQ.val.match(/__c::(.*?)__/)[1]
    VAL.d = REQ.val.match(/__d::(.*?)__/)[1]
    VAL.e = REQ.val.match(/__e::(.*?)__/)[1]
    VAL.f = decodeURI(REQ.val.match(/__f::(.*?)__/)[1]) // URLデコード必要あり
    VAL.g = REQ.val.match(/__g::(.*?)__/)[1]
    VAL.h = REQ.val.match(/__h::(.*?)__/)[1]
    // mozrank不使用化のため削除
    //VAL.i = REQ.val.match(/__i::(.*?)__/)[1]
    VAL.j = decodeURI(REQ.val.match(/__j::(.*?)__/)[1]) // URLデコード必要あり
    VAL.k = REQ.val.match(/__k::(.*?)__/)[1]
    VAL.l = REQ.val.match(/__l::(.*?)__/)[1]
    VAL.m = REQ.val.match(/__m::(.*?)__/)[1]
    VAL.n = REQ.val.match(/__n::(.*?)__/)[1]
    VAL.o = decodeURI(REQ.val.match(/__o::(.*?)__/)[1]) // URLデコード必要あり
    VAL.p = REQ.val.match(/__p::(.*?)__/)[1]
    VAL.q = REQ.val.match(/__q::(.*?)__/)[1]
    VAL.r = decodeURI(REQ.val.match(/__r::(.*?)__/)[1]) // URLデコード必要ありs

    // リクエストの値に従いスプレッドシートに書き込む
    var target_range = main.getRange(REQ.row, 1, 1, Object.keys(VAL).length)
    target_range.setValues([values(VAL)])

    var out = ContentService.createTextOutput();

    //Mime TypeをJSONに設定
    out.setMimeType(ContentService.MimeType.JSON);

    //JSONテキストをセットする
    var result = { status: "done", data: target_range.getValues() }
    out.setContent(JSON.stringify(result));

    return out
}

/* Object.keys()のvalue版 */
function values(obj) {
    var result = []
    Object.keys(obj).forEach(function (key) {
        var val = obj[key]
        result.push(val)
    })
    return result
}