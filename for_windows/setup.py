# python setup.py bdist_mac でappファイルが作成される
# bdist_mac ではなく build オプションをmacで実行すると、UNIX実行ファイル形式になる（拡張子なし）
# coding: utf-8
# cx_Freeze 用セットアップファイル
 
import sys
from cx_Freeze import setup, Executable
import requests
from multiprocessing import Queue
 
base = None

## GUI=有効, CUI=無効 にする
#if sys.platform == 'win32' : base = 'Win32GUI'
 
# exe にしたい python ファイルを指定
exe = Executable(script = 'check.py', icon = "python_01.ico", base = base)
# セットアップ
setup(
  name = 'ドメイン選別ツール',
  version = '0.1',
  description = 'converter',
  executables = [exe],
  options = {
    "build_exe":{
      "packages": [
        "multiprocessing"
      ],
      "include_files":[
        "idna"
      ],
    }
  }
)
