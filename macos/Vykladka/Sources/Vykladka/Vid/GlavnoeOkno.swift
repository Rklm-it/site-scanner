import SwiftUI
import UniformTypeIdentifiers
import AppKit

struct GlavnoeOkno: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    @State private var razbor: Arhiv.Razbor?
    @State private var paraMaketov: ParaMaketov?
    @State private var razborIdet = false
    @State private var pokazatNastroyki = false
    @State private var navedeno = false

    var body: some View {
        Group {
            if sostoyanie.nastroyki.podklyucheno {
                osnovnoe
            } else {
                Podklyuchenie()
            }
        }
        .sheet(item: $razbor) { razbor in
            NovayaVykladka(razbor: razbor)
                .environmentObject(sostoyanie)
        }
        .sheet(item: $paraMaketov) { para in
            SkleykaMaketov(nachalnaya: para) { itog, ishodnaya in
                prinyatSkleyku(itog, ishodnaya: ishodnaya)
            }
            .environmentObject(sostoyanie)
        }
        .sheet(isPresented: $pokazatNastroyki) {
            NastroykiVid().environmentObject(sostoyanie)
        }
        .alert("Не получилось", isPresented: Binding(
            get: { sostoyanie.oshibka != nil },
            set: { if !$0 { sostoyanie.oshibka = nil } }
        )) {
            Button("Понятно", role: .cancel) { sostoyanie.oshibka = nil }
        } message: {
            Text(sostoyanie.oshibka ?? "")
        }
    }

    private var osnovnoe: some View {
        NavigationSplitView {
            SpisokSaytov()
                .navigationSplitViewColumnWidth(min: 260, ideal: 290)
        } detail: {
            if let sayt = sostoyanie.vybrannyySayt {
                KartochkaSayta(sayt: sayt)
            } else {
                ZonaSbrosa(navedeno: navedeno)
            }
        }
        .toolbar {
            ToolbarItem(placement: .navigation) {
                // Машин у владельца две, и отвечают на ssh они одинаково.
                // Пусть всегда видно, к какой из них подключено окно.
                Label(sostoyanie.nastroyki.opisanie, systemImage: "server.rack")
                    .foregroundStyle(.secondary)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    vybratArhivRuchkoy()
                } label: {
                    Label("Положить архив", systemImage: "arrow.up.doc")
                }
                .disabled(sostoyanie.zanyat || razborIdet)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    vybratPapkuMaketov()
                } label: {
                    Label("Склеить макеты", systemImage: "rectangle.on.rectangle")
                }
                .disabled(sostoyanie.zanyat || razborIdet)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    sostoyanie.obnovitVsyo()
                } label: {
                    Label("Обновить", systemImage: "arrow.clockwise")
                }
                .disabled(sostoyanie.zanyat)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    pokazatNastroyki = true
                } label: {
                    Label("Настройки", systemImage: "gearshape")
                }
            }
        }
        .safeAreaInset(edge: .bottom) { polosaSostoyaniya }
        .onDrop(of: [UTType.fileURL], isTargeted: $navedeno) { postavshchiki in
            prinyat(postavshchiki)
        }
        .onAppear { sostoyanie.obnovitVsyo() }
    }

    @ViewBuilder
    private var polosaSostoyaniya: some View {
        if sostoyanie.zanyat || razborIdet || sostoyanie.soobshchenie != nil {
            HStack(spacing: 10) {
                if sostoyanie.zanyat || razborIdet {
                    ProgressView().controlSize(.small)
                    Text(razborIdet ? "Разбираю архив…" : sostoyanie.shag)
                } else if let soobshchenie = sostoyanie.soobshchenie {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                    Text(soobshchenie)
                    Button("Скрыть") { sostoyanie.soobshchenie = nil }
                        .buttonStyle(.link)
                }
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(.regularMaterial)
            .overlay(alignment: .top) { Divider() }
        }
    }

    // MARK: - Приём архива

    private func prinyat(_ postavshchiki: [NSItemProvider]) -> Bool {
        guard let postavshchik = postavshchiki.first, !sostoyanie.zanyat, !razborIdet else { return false }
        postavshchik.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { element, _ in
            var adres: URL?
            if let dannye = element as? Data {
                adres = URL(dataRepresentation: dannye, relativeTo: nil)
            } else if let gotovyy = element as? URL {
                adres = gotovyy
            }
            guard let adres else { return }
            DispatchQueue.main.async { razobratArhiv(adres) }
        }
        return true
    }

    private func vybratArhivRuchkoy() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = true
        panel.message = "Архив со сборкой сайта (.zip или .tar.gz) либо папка с index.html"
        if panel.runModal() == .OK, let adres = panel.url {
            razobratArhiv(adres)
        }
    }

    private func razobratArhiv(_ adres: URL) {
        razborIdet = true
        Task {
            do {
                let (korn, vremennaya) = try await vFone { try Arhiv.raspakovatVoVremennuyu(adres) }
                do {
                    razbor = try await vFone { try Arhiv.razobrat(raspakovano: korn, vremennaya: vremennaya) }
                } catch {
                    // index.html не нашёлся. Прежде чем ругаться, смотрим, не пара
                    // ли это макетов Stitch: у него в выгрузке два code.html и
                    // ни одного index.html — сам по себе такой архив не сайт.
                    if let para = Makety.naytiParu(v: korn) {
                        paraMaketov = ParaMaketov(para: para, vremennaya: vremennaya)
                    } else {
                        if let vremennaya { try? FileManager.default.removeItem(at: vremennaya) }
                        sostoyanie.oshibka = error.localizedDescription
                    }
                }
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            razborIdet = false
        }
    }

    private func vybratPapkuMaketov() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = true
        panel.message = "Папка с выгрузкой Stitch (две версии) или архив с ней"
        guard panel.runModal() == .OK, let adres = panel.url else { return }
        razborIdet = true
        Task {
            do {
                let (korn, vremennaya) = try await vFone { try Arhiv.raspakovatVoVremennuyu(adres) }
                if let para = Makety.naytiParu(v: korn) {
                    paraMaketov = ParaMaketov(para: para, vremennaya: vremennaya)
                } else {
                    sostoyanie.oshibka = "В этой папке не нашлось ровно двух HTML-макетов. Склеивать нечего."
                }
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            razborIdet = false
        }
    }

    /// Принять склеенное и отдать в обычную выкладку.
    private func prinyatSkleyku(_ itog: Makety.Itog, ishodnaya: URL?) {
        if let ishodnaya { try? FileManager.default.removeItem(at: ishodnaya) }
        razborIdet = true
        Task {
            do {
                razbor = try await vFone {
                    try Arhiv.razobrat(raspakovano: itog.papka, vremennaya: itog.papka)
                }
                var otchet = "Склеено."
                if itog.kartinokSkachano > 0 {
                    otchet += " Картинок забрано к себе: \(itog.kartinokSkachano)."
                }
                if itog.kartinokNeVzyalos > 0 {
                    otchet += " Не забралось: \(itog.kartinokNeVzyalos) — они остались ссылками на Stitch и однажды пропадут."
                }
                if itog.tailwindMestnyy { otchet += " Tailwind лежит рядом, чужой CDN не нужен." }
                sostoyanie.soobshchenie = otchet
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            razborIdet = false
        }
    }
}

/// Пустое место посередине, когда сайт не выбран.
struct ZonaSbrosa: View {
    var navedeno: Bool

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: navedeno ? "tray.and.arrow.down.fill" : "tray.and.arrow.down")
                .font(.system(size: 54))
                .foregroundStyle(navedeno ? Color.accentColor : .secondary)
            Text("Положите сюда архив со сборкой")
                .font(.title3)
            Text(".zip или .tar.gz с index.html внутри — либо готовую папку")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(navedeno ? Color.accentColor.opacity(0.08) : Color.clear)
    }
}
