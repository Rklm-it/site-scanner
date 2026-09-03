import Foundation

/// Что с сайтом прямо сейчас. Проверяется с мака, а не с сервера: сервер
/// всегда ответит сам себе, а важно, отвечает ли он клиенту.
struct Zdorovye: Equatable {
    var domen: String
    var kod: Int?
    var otklik: Double?
    var oshibka: String?
    var sertifikatDo: Date?
    var proveryeno: Date = Date()

    var horosho: Bool { kod == 200 }

    var dneyDoKoncaSertifikata: Int? {
        guard let sertifikatDo else { return nil }
        return Calendar.current.dateComponents([.day], from: Date(), to: sertifikatDo).day
    }

    var korotko: String {
        if let oshibka { return oshibka }
        guard let kod else { return "не проверялся" }
        let vremya = otklik.map { String(format: "%.0f мс", $0 * 1000) } ?? ""
        return "\(kod) · \(vremya)"
    }

    /// Один заход: код ответа, время ответа и срок сертификата.
    static func proverit(domen: String) async -> Zdorovye {
        var rezultat = Zdorovye(domen: domen)
        guard let adres = URL(string: "https://\(domen)/") else {
            rezultat.oshibka = "неверный домен"
            return rezultat
        }

        var zapros = URLRequest(url: adres)
        zapros.httpMethod = "GET"
        zapros.timeoutInterval = 15
        // Кэш здесь врал бы в самом важном месте: проверяем живой ответ.
        zapros.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        zapros.setValue("Vykladka/1.0 (проверка прототипа)", forHTTPHeaderField: "User-Agent")

        let nachalo = Date()
        do {
            let (_, otvet) = try await URLSession.shared.data(for: zapros)
            rezultat.otklik = Date().timeIntervalSince(nachalo)
            rezultat.kod = (otvet as? HTTPURLResponse)?.statusCode
        } catch {
            rezultat.oshibka = error.localizedDescription
        }

        rezultat.sertifikatDo = (try? await vFone { srokSertifikata(domen) }) ?? nil
        return rezultat
    }

    /// Срок сертификата берём openssl-ом: URLSession его не показывает, а
    /// «сертификат кончается через три дня» — ровно та новость, которую хочется
    /// узнать до того, как её увидит клиент.
    static func srokSertifikata(_ domen: String) -> Date? {
        let komanda = "echo | /usr/bin/openssl s_client -servername \(Kavychki.odinarnye(domen)) "
            + "-connect \(Kavychki.odinarnye(domen + ":443")) 2>/dev/null "
            + "| /usr/bin/openssl x509 -noout -enddate"
        guard let rezultat = try? Zapusk.zapustit("/bin/sh", ["-c", komanda]), rezultat.udalos else { return nil }

        let tekst = rezultat.tekst.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let znak = tekst.range(of: "notAfter=") else { return nil }
        let znachenie = String(tekst[znak.upperBound...]).trimmingCharacters(in: .whitespaces)

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM d HH:mm:ss yyyy zzz"
        return formatter.date(from: znachenie)
    }
}
