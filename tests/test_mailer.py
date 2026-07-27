import pytest

from webapp import mailer


class FakeSMTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.logged = None
        self.sent = []

    def login(self, user, password):
        self.logged = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


CFG = {"host": "smtp.yandex.ru", "port": 465, "user": "me@yandex.ru",
       "password": "app-pass", "from_name": "Иван"}


def test_send_email_builds_and_sends():
    captured = {}

    def factory(host, port):
        s = FakeSMTP(host, port)
        captured["srv"] = s
        return s

    mailer.send_email("client@firma.ru", "Тема", "Тело письма", cfg=CFG, smtp_factory=factory)
    srv = captured["srv"]
    assert srv.host == "smtp.yandex.ru" and srv.port == 465
    assert srv.logged == ("me@yandex.ru", "app-pass")
    msg = srv.sent[0]
    assert msg["To"] == "client@firma.ru"
    assert msg["Subject"] == "Тема"
    assert msg["From"] == "Иван <me@yandex.ru>"
    assert "Тело письма" in msg.get_content()


def test_send_email_requires_config():
    empty = {"host": "", "port": 465, "user": "", "password": "", "from_name": ""}
    with pytest.raises(RuntimeError):
        mailer.send_email("a@b.ru", "s", "b", cfg=empty, smtp_factory=lambda h, p: FakeSMTP(h, p))


def test_send_email_rejects_bad_recipient():
    with pytest.raises(ValueError):
        mailer.send_email("нет-собаки", "s", "b", cfg=CFG, smtp_factory=lambda h, p: FakeSMTP(h, p))
