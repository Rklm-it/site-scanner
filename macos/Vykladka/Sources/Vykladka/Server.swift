import Foundation

/// Всё, что приложение делает с сервером прототипов.
struct Server {

    let nastroyki: Nastroyki
    var ssh: Ssh { Ssh(nastroyki: nastroyki) }

    enum Beda: LocalizedError {
        case malo_mesta(nuzhno: Int64, est: Int64)
        case konfigNeSobralsya(String)
        case netPredydushchey

        var errorDescription: String? {
            switch self {
            case let .malo_mesta(nuzhno, est):
                let n = ByteCountFormatter.string(fromByteCount: nuzhno, countStyle: .file)
                let e = ByteCountFormatter.string(fromByteCount: est, countStyle: .file)
                return "На сервере мало места: нужно около \(n), свободно \(e). Удалите ненужный прототип или почистите образы (docker image prune -f)."
            case let .konfigNeSobralsya(vyvod):
                return "Caddy не принял конфиг, домен НЕ включён — вернул как было.\n\n\(vyvod)"
            case .netPredydushchey:
                return "Предыдущей версии на сервере нет — откатывать не к чему."
            }
        }
    }

    struct SostoyanieServera {
        var vsegoMesta: Int64 = 0
        var svobodno: Int64 = 0
        var caddy: String = ""
        var razmerySaytov: [String: Int64] = [:]

        var svobodnoTekstom: String { ByteCountFormatter.string(fromByteCount: svobodno, countStyle: .file) }
        var vsegoTekstom: String { ByteCountFormatter.string(fromByteCount: vsegoMesta, countStyle: .file) }
        var caddyZhiv: Bool { caddy.lowercased().contains("up") }
    }

    // MARK: - Чтение состояния

    func spisokSaytov() throws -> [Sayt] {
        let komanda = """
        for f in \(Kavychki.odinarnye(nastroyki.papkaBlokov))/*.caddy; do
            [ -e "$f" ] || continue
            echo "=== $(basename "$f") ==="
            cat "$f"
        done
        """
        let rezultat = try ssh.vypolnit(komanda)
        return Bloki.razobrat(rezultat.tekst)
    }

    func sostoyanie() throws -> SostoyanieServera {
        let komanda = """
        echo '=== mesto ==='
        df -Pk \(Kavychki.odinarnye(nastroyki.papkaSaytov)) | tail -1
        echo '=== papki ==='
        du -sk \(Kavychki.odinarnye(nastroyki.papkaSaytov))/* 2>/dev/null || true
        echo '=== caddy ==='
        docker ps --filter 'name=caddy' --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'docker недоступен'
        """
        let tekst = try ssh.vypolnit(komanda).tekst
        var sostoyanie = SostoyanieServera()
        var razdel = ""

        for stroka in tekst.split(separator: "\n") {
            let s = String(stroka).trimmingCharacters(in: .whitespaces)
            if s.hasPrefix("=== ") { razdel = s.replacingOccurrences(of: "=", with: "").trimmingCharacters(in: .whitespaces); continue }
            guard !s.isEmpty else { continue }

            switch razdel {
            case "mesto":
                // df -Pk: устройство, всего, занято, свободно, %, точка
                let polya = s.split(separator: " ", omittingEmptySubsequences: true).map(String.init)
                if polya.count >= 4, let vsego = Int64(polya[1]), let svobodno = Int64(polya[3]) {
                    sostoyanie.vsegoMesta = vsego * 1024
                    sostoyanie.svobodno = svobodno * 1024
                }
            case "papki":
                let polya = s.split(separator: "\t", omittingEmptySubsequences: true).map(String.init)
                if polya.count >= 2, let kilobayt = Int64(polya[0].trimmingCharacters(in: .whitespaces)) {
                    let imya = (polya[1] as NSString).lastPathComponent
                    sostoyanie.razmerySaytov[imya] = kilobayt * 1024
                }
            case "caddy":
                sostoyanie.caddy = sostoyanie.caddy.isEmpty ? s : sostoyanie.caddy + "; " + s
            default:
                break
            }
        }
        return sostoyanie
    }

    // MARK: - Выкладка

