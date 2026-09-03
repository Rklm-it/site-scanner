import Foundation

/// Разбор того, что положили в окно: архив со сборкой или готовая папка.
enum Arhiv {

    struct Sled: Identifiable {
        var id = UUID()
        var fayl: String
        var fragment: String
    }

    struct Razbor: Identifiable {
        var id = UUID()
        /// Папка, внутри которой лежит index.html. Именно её содержимое уезжает на сервер.
        var korn: URL
        /// Папка, которую надо удалить после выкладки (распакованный архив).
        var vremennaya: URL?
        var statichnyePapki: [String]
        var faylov: Int
        var razmer: Int64
        var sledyLovable: [Sled]
        /// Похоже на сборку одностраничника (Vite/React) — значит неизвестные
        /// пути надо отдавать index.html.
        var odnostranichnik: Bool

        var razmerTekstom: String {
            ByteCountFormatter.string(fromByteCount: razmer, countStyle: .file)
        }
    }

    enum Beda: LocalizedError {
        case neznakomyyFormat(String)
        case netIndexa
        case pusto

        var errorDescription: String? {
            switch self {
            case let .neznakomyyFormat(rasshirenie):
                return "Не понимаю формат «\(rasshirenie)». Кладите .zip, .tar.gz или папку со сборкой."
            case .netIndexa:
                return "В архиве нет index.html — это не собранный сайт. Кладите результат сборки (папка dist), а не исходники."
            case .pusto:
                return "Архив пустой."
            }
        }
    }

    // MARK: - Распаковка

    static func razobrat(_ istochnik: URL) throws -> Razbor {
        var vremennaya: URL?
        let raspakovano: URL

        var eto_papka: ObjCBool = false
        FileManager.default.fileExists(atPath: istochnik.path, isDirectory: &eto_papka)

        if eto_papka.boolValue {
            raspakovano = istochnik
        } else {
            let kuda = Papki.vremennaya.appendingPathComponent("raspakovka-\(UUID().uuidString)", isDirectory: true)
            try FileManager.default.createDirectory(at: kuda, withIntermediateDirectories: true)
            vremennaya = kuda
            try raspakovat(istochnik, v: kuda)
            raspakovano = kuda
        }

        guard let korn = naytiKoren(raspakovano) else {
            if let vremennaya { try? FileManager.default.removeItem(at: vremennaya) }
            throw Beda.netIndexa
        }

        let papki = papkiVerhnegoUrovnya(korn)
        let (faylov, razmer) = posschitat(korn)
        guard faylov > 0 else { throw Beda.pusto }

        return Razbor(
            korn: korn,
            vremennaya: vremennaya,
            statichnyePapki: papki,
            faylov: faylov,
            razmer: razmer,
            sledyLovable: naytiSledyLovable(korn),
            // Сборка Vite кладёт бандл в assets/ — у неё есть клиентский
            // роутер, и неизвестные пути должны отдавать index.html. Одиночная
            // страница без assets в этом не нуждается.
            odnostranichnik: papki.contains("assets")
        )
    }

    private static func raspakovat(_ arhiv: URL, v papka: URL) throws {
        let imya = arhiv.lastPathComponent.lowercased()
        if imya.hasSuffix(".zip") {
            // ditto, а не unzip: правильно разбирает архивы, сделанные Finder-ом.
            try Zapusk.objazatelno("/usr/bin/ditto", ["-x", "-k", arhiv.path, papka.path])
        } else if imya.hasSuffix(".tar.gz") || imya.hasSuffix(".tgz") || imya.hasSuffix(".tar") {
            try Zapusk.objazatelno("/usr/bin/tar", ["-xf", arhiv.path, "-C", papka.path])
        } else {
            throw Beda.neznakomyyFormat(arhiv.pathExtension)
        }
    }

