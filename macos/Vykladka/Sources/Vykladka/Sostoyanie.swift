import Foundation
import SwiftUI

/// Состояние приложения: что знаем о сервере и сайтах.
///
/// Вся работа с сервером блокирующая (ssh, tar, разбор логов) и уходит в фон
/// через vFone; сюда результаты возвращаются уже на главном потоке.
@MainActor
final class Sostoyanie: ObservableObject {

    @Published var nastroyki: Nastroyki
    @Published var sayty: [Sayt] = []
    @Published var zdorovye: [String: Zdorovye] = [:]
    @Published var zahody: [String: [Poseshchenie]] = [:]
    @Published var serverSostoyanie: Server.SostoyanieServera?

    @Published var vybran: String?
    @Published var zanyat = false
    @Published var shag = ""
    @Published var oshibka: String?
    @Published var soobshchenie: String?

    private var baza: Baza?

    init() {
        nastroyki = Nastroyki.prochitat()
        Papki.pochistitVremennoe()
        baza = try? Baza()
        if nastroyki.podklyucheno {
            _ = try? Klyuchi.vylozhitVFayl()
        }
    }

    var server: Server { Server(nastroyki: nastroyki) }

    var vybrannyySayt: Sayt? { sayty.first { $0.imya == vybran } }

    func sohranitNastroyki() {
        nastroyki.zapisat()
    }

    // MARK: - Общий каркас операций

    private func rabota(_ nazvanie: String, _ delo: @escaping () throws -> Void) {
        guard !zanyat else { return }
        zanyat = true
        shag = nazvanie
        oshibka = nil
        Task {
            do {
                try await vFone(delo)
            } catch {
                oshibka = error.localizedDescription
            }
            zanyat = false
            shag = ""
        }
    }

    // MARK: - Обновление списка

    func obnovitVsyo() {
        guard nastroyki.podklyucheno else { return }
        zanyat = true
        shag = "Спрашиваю сервер…"
        Task {
            do {
                let server = self.server
                let spisok = try await vFone { try server.spisokSaytov() }
                let sostoyanie = try await vFone { try server.sostoyanie() }
                self.sayty = spisok
                self.serverSostoyanie = sostoyanie
                if self.vybran == nil { self.vybran = spisok.first?.imya }
            } catch {
                self.oshibka = error.localizedDescription
            }
            self.zanyat = false
            self.shag = ""
            await self.proveritZdorovye()
        }
    }

    func proveritZdorovye() async {
        for sayt in sayty {
            let rezultat = await Zdorovye.proverit(domen: sayt.domen)
            zdorovye[sayt.imya] = rezultat
        }
    }

    // MARK: - Посещения

    func obnovitPoseshcheniya(_ sayt: Sayt, dney: Int = 30) {
        guard let baza else { return }
        let kopiyaNastroek = self.nastroyki
        zanyat = true
        shag = "Читаю лог посещений…"
        Task {
            do {
                _ = try await vFone { try Zhurnal.sinhronizirovat(sayt: sayt, nastroyki: kopiyaNastroek, baza: baza) }
                let nachalo = Date().addingTimeInterval(-Double(dney) * 86400)
                let zaprosy = try await vFone { try baza.zaprosy(sayt: sayt.imya, s: nachalo) }
                let spisok = Zhurnal.zahody(zaprosy)
                // Обратные имена — по одному разу на адрес, с запоминанием.
                let adresa = Array(Set(spisok.filter { $0.vid == .chelovek }.map { $0.ip })).prefix(60)
                for ip in adresa {
                    if baza.imyaAdresa(ip) == nil {
                        let imya = try? await vFone { Imena.obratnoye(ip) }
                        baza.zapisatImyaAdresa(ip, imya ?? nil)
                    }
                }
                self.zahody[sayt.imya] = spisok
            } catch {
                self.oshibka = error.localizedDescription
            }
            self.zanyat = false
            self.shag = ""
        }
    }

