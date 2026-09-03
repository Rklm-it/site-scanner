import Foundation

/// Одно обращение к сайту, разобранное из лога Caddy.
struct Zapros {
    enum Vid: String {
        case chelovek
        case preview
        case bot

        var nazvanie: String {
            switch self {
            case .chelovek: return "человек"
            case .preview: return "превью ссылки"
            case .bot: return "робот"
            }
        }
    }

    var sayt: String
    var kogda: Date
    var ip: String
    var metod: String = "GET"
    var uri: String = "/"
    var status: Int = 0
    var ua: String = ""
    var referer: String = ""
    var vid: Vid = .chelovek

    /// Картинка, шрифт, бандл — не страница. Для счёта заходов не годится:
    /// одна страница тянет их десятками.
    var etoFayl: Bool {
        if uri.hasPrefix("/assets/") { return true }
        let rasshireniya = ["js", "css", "png", "jpg", "jpeg", "webp", "svg", "gif", "ico",
                            "woff", "woff2", "ttf", "otf", "map", "avif", "mp4", "webm"]
        let put = uri.split(separator: "?").first.map(String.init) ?? uri
        let rasshirenie = (put as NSString).pathExtension.lowercased()
        return rasshireniya.contains(rasshirenie)
    }
}

/// Заход: подряд идущие обращения с одного адреса и браузера.
struct Poseshchenie: Identifiable {
    var id = UUID()
    var nachalo: Date
    var konec: Date
    var ip: String
    var ua: String
    var vid: Zapros.Vid
    var stranicy: [String]
    var otkuda: String
    var zaprosov: Int

    var ustroystvo: String { Zhurnal.ustroystvo(ua) }
    var dlitelnost: TimeInterval { konec.timeIntervalSince(nachalo) }
}

enum Zhurnal {

    // MARK: - Опознание

    /// Мессенджеры и соцсети открывают ссылку сами, как только её отправили.
    /// Без этого списка выглядит так, будто клиент посмотрел сайт через
    /// секунду после отправки — а он ещё даже не открыл переписку. Проверяется
    /// ПЕРВЫМ: во многих таких строках есть слово bot.
    static let priznakiPreview = [
        "telegrambot", "whatsapp", "facebookexternalhit", "twitterbot", "slackbot",
        "discordbot", "linkedinbot", "vkshare", "vkontakte", "skypeuripreview",
        "viber", "redditbot", "pinterest", "bingpreview", "embedly", "quora link preview",
        "outlook", "iframely", "nuzzel", "snapchat", "flipboard"
    ]

    static let priznakiBota = [
        "bot", "crawl", "spider", "slurp", "curl", "wget", "python-requests", "python-urllib",
        "go-http-client", "java/", "libwww", "scrapy", "httpclient", "okhttp", "axios",
        "ahrefs", "semrush", "mj12", "dotbot", "dataprovider", "censys", "zgrab", "masscan",
        "expanse", "netcraft", "netsystems", "paloalto", "internetmeasurement",
        "headlesschrome", "phantomjs", "lighthouse", "gtmetrix", "pingdom", "uptimerobot",
        "site24x7", "statuscake", "monitoring", "scanner", "nmap", "zabbix"
    ]

    static func opoznat(ua: String) -> Zapros.Vid {
        let nizhniy = ua.lowercased()
        if nizhniy.trimmingCharacters(in: .whitespaces).isEmpty { return .bot }
        for priznak in priznakiPreview where nizhniy.contains(priznak) { return .preview }
        for priznak in priznakiBota where nizhniy.contains(priznak) { return .bot }
        return .chelovek
    }

    static func ustroystvo(_ ua: String) -> String {
        let n = ua.lowercased()
        var chto = "неизвестное устройство"
        if n.contains("iphone") { chto = "iPhone" }
        else if n.contains("ipad") { chto = "iPad" }
        else if n.contains("android") { chto = n.contains("mobile") ? "телефон Android" : "планшет Android" }
        else if n.contains("macintosh") || n.contains("mac os x") { chto = "Mac" }
        else if n.contains("windows") { chto = "Windows" }
        else if n.contains("linux") { chto = "Linux" }

        var brauzer = ""
        if n.contains("yabrowser") { brauzer = "Яндекс" }
        else if n.contains("edg/") { brauzer = "Edge" }
        else if n.contains("firefox") { brauzer = "Firefox" }
        else if n.contains("chrome") || n.contains("crios") { brauzer = "Chrome" }
        else if n.contains("safari") { brauzer = "Safari" }

        return brauzer.isEmpty ? chto : "\(chto), \(brauzer)"
    }

    // MARK: - Разбор строки лога