    /// Полный цикл: упаковать, залить рядом, переставить, прописать домен,
    /// проверить конфиг и перечитать Caddy.
    ///
    /// Заливка идёт в соседнюю папку и переставляется переименованием, а не
    /// поверх живой. Иначе полминуты, пока распаковывается архив, клиент видит
    /// наполовину собранный сайт — и, по закону подлости, именно в эту минуту
    /// он ссылку и откроет.
    func vylozhit(
        imya: String,
        domen: String,
        razbor: Arhiv.Razbor,
        pisatBlok: Bool,
        odnostranichnik: Bool,
        shag: @escaping (String) -> Void
    ) throws {
        let papka = "\(nastroyki.papkaSaytov)/\(imya)"
        let blokFayl = "\(nastroyki.papkaBlokov)/\(imya).caddy"

        shag("Проверяю место на сервере…")
        let mesto = try sostoyanie()
        let nuzhno = Int64(Double(razbor.razmer) * 1.3)
        if mesto.svobodno > 0 && mesto.svobodno < nuzhno {
            throw Beda.malo_mesta(nuzhno: nuzhno, est: mesto.svobodno)
        }

        shag("Пакую \(razbor.faylov) файлов (\(razbor.razmerTekstom))…")
        let arhiv = try Arhiv.upakovat(razbor.korn)
        defer { try? FileManager.default.removeItem(at: arhiv) }

        shag("Заливаю на сервер…")
        let zalivka = """
        set -e
        d=\(Kavychki.odinarnye(papka))
        rm -rf "$d.novoe"
        mkdir -p "$d.novoe"
        tar xzf - -C "$d.novoe"
        """
        try ssh.vypolnit(zalivka, vhodFayl: arhiv)

        shag("Переставляю версию…")
        let perestanovka = """
        set -e
        d=\(Kavychki.odinarnye(papka))
        rm -rf "$d.staroe"
        if [ -d "$d" ]; then mv "$d" "$d.staroe"; fi
        mv "$d.novoe" "$d"
        """
        try ssh.vypolnit(perestanovka)

        if pisatBlok {
            shag("Прописываю домен в Caddy…")
            let staryyBlok = try? ssh.poprobovat("cat \(Kavychki.odinarnye(blokFayl))")
            let byloRanshe = (staryyBlok?.udalos == true) ? staryyBlok?.tekst : nil

            let novyy = Bloki.sobrat(
                imya: imya,
                domen: domen,
                statichnyePapki: razbor.statichnyePapki,
                odnostranichnik: odnostranichnik
            )
            try ssh.vypolnit("cat > \(Kavychki.odinarnye(blokFayl))", vhod: Data(novyy.utf8))

            shag("Проверяю конфиг…")
            let proverka = try ssh.poprobovat(vKompose("caddy validate --config /etc/caddy/Caddyfile"))
            if !proverka.udalos {
                // Откатываем блок: сломанный конфиг гасит ВСЕ сайты сразу, а не
                // только этот. Пусть лучше новый домен не заведётся.
                if let byloRanshe {
                    try? ssh.vypolnit("cat > \(Kavychki.odinarnye(blokFayl))", vhod: Data(byloRanshe.utf8))
                } else {
                    try? ssh.vypolnit("rm -f \(Kavychki.odinarnye(blokFayl))")
                }
                throw Beda.konfigNeSobralsya(proverka.oshibka + proverka.tekst)
            }

            shag("Перечитываю Caddy…")
            try ssh.vypolnit(vKompose("caddy reload --config /etc/caddy/Caddyfile"))
        }

        shag("Готово.")
    }

    /// Вернуть предыдущую версию. Меняет местами текущую и «.staroe».
    func otkatit(imya: String) throws {
        let papka = "\(nastroyki.papkaSaytov)/\(imya)"
        let rezultat = try ssh.poprobovat("""
        set -e
        d=\(Kavychki.odinarnye(papka))
        if [ ! -d "$d.staroe" ]; then exit 3; fi
        rm -rf "$d.obmen"
        mv "$d" "$d.obmen"
        mv "$d.staroe" "$d"
        mv "$d.obmen" "$d.staroe"
        """)
        if rezultat.kod == 3 { throw Beda.netPredydushchey }
        guard rezultat.udalos else {
            throw Ssh.Beda.komandaUpala("откат", rezultat.kod, rezultat.oshibka)
        }
    }

    /// Убрать сайт: снять домен, перечитать Caddy, удалить файлы.
    ///
    /// Порядок именно такой: сначала домен перестаёт отвечать, потом исчезают
    /// файлы. Наоборот было бы хуже — Caddy какое-то время отдавал бы 404 по
    /// живому домену и продолжал держать на него сертификат.
    ///
    /// Лог посещений НЕ удаляется: это единственная история по сайту на
    /// сервере, и весит она мегабайты. Своя копия у приложения тоже остаётся.
    func udalit(sayt: Sayt, shag: @escaping (String) -> Void) throws {
        let papka = "\(nastroyki.papkaSaytov)/\(sayt.imya)"
        let blokFayl = "\(nastroyki.papkaBlokov)/\(sayt.faylBloka)"

        shag("Снимаю домен…")
        try ssh.vypolnit("rm -f \(Kavychki.odinarnye(blokFayl))")

        shag("Проверяю конфиг…")
        let proverka = try ssh.poprobovat(vKompose("caddy validate --config /etc/caddy/Caddyfile"))
        guard proverka.udalos else {
            throw Beda.konfigNeSobralsya(proverka.oshibka + proverka.tekst)
        }

        shag("Перечитываю Caddy…")
        try ssh.vypolnit(vKompose("caddy reload --config /etc/caddy/Caddyfile"))

        shag("Удаляю файлы…")
        try ssh.vypolnit("""
        d=\(Kavychki.odinarnye(papka))
        rm -rf "$d" "$d.staroe" "$d.novoe" "$d.obmen"
        """)

        shag("Готово.")
    }

    /// Перечитать Caddy руками — на случай, когда блок правили без приложения.
    func perechitat() throws {
        let proverka = try ssh.poprobovat(vKompose("caddy validate --config /etc/caddy/Caddyfile"))
        guard proverka.udalos else { throw Beda.konfigNeSobralsya(proverka.oshibka + proverka.tekst) }
        try ssh.vypolnit(vKompose("caddy reload --config /etc/caddy/Caddyfile"))
    }

    private func vKompose(_ komanda: String) -> String {
        "cd \(Kavychki.odinarnye(nastroyki.papkaCompose)) && docker compose exec -T caddy \(komanda)"
    }
}