    func imyaAdresa(_ ip: String) -> String? {
        guard let baza else { return nil }
        if let znachenie = baza.imyaAdresa(ip) { return znachenie }
        return nil
    }

    // MARK: - Выкладка

    func vylozhit(imya: String, domen: String, razbor: Arhiv.Razbor, pisatBlok: Bool, odnostranichnik: Bool) {
        guard !zanyat else { return }
        zanyat = true
        oshibka = nil
        soobshchenie = nil
        let server = self.server
        Task {
            do {
                try await vFone {
                    try server.vylozhit(
                        imya: imya, domen: domen, razbor: razbor,
                        pisatBlok: pisatBlok, odnostranichnik: odnostranichnik
                    ) { tekst in
                        DispatchQueue.main.async { self.shag = tekst }
                    }
                }
                if let vremennaya = razbor.vremennaya {
                    try? FileManager.default.removeItem(at: vremennaya)
                }
                self.soobshchenie = "Выложено: \(domen)"
                self.vybran = imya
            } catch {
                self.oshibka = error.localizedDescription
            }
            self.zanyat = false
            self.shag = ""
            self.obnovitVsyo()
        }
    }

    func otkatit(_ sayt: Sayt) {
        let server = self.server
        rabota("Возвращаю предыдущую версию…") {
            try server.otkatit(imya: sayt.imya)
        }
    }

    func udalit(_ sayt: Sayt) {
        guard !zanyat else { return }
        zanyat = true
        oshibka = nil
        let server = self.server
        Task {
            do {
                try await vFone {
                    try server.udalit(sayt: sayt) { tekst in
                        DispatchQueue.main.async { self.shag = tekst }
                    }
                }
                self.soobshchenie = "Сайт \(sayt.domen) убран с сервера."
                self.vybran = nil
            } catch {
                self.oshibka = error.localizedDescription
            }
            self.zanyat = false
            self.shag = ""
            self.obnovitVsyo()
        }
    }

    // MARK: - Подключение сервера

    /// Первое подключение: подтвердить ключ сервера, завести свой ключ и
    /// положить его в authorized_keys. Пароль после этого не хранится.
    func podklyuchit(parol: String, otpechatki: [String], stroki: String) async {
        zanyat = true
        oshibka = nil
        shag = "Настраиваю вход по ключу…"
        do {
            try Ssh.doveritKlyuchu(stroki: stroki)
            nastroyki.otpechatokServera = otpechatki.first ?? ""

            let publichnyy: String
            if let est = Klyuchi.publichnyyTekst(), Klyuchi.estKlyuch {
                publichnyy = est
            } else {
                let imyaMaka = Host.current().localizedName ?? "mac"
                publichnyy = try await vFone { try Klyuchi.sozdatParu(kommentariy: "vykladka@\(imyaMaka)") }
            }

            let kopiyaNastroek = self.nastroyki
            try await vFone {
                try Ssh.postavitKlyuchPoParolyu(nastroyki: kopiyaNastroek, parol: parol, publichnyyKlyuch: publichnyy)
            }
            try Klyuchi.vylozhitVFayl()

            let proverka = try await vFone { try Ssh(nastroyki: kopiyaNastroek).proverit() }
            guard proverka else {
                throw NSError(domain: "Vykladka", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: "Ключ поставлен, но вход по нему не работает. Проверьте, что на сервере разрешена аутентификация по ключу (PubkeyAuthentication yes)."
                ])
            }

            self.nastroyki.podklyucheno = true
            sohranitNastroyki()
            soobshchenie = "Сервер подключён. Пароль больше не нужен и нигде не сохранён."
        } catch {
            oshibka = error.localizedDescription
        }
        zanyat = false
        shag = ""
        obnovitVsyo()
    }

    func otklyuchit() {
        Klyuchi.udalit()
        Klyuchi.ubratFayl()
        nastroyki.podklyucheno = false
        sohranitNastroyki()
        sayty = []
        serverSostoyanie = nil
    }
}