    /// Caddy пишет по строке JSON на запрос. Поля отличаются между версиями
    /// (remote_ip появился вместо remote_addr), поэтому читаем оба.
    static func razobratStroku(_ stroka: String, sayt: String) -> Zapros? {
        guard let dannye = stroka.data(using: .utf8),
              let obekt = try? JSONSerialization.jsonObject(with: dannye) as? [String: Any],
              let vremya = obekt["ts"] as? Double,
              let zapros = obekt["request"] as? [String: Any] else { return nil }

        var ip = (zapros["remote_ip"] as? String) ?? ""
        if ip.isEmpty, let adres = zapros["remote_addr"] as? String {
            // remote_addr приходит как «1.2.3.4:54321»
            ip = adres.split(separator: ":").dropLast().joined(separator: ":")
            if ip.isEmpty { ip = adres }
        }

        let zagolovki = (zapros["headers"] as? [String: Any]) ?? [:]
        func zagolovok(_ imya: String) -> String {
            if let spisok = zagolovki[imya] as? [String] { return spisok.first ?? "" }
            if let odna = zagolovki[imya] as? String { return odna }
            return ""
        }

        let ua = zagolovok("User-Agent")
        return Zapros(
            sayt: sayt,
            kogda: Date(timeIntervalSince1970: vremya),
            ip: ip,
            metod: (zapros["method"] as? String) ?? "GET",
            uri: (zapros["uri"] as? String) ?? "/",
            status: (obekt["status"] as? Int) ?? 0,
            ua: ua,
            referer: zagolovok("Referer"),
            vid: opoznat(ua: ua)
        )
    }

    // MARK: - Забрать новое с сервера

    /// Дочитать лог сайта и положить новые записи в базу. Возвращает, сколько
    /// добавилось.
    ///
    /// Сервер не разбирает ничего: отдаёт хвост файла от известного смещения.
    /// Если файл провернулся ротацией и стал короче — читаем с начала.
    @discardableResult
    static func sinhronizirovat(sayt: Sayt, nastroyki: Nastroyki, baza: Baza) throws -> Int {
        let ssh = Ssh(nastroyki: nastroyki)
        let log = "\(nastroyki.papkaLogov)/\(sayt.imya).log"
        let smeshchenie = baza.smeshchenie(sayt: sayt.imya)

        // При первом заходе прихватываем и то, что уже провернулось ротацией.
        let starye = smeshchenie == 0
            ? "cat \(Kavychki.odinarnye(nastroyki.papkaLogov))/\(sayt.imya)-*.log 2>/dev/null || true"
            : "true"

        let komanda = """
        f=\(Kavychki.odinarnye(log))
        if [ ! -f "$f" ]; then echo 0; exit 0; fi
        s=$(wc -c < "$f")
        echo "$s"
        o=\(smeshchenie)
        if [ "$s" -lt "$o" ]; then o=0; fi
        \(starye)
        tail -c +$((o + 1)) "$f"
        """

        let rezultat = try ssh.vypolnit(komanda)
        let tekst = rezultat.tekst
        guard let konecPervoy = tekst.firstIndex(of: "\n") else { return 0 }
        let razmer = Int64(tekst[tekst.startIndex..<konecPervoy].trimmingCharacters(in: .whitespaces)) ?? 0
        let telo = String(tekst[tekst.index(after: konecPervoy)...])

        var zaprosy: [Zapros] = []
        for stroka in telo.split(separator: "\n") {
            let s = String(stroka)
            guard s.hasPrefix("{") else { continue }
            if let zapros = razobratStroku(s, sayt: sayt.imya) { zaprosy.append(zapros) }
        }

        try baza.dobavit(zaprosy)
        try baza.zapisatSmeshchenie(sayt: sayt.imya, razmer)
        return zaprosy.count
    }

    // MARK: - Заходы

    /// Склеить обращения в заходы. Куки нет и не будет — на странице клиента не
    /// должно быть ни счётчиков, ни трекеров, — поэтому «тот же посетитель» это
    /// пара «адрес + браузер», а перерыв больше получаса считается новым
    /// заходом. Телефон, переключившийся с wi-fi на мобильный, посчитается
    /// дважды: точнее без счётчика на странице не выйдет.
    static let pereryv: TimeInterval = 30 * 60

    static func zahody(_ zaprosy: [Zapros]) -> [Poseshchenie] {
        var otkrytye: [String: Poseshchenie] = [:]
        var gotovye: [Poseshchenie] = []

        for zapros in zaprosy.sorted(by: { $0.kogda < $1.kogda }) {
            let klyuch = zapros.ip + "|" + zapros.ua
            if var tekushchiy = otkrytye[klyuch], zapros.kogda.timeIntervalSince(tekushchiy.konec) <= pereryv {
                tekushchiy.konec = zapros.kogda
                tekushchiy.zaprosov += 1
                if !zapros.etoFayl, !tekushchiy.stranicy.contains(zapros.uri) {
                    tekushchiy.stranicy.append(zapros.uri)
                }
                if tekushchiy.otkuda.isEmpty { tekushchiy.otkuda = zapros.referer }
                otkrytye[klyuch] = tekushchiy
            } else {
                if let zakonchennyy = otkrytye[klyuch] { gotovye.append(zakonchennyy) }
                otkrytye[klyuch] = Poseshchenie(
                    nachalo: zapros.kogda,
                    konec: zapros.kogda,
                    ip: zapros.ip,
                    ua: zapros.ua,
                    vid: zapros.vid,
                    stranicy: zapros.etoFayl ? [] : [zapros.uri],
                    otkuda: zapros.referer,
                    zaprosov: 1
                )
            }
        }
        gotovye.append(contentsOf: otkrytye.values)
        return gotovye.sorted { $0.nachalo > $1.nachalo }
    }
}
