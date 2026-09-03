import Foundation

/// Сайт на сервере: папка со статикой, домен и блок Caddy.
struct Sayt: Identifiable, Equatable {
    /// Имя папки в /root/prototypes-static, имя файла блока и имя лог-файла.
    var imya: String
    var domen: String
    var sozdan: String
    /// Блок написан приложением (есть метка) — значит его можно менять и удалять.
    /// Чужой блок показываем, но не трогаем: его завёл человек руками.
    var nash: Bool
    var faylBloka: String

    var id: String { imya }
    var adres: String { "https://\(domen)" }

    /// Имя годится в имя папки и файла: латиница, цифры, дефис.
    static func imyaGodnoe(_ imya: String) -> Bool {
        !imya.isEmpty && imya.range(of: "^[a-z0-9][a-z0-9-]{0,62}$", options: .regularExpression) != nil
    }

    static func domenGodnyy(_ domen: String) -> Bool {
        domen.range(of: "^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
                    options: .regularExpression) != nil
    }
}

/// Разбор и сборка блоков Caddy.
enum Bloki {

    static let metkaNachalo = "# vykladka:"

    /// Разобрать содержимое каталога блоков. На вход — вывод команды, которая
    /// печатает «=== имя файла ===» и содержимое каждого .caddy.
    static func razobrat(_ vygruzka: String) -> [Sayt] {
        var sayty: [Sayt] = []
        var tekushchiyFayl = ""
        var nakoplennoe: [String] = []

        func zakryt() {
            guard !tekushchiyFayl.isEmpty else { return }
            if let sayt = izFayla(imyaFayla: tekushchiyFayl, soderzhimoe: nakoplennoe.joined(separator: "\n")) {
                sayty.append(sayt)
            }
            nakoplennoe = []
        }

        for stroka in vygruzka.split(separator: "\n", omittingEmptySubsequences: false) {
            let tekst = String(stroka)
            if tekst.hasPrefix("=== ") && tekst.hasSuffix(" ===") {
                zakryt()
                tekushchiyFayl = String(tekst.dropFirst(4).dropLast(4))
            } else {
                nakoplennoe.append(tekst)
            }
        }
        zakryt()

        return sayty.sorted { $0.imya < $1.imya }
    }

    static func izFayla(imyaFayla: String, soderzhimoe: String) -> Sayt? {
        // Файл-заметка блоков не содержит.
        if imyaFayla.hasPrefix("00-") { return nil }

        var imya = (imyaFayla as NSString).deletingPathExtension
        var domen = ""
        var sozdan = ""
        var nash = false

        for stroka in soderzhimoe.split(separator: "\n") {
            let tekst = stroka.trimmingCharacters(in: .whitespaces)
            if tekst.hasPrefix(metkaNachalo) {
                nash = true
                for para in tekst.dropFirst(metkaNachalo.count).split(separator: " ") {
                    let chasti = para.split(separator: "=", maxSplits: 1)
                    guard chasti.count == 2 else { continue }
                    let znachenie = String(chasti[1])
                    switch chasti[0] {
                    case "name": imya = znachenie
                    case "domain": domen = znachenie
                    case "created": sozdan = znachenie
                    default: break
                    }
                }
            }
            // Домен из самого блока — для чужих файлов без метки.
            if domen.isEmpty, tekst.hasSuffix("{"), !tekst.hasPrefix("#"), !tekst.hasPrefix("@") {
                let kandidat = tekst.dropLast().trimmingCharacters(in: .whitespaces)
                if Sayt.domenGodnyy(kandidat) { domen = kandidat }
            }
        }

        guard !domen.isEmpty else { return nil }
        return Sayt(imya: imya, domen: domen, sozdan: sozdan, nash: nash, faylBloka: imyaFayla)
    }

