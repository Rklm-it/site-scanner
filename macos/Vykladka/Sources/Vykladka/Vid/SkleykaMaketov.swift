import SwiftUI
import AppKit
import UniformTypeIdentifiers

struct ParaMaketov: Identifiable {
    var id = UUID()
    var para: Makety.Para
    var vremennaya: URL?
}

/// Две версии из Stitch — под ПК и под телефон — в одну страницу.
struct SkleykaMaketov: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    @Environment(\.dismiss) private var zakryt

    var nachalnaya: ParaMaketov
    var gotovo: (Makety.Itog, URL?) -> Void

    @State private var pk: URL
    @State private var telefon: URL
    @State private var skachivatKartinki = true
    @State private var mestnyyTailwind = true
    @State private var idet = false
    @State private var shag = ""

    init(nachalnaya: ParaMaketov, gotovo: @escaping (Makety.Itog, URL?) -> Void) {
        self.nachalnaya = nachalnaya
        self.gotovo = gotovo
        _pk = State(initialValue: nachalnaya.para.pk)
        _telefon = State(initialValue: nachalnaya.para.telefon)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    zagolovok
                    versii
                    chto_zabrat
                    pochemu
                }
                .padding(24)
            }
            Divider()
            niz
        }
        .frame(width: 620, height: 600)
    }

    private var zagolovok: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Две версии в одну страницу").font(.title2.bold())
            Text("В папке нашлись два макета и ни одного index.html — похоже на выгрузку из Stitch. "
                 + "Склею их в одну страницу: широкий экран увидит версию для ПК, узкий — для телефона.")
                .foregroundStyle(.secondary)
        }
    }

    private var versii: some View {
        VStack(alignment: .leading, spacing: 10) {
            stroka("Версия для ПК", pk) { vybrat { pk = $0 } }
            stroka("Версия для телефона", telefon) { vybrat { telefon = $0 } }
            Button {
                let bylo = pk
                pk = telefon
                telefon = bylo
            } label: {
                Label("Поменять местами", systemImage: "arrow.left.arrow.right")
            }
            Text("Версии определены по разметке: в настольной много брейкпоинтов Tailwind, "
                 + "в телефонной их почти нет. По именам файлов Stitch их не отличить.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    private func stroka(_ nazvanie: String, _ fayl: URL, _ deystvie: @escaping () -> Void) -> some View {
        HStack {
            Text(nazvanie).frame(width: 170, alignment: .leading)
            Text(fayl.deletingLastPathComponent().lastPathComponent + "/" + fayl.lastPathComponent)
                .font(.system(.callout, design: .monospaced))
                .lineLimit(1)
                .truncationMode(.head)
            Spacer()
            Button("Выбрать…", action: deystvie)
        }
    }

    private var chto_zabrat: some View {
        VStack(alignment: .leading, spacing: 10) {
            Toggle("Забрать картинки к себе", isOn: $skachivatKartinki)
            Text("Картинки макета лежат на серверах Stitch по временным ссылкам. Ссылка протухнет — "
                 + "клиент откроет прототип и увидит пустые места, причём ровно тогда, когда решит "
                 + "показать его партнёру. Та же беда была у мебельщика: все фотографии жили на чужом CDN.")
                .font(.callout)
                .foregroundStyle(.secondary)
            Toggle("Забрать Tailwind к себе", isOn: $mestnyyTailwind)
            Text("Иначе стили тянутся скриптом с чужого CDN и компилируются в браузере: недоступен CDN — "
                 + "сайт открывается голой разметкой.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    private var pochemu: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Почему одна страница, а не два адреса").font(.headline)
            Text("Отдавать разные файлы по User-Agent нельзя: превью мессенджеров приходят с непонятным "
                 + "User-Agent и утащат не ту версию; ссылку пересылают с телефона на ПК; ноутбук с окном "
                 + "в половину экрана — «ПК» по User-Agent и телефон по факту. Переключение идёт по ширине "
                 + "окна, поэтому всё это решается само.\n\n"
                 + "Плата — страница весит вдвое: браузер грузит обе вёрстки, показывает одну. Для показа "
                 + "это ничего, перед сдачей вёрстки надо свести в одну адаптивную.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    private var niz: some View {
        HStack {
            if idet {
                ProgressView().controlSize(.small)
                Text(shag).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Отмена") {
                if let vremennaya = nachalnaya.vremennaya {
                    try? FileManager.default.removeItem(at: vremennaya)
                }
                zakryt()
            }
            Button("Склеить") { skleit() }
                .keyboardShortcut(.defaultAction)
                .disabled(idet)
        }
        .padding(16)
    }

    private func vybrat(_ kuda: @escaping (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.html]
        panel.message = "HTML-файл макета"
        if panel.runModal() == .OK, let adres = panel.url { kuda(adres) }
    }

    private func skleit() {
        idet = true
        let para = Makety.Para(pk: pk, telefon: telefon)
        let kartinki = skachivatKartinki
        let tailwind = mestnyyTailwind
        Task {
            do {
                let itog = try await vFone {
                    try Makety.sobratPapku(para, skachivatKartinki: kartinki, mestnyyTailwind: tailwind) { tekst in
                        DispatchQueue.main.async { shag = tekst }
                    }
                }
                gotovo(itog, nachalnaya.vremennaya)
                zakryt()
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            idet = false
            shag = ""
        }
    }
}
