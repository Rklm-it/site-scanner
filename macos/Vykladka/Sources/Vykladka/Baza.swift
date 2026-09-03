import Foundation
import SQLite3

/// Свой SQLite: разобранные обращения к сайтам.
///
/// История живёт на маке, а не на сервере, и это осознанно. На сервере лог
/// ротируется по размеру и старое затирается; здесь остаётся всё, в том числе
/// по сайтам, которые давно удалены. Разбор тоже идёт на маке — серверу
/// достаётся только `tail`.
final class Baza {

    private var baza: OpaquePointer?
    private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    enum Beda: LocalizedError {
        case neOtkrylas(String)
        case zapros(String)

        var errorDescription: String? {
            switch self {
            case let .neOtkrylas(prichina): return "Не открылась база посещений: \(prichina)"
            case let .zapros(prichina): return "Ошибка базы: \(prichina)"
            }
        }
    }

    init() throws {
        guard sqlite3_open(Papki.baza.path, &baza) == SQLITE_OK else {
            let prichina = baza.map { String(cString: sqlite3_errmsg($0)) } ?? "неизвестно"
            throw Beda.neOtkrylas(prichina)
        }
        try vypolnit("PRAGMA journal_mode=WAL;")
        try sozdatTablicy()
    }

    deinit { sqlite3_close(baza) }

    private func vypolnit(_ sql: String) throws {
        var oshibka: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(baza, sql, nil, nil, &oshibka) != SQLITE_OK {
            let tekst = oshibka.map { String(cString: $0) } ?? "неизвестно"
            sqlite3_free(oshibka)
            throw Beda.zapros(tekst)
        }
    }

    private func sozdatTablicy() throws {
        try vypolnit("""
        CREATE TABLE IF NOT EXISTS zaprosy (
            sayt TEXT NOT NULL,
            kogda REAL NOT NULL,
            ip TEXT NOT NULL,
            metod TEXT NOT NULL DEFAULT '',
            uri TEXT NOT NULL DEFAULT '',
            status INTEGER NOT NULL DEFAULT 0,
            ua TEXT NOT NULL DEFAULT '',
            referer TEXT NOT NULL DEFAULT '',
            vid TEXT NOT NULL DEFAULT 'chelovek',
            PRIMARY KEY (sayt, kogda, ip, uri)
        );
        CREATE INDEX IF NOT EXISTS i_zaprosy_sayt ON zaprosy (sayt, kogda);

        CREATE TABLE IF NOT EXISTS smeshcheniya (
            sayt TEXT PRIMARY KEY,
            smeshchenie INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS imena_ip (
            ip TEXT PRIMARY KEY,
            imya TEXT,
            kogda REAL NOT NULL
        );
        """)
    }

    // MARK: - Запросы