    /// Собрать блок Caddy для сайта.
    ///
    /// `statichnyePapki` — папки верхнего уровня из архива (assets, images,
    /// fonts…). Из них строится список путей, которые отдаются как файлы.
    /// Это важнее, чем кажется: если ловить файлы общим `try_files`, промах по
    /// картинке вернёт index.html с кодом 200, а правило кэширования пометит
    /// эту разметку «хранить неделю». На mebel-ryazane так и вышло — после
    /// выкладки фотографий на странице неделю не было ни одной.
    static func sobrat(
        imya: String,
        domen: String,
        statichnyePapki: [String],
        odnostranichnik: Bool,
        sozdan: Date = Date(),
        primechanie: String = ""
    ) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "ru_RU")
        let data = formatter.string(from: sozdan)

        let papki = statichnyePapki.sorted()
        let putiPapok = papki.map { "/\($0)/*" }
        let fiksirovannye = ["/favicon.ico", "/og.png", "/robots.txt", "/sitemap.xml"]
        let vseFaylovye = (putiPapok + fiksirovannye).joined(separator: " ")

        var stroki: [String] = []
        stroki.append("# vykladka: name=\(imya) domain=\(domen) created=\(data)")
        stroki.append("#")
        stroki.append("# Файл написан приложением «Выкладка». Правки руками переживут reload,")
        stroki.append("# но следующая выкладка этого сайта их перезапишет.")
        if !primechanie.isEmpty {
            stroki.append("#")
            for stroka in primechanie.split(separator: "\n") {
                stroki.append("# \(stroka)")
            }
        }
        stroki.append("")
        stroki.append("\(domen) {")
        stroki.append("\tencode gzip")
        stroki.append("")
        stroki.append("\theader {")
        stroki.append("\t\tStrict-Transport-Security \"max-age=31536000\"")
        stroki.append("\t\tX-Content-Type-Options nosniff")
        stroki.append("\t\tReferrer-Policy no-referrer")
        stroki.append("\t\t-Server")
        stroki.append("\t}")
        stroki.append("")
        stroki.append("\t# Лог посещений. Ротация обязательна: без неё файл растёт до отказа диска.")
        stroki.append("\tlog {")
        stroki.append("\t\toutput file /var/log/caddy/\(imya).log {")
        stroki.append("\t\t\troll_size 5MiB")
        stroki.append("\t\t\troll_keep 3")
        stroki.append("\t\t}")
        stroki.append("\t\tformat json")
        stroki.append("\t}")
        stroki.append("")
        stroki.append("\troot * /srv/\(imya)")
        stroki.append("")
        stroki.append("\t# Файлы отдаются как файлы: ненайденный — честный 404, а не index.html.")
        stroki.append("\t# Матчер намеренно БЕЗ `file`: промах обязан дойти до file_server.")
        stroki.append("\t@fayly path \(vseFaylovye)")
        stroki.append("\thandle @fayly {")
        stroki.append("\t\tfile_server")
        stroki.append("\t}")
        stroki.append("")
        if odnostranichnik {
            stroki.append("\t# Одностраничник: неизвестный путь отдаём index.html, чтобы ссылка")
            stroki.append("\t# с «хвостом» не приводила на 404.")
            stroki.append("\thandle {")
            stroki.append("\t\ttry_files {path} {path}/ /index.html")
            stroki.append("\t\tfile_server")
            stroki.append("\t}")
        } else {
            stroki.append("\thandle {")
            stroki.append("\t\tfile_server")
            stroki.append("\t}")
        }
        stroki.append("")

        // `file` в матчерах кэша обязателен: без него метка «хранить долго»
        // вешается и на ответ 404, то есть браузер запоминает промах.
        if papki.contains("assets") {
            stroki.append("\t# Бандл именован с хешем — можно кэшировать надолго.")
            stroki.append("\t@sborka {")
            stroki.append("\t\tpath /assets/*")
            stroki.append("\t\tfile")
            stroki.append("\t}")
            stroki.append("\theader @sborka Cache-Control \"public, max-age=2592000, immutable\"")
            stroki.append("")
        }
        let prochie = papki.filter { $0 != "assets" }
        if !prochie.isEmpty {
            stroki.append("\t# Картинки и шрифты хешем не именованы, но и меняются редко.")
            stroki.append("\t# Неделя, а не месяц: замена фотографии должна доехать до клиента,")
            stroki.append("\t# которому ссылку уже показали.")
            let putiProchih = prochie.map { "/" + $0 + "/*" }.joined(separator: " ")
            stroki.append("\t@fayly_prochie {")
            stroki.append("\t\tpath \(putiProchih)")
            stroki.append("\t\tfile")
            stroki.append("\t}")
            stroki.append("\theader @fayly_prochie Cache-Control \"public, max-age=604800\"")
            stroki.append("")
        }

        stroki.append("\t# Разметку кэшировать нельзя: она меняется на каждом обновлении и тянет")
        stroki.append("\t# за собой новые имена бандла. «/» в матчере обязателен — браузер")
        stroki.append("\t# запрашивает корень, и без него старая страница живёт в кэше.")
        stroki.append("\t@html path / /index.html")
        stroki.append("\theader @html Cache-Control \"no-cache\"")
        stroki.append("}")
        stroki.append("")

        return stroki.joined(separator: "\n")
    }
}
