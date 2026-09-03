import Foundation

/// Запуск внешней программы. Всё общение с сервером идёт через системный ssh,
/// поэтому этот файл — фундамент всего остального.
enum Zapusk {

    struct Rezultat {
        var kod: Int32
        var vyvod: Data
        var oshibka: String

        var tekst: String { String(decoding: vyvod, as: UTF8.self) }
        var udalos: Bool { kod == 0 }
    }

    enum Beda: LocalizedError {
        case neZapustilas(String, String)
        case upala(String, Int32, String)

        var errorDescription: String? {
            switch self {
            case let .neZapustilas(programma, prichina):
                return "Не удалось запустить \(programma): \(prichina)"
            case let .upala(programma, kod, oshibka):
                let hvost = oshibka.trimmingCharacters(in: .whitespacesAndNewlines)
                return "\(programma) вернула код \(kod)" + (hvost.isEmpty ? "" : ":\n\(hvost)")
            }
        }
    }

    /// Запустить и дождаться. Ввод можно передать данными или файлом — файл
    /// нужен для выгрузки: архив на несколько сотен мегабайт в память тянуть
    /// незачем, ssh прочитает его сам.
    ///
    /// Оба потока вывода читаются в отдельных потоках. Без этого запуск с
    /// большим выводом встаёт намертво: труба забивается на 64 КБ, дочерний
    /// процесс блокируется на write, а мы ждём его завершения.
    static func zapustit(
        _ put: String,
        _ argumenty: [String],
        vhod: Data? = nil,
        vhodFayl: URL? = nil,
        sreda: [String: String]? = nil
    ) throws -> Rezultat {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: put)
        process.arguments = argumenty

        if let sreda {
            var polnaya = ProcessInfo.processInfo.environment
            for (klyuch, znachenie) in sreda { polnaya[klyuch] = znachenie }
            process.environment = polnaya
        }

        let trubaVyvoda = Pipe()
        let trubaOshibok = Pipe()
        process.standardOutput = trubaVyvoda
        process.standardError = trubaOshibok

        var trubaVhoda: Pipe?
        if let vhodFayl {
            guard let deskriptor = try? FileHandle(forReadingFrom: vhodFayl) else {
                throw Beda.neZapustilas(put, "не открылся файл ввода \(vhodFayl.path)")
            }
            process.standardInput = deskriptor
        } else {
            let truba = Pipe()
            trubaVhoda = truba
            process.standardInput = truba
        }

        var sobrannyyVyvod = Data()
        var sobrannayaOshibka = Data()
        let gruppa = DispatchGroup()
        let ochered = DispatchQueue(label: "vykladka.chtenie", attributes: .concurrent)

        gruppa.enter()
        ochered.async {
            sobrannyyVyvod = trubaVyvoda.fileHandleForReading.readDataToEndOfFile()
            gruppa.leave()
        }
        gruppa.enter()
        ochered.async {
            sobrannayaOshibka = trubaOshibok.fileHandleForReading.readDataToEndOfFile()
            gruppa.leave()
        }

        do {
            try process.run()
        } catch {
            throw Beda.neZapustilas(put, error.localizedDescription)
        }

        if let trubaVhoda {
            if let vhod { trubaVhoda.fileHandleForWriting.write(vhod) }
            try? trubaVhoda.fileHandleForWriting.close()
        }

        process.waitUntilExit()
        gruppa.wait()

        return Rezultat(
            kod: process.terminationStatus,
            vyvod: sobrannyyVyvod,
            oshibka: String(decoding: sobrannayaOshibka, as: UTF8.self)
        )
    }

    /// То же самое, но неуспешный код — это ошибка. Так вызывать удобнее там,
    /// где продолжать после провала бессмысленно.
    @discardableResult
    static func objazatelno(
        _ put: String,
        _ argumenty: [String],
        vhod: Data? = nil,
        vhodFayl: URL? = nil,
        sreda: [String: String]? = nil
    ) throws -> Rezultat {
        let rezultat = try zapustit(put, argumenty, vhod: vhod, vhodFayl: vhodFayl, sreda: sreda)
        guard rezultat.udalos else {
            throw Beda.upala((put as NSString).lastPathComponent, rezultat.kod, rezultat.oshibka)
        }
        return rezultat
    }
}

/// Выполнить блокирующую работу в фоне и дождаться из async-кода.
/// Вся работа с сервером блокирующая: ssh, tar, разбор логов. Держать её на
/// главном потоке нельзя — окно замрёт на всё время выкладки.
func vFone<T>(_ rabota: @escaping () throws -> T) async throws -> T {
    try await withCheckedThrowingContinuation { prodolzhenie in
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                prodolzhenie.resume(returning: try rabota())
            } catch {
                prodolzhenie.resume(throwing: error)
            }
        }
    }
}
