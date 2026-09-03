import SwiftUI
import UniformTypeIdentifiers
import AppKit

struct GlavnoeOkno: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    @State private var razbor: Arhiv.Razbor?
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
        .overlay(alignment: .bottom) { polosaSostoyaniya }
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
                let rezultat = try await vFone { try Arhiv.razobrat(adres) }
                razbor = rezultat
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
