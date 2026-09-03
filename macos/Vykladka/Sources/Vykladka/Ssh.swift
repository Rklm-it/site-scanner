import Foundation

/// Обёртка над системным ssh.
///
/// Ничего своего в протоколе: те же /usr/bin/ssh и ssh-keygen, что и в
/// терминале. Значит поведение предсказуемо, обновления безопасности приходят
/// с macOS, а в проекте нет реализации SSH, которую надо сопровождать.
struct Ssh {

    let nastroyki: Nastroyki

    enum Beda: LocalizedError {
        case netPodklyucheniya
        case komandaUpala(String, Int32, String)
        case hostNeOtvechaet(String)

        var errorDescription: String? {
            switch self {
            case .netPodklyucheniya:
                return "Сервер ещё не подключён — заполните настройки."
            case let .komandaUpala(komanda, kod, oshibka):
                let hvost = oshibka.trimmingCharacters(in: .whitespacesAndNewlines)
                let korotko = komanda.count > 120 ? String(komanda.prefix(120)) + "…" : komanda
                return "Команда на сервере вернула код \(kod):\n\(korotko)\n\n\(hvost)"
            case let .hostNeOtvechaet(adres):
                return "Сервер \(adres) не отвечает или не отдал ключ SSH."
            }
        }
    }

    // MARK: - Опции

    /// Общие опции. StrictHostKeyChecking=yes и свой known_hosts — это и есть
    /// защита от подмены сервера: ключ подтверждён хозяином один раз, дальше
    /// любое расхождение обрывает подключение, а не спрашивает «продолжить?».
    private var bazovyeOpcii: [String] {
        [
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=\(Ssh.putDlyaOpcii(Papki.izvestnyeHosty.path))",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=4",
            "-p", "\(nastroyki.port)"
        ]
    }

    private var opciiKlyucha: [String] {
        [
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-i", Papki.klyuchFayl.path
        ]
    }

    private var adres: String { "\(nastroyki.polzovatel)@\(nastroyki.host)" }

    /// Путь в значении -o. Пробел там означает «следующий файл», поэтому путь
    /// с пробелом надо брать в кавычки — ssh их снимает при разборе. Свои
    /// файлы мы держим в пути без пробелов (см. Papki.sshPapka), но домашняя
    /// папка пользователя может называться как угодно.
    static func putDlyaOpcii(_ put: String) -> String {
        put.rangeOfCharacter(from: .whitespaces) == nil ? put : "\"\(put)\""
    }

    // MARK: - Выполнение

    /// Выполнить команду на сервере. Команда уезжает одной строкой и
    /// выполняется удалённым sh — то есть пишется как обычный скрипт.
    @discardableResult
    func vypolnit(_ komanda: String, vhodFayl: URL? = nil, vhod: Data? = nil) throws -> Zapusk.Rezultat {
        guard !nastroyki.host.isEmpty else { throw Beda.netPodklyucheniya }
        guard Klyuchi.estKlyuch else { throw Klyuchi.Beda.netKlyucha }
        let argumenty = bazovyeOpcii + opciiKlyucha + [adres, komanda]
        let rezultat = try Zapusk.zapustit("/usr/bin/ssh", argumenty, vhod: vhod, vhodFayl: vhodFayl)
        guard rezultat.udalos else {
            throw Beda.komandaUpala(komanda, rezultat.kod, rezultat.oshibka)
        }
        return rezultat
    }

    /// То же, но неуспех — не ошибка: код возврата разбирает вызывающий.
    /// Нужно там, где «нет такого файла» — нормальный ответ.
    func poprobovat(_ komanda: String) throws -> Zapusk.Rezultat {
        guard !nastroyki.host.isEmpty else { throw Beda.netPodklyucheniya }
        guard Klyuchi.estKlyuch else { throw Klyuchi.Beda.netKlyucha }
        let argumenty = bazovyeOpcii + opciiKlyucha + [adres, komanda]
        return try Zapusk.zapustit("/usr/bin/ssh", argumenty)
    }

    func proverit() throws -> Bool {
        let rezultat = try poprobovat("echo vykladka-ok")
        return rezultat.tekst.contains("vykladka-ok")
    }

    // MARK: - Ключ сервера

