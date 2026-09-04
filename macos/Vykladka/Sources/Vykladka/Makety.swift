import Foundation

/// Склейка двух макетов Stitch — под ПК и под телефон — в одну страницу.
///
/// Stitch отдаёт две отдельные вёрстки, и напрашивается разложить их по разным
/// адресам, отдавая нужную по User-Agent. Так делать нельзя:
///
///  - превью мессенджеров приходят с непонятным User-Agent и получат не ту
///    версию — клиенту в переписку прилетит поехавший макет;
///  - ссылку пересылают: открыл с телефона, кинул дизайнеру на ПК;
///  - ноутбук с окном в половину экрана — «ПК» по User-Agent и телефон по факту;
///  - на один адрес два разных ответа путают кэш браузеров и прокси.
///
/// Поэтому обе вёрстки кладутся в ОДИН файл, каждая в свой контейнер, и
/// переключаются медиазапросом по ширине окна. Плата — страница весит вдвое:
/// браузер грузит обе, показывает одну. Для прототипа на показ это ничего не
/// стоит; перед сдачей боевого сайта вёрстки надо свести в одну адаптивную.
enum Makety {

    static let granica = 768

    struct Para {
        var pk: URL
        var telefon: URL
    }

    struct Itog {
        var papka: URL
        var kartinokSkachano: Int
        var kartinokNeVzyalos: Int
        var tailwindMestnyy: Bool
    }

    enum Beda: LocalizedError {
        case netTela(String)

        var errorDescription: String? {
            switch self {
            case let .netTela(imya):
                return "В файле \(imya) не нашлось разметки — это не похоже на страницу."
            }
        }
    }

    // MARK: - Поиск пары