    func dobavit(_ zaprosy: [Zapros]) throws {
        guard !zaprosy.isEmpty else { return }
        try vypolnit("BEGIN;")
        var operator_: OpaquePointer?
        let sql = """
        INSERT OR IGNORE INTO zaprosy (sayt, kogda, ip, metod, uri, status, ua, referer, vid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        guard sqlite3_prepare_v2(baza, sql, -1, &operator_, nil) == SQLITE_OK else {
            try? vypolnit("ROLLBACK;")
            throw Beda.zapros(String(cString: sqlite3_errmsg(baza)))
        }
        defer { sqlite3_finalize(operator_) }

        for zapros in zaprosy {
            sqlite3_reset(operator_)
            sqlite3_bind_text(operator_, 1, zapros.sayt, -1, SQLITE_TRANSIENT)
            sqlite3_bind_double(operator_, 2, zapros.kogda.timeIntervalSince1970)
            sqlite3_bind_text(operator_, 3, zapros.ip, -1, SQLITE_TRANSIENT)
            sqlite3_bind_text(operator_, 4, zapros.metod, -1, SQLITE_TRANSIENT)
            sqlite3_bind_text(operator_, 5, zapros.uri, -1, SQLITE_TRANSIENT)
            sqlite3_bind_int(operator_, 6, Int32(zapros.status))
            sqlite3_bind_text(operator_, 7, zapros.ua, -1, SQLITE_TRANSIENT)
            sqlite3_bind_text(operator_, 8, zapros.referer, -1, SQLITE_TRANSIENT)
            sqlite3_bind_text(operator_, 9, zapros.vid.rawValue, -1, SQLITE_TRANSIENT)
            guard sqlite3_step(operator_) == SQLITE_DONE else {
                try? vypolnit("ROLLBACK;")
                throw Beda.zapros(String(cString: sqlite3_errmsg(baza)))
            }
        }
        try vypolnit("COMMIT;")
    }

    func zaprosy(sayt: String, s nachalo: Date) throws -> [Zapros] {
        var operator_: OpaquePointer?
        let sql = """
        SELECT kogda, ip, metod, uri, status, ua, referer, vid
        FROM zaprosy WHERE sayt = ? AND kogda >= ? ORDER BY kogda;
        """
        guard sqlite3_prepare_v2(baza, sql, -1, &operator_, nil) == SQLITE_OK else {
            throw Beda.zapros(String(cString: sqlite3_errmsg(baza)))
        }
        defer { sqlite3_finalize(operator_) }
        sqlite3_bind_text(operator_, 1, sayt, -1, SQLITE_TRANSIENT)
        sqlite3_bind_double(operator_, 2, nachalo.timeIntervalSince1970)

        var sobrano: [Zapros] = []
        while sqlite3_step(operator_) == SQLITE_ROW {
            sobrano.append(Zapros(
                sayt: sayt,
                kogda: Date(timeIntervalSince1970: sqlite3_column_double(operator_, 0)),
                ip: tekst(operator_, 1),
                metod: tekst(operator_, 2),
                uri: tekst(operator_, 3),
                status: Int(sqlite3_column_int(operator_, 4)),
                ua: tekst(operator_, 5),
                referer: tekst(operator_, 6),
                vid: Zapros.Vid(rawValue: tekst(operator_, 7)) ?? .chelovek
            ))
        }
        return sobrano
    }

    private func tekst(_ operator_: OpaquePointer?, _ nomer: Int32) -> String {
        guard let ukazatel = sqlite3_column_text(operator_, nomer) else { return "" }
        return String(cString: ukazatel)
    }

    // MARK: - Смещения в логах

    func smeshchenie(sayt: String) -> Int64 {
        var operator_: OpaquePointer?
        guard sqlite3_prepare_v2(baza, "SELECT smeshchenie FROM smeshcheniya WHERE sayt = ?;", -1, &operator_, nil) == SQLITE_OK else {
            return 0
        }
        defer { sqlite3_finalize(operator_) }
        sqlite3_bind_text(operator_, 1, sayt, -1, SQLITE_TRANSIENT)
        guard sqlite3_step(operator_) == SQLITE_ROW else { return 0 }
        return sqlite3_column_int64(operator_, 0)
    }

    func zapisatSmeshchenie(sayt: String, _ znachenie: Int64) throws {
        var operator_: OpaquePointer?
        let sql = "INSERT INTO smeshcheniya (sayt, smeshchenie) VALUES (?, ?) ON CONFLICT(sayt) DO UPDATE SET smeshchenie = excluded.smeshchenie;"
        guard sqlite3_prepare_v2(baza, sql, -1, &operator_, nil) == SQLITE_OK else {
            throw Beda.zapros(String(cString: sqlite3_errmsg(baza)))
        }
        defer { sqlite3_finalize(operator_) }
        sqlite3_bind_text(operator_, 1, sayt, -1, SQLITE_TRANSIENT)
        sqlite3_bind_int64(operator_, 2, znachenie)
        guard sqlite3_step(operator_) == SQLITE_DONE else {
            throw Beda.zapros(String(cString: sqlite3_errmsg(baza)))
        }
    }

    // MARK: - Обратные имена адресов

    func imyaAdresa(_ ip: String) -> String?? {
        var operator_: OpaquePointer?
        guard sqlite3_prepare_v2(baza, "SELECT imya FROM imena_ip WHERE ip = ?;", -1, &operator_, nil) == SQLITE_OK else {
            return nil
        }
        defer { sqlite3_finalize(operator_) }
        sqlite3_bind_text(operator_, 1, ip, -1, SQLITE_TRANSIENT)
        guard sqlite3_step(operator_) == SQLITE_ROW else { return nil }
        if sqlite3_column_type(operator_, 0) == SQLITE_NULL { return .some(nil) }
        return .some(tekst(operator_, 0))
    }

    func zapisatImyaAdresa(_ ip: String, _ imya: String?) {
        var operator_: OpaquePointer?
        let sql = "INSERT INTO imena_ip (ip, imya, kogda) VALUES (?, ?, ?) ON CONFLICT(ip) DO UPDATE SET imya = excluded.imya, kogda = excluded.kogda;"
        guard sqlite3_prepare_v2(baza, sql, -1, &operator_, nil) == SQLITE_OK else { return }
        defer { sqlite3_finalize(operator_) }
        sqlite3_bind_text(operator_, 1, ip, -1, SQLITE_TRANSIENT)
        if let imya {
            sqlite3_bind_text(operator_, 2, imya, -1, SQLITE_TRANSIENT)
        } else {
            sqlite3_bind_null(operator_, 2)
        }
        sqlite3_bind_double(operator_, 3, Date().timeIntervalSince1970)
        sqlite3_step(operator_)
    }
}
