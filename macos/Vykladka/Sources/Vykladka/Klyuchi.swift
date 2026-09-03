import Foundation
import Security

/// Ключ для входа на сервер: заводится один раз, лежит в Связке ключей macOS.
///
/// Почему не пароль. Пароль от VPS — это root, и хранить его на ноутбуке
/// незачем: он нужен ровно один раз, чтобы положить на сервер публичную
/// половину ключа. Дальше работает ключ, а пароль на сервере можно вообще
/// выключить — в логах видно, что в root по паролю круглосуточно ломятся боты.
///
/// Приватная половина лежит в Связке (защищена входом в мак), а ssh умеет
/// читать ключ только из файла — поэтому на время работы приложения ключ
/// выкладывается во временный файл с правами 600 и убирается при выходе.
enum Klyuchi {

    private static let sluzhba = "ru.nexusflow.vykladka"
    private static let uchet = "ssh-private-key"

    enum Beda: LocalizedError {
        case svyazka(OSStatus)
        case netKlyucha

        var errorDescription: String? {
            switch self {
            case let .svyazka(status):
                let tekst = SecCopyErrorMessageString(status, nil) as String? ?? "код \(status)"
                return "Связка ключей: \(tekst)"
            case .netKlyucha:
                return "Ключ не найден. Подключите сервер заново в настройках."
            }
        }
    }

    // MARK: - Связка ключей

    static func sohranit(privatnyy: Data) throws {
        udalit()
        let zapros: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: sluzhba,
            kSecAttrAccount as String: uchet,
            kSecValueData as String: privatnyy,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlocked
        ]
        let status = SecItemAdd(zapros as CFDictionary, nil)
        guard status == errSecSuccess else { throw Beda.svyazka(status) }
    }

    static func privatnyy() -> Data? {
        let zapros: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: sluzhba,
            kSecAttrAccount as String: uchet,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var nayden: CFTypeRef?
        let status = SecItemCopyMatching(zapros as CFDictionary, &nayden)
        guard status == errSecSuccess else { return nil }
        return nayden as? Data
    }

    static func udalit() {
        let zapros: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: sluzhba,
            kSecAttrAccount as String: uchet
        ]
        SecItemDelete(zapros as CFDictionary)
    }

    static var estKlyuch: Bool { privatnyy() != nil }

    // MARK: - Файл для ssh

    /// Достать ключ из Связки в файл с правами 600. Возвращает путь.
    @discardableResult
    static func vylozhitVFayl() throws -> URL {
        guard let dannye = privatnyy() else { throw Beda.netKlyucha }
        let put = Papki.klyuchFayl
        let fm = FileManager.default
        try? fm.removeItem(at: put)
        // Права выставляем при создании, а не после: между записью и chmod
        // файл иначе успевает полежать доступным для чтения.
        guard fm.createFile(atPath: put.path, contents: dannye,
                            attributes: [.posixPermissions: 0o600]) else {
            throw Beda.netKlyucha
        }
        return put
    }

    /// Убрать файл с ключом. Вызывается при выходе из приложения.
    static func ubratFayl() {
        try? FileManager.default.removeItem(at: Papki.klyuchFayl)
    }

    // MARK: - Создание пары

    /// Создать новую пару ed25519. Приватная половина уезжает в Связку,
    /// публичная возвращается строкой — её и надо положить на сервер.
    static func sozdatParu(kommentariy: String) throws -> String {
        let vremennaya = Papki.vremennaya.appendingPathComponent("klyuch-\(UUID().uuidString)")
        defer {
            try? FileManager.default.removeItem(at: vremennaya)
            try? FileManager.default.removeItem(at: vremennaya.appendingPathExtension("pub"))
        }

        try Zapusk.objazatelno("/usr/bin/ssh-keygen", [
            "-t", "ed25519",
            "-N", "",                       // без парольной фразы: её роль играет Связка
            "-C", kommentariy,
            "-f", vremennaya.path
        ])

        let privatnyy = try Data(contentsOf: vremennaya)
        let publichnyy = try String(contentsOf: vremennaya.appendingPathExtension("pub"), encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)

        try sohranit(privatnyy: privatnyy)
        try publichnyy.write(to: Papki.publichnyyKlyuch, atomically: true, encoding: .utf8)
        return publichnyy
    }

    static func publichnyyTekst() -> String? {
        try? String(contentsOf: Papki.publichnyyKlyuch, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
