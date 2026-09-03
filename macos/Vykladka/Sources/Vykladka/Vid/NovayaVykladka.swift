import SwiftUI

/// Что делать с положенным архивом: завести новый сайт или обновить готовый.
struct NovayaVykladka: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    @Environment(\.dismiss) private var zakryt

    var razbor: Arhiv.Razbor

    @State private var novyy = true
    @State private var imya = ""
    @State private var domen = ""
    @State private var obnovlyaemyy = ""
    @State private var odnostranichnik = true
    @State private var nesmotryaNaSledy = false
    @State private var proverkaDomena: ProverkaDomena?
    @State private var proveryayu = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    svodkaArhiva
                    vyborCeli
                    if !razbor.sledyLovable.isEmpty { sledy }
                }
                .padding(24)
            }
            Divider()
            nizhnyayaPanel
        }
        .frame(width: 620, height: 620)
        .onAppear { podgotovit() }
    }

    // MARK: - Архив

    private var svodkaArhiva: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Архив разобран").font(.title2.bold())
            Text("\(razbor.faylov) файлов, \(razbor.razmerTekstom)")
                .foregroundStyle(.secondary)
            if !razbor.statichnyePapki.isEmpty {
                Text("Папки: \(razbor.statichnyePapki.joined(separator: ", "))")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Toggle("Одностраничник: неизвестные пути отдавать index.html", isOn: $odnostranichnik)
                .padding(.top, 4)
        }
    }

    // MARK: - Куда

    private var vyborCeli: some View {
        VStack(alignment: .leading, spacing: 14) {
            Picker("", selection: $novyy) {
                Text("Новый сайт").tag(true)
                Text("Обновить готовый").tag(false)
            }
            .pickerStyle(.segmented)

            if novyy {
                TextField("Имя (латиницей: papinalavka)", text: $imya)
                TextField("Домен (lavka-review.nexus-flow.ru)", text: $domen)
                    .onSubmit { proveritDomen() }
                HStack {
                    Button(proveryayu ? "Проверяю…" : "Проверить A-запись") { proveritDomen() }
                        .disabled(domen.isEmpty || proveryayu)
                    if proveryayu { ProgressView().controlSize(.small) }
                }
                if let proverka = proverkaDomena {
                    HStack(alignment: .top, spacing: 7) {
                        Image(systemName: proverka.sovpadaet ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                            .foregroundStyle(proverka.sovpadaet ? .green : .orange)
                        Text(proverka.opisanie).font(.callout)
                    }
                    if !proverka.sovpadaet {
                        Text("Caddy пойдёт за сертификатом сразу, как увидит домен. Пока A-запись не "
                             + "на этот сервер, выпуск не пройдёт, а повторы упрутся в недельный лимит "
                             + "Let's Encrypt — тогда домен не включится, даже когда DNS почините.")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                }
            } else {
                Picker("Какой сайт обновляем", selection: $obnovlyaemyy) {
                    ForEach(sostoyanie.sayty) { sayt in
                        Text("\(sayt.domen)  (\(sayt.imya))").tag(sayt.imya)
                    }
                }
                .pickerStyle(.menu)
                Text("Файлы заменятся целиком, предыдущая версия останется рядом — откатить можно одной кнопкой.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Следы конструктора

    private var sledy: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Нашлись следы Lovable — \(razbor.sledyLovable.count) файлов", systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .font(.headline)
            Text("Клиент смотрит на сайт своей компании, а не на витрину конструктора. "
                 + "По бейджу в углу за минуту выясняется, что «сайт собран мышкой», — и разговор о цене "
                 + "после этого другой. Пересборка возвращает следы обратно, поэтому проверка идёт "
                 + "перед каждой выкладкой.")
                .font(.callout)
                .foregroundStyle(.secondary)
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(razbor.sledyLovable) { sled in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(sled.fayl).font(.system(.caption, design: .monospaced))
                            Text(sled.fragment)
                                .font(.system(.caption2, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: 130)
            .padding(8)
            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))

            Toggle("Всё равно выложить", isOn: $nesmotryaNaSledy)
        }
    }

    // MARK: - Низ

    private var nizhnyayaPanel: some View {
        HStack {
            if sostoyanie.zanyat {
                ProgressView().controlSize(.small)
                Text(sostoyanie.shag).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Отмена") {
                if let vremennaya = razbor.vremennaya { try? FileManager.default.removeItem(at: vremennaya) }
                zakryt()
            }
            Button("Выложить") { vylozhit() }
                .keyboardShortcut(.defaultAction)
                .disabled(!gotovo)
        }
        .padding(16)
    }

    private var gotovo: Bool {
        if sostoyanie.zanyat { return false }
        if !razbor.sledyLovable.isEmpty && !nesmotryaNaSledy { return false }
        if novyy {
            return Sayt.imyaGodnoe(imya) && Sayt.domenGodnyy(domen)
        }
        return !obnovlyaemyy.isEmpty
    }

    // MARK: - Действия

    private func podgotovit() {
        obnovlyaemyy = sostoyanie.vybran ?? sostoyanie.sayty.first?.imya ?? ""
        novyy = sostoyanie.sayty.isEmpty
        odnostranichnik = razbor.odnostranichnik
        if imya.isEmpty {
            imya = razbor.korn.deletingPathExtension().lastPathComponent
                .lowercased()
                .replacingOccurrences(of: "[^a-z0-9-]", with: "-", options: .regularExpression)
                .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
        }
    }

    private func proveritDomen() {
        let imyaDomena = domen.trimmingCharacters(in: .whitespaces).lowercased()
        guard !imyaDomena.isEmpty else { return }
        proveryayu = true
        let nastroyki = sostoyanie.nastroyki
        Task {
            let rezultat = try? await vFone { ProverkaDomena.proverit(domen: imyaDomena, nastroyki: nastroyki) }
            proverkaDomena = rezultat
            proveryayu = false
        }
    }

    private func vylozhit() {
        if novyy {
            sostoyanie.vylozhit(
                imya: imya, domen: domen.trimmingCharacters(in: .whitespaces).lowercased(),
                razbor: razbor, pisatBlok: true, odnostranichnik: odnostranichnik
            )
        } else {
            guard let sayt = sostoyanie.sayty.first(where: { $0.imya == obnovlyaemyy }) else { return }
            // Чужой блок не трогаем: его завёл человек и, возможно, не так, как
            // сделало бы приложение. Файлы обновляем, конфиг оставляем.
            sostoyanie.vylozhit(
                imya: sayt.imya, domen: sayt.domen,
                razbor: razbor, pisatBlok: sayt.nash, odnostranichnik: odnostranichnik
            )
        }
        zakryt()
    }
}
