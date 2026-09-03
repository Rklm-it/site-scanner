import SwiftUI

struct NastroykiVid: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    @Environment(\.dismiss) private var zakryt

    @State private var obnovlyayuGeo = false
    @State private var sprositOtklyuchenie = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    server
                    puti
                    geo
                    opasnoe
                }
                .padding(24)
            }
            Divider()
            HStack {
                Spacer()
                Button("Готово") {
                    sostoyanie.sohranitNastroyki()
                    zakryt()
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(16)
        }
        .frame(width: 620, height: 600)
        .confirmationDialog("Отключить сервер?", isPresented: $sprositOtklyuchenie, titleVisibility: .visible) {
            Button("Отключить", role: .destructive) {
                sostoyanie.otklyuchit()
                zakryt()
            }
            Button("Отмена", role: .cancel) { }
        } message: {
            Text("Ключ будет удалён из Связки. На сервере он останется в authorized_keys — убрать его оттуда придётся вручную.")
        }
    }

    private var server: some View {
        GroupBox("Сервер") {
            VStack(alignment: .leading, spacing: 8) {
                Text(sostoyanie.nastroyki.opisanie).font(.system(.body, design: .monospaced))
                if !sostoyanie.nastroyki.otpechatokServera.isEmpty {
                    Text("Отпечаток: \(sostoyanie.nastroyki.otpechatokServera)")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                Text("Вход по ключу; пароль нигде не сохранён.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(6)
        }
    }

    private var puti: some View {
        GroupBox("Пути на сервере") {
            VStack(alignment: .leading, spacing: 10) {
                pole("Сайты", $sostoyanie.nastroyki.papkaSaytov)
                pole("Блоки Caddy", $sostoyanie.nastroyki.papkaBlokov)
                pole("Логи", $sostoyanie.nastroyki.papkaLogov)
                pole("Каталог docker compose", $sostoyanie.nastroyki.papkaCompose)
                Text("Это сервер прототипов: /root/site-scanner. На сервере сканера каталог называется "
                     + "иначе (/root/site-scanner-main), и Caddy прототипов там нет.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            .padding(6)
        }
    }

    private func pole(_ nazvanie: String, _ znachenie: Binding<String>) -> some View {
        HStack {
            Text(nazvanie).frame(width: 170, alignment: .leading)
            TextField("", text: znachenie).font(.system(.body, design: .monospaced))
        }
    }

    private var geo: some View {
        GroupBox("Определение страны") {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Button(obnovlyayuGeo ? "Качаю…" : "Обновить базу") { obnovitGeo() }
                        .disabled(obnovlyayuGeo)
                    if obnovlyayuGeo { ProgressView().controlSize(.small) }
                    Text(Geo.shared.zagruzhena ? "база загружена" : "базы нет — страна показываться не будет")
                        .foregroundStyle(.secondary)
                }
                Text("Файл скачивается на мак и используется офлайн: адреса посетителей никуда не "
                     + "отправляются. Города в бесплатной базе нет — вместо него показывается обратное "
                     + "имя адреса, у российских провайдеров в нём обычно виден оператор и город.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                Text("IP-геолокация: DB-IP (db-ip.com), лицензия CC BY 4.0.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(6)
        }
    }

    private var opasnoe: some View {
        GroupBox("Прочее") {
            VStack(alignment: .leading, spacing: 10) {
                Button("Перечитать Caddy на сервере") { perechitat() }
                    .disabled(sostoyanie.zanyat)
                Text("Нужно, если блок правили руками, минуя приложение.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                Divider()
                Button("Отключить сервер", role: .destructive) { sprositOtklyuchenie = true }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(6)
        }
    }

    private func obnovitGeo() {
        obnovlyayuGeo = true
        Task {
            do {
                try await Geo.shared.obnovit()
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            obnovlyayuGeo = false
        }
    }

    private func perechitat() {
        let server = sostoyanie.server
        Task {
            do {
                try await vFone { try server.perechitat() }
                sostoyanie.soobshchenie = "Caddy перечитал конфиг."
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
        }
    }
}
