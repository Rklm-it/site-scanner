import Foundation

/// Откуда пришёл посетитель.
///
/// Страна определяется офлайн, по бесплатной базе DB-IP (лицензия CC BY 4.0,
/// указание источника обязательно — оно есть в настройках). Файл скачивается
/// на мак один раз в месяц по кнопке; адреса посетителей при этом никуда не
/// уходят, что и есть причина не пользоваться онлайновым сервисом.
///
/// Города здесь нет: городская база DB-IP весит сотни мегабайт, и ради неё
/// пришлось бы заводить отдельный импорт. Вместо города показываем обратное имя
/// адреса — у российских провайдеров в нём обычно виден и оператор, и город.
final class Geo {

    private struct Diapazon {
        var nachalo: UInt32
        var konec: UInt32
        var strana: String
    }

    private var diapazony: [Diapazon] = []
    private(set) var zagruzhena = false
    private(set) var datBazy: Date?

    static let shared = Geo()

    private init() { prochitatSFayla() }

    // MARK: - Чтение

    func prochitatSFayla() {
        guard let dannye = try? String(contentsOf: Papki.geoBaza, encoding: .utf8) else { return }
        razobrat(dannye)
        datBazy = (try? FileManager.default.attributesOfItem(atPath: Papki.geoBaza.path))?[.modificationDate] as? Date
    }

    private func razobrat(_ csv: String) {
        var sobrano: [Diapazon] = []
        sobrano.reserveCapacity(400_000)
        for stroka in csv.split(separator: "\n", omittingEmptySubsequences: true) {
            let polya = stroka.split(separator: ",")
            guard polya.count >= 3,
                  let nachalo = vChislo(String(polya[0])),
                  let konec = vChislo(String(polya[1])) else { continue }   // IPv6 отбрасываем
            sobrano.append(Diapazon(nachalo: nachalo, konec: konec, strana: String(polya[2])))
        }
        diapazony = sobrano.sorted { $0.nachalo < $1.nachalo }
        zagruzhena = !diapazony.isEmpty
    }

    private func vChislo(_ adres: String) -> UInt32? {
        let chasti = adres.split(separator: ".")
        guard chasti.count == 4 else { return nil }
        var itog: UInt32 = 0
        for chast in chasti {
            guard let bayt = UInt32(chast), bayt < 256 else { return nil }
            itog = itog << 8 | bayt
        }
        return itog
    }

    // MARK: - Поиск

    func strana(_ ip: String) -> String? {
        guard zagruzhena, let chislo = vChislo(ip) else { return nil }
        var levo = 0, pravo = diapazony.count - 1
        while levo <= pravo {
            let seredina = (levo + pravo) / 2
            let diapazon = diapazony[seredina]
            if chislo < diapazon.nachalo { pravo = seredina - 1 }
            else if chislo > diapazon.konec { levo = seredina + 1 }
            else { return Geo.nazvanieStrany(diapazon.strana) }
        }
        return nil
    }

    // MARK: - Обновление базы

    /// Скачать свежую базу. У DB-IP файл выходит помесячно; в начале месяца
    /// свежего может ещё не быть, поэтому при неудаче берём предыдущий.
    func obnovit() async throws {
        let kalendar = Calendar(identifier: .gregorian)
        var kogda = Date()
        var poslednyayaBeda: Error?

        for _ in 0..<2 {
            let chasti = kalendar.dateComponents([.year, .month], from: kogda)
            guard let god = chasti.year, let mesyac = chasti.month else { break }
            let imya = String(format: "dbip-country-lite-%04d-%02d.csv.gz", god, mesyac)
            guard let adres = URL(string: "https://download.db-ip.com/free/\(imya)") else { break }

            do {
                let (vremennyy, otvet) = try await URLSession.shared.download(from: adres)
                guard (otvet as? HTTPURLResponse)?.statusCode == 200 else {
                    throw NSError(domain: "Geo", code: 1, userInfo: [
                        NSLocalizedDescriptionKey: "DB-IP не отдал \(imya)"
                    ])
                }
                let gz = Papki.vremennaya.appendingPathComponent(imya)
                try? FileManager.default.removeItem(at: gz)
                try FileManager.default.moveItem(at: vremennyy, to: gz)
                defer { try? FileManager.default.removeItem(at: gz) }

                let raspakovannyy = try Zapusk.objazatelno("/usr/bin/gunzip", ["-c", gz.path])
                let csv = String(decoding: raspakovannyy.vyvod, as: UTF8.self)
                try csv.write(to: Papki.geoBaza, atomically: true, encoding: .utf8)
                razobrat(csv)
                datBazy = Date()
                return
            } catch {
                poslednyayaBeda = error
                kogda = kalendar.date(byAdding: .month, value: -1, to: kogda) ?? kogda
            }
        }
        if let poslednyayaBeda { throw poslednyayaBeda }
    }

    // MARK: - Названия

    static let strany: [String: String] = [
        "RU": "Россия", "UA": "Украина", "BY": "Беларусь", "KZ": "Казахстан",
        "AM": "Армения", "AZ": "Азербайджан", "GE": "Грузия", "MD": "Молдова",
        "UZ": "Узбекистан", "KG": "Киргизия", "TJ": "Таджикистан", "TM": "Туркмения",
        "DE": "Германия", "NL": "Нидерланды", "FR": "Франция", "GB": "Великобритания",
        "US": "США", "CA": "Канада", "PL": "Польша", "CZ": "Чехия", "FI": "Финляндия",
        "SE": "Швеция", "NO": "Норвегия", "LT": "Литва", "LV": "Латвия", "EE": "Эстония",
        "TR": "Турция", "CN": "Китай", "JP": "Япония", "KR": "Корея", "IN": "Индия",
        "IL": "Израиль", "AE": "ОАЭ", "TH": "Таиланд", "VN": "Вьетнам", "RS": "Сербия",
        "BG": "Болгария", "RO": "Румыния", "IT": "Италия", "ES": "Испания", "PT": "Португалия",
        "CH": "Швейцария", "AT": "Австрия", "BE": "Бельгия", "IE": "Ирландия", "DK": "Дания",
        "SG": "Сингапур", "AU": "Австралия", "BR": "Бразилия", "MX": "Мексика", "AR": "Аргентина"
    ]

    static func nazvanieStrany(_ kod: String) -> String {
        strany[kod.uppercased()] ?? kod.uppercased()
    }
}
