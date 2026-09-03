import Foundation

/// Куда приложение складывает своё. Всё в одном месте, чтобы не искать по коду.
enum Papki {

    /// ~/Library/Application Support/Vykladka
    static var korn: URL {
        let baza = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let papka = baza.appendingPathComponent("Vykladka", isDirectory: true)
        try? FileManager.default.createDirectory(at: papka, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        return papka
    }

    static var nastroykiFayl: URL { korn.appendingPathComponent("nastroyki.json") }
    static var baza: URL { korn.appendingPathComponent("poseshcheniya.sqlite") }
    static var geoBaza: URL { korn.appendingPathComponent("geo-strany.csv") }

    /// Файлы, которые читает сам ssh, — в домашней папке, а не в Application
    /// Support. Причина не в аккуратности: значение `UserKnownHostsFile` ssh
    /// разбирает как СПИСОК файлов через пробел, поэтому путь
    /// «…/Application Support/Vykladka/known_hosts» распадается на два куска.
    /// Ни один из них не существует, ssh считает ключ сервера неизвестным и
    /// отвечает «No ED25519 host key is known … Host key verification failed» —
    /// при том что файл записан и лежит на месте. Здесь пробелов нет.
    static var sshPapka: URL {
        let dom = FileManager.default.homeDirectoryForCurrentUser
        let papka = dom.appendingPathComponent(".vykladka", isDirectory: true)
        try? FileManager.default.createDirectory(at: papka, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        return papka
    }

    static var izvestnyeHosty: URL { sshPapka.appendingPathComponent("known_hosts") }
    static var klyuchFayl: URL { sshPapka.appendingPathComponent("id_ed25519") }
    static var publichnyyKlyuch: URL { sshPapka.appendingPathComponent("id_ed25519.pub") }

    /// Временная папка приложения: распаковка архивов, файл с паролем на один
    /// вызов. Чистится при каждом запуске — мусор с прошлого раза не нужен.
    static var vremennaya: URL {
        let papka = korn.appendingPathComponent("vremennoe", isDirectory: true)
        try? FileManager.default.createDirectory(at: papka, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        return papka
    }

    static func pochistitVremennoe() {
        let fm = FileManager.default
        guard let soderzhimoe = try? fm.contentsOfDirectory(at: vremennaya,
                                                           includingPropertiesForKeys: nil) else { return }
        for element in soderzhimoe { try? fm.removeItem(at: element) }
    }
}

/// Настройки подключения и путей на сервере.
///
/// Пароль здесь НЕ хранится и храниться не должен: он нужен ровно один раз,
/// чтобы поставить ключ, после чего забывается. Приватный ключ лежит в Связке
/// ключей — см. Klyuchi.swift.
struct Nastroyki: Codable, Equatable {
    var host: String = ""
    var port: Int = 22
    var polzovatel: String = "root"

    /// Куда кладутся сами сайты. Отдаётся Caddy как /srv.
    var papkaSaytov: String = "/root/prototypes-static"
    /// Блоки Caddy, по файлу на сайт.
    var papkaBlokov: String = "/root/caddy-sites"
    /// Логи посещений, по файлу на сайт.
    var papkaLogov: String = "/root/caddy-logs"
    /// Где лежит docker-compose.yml стека прототипов — оттуда перечитывается Caddy.
    var papkaCompose: String = "/root/site-scanner/deploy/prototype"

    /// Отпечаток ключа сервера, подтверждённый хозяином при первом подключении.
    /// Показывается в настройках: сменился — значит либо переустановили сервер,
    /// либо вас слушают.
    var otpechatokServera: String = ""

    /// Подключение уже настроено: ключ поставлен и проверен.
    var podklyucheno: Bool = false

    var opisanie: String {
        let hvost = port == 22 ? "" : ":\(port)"
        return "\(polzovatel)@\(host)\(hvost)"
    }

    static func prochitat() -> Nastroyki {
        guard let dannye = try? Data(contentsOf: Papki.nastroykiFayl),
              let nastroyki = try? JSONDecoder().decode(Nastroyki.self, from: dannye) else {
            return Nastroyki()
        }
        return nastroyki
    }

    func zapisat() {
        let koder = JSONEncoder()
        koder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let dannye = try? koder.encode(self) else { return }
        try? dannye.write(to: Papki.nastroykiFayl, options: .atomic)
    }
}