    /// Найти в папке два макета. Ищем и вложенными папками (как выгружает
    /// Stitch — по папке на версию), и файлами рядом.
    static func naytiParu(v papka: URL) -> Para? {
        let fm = FileManager.default
        var kandidaty: [URL] = []

        guard let soderzhimoe = try? fm.contentsOfDirectory(
            at: papka, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else { return nil }

        for element in soderzhimoe.sorted(by: { $0.path < $1.path }) where element.lastPathComponent != "__MACOSX" {
            var eto_papka: ObjCBool = false
            fm.fileExists(atPath: element.path, isDirectory: &eto_papka)
            if eto_papka.boolValue {
                if let vnutri = try? fm.contentsOfDirectory(at: element, includingPropertiesForKeys: nil,
                                                           options: [.skipsHiddenFiles]) {
                    kandidaty.append(contentsOf: vnutri.filter { $0.pathExtension.lowercased() == "html" })
                }
            } else if element.pathExtension.lowercased() == "html" {
                kandidaty.append(element)
            }
        }

        guard kandidaty.count == 2 else { return nil }
        let pervyy = kandidaty[0], vtoroy = kandidaty[1]

        if let pk = poRazmetke(pervyy, vtoroy) { return pk }
        if pohozheNaTelefon(pervyy) && !pohozheNaTelefon(vtoroy) { return Para(pk: vtoroy, telefon: pervyy) }
        if pohozheNaTelefon(vtoroy) && !pohozheNaTelefon(pervyy) { return Para(pk: pervyy, telefon: vtoroy) }
        // Не разобрались — отдаём как есть, в окне версии можно поменять местами.
        return Para(pk: pervyy, telefon: vtoroy)
    }

    private static func pohozheNaTelefon(_ fayl: URL) -> Bool {
        let put = fayl.path.lowercased()
        for slovo in ["mobile", "phone", "telefon", "mob", "ios", "android", "small"] where put.contains(slovo) {
            return true
        }
        return false
    }

    /// По именам файлов Stitch отличить версии нельзя — у него это
    /// «aloe_spa_1» и «aloe_spa_2». Зато видно по разметке: настольная вёрстка
    /// полна брейкпоинтов Tailwind (lg:, xl:, 2xl:), в телефонной их почти нет.
    private static func poRazmetke(_ pervyy: URL, _ vtoroy: URL) -> Para? {
        guard let a = try? String(contentsOf: pervyy, encoding: .utf8),
              let b = try? String(contentsOf: vtoroy, encoding: .utf8) else { return nil }
        let ballA = shirokieKlassy(a), ballB = shirokieKlassy(b)
        // Разница должна быть заметной, иначе это гадание.
        guard abs(ballA - ballB) >= 5 else { return nil }
        return ballA > ballB ? Para(pk: pervyy, telefon: vtoroy) : Para(pk: vtoroy, telefon: pervyy)
    }

    private static func shirokieKlassy(_ dokument: String) -> Int {
        var vsego = 0
        for priznak in [" lg:", " xl:", " 2xl:", "\"lg:", "\"xl:"] {
            vsego += dokument.components(separatedBy: priznak).count - 1
        }
        return vsego
    }

    // MARK: - Сборка папки

    /// Собрать папку с готовым index.html. Возвращает временную папку — её
    /// отдают в обычный разбор архива и удаляют после выкладки.
    static func sobratPapku(
        _ para: Para,
        skachivatKartinki: Bool = true,
        mestnyyTailwind: Bool = true,
        shag: (String) -> Void = { _ in }
    ) throws -> Itog {
        let fm = FileManager.default
        let kuda = Papki.vremennaya.appendingPathComponent("skleyka-\(UUID().uuidString)", isDirectory: true)
        try fm.createDirectory(at: kuda, withIntermediateDirectories: true)

        shag("Склеиваю макеты…")
        var stranica = try skleit(pk: para.pk, telefon: para.telefon)

        // Картинки и прочее, что лежало рядом с макетами. screen.png — это
        // скриншот из Stitch, на сайте он не нужен и весит прилично.
        for istochnik in [para.pk.deletingLastPathComponent(), para.telefon.deletingLastPathComponent()] {
            guard let ryadom = try? fm.contentsOfDirectory(at: istochnik, includingPropertiesForKeys: nil,
                                                          options: [.skipsHiddenFiles]) else { continue }
            for fayl in ryadom where fayl.pathExtension.lowercased() != "html" {
                let imya = fayl.lastPathComponent
                if imya == "screen.png" || imya == "__MACOSX" { continue }
                let cel = kuda.appendingPathComponent(imya)
                if !fm.fileExists(atPath: cel.path) { try? fm.copyItem(at: fayl, to: cel) }
            }
        }

        var skachano = 0, neVzyalos = 0, tailwindVzyat = false

        if skachivatKartinki {
            shag("Забираю картинки к себе…")
            let rezultat = zabratKartinki(stranica, v: kuda, shag: shag)
            stranica = rezultat.tekst
            skachano = rezultat.vzyato
            neVzyalos = rezultat.neVzyato
        }

        if mestnyyTailwind {
            shag("Забираю Tailwind к себе…")
            let rezultat = zabratTailwind(stranica, v: kuda)
            stranica = rezultat.tekst
            tailwindVzyat = rezultat.vzyat
        }

        try stranica.write(to: kuda.appendingPathComponent("index.html"), atomically: true, encoding: .utf8)
        return Itog(papka: kuda, kartinokSkachano: skachano,
                    kartinokNeVzyalos: neVzyalos, tailwindMestnyy: tailwindVzyat)
    }

    // MARK: - Склейка документов

    static func skleit(pk: URL, telefon: URL) throws -> String {
        let dokumentPk = try String(contentsOf: pk, encoding: .utf8)
        let dokumentTel = try String(contentsOf: telefon, encoding: .utf8)

        guard let chastiPk = razobrat(dokumentPk) else { throw Beda.netTela(pk.lastPathComponent) }
        guard let chastiTel = razobrat(dokumentTel) else { throw Beda.netTela(telefon.lastPathComponent) }

        // Голову собираем по тегам, а не строками. Причина в том, что у Stitch
        // в каждом файле СВОЙ tailwind.config, и если вставить оба, второй
        // молча затрёт первый — вёрстка одной из версий поедет.
        var ssylki: [String] = []
        var stili: [String] = []
        var konfigi: [String] = []
        var prochieSkripty: [String] = []

        for chasti in [chastiPk, chastiTel] {
            for ssylka in tegi(chasti.golova, "link") where !ssylki.contains(where: {
                atribut("href", v: $0) == atribut("href", v: ssylka)
            }) {
                ssylki.append(ssylka)
            }
            stili.append(contentsOf: tegi(chasti.golova, "style"))
            for skript in tegi(chasti.golova, "script") {
                if skript.contains("tailwind.config") {
                    konfigi.append(skript)
                } else if !prochieSkripty.contains(skript) {
                    prochieSkripty.append(skript)
                }
            }
        }

        // Какой из конфигов оставить — вопрос не вкуса. У этой пары в
        // настольном конфиге шрифты названы «playfairDisplay», такого семейства
        // не существует, и сам он их даже не подключает: отдельно эта версия
        // рендерится системным шрифтом. Поэтому берём тот конфиг, чьи названия
        // шрифтов совпадают с реально подключёнными.
        let semeystva = semeystvaIzSsylok(ssylki)
        let konfig = vybratKonfig(konfigi, semeystva: semeystva)

        let zagolovok = naytiZagolovok(dokumentPk) ?? naytiZagolovok(dokumentTel) ?? "Прототип"

        return """
        <!DOCTYPE html>
        <html lang="ru">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>\(zagolovok)</title>
        \(ssylki.joined(separator: "\n"))
        \(prochieSkripty.joined(separator: "\n"))
        \(konfig)
        \(stili.joined(separator: "\n"))
        <style>
        /* Две вёрстки в одном файле. Переключаются по ШИРИНЕ ОКНА, а не по
           User-Agent: иначе превью мессенджеров, узкое окно ноутбука и
           пересланная ссылка дают не ту версию. */
        [data-vykladka="pk"], [data-vykladka="telefon"] { display: block; }
        @media (max-width: \(granica - 1)px) { [data-vykladka="pk"]      { display: none !important; } }
        @media (min-width: \(granica)px)     { [data-vykladka="telefon"] { display: none !important; } }
        </style>
        </head>
        <body>
        <div data-vykladka="pk"\(atributyKontenera(chastiPk.atributyTela))>
        \(chastiPk.telo)
        </div>
        <div data-vykladka="telefon"\(atributyKontenera(chastiTel.atributyTela))>
        \(chastiTel.telo)
        </div>
        </body>
        </html>
        """
    }

    // MARK: - Забрать чужое к себе

    /// Картинки макета Stitch лежат на lh3.googleusercontent.com по временным
    /// ссылкам. Это ровно та беда, что была у mebel-ryazane с LPgenerator:
    /// сайт клиента живёт на чужом хранилище. Ссылка протухнет — клиент
    /// откроет прототип и увидит пустые места, причём ровно тогда, когда
    /// решит показать его партнёру.
    private static func zabratKartinki(
        _ stranica: String, v papka: URL, shag: (String) -> Void
    ) -> (tekst: String, vzyato: Int, neVzyato: Int) {
        let adresa = naytiVneshnie(stranica)
        guard !adresa.isEmpty else { return (stranica, 0, 0) }

        let kartinki = papka.appendingPathComponent("images", isDirectory: true)
        try? FileManager.default.createDirectory(at: kartinki, withIntermediateDirectories: true)

        var tekst = stranica
        var vzyato = 0, neVzyato = 0
        var nomer = 0

        for adres in adresa {
            nomer += 1
            shag("Картинка \(nomer) из \(adresa.count)…")
            guard let dannye = Zagruzka.skachat(adres), dannye.count > 100 else {
                neVzyato += 1
                continue
            }
            let imya = String(format: "%03d.%@", nomer, rasshirenie(dannye))
            let kuda = kartinki.appendingPathComponent(imya)
            guard (try? dannye.write(to: kuda)) != nil else { neVzyato += 1; continue }
            tekst = tekst.replacingOccurrences(of: adres, with: "images/\(imya)")
            vzyato += 1
        }
        return (tekst, vzyato, neVzyato)
    }

    /// Tailwind тянется скриптом с чужого CDN и компилирует классы прямо в
    /// браузере. Пока страница показывается клиенту — терпимо, но если CDN
    /// недоступен, сайт открывается голой разметкой. Кладём скрипт рядом.
    private static func zabratTailwind(_ stranica: String, v papka: URL) -> (tekst: String, vzyat: Bool) {
        guard stranica.contains("cdn.tailwindcss.com"),
              let dannye = Zagruzka.skachat("https://cdn.tailwindcss.com"), dannye.count > 1000 else {
            return (stranica, false)
        }
        let kuda = papka.appendingPathComponent("tailwind.js")
        guard (try? dannye.write(to: kuda)) != nil else { return (stranica, false) }
        return (stranica.replacingOccurrences(of: "https://cdn.tailwindcss.com", with: "tailwind.js"), true)
    }

    /// Адреса картинок: src="…" и фоны url(…). Шрифты Google оставляем
    /// ссылками — это стандартный способ, и они не протухают.
    private static func naytiVneshnie(_ stranica: String) -> [String] {
        var naydeno: [String] = []
        for shablon in ["src=\"(https://[^\"]+)\"", "url\\((https://[^)\"']+)\\)"] {
            guard let regulyarka = try? NSRegularExpression(pattern: shablon, options: [.caseInsensitive]) else { continue }
            let diapazon = NSRange(stranica.startIndex..<stranica.endIndex, in: stranica)
            for sovpadenie in regulyarka.matches(in: stranica, options: [], range: diapazon) {
                guard let kusok = Range(sovpadenie.range(at: 1), in: stranica) else { continue }
                let adres = String(stranica[kusok])
                if adres.contains("fonts.googleapis.com") || adres.contains("fonts.gstatic.com") { continue }
                if adres.contains("cdn.tailwindcss.com") { continue }
                if !naydeno.contains(adres) { naydeno.append(adres) }
            }
        }
        return naydeno
    }

    /// Расширение по первым байтам: у ссылок Stitch его в адресе нет.
    private static func rasshirenie(_ dannye: Data) -> String {
        let nachalo = [UInt8](dannye.prefix(12))
        if nachalo.count >= 8, nachalo[0] == 0x89, nachalo[1] == 0x50 { return "png" }
        if nachalo.count >= 3, nachalo[0] == 0xFF, nachalo[1] == 0xD8 { return "jpg" }
        if nachalo.count >= 12, nachalo[0] == 0x52, nachalo[8] == 0x57 { return "webp" }
        if nachalo.count >= 4, nachalo[0] == 0x47, nachalo[1] == 0x49 { return "gif" }
        if let tekst = String(data: dannye.prefix(200), encoding: .utf8), tekst.contains("<svg") { return "svg" }
        return "jpg"
    }

    // MARK: - Разбор документа

    private struct Chasti {
        var golova: String
        var telo: String
        var atributyTela: String
    }

    private static func razobrat(_ dokument: String) -> Chasti? {
        let golova = mezhdu(dokument, teg: "head")?.soderzhimoe ?? ""
        guard let telo = mezhdu(dokument, teg: "body") else {
            let chistyy = dokument.trimmingCharacters(in: .whitespacesAndNewlines)
            guard chistyy.contains("<") else { return nil }
            return Chasti(golova: golova, telo: chistyy, atributyTela: "")
        }
        return Chasti(golova: golova, telo: telo.soderzhimoe, atributyTela: telo.atributy)
    }

    private static func mezhdu(_ tekst: String, teg: String) -> (soderzhimoe: String, atributy: String)? {
        guard let regulyarka = try? NSRegularExpression(
            pattern: "<\(teg)([^>]*)>(.*)</\(teg)\\s*>",
            options: [.caseInsensitive, .dotMatchesLineSeparators]) else { return nil }
        let diapazon = NSRange(tekst.startIndex..<tekst.endIndex, in: tekst)
        guard let sovpadenie = regulyarka.firstMatch(in: tekst, options: [], range: diapazon),
              let atributy = Range(sovpadenie.range(at: 1), in: tekst),
              let soderzhimoe = Range(sovpadenie.range(at: 2), in: tekst) else { return nil }
        return (String(tekst[soderzhimoe]), String(tekst[atributy]))
    }

    private static func tegi(_ golova: String, _ teg: String) -> [String] {
        let shablon = teg == "link" ? "<link\\b[^>]*>" : "<\(teg)\\b[^>]*>.*?</\(teg)>"
        guard let regulyarka = try? NSRegularExpression(
            pattern: shablon, options: [.caseInsensitive, .dotMatchesLineSeparators]) else { return [] }
        let diapazon = NSRange(golova.startIndex..<golova.endIndex, in: golova)
        return regulyarka.matches(in: golova, options: [], range: diapazon).compactMap {
            Range($0.range, in: golova).map { kusok in String(golova[kusok]) }
        }
    }

    private static func semeystvaIzSsylok(_ ssylki: [String]) -> [String] {
        guard let regulyarka = try? NSRegularExpression(pattern: "family=([^&:\"']+)") else { return [] }
        var naydeno: [String] = []
        for ssylka in ssylki {
            let diapazon = NSRange(ssylka.startIndex..<ssylka.endIndex, in: ssylka)
            for sovpadenie in regulyarka.matches(in: ssylka, options: [], range: diapazon) {
                guard let kusok = Range(sovpadenie.range(at: 1), in: ssylka) else { continue }
                let semeystvo = String(ssylka[kusok]).replacingOccurrences(of: "+", with: " ")
                if !naydeno.contains(semeystvo) { naydeno.append(semeystvo) }
            }
        }
        return naydeno
    }

    private static func vybratKonfig(_ konfigi: [String], semeystva: [String]) -> String {
        guard let pervyy = konfigi.first else { return "" }
        var luchshiy = pervyy
        var luchshiyBall = -1
        for konfig in konfigi {
            let nizhniy = konfig.lowercased()
            let ball = semeystva.filter { nizhniy.contains($0.lowercased()) }.count
            if ball > luchshiyBall {
                luchshiy = konfig
                luchshiyBall = ball
            }
        }
        return luchshiy
    }

    private static func naytiZagolovok(_ dokument: String) -> String? {
        guard let zagolovok = mezhdu(dokument, teg: "title")?.soderzhimoe
            .trimmingCharacters(in: .whitespacesAndNewlines), !zagolovok.isEmpty else { return nil }
        return zagolovok
    }

    /// Классы и стили с <body> переезжают на контейнер: у Stitch там лежит фон
    /// и базовый шрифт всей страницы, и без них вёрстка едет.
    private static func atributyKontenera(_ atributyTela: String) -> String {
        var kusochki: [String] = []
        for imya in ["class", "style"] {
            if let znachenie = atribut(imya, v: atributyTela), !znachenie.isEmpty {
                kusochki.append("\(imya)=\"\(znachenie)\"")
            }
        }
        return kusochki.isEmpty ? "" : " " + kusochki.joined(separator: " ")
    }

    private static func atribut(_ imya: String, v stroka: String) -> String? {
        for shablon in ["\(imya)\\s*=\\s*\"([^\"]*)\"", "\(imya)\\s*=\\s*'([^']*)'"] {
            guard let regulyarka = try? NSRegularExpression(pattern: shablon, options: [.caseInsensitive]) else { continue }
            let diapazon = NSRange(stroka.startIndex..<stroka.endIndex, in: stroka)
            if let sovpadenie = regulyarka.firstMatch(in: stroka, options: [], range: diapazon),
               let znachenie = Range(sovpadenie.range(at: 1), in: stroka) {
                return String(stroka[znachenie])
            }
        }
        return nil
    }
}

/// Синхронная загрузка по сети: склейка идёт в фоне целиком, и разводить
/// внутри неё асинхронность незачем.
enum Zagruzka {
    static func skachat(_ adres: String, timeout: TimeInterval = 30) -> Data? {
        guard let ssylka = URL(string: adres) else { return nil }
        var zapros = URLRequest(url: ssylka)
        zapros.timeoutInterval = timeout
        zapros.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
                        forHTTPHeaderField: "User-Agent")

        var itog: Data?
        let ozhidanie = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: zapros) { dannye, otvet, _ in
            if let kod = (otvet as? HTTPURLResponse)?.statusCode, kod == 200 { itog = dannye }
            ozhidanie.signal()
        }.resume()
        _ = ozhidanie.wait(timeout: .now() + timeout + 5)
        return itog
    }
}
