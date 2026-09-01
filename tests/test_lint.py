"""Проверка на необъявленные имена в коде сервера и движка.

Появился после живого случая: в обработчике отправки части стояло `log.info`,
а логгер в этом модуле называется `_scan_log`. Синтаксис верный, тесты зелёные,
образ собрался — и выгрузка упала на сервере владельца уже после того, как сайт
был скачан, с сообщением «NameError: name 'log' is not defined».

Такие опечатки ловятся статически за секунду, поэтому ловим их здесь, а не на
боевом сервере.
"""

import subprocess
import sys

import pytest

FAJLY = ["webapp/server.py", "scanner/mirror.py", "scanner/relizy.py",
         "tools/vzyat-vygruzku.py"]


def test_net_neobyavlennyh_imyon():
    try:
        import pyflakes  # noqa: F401
    except ImportError:
        pytest.skip("pyflakes не установлен: pip install pyflakes")

    itog = subprocess.run([sys.executable, "-m", "pyflakes", *FAJLY],
                          capture_output=True, text=True)
    # Неиспользуемые импорты в счёт не идут — ловим именно необъявленные имена,
    # то есть то, что падает в бою.
    bedy = [s for s in itog.stdout.splitlines() if "undefined name" in s]
    assert not bedy, "необъявленные имена:\n" + "\n".join(bedy)
