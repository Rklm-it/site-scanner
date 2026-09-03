import Foundation
import Darwin

/// Имена и адреса. Нужно в двух местах: проверить, что домен указывает на наш
/// сервер, до того как Caddy пойдёт за сертификатом, и опознать, откуда пришёл
/// посетитель.
enum Imena {

    /// Адреса имени (IPv4 и IPv6) системным резолвером.
    static func adresa(_ imya: String) -> [String] {
        var podskazki = addrinfo()
        podskazki.ai_family = AF_UNSPEC
        podskazki.ai_socktype = SOCK_STREAM

        var spisok: UnsafeMutablePointer<addrinfo>?
        guard getaddrinfo(imya, nil, &podskazki, &spisok) == 0, let nachalo = spisok else { return [] }
        defer { freeaddrinfo(nachalo) }

        var naydeno: [String] = []
        var uzel: UnsafeMutablePointer<addrinfo>? = nachalo
        while let tekushchiy = uzel {
            var bufer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            if getnameinfo(tekushchiy.pointee.ai_addr, tekushchiy.pointee.ai_addrlen,
                           &bufer, socklen_t(bufer.count), nil, 0, NI_NUMERICHOST) == 0 {
                let adres = String(cString: bufer)
                if !naydeno.contains(adres) { naydeno.append(adres) }
            }
            uzel = tekushchiy.pointee.ai_next
        }
        return naydeno
    }

    /// Обратное имя адреса. Для российских провайдеров оно часто говорит
    /// больше, чем страна: в имени видно и оператора, и город.
    static func obratnoye(_ ip: String) -> String? {
        var podskazki = addrinfo()
        podskazki.ai_family = AF_UNSPEC
        podskazki.ai_socktype = SOCK_STREAM
        podskazki.ai_flags = AI_NUMERICHOST

        var spisok: UnsafeMutablePointer<addrinfo>?
        guard getaddrinfo(ip, nil, &podskazki, &spisok) == 0, let nachalo = spisok else { return nil }
        defer { freeaddrinfo(nachalo) }

        var bufer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        guard getnameinfo(nachalo.pointee.ai_addr, nachalo.pointee.ai_addrlen,
                          &bufer, socklen_t(bufer.count), nil, 0, NI_NAMEREQD) == 0 else { return nil }
        let imya = String(cString: bufer)
        return imya == ip ? nil : imya
    }

    /// Похоже ли на адрес, а не на имя.
    static func etoAdres(_ stroka: String) -> Bool {
        var v4 = in_addr()
        if inet_pton(AF_INET, stroka, &v4) == 1 { return true }
        var v6 = in6_addr()
        return inet_pton(AF_INET6, stroka, &v6) == 1
    }
}

/// Проверка домена перед тем, как заводить его в Caddy.
///
/// Порядок здесь не косметический. Caddy, увидев новый домен, сразу идёт за
/// сертификатом в Let's Encrypt. Если A-запись ещё не проставлена или ведёт не
/// туда, проверка не пройдёт, а повторы упрутся в недельный лимит выпуска — и
/// домен нельзя будет включить, даже когда DNS почините.
struct ProverkaDomena {
    var domen: String
    var adresaDomena: [String]
    var adresaServera: [String]

    var sovpadaet: Bool {
        !adresaDomena.isEmpty && !adresaServera.isEmpty
            && !adresaDomena.filter { adresaServera.contains($0) }.isEmpty
    }

    var opisanie: String {
        if adresaDomena.isEmpty {
            return "У домена \(domen) нет A-записи — Caddy не получит сертификат."
        }
        if sovpadaet {
            return "A-запись на месте: \(adresaDomena.joined(separator: ", "))"
        }
        return "Домен ведёт на \(adresaDomena.joined(separator: ", ")), "
            + "а сервер — \(adresaServera.joined(separator: ", ")). Сертификат не выпустится."
    }

    static func proverit(domen: String, nastroyki: Nastroyki) -> ProverkaDomena {
        let serverAdresa = Imena.etoAdres(nastroyki.host) ? [nastroyki.host] : Imena.adresa(nastroyki.host)
        return ProverkaDomena(
            domen: domen,
            adresaDomena: Imena.adresa(domen),
            adresaServera: serverAdresa
        )
    }
}
