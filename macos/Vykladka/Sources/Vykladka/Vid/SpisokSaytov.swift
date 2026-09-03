import SwiftUI

struct SpisokSaytov: View {

    @EnvironmentObject var sostoyanie: Sostoyanie

    var body: some View {
        VStack(spacing: 0) {
            List(selection: $sostoyanie.vybran) {
                Section("Сайты") {
                    ForEach(sostoyanie.sayty) { sayt in
                        StrokaSayta(sayt: sayt, zdorovye: sostoyanie.zdorovye[sayt.imya])
                            .tag(sayt.imya)
                    }
                }
            }
            .listStyle(.sidebar)

            Divider()
            podval
        }
    }

    @ViewBuilder
    private var podval: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let sostoyanieServera = sostoyanie.serverSostoyanie {
                HStack(spacing: 6) {
                    Image(systemName: sostoyanieServera.caddyZhiv ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(sostoyanieServera.caddyZhiv ? .green : .orange)
                    Text(sostoyanieServera.caddyZhiv ? "Caddy работает" : "Caddy не найден")
                        .font(.callout)
                }
                Text("Место: свободно \(sostoyanieServera.svobodnoTekstom) из \(sostoyanieServera.vsegoTekstom)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("Состояние сервера ещё не спрашивали")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }
}

struct StrokaSayta: View {
    var sayt: Sayt
    var zdorovye: Zdorovye?

    var body: some View {
        HStack(spacing: 9) {
            Circle()
                .fill(cvet)
                .frame(width: 8, height: 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(sayt.domen).lineLimit(1)
                HStack(spacing: 6) {
                    Text(sayt.imya)
                    if !sayt.nash {
                        Text("не наш блок")
                            .padding(.horizontal, 5)
                            .background(Color.secondary.opacity(0.15), in: Capsule())
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }

    private var cvet: Color {
        guard let zdorovye else { return .secondary.opacity(0.4) }
        if zdorovye.horosho { return .green }
        if zdorovye.kod != nil { return .orange }
        return .red
    }
}
