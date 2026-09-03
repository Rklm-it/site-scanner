import SwiftUI
import AppKit

struct KartochkaSayta: View {

    @EnvironmentObject var sostoyanie: Sostoyanie
    var sayt: Sayt

    @State private var sprositUdalenie = false
    @State private var sprositOtkat = false
    @State private var chto: Vidimoe = .lyudi
    @State private var dney = 30

    enum Vidimoe: String, CaseIterable, Identifiable {
        case lyudi = "Люди"
        case preview = "Превью ссылок"
        case boty = "Роботы"
        var id: String { rawValue }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                shapka
                sostoyanieSayta
                deystviya
                Divider()
                poseshcheniya
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .navigationTitle(sayt.domen)
        .onAppear { sostoyanie.obnovitPoseshcheniya(sayt, dney: dney) }
        .onChange(of: sayt.imya) { _ in sostoyanie.obnovitPoseshcheniya(sayt, dney: dney) }
        .confirmationDialog("Убрать \(sayt.domen) с сервера?", isPresented: $sprositUdalenie, titleVisibility: .visible) {
            Button("Убрать сайт", role: .destructive) { sostoyanie.udalit(sayt) }
            Button("Отмена", role: .cancel) { }
        } message: {
            Text("Домен перестанет отвечать, файлы будут удалены. Лог посещений на сервере и история в приложении останутся. A-запись у регистратора снимается руками.")
        }
        .confirmationDialog("Вернуть предыдущую версию?", isPresented: $sprositOtkat, titleVisibility: .visible) {
            Button("Откатить") { sostoyanie.otkatit(sayt) }
            Button("Отмена", role: .cancel) { }
        } message: {
            Text("Текущая и предыдущая версии поменяются местами. Откатить обратно можно тем же действием.")
        }
    }

    // MARK: - Шапка

    private var shapka: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(sayt.domen).font(.largeTitle.bold())
            HStack(spacing: 10) {
                Text("папка \(sayt.imya)")
                if !sayt.sozdan.isEmpty { Text("заведён \(sayt.sozdan)") }
                if !sayt.nash {
                    Text("блок написан руками — приложение его не меняет")
                        .foregroundStyle(.orange)
                }
            }
            .font(.callout)
            .foregroundStyle(.secondary)
        }
    }

    private var zdorovye: Zdorovye? { sostoyanie.zdorovye[sayt.imya] }

    private var sostoyanieSayta: some View {
        HStack(spacing: 26) {
            pokazatel("Ответ", zdorovye?.korotko ?? "—",
                      cvet: (zdorovye?.horosho ?? false) ? .green : .orange)
            pokazatel("Сертификат", srokSertifikata, cvet: cvetSertifikata)
            pokazatel("Размер", razmerSayta, cvet: .secondary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.secondary.opacity(0.07), in: RoundedRectangle(cornerRadius: 10))
    }

    private func pokazatel(_ nazvanie: String, _ znachenie: String, cvet: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(nazvanie).font(.caption).foregroundStyle(.secondary)
            Text(znachenie).font(.title3.weight(.medium)).foregroundStyle(cvet)
        }
    }

    private var srokSertifikata: String {
        guard let dney = zdorovye?.dneyDoKoncaSertifikata else { return "—" }
        return "ещё " + schislom(dney, "день", "дня", "дней")
    }

    private var cvetSertifikata: Color {
        guard let dney = zdorovye?.dneyDoKoncaSertifikata else { return .secondary }
        if dney < 7 { return .red }
        if dney < 20 { return .orange }
        return .green
    }

    private var razmerSayta: String {
        guard let bayty = sostoyanie.serverSostoyanie?.razmerySaytov[sayt.imya] else { return "—" }
        return ByteCountFormatter.string(fromByteCount: bayty, countStyle: .file)
    }

    // MARK: - Действия

    private var deystviya: some View {
        HStack(spacing: 10) {
            Button {
                if let adres = URL(string: sayt.adres) { NSWorkspace.shared.open(adres) }
            } label: { Label("Открыть", systemImage: "safari") }

            Button {
                sostoyanie.obnovitPoseshcheniya(sayt, dney: dney)
            } label: { Label("Обновить посещения", systemImage: "arrow.clockwise") }
                .disabled(sostoyanie.zanyat)

            Button {
                sprositOtkat = true
            } label: { Label("Откатить", systemImage: "arrow.uturn.backward") }
                .disabled(sostoyanie.zanyat)

            Spacer()

            Button(role: .destructive) {
                sprositUdalenie = true
            } label: { Label("Убрать сайт", systemImage: "trash") }
                .disabled(sostoyanie.zanyat || !sayt.nash)
        }
    }

    // MARK: - Посещения

    private var vseZahody: [Poseshchenie] { sostoyanie.zahody[sayt.imya] ?? [] }

    private var otobrannye: [Poseshchenie] {
        switch chto {
        case .lyudi: return vseZahody.filter { $0.vid == .chelovek }
        case .preview: return vseZahody.filter { $0.vid == .preview }
        case .boty: return vseZahody.filter { $0.vid == .bot }
        }
    }

    private var poseshcheniya: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Кто заходил").font(.title2.bold())
                Spacer()
                Picker("", selection: $dney) {
                    Text("7 дней").tag(7)
                    Text("30 дней").tag(30)
                    Text("90 дней").tag(90)
                }
                .pickerStyle(.segmented)
                .frame(width: 260)
                .onChange(of: dney) { novoe in sostoyanie.obnovitPoseshcheniya(sayt, dney: novoe) }
            }

            Text(svodka).foregroundStyle(.secondary)

            Picker("", selection: $chto) {
                ForEach(Vidimoe.allCases) { variant in
                    Text("\(variant.rawValue) (\(kolichestvo(variant)))").tag(variant)
                }
            }
            .pickerStyle(.segmented)

            if chto == .preview {
                Text("Мессенджеры открывают ссылку сами, как только её отправили. Это не клиент — "
                     + "это робот WhatsApp или Telegram сходил за картинкой для превью.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            if otobrannye.isEmpty {
                Text("Пока никого.")
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 16)
            } else {
                ForEach(otobrannye) { zahod in
                    StrokaZahoda(zahod: zahod, imyaAdresa: sostoyanie.imyaAdresa(zahod.ip))
                    Divider()
                }
            }
        }
    }

    private func kolichestvo(_ variant: Vidimoe) -> Int {
        switch variant {
        case .lyudi: return vseZahody.filter { $0.vid == .chelovek }.count
        case .preview: return vseZahody.filter { $0.vid == .preview }.count
        case .boty: return vseZahody.filter { $0.vid == .bot }.count
        }
    }

    private var svodka: String {
        let lyudi = vseZahody.filter { $0.vid == .chelovek }
        guard !lyudi.isEmpty else {
            return "За \(schislom(dney, "день", "дня", "дней")) людей не было."
        }
        let adresov = Set(lyudi.map { $0.ip }).count
        let formatter = RelativeDateTimeFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        let posledniy = lyudi.map { $0.nachalo }.max() ?? Date()
        return schislom(lyudi.count, "заход", "захода", "заходов")
            + " с " + schislom(adresov, "адреса", "адресов", "адресов")
            + ". Последний — \(formatter.localizedString(for: posledniy, relativeTo: Date()))."
    }
}