    /// Спросить у сервера его ключи и посчитать отпечатки, ничего пока не
    /// доверяя. Показываются хозяину: подтвердил — записываем в known_hosts.
    static func sprositKlyuchServera(host: String, port: Int) throws -> (stroki: String, otpechatki: [String]) {
        let rezultat = try Zapusk.zapustit("/usr/bin/ssh-keyscan", ["-T", "10", "-p", "\(port)", host])
        let stroki = rezultat.tekst.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !stroki.isEmpty else { throw Beda.hostNeOtvechaet("\(host):\(port)") }

        let vremennyy = Papki.vremennaya.appendingPathComponent("keyscan-\(UUID().uuidString)")
        try stroki.write(to: vremennyy, atomically: true, encoding: .utf8)
        defer { try? FileManager.default.removeItem(at: vremennyy) }

        let razbor = try Zapusk.zapustit("/usr/bin/ssh-keygen", ["-l", "-f", vremennyy.path])
        let otpechatki = razbor.tekst
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        return (stroki, otpechatki)
    }

    /// Записать подтверждённые ключи сервера в свой known_hosts.
    static func doveritKlyuchu(stroki: String) throws {
        try (stroki + "\n").write(to: Papki.izvestnyeHosty, atomically: true, encoding: .utf8)
        try? FileManager.default.setAttributes([.posixPermissions: 0o600],
                                               ofItemAtPath: Papki.izvestnyeHosty.path)
    }

    // MARK: - Первый вход по паролю

    /// Единственное место, где используется пароль: положить публичный ключ в
    /// authorized_keys. После этого пароль забывается и больше не нужен.
    ///
    /// Пароль передаётся ssh не аргументом и не переменной окружения (их видно
    /// в списке процессов), а файлом с правами 600, который читает
    /// вспомогательный скрипт SSH_ASKPASS и который удаляется сразу после.
    static func postavitKlyuchPoParolyu(
        nastroyki: Nastroyki,
        parol: String,
        publichnyyKlyuch: String
    ) throws {
        let papka = Papki.vremennaya
        let parolFayl = papka.appendingPathComponent("parol-\(UUID().uuidString)")
        let pomoshchnik = papka.appendingPathComponent("askpass-\(UUID().uuidString).sh")
        let fm = FileManager.default

        defer {
            try? fm.removeItem(at: parolFayl)
            try? fm.removeItem(at: pomoshchnik)
        }

        guard fm.createFile(atPath: parolFayl.path, contents: Data(parol.utf8),
                            attributes: [.posixPermissions: 0o600]) else {
            throw Beda.netPodklyucheniya
        }
        let skript = "#!/bin/sh\ncat \"$VYKLADKA_PAROL\"\n"
        guard fm.createFile(atPath: pomoshchnik.path, contents: Data(skript.utf8),
                            attributes: [.posixPermissions: 0o700]) else {
            throw Beda.netPodklyucheniya
        }

        let ustanovka = """
        set -e
        mkdir -p "$HOME/.ssh"
        chmod 700 "$HOME/.ssh"
        touch "$HOME/.ssh/authorized_keys"
        chmod 600 "$HOME/.ssh/authorized_keys"
        if ! grep -qxF \(Kavychki.odinarnye(publichnyyKlyuch)) "$HOME/.ssh/authorized_keys"; then
            echo \(Kavychki.odinarnye(publichnyyKlyuch)) >> "$HOME/.ssh/authorized_keys"
        fi
        echo vykladka-klyuch-postavlen
        """

        let argumenty = [
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=\(Ssh.putDlyaOpcii(Papki.izvestnyeHosty.path))",
            "-o", "ConnectTimeout=15",
            "-o", "BatchMode=no",
            "-o", "PubkeyAuthentication=no",
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "NumberOfPasswordPrompts=1",
            "-p", "\(nastroyki.port)",
            "\(nastroyki.polzovatel)@\(nastroyki.host)",
            ustanovka
        ]

        let rezultat = try Zapusk.zapustit("/usr/bin/ssh", argumenty, sreda: [
            "SSH_ASKPASS": pomoshchnik.path,
            "SSH_ASKPASS_REQUIRE": "force",
            "VYKLADKA_PAROL": parolFayl.path,
            // Старым сборкам OpenSSH askpass нужен признак графической сессии.
            // На macOS 13+ хватает SSH_ASKPASS_REQUIRE, но лишним не будет.
            "DISPLAY": ":0"
        ])

        guard rezultat.tekst.contains("vykladka-klyuch-postavlen") else {
            throw Beda.komandaUpala("установка ключа", rezultat.kod, rezultat.oshibka)
        }
    }
}

/// Экранирование для удалённого sh. Всё, что уезжает в команду из ввода
/// хозяина или из имён файлов, проходит через это.
enum Kavychki {
    static func odinarnye(_ stroka: String) -> String {
        "'" + stroka.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}
