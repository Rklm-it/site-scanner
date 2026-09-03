import Foundation
import Security

/// Ключ для входа на сервер: заводится один раз, лежит файлом с правами 600 в
/// ~/.vykladka — ровно там же и так же, как ssh хранит собственные ключи.
///
/// Почему не пароль. Пароль от VPS — это root, и держать его на ноутбуке
/// незачем: он нужен ровно один раз, чтобы положить на сервер публичную
/// половину ключа. Дальше работает ключ, а вход по паролю на сервере можно
/// выключить совсем.
///
/// Почему не Связка ключей, хотя сначала было именно так. Связка привязывает
/// доступ к подписи программы, а приложение подписывается «для себя» и подпись
/// меняется при КАЖДОЙ пересборке. Для Связки после `./sobrat.sh` это другая
/// программа: ключ не отдаётся, файл не создаётся, и наружу это выходит
/// невнятным «Permission denied (publickey)» при первой же команде — на живом
/// запуске так и случилось. Файл 600 в домашней папке даёт ту же защиту, что и
/// ~/.ssh/id_ed25519, и не ломается от пересборки.
enum Klyuchi {

    private static let sluzhba = "ru.nexusflow.vykladka"
    private static let uchet = "ssh-private-key"

    enum Beda: LocalizedError {
        case netKlyucha
        case neSozdalsya(String)

        var errorDescription: String? {
            switch self {
            case .netKlyucha:
                return "Ключ для входа не найден. Подключите сервер заново в настройках — понадобится пароль, один раз."
            case let .neSozdalsya(prichina):
                return "Не удалось завести ключ: \(prichina)"
            }
        }
    }

    static var estKlyuch: Bool {
        FileManager.default.fileExists(atPath: Papki.klyuchFayl.path)
    }

    static func publichnyyTekst() -> String? {
        try? String(contentsOf: Papki.publichnyyKlyuch, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Создать новую пару ed25519 прямо в рабочем месте. Возвращает публичную
    /// половину — её и надо положить на сервер.
    static func sozdatParu(kommentariy: String) throws -> String {
        let fm = FileManager.default
        try? fm.removeItem(at: Papki.klyuchFayl)
        try? fm.removeItem(at: Papki.publichnyyKlyuch)

        let rezultat = try Zapusk.zapustit("/usr/bin/ssh-keygen", [
            "-t", "ed25519",
            "-N", "",                       // без парольной фразы: ключ и так лежит только у хозяина
            "-C", kommentariy,
            "-f", Papki.klyuchFayl.path
        ])
        guard rezultat.udalos, estKlyuch else {
            throw Beda.neSozdalsya(rezultat.oshibka.trimmingCharacters(in: .whitespacesAndNewlines))
        }

        // ssh-keygen и так ставит 600, но проверять права — его дело, а не наше
        // предположение: ssh откажется работать с ключом, доступным другим.
        try? fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: Papki.klyuchFayl.path)

        guard let publichnyy = publichnyyTekst() else { throw Beda.netKlyucha }
        return publichnyy
    }

    static func udalit() {
        let fm = FileManager.default
        try? fm.removeItem(at: Papki.klyuchFayl)
        try? fm.removeItem(at: Papki.publichnyyKlyuch)
        udalitIzSvyazki()
    }

    // MARK: - Переезд со Связки

    /// Ранние сборки держали ключ в Связке. Если он там есть, а файла нет —
    /// переносим и из Связки убираем. Связка может при этом спросить
    /// разрешение; отказ не страшен, тогда ключ просто заводится заново.
    static func perenestiIzSvyazki() {
        guard !estKlyuch, let dannye = izSvyazki() else { return }
        let fm = FileManager.default
        if fm.createFile(atPath: Papki.klyuchFayl.path, contents: dannye,
                         attributes: [.posixPermissions: 0o600]) {
            udalitIzSvyazki()
        }
    }

    private static func izSvyazki() -> Data? {
        let zapros: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: sluzhba,
            kSecAttrAccount as String: uchet,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var nayden: CFTypeRef?
        guard SecItemCopyMatching(zapros as CFDictionary, &nayden) == errSecSuccess else { return nil }
        return nayden as? Data
    }

    private static func udalitIzSvyazki() {
        let zapros: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: sluzhba,
            kSecAttrAccount as String: uchet
        ]
        SecItemDelete(zapros as CFDictionary)
    }
}