struct StrokaZahoda: View {
    var zahod: Poseshchenie
    var imyaAdresa: String?

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                Text(kogda).font(.callout.weight(.medium))
                if let skolko = dlitelnost {
                    Text(skolko).font(.caption).foregroundStyle(.secondary)
                }
            }
            .frame(width: 160, alignment: .leading)

            VStack(alignment: .leading, spacing: 3) {
                Text(otkuda).font(.callout)
                Text(zahod.ustroystvo).font(.caption).foregroundStyle(.secondary)
                if !zahod.stranicy.isEmpty {
                    Text(zahod.stranicy.prefix(6).joined(separator: "  ·  "))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                if !zahod.otkuda.isEmpty {
                    Text("пришёл с \(zahod.otkuda)").font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            Text(schislom(zahod.zaprosov, "запрос", "запроса", "запросов"))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 7)
    }

    private var kogda: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        formatter.dateFormat = "d MMMM, HH:mm"
        return formatter.string(from: zahod.nachalo)
    }

    /// Заход из одного обращения длится ноль секунд, и «0 сек. на сайте»
    /// выглядит как поломка. Такому заходу времени просто нет.
    private var dlitelnost: String? {
        let sekund = Int(zahod.dlitelnost)
        if sekund < 1 { return nil }
        if sekund < 60 { return schislom(sekund, "секунда", "секунды", "секунд") + " на сайте" }
        return schislom(sekund / 60, "минута", "минуты", "минут") + " на сайте"
    }

    private var otkuda: String {
        var chasti: [String] = []
        if let strana = Geo.shared.strana(zahod.ip) { chasti.append(strana) }
        chasti.append(zahod.ip)
        if let imyaAdresa, !imyaAdresa.isEmpty { chasti.append(imyaAdresa) }
        return chasti.joined(separator: " · ")
    }
}