    /// Найти папку с index.html. Архив бывает и с одной обёрткой внутри
    /// (dist/, build/, имя проекта) — заходим внутрь, но не глубже трёх уровней,
    /// чтобы не подобрать index.html из какого-нибудь примера в node_modules.
    private static func naytiKoren(_ nachalo: URL) -> URL? {
        let fm = FileManager.default
        var ocheredi: [(URL, Int)] = [(nachalo, 0)]
        while !ocheredi.isEmpty {
            let (papka, glubina) = ocheredi.removeFirst()
            guard let soderzhimoe = try? fm.contentsOfDirectory(
                at: papka, includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]) else { continue }

            if soderzhimoe.contains(where: { $0.lastPathComponent == "index.html" }) {
                return papka
            }
            guard glubina < 3 else { continue }
            for element in soderzhimoe where element.lastPathComponent != "__MACOSX" {
                var eto_papka: ObjCBool = false
                fm.fileExists(atPath: element.path, isDirectory: &eto_papka)
                if eto_papka.boolValue { ocheredi.append((element, glubina + 1)) }
            }
        }
        return nil
    }

    private static func papkiVerhnegoUrovnya(_ korn: URL) -> [String] {
        let fm = FileManager.default
        guard let soderzhimoe = try? fm.contentsOfDirectory(
            at: korn, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else { return [] }
        var papki: [String] = []
        for element in soderzhimoe {
            var eto_papka: ObjCBool = false
            fm.fileExists(atPath: element.path, isDirectory: &eto_papka)
            let imya = element.lastPathComponent
            if eto_papka.boolValue && imya != "__MACOSX" { papki.append(imya) }
        }
        return papki.sorted()
    }

    private static func posschitat(_ korn: URL) -> (Int, Int64) {
        let fm = FileManager.default
        var faylov = 0
        var razmer: Int64 = 0
        guard let obhod = fm.enumerator(at: korn, includingPropertiesForKeys: [.fileSizeKey, .isRegularFileKey]) else {
            return (0, 0)
        }
        for sluchay in obhod {
            guard let url = sluchay as? URL,
                  let svoystva = try? url.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey]),
                  svoystva.isRegularFile == true else { continue }
            faylov += 1
            razmer += Int64(svoystva.fileSize ?? 0)
        }
        return (faylov, razmer)
    }

    // MARK: - Следы конструктора

    /// Клиент смотрит на сайт своей компании, а не на витрину чужого
    /// конструктора: бейдж «Edit with Lovable» в углу превращает показ работы в
    /// показ инструмента, и по нему за минуту выясняется, что «сайт собран
    /// мышкой». Пересборка возвращает следы обратно, поэтому проверка идёт
    /// перед КАЖДОЙ выкладкой, а не один раз при заведении клиента.
    static let priznakiLovable = ["lovable", "gpteng", "gptengineer"]

    static func naytiSledyLovable(_ korn: URL) -> [Sled] {
        let fm = FileManager.default
        let interesnye: Set<String> = ["html", "js", "mjs", "css", "json", "webmanifest", "xml", "txt"]
        var naydeno: [Sled] = []

        guard let obhod = fm.enumerator(at: korn, includingPropertiesForKeys: [.fileSizeKey]) else { return [] }
        for sluchay in obhod {
            guard let url = sluchay as? URL,
                  interesnye.contains(url.pathExtension.lowercased()),
                  let svoystva = try? url.resourceValues(forKeys: [.fileSizeKey]),
                  (svoystva.fileSize ?? 0) < 16 * 1024 * 1024,
                  let dannye = try? Data(contentsOf: url) else { continue }

            let tekst = String(decoding: dannye, as: UTF8.self)
            let nizhniy = tekst.lowercased()
            for priznak in priznakiLovable where nizhniy.contains(priznak) {
                let otnositelnyy = url.path.replacingOccurrences(of: korn.path + "/", with: "")
                naydeno.append(Sled(fayl: otnositelnyy, fragment: vyrezat(nizhniy, vokrug: priznak)))
                break
            }
            if naydeno.count >= 40 { break }
        }
        return naydeno
    }

    private static func vyrezat(_ tekst: String, vokrug priznak: String) -> String {
        guard let diapazon = tekst.range(of: priznak) else { return priznak }
        let nachalo = tekst.index(diapazon.lowerBound, offsetBy: -50, limitedBy: tekst.startIndex) ?? tekst.startIndex
        let konec = tekst.index(diapazon.upperBound, offsetBy: 50, limitedBy: tekst.endIndex) ?? tekst.endIndex
        return String(tekst[nachalo..<konec])
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespaces)
    }

    // MARK: - Упаковка для отправки

    /// Сложить содержимое папки в .tar.gz для отправки. Отдельный файл, а не
    /// поток: так видно размер (значит можно показать прогресс) и не нужен
    /// шелл с трубой между двумя процессами.
    static func upakovat(_ korn: URL) throws -> URL {
        let kuda = Papki.vremennaya.appendingPathComponent("otpravka-\(UUID().uuidString).tar.gz")
        try Zapusk.objazatelno("/usr/bin/tar", [
            "--no-mac-metadata",
            "--exclude", ".DS_Store",
            "--exclude", "__MACOSX",
            "--exclude", ".git",
            "-czf", kuda.path,
            "-C", korn.path, "."
        ], sreda: ["COPYFILE_DISABLE": "1"])
        return kuda
    }
}
