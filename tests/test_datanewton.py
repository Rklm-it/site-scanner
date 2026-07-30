"""Тесты обогащения оборотом через DataNewton (без сети)."""

from scanner import datanewton

# Урезанный ответ /v1/finance: дерево fin_results со строкой 2110 «Выручка».
FINANCE_JSON = {
    "balances": {"okud": "0710001"},
    "fin_results": {
        "name": "Отчёт о финрезультатах", "code": "0710002",
        "years": [2022, 2023, 2024],
        "childrenMap": {
            "Выручка": {"name": "Выручка", "code": "2110",
                        "sum": {"2022": 50000.0, "2023": 60000.0, "2024": 72000.0}, "row_num": 1},
            "Прибыль": {"name": "Чистая прибыль", "code": "2400",
                        "sum": {"2024": 5000.0}, "row_num": 9},
        },
    },
}


class FakeResp:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _sess(resp):
    class S:
        def get(self, *a, **k):
            return resp
    return S()


def test_latest_revenue_takes_newest_year_in_rubles():
    # 72000 тыс.руб за 2024 → 72 000 000 руб
    assert datanewton._latest_revenue(FINANCE_JSON) == 72_000_000


def test_latest_revenue_none_when_no_2110():
    assert datanewton._latest_revenue({"fin_results": {"code": "0710002"}}) is None


def test_revenue_by_inn_ok():
    rev, err = datanewton.revenue_by_inn("7707083893", token="k",
                                         session=_sess(FakeResp(200, FINANCE_JSON)))
    assert rev == 72_000_000 and err is None


def test_revenue_by_inn_bad_key():
    rev, err = datanewton.revenue_by_inn("7707083893", token="k",
                                         session=_sess(FakeResp(403)))
    assert rev is None and "403" in err


def test_revenue_by_inn_no_data_is_not_error():
    rev, err = datanewton.revenue_by_inn("7707083893", token="k",
                                         session=_sess(FakeResp(200, {"fin_results": {}})))
    assert rev is None and err is None


def test_revenue_by_inn_skips_without_inn_or_token():
    assert datanewton.revenue_by_inn("", token="k") == (None, None)
    assert datanewton.revenue_by_inn("123", token=None) == (None, None)
