import SwiftUI

/// Первый экран: подключить сервер.
///
/// Пароль спрашивается один раз и используется ровно для одного дела — положить
/// на сервер публичную половину нового ключа. Нигде не сохраняется: ни в
/// настройках, ни в Связке. Дальше вход только по ключу.
struct Podklyuchenie: View {

    @EnvironmentObject var sostoyanie: Sostoyanie

    @State private var host = ""
    @State private var port = "22"
    @State private var polzovatel = "root"
    @State private var parol = ""

    @State private var otpechatki: [String] = []
    @State private var strokiKlyucha = ""
    @State private var sprashivayu = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                zagolovok
                shagAdres
                if !otpechatki.isEmpty { shagOtpechatok }
                if !otpechatki.isEmpty { shagParol }
            }
            .padding(30)
            .frame(maxWidth: 640, alignment: .leading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var zagolovok: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Подключить сервер прототипов")
                .font(.largeTitle.bold())
            Text("Это машина, где стоит Caddy и лежит /root/prototypes-static. "
                 + "Не сервер сканера — там нет ни Caddy, ни статики прототипов.")
                .foregroundStyle(.secondary)
        }
    }

    private var shagAdres: some View {
        GroupBox("1. Адрес") {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    TextField("IP или имя хоста", text: $host)
                    TextField("Порт", text: $port).frame(width: 70)
                }
                TextField("Пользователь", text: $polzovatel)
                HStack {
                    Button(sprashivayu ? "Спрашиваю…" : "Спросить ключ сервера") { sprositKlyuch() }
                        .disabled(host.isEmpty || sprashivayu)
                    if sprashivayu { ProgressView().controlSize(.small) }
                }
            }
            .padding(6)
        }
    }

    private var shagOtpechatok: some View {
        GroupBox("2. Отпечаток сервера") {
            VStack(alignment: .leading, spacing: 10) {
                Text("Сверьте с тем, что печатает сам сервер. На нём это команда:")
                    .foregroundStyle(.secondary)
                Text("ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub")
                    .font(.system(.callout, design: .monospaced))
                    .textSelection(.enabled)
                ForEach(otpechatki, id: \.self) { otpechatok in
                    Text(otpechatok)
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }
                Text("Если потом отпечаток сменится, приложение откажется подключаться — "
                     + "это либо переустановленный сервер, либо подмена.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            .padding(6)
        }
    }

    private var shagParol: some View {
        GroupBox("3. Пароль — один раз") {
            VStack(alignment: .leading, spacing: 12) {
                SecureField("Пароль от \(polzovatel)@\(host)", text: $parol)
                Text("Приложение заведёт себе ключ, положит его в authorized_keys и забудет пароль. "
                     + "После этого вход по паролю на сервере можно выключить совсем — в логах видно, "
                     + "что в root по паролю ломятся круглосуточно.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Подключить") { podklyuchit() }
                        .keyboardShortcut(.defaultAction)
                        .disabled(parol.isEmpty || sostoyanie.zanyat)
                    if sostoyanie.zanyat {
                        ProgressView().controlSize(.small)
                        Text(sostoyanie.shag).foregroundStyle(.secondary)
                    }
                }
            }
            .padding(6)
        }
    }

    private func sprositKlyuch() {
        sprashivayu = true
        let imya = host.trimmingCharacters(in: .whitespaces)
        let nomer = Int(port) ?? 22
        Task {
            do {
                let otvet = try await vFone { try Ssh.sprositKlyuchServera(host: imya, port: nomer) }
                strokiKlyucha = otvet.stroki
                otpechatki = otvet.otpechatki
            } catch {
                sostoyanie.oshibka = error.localizedDescription
            }
            sprashivayu = false
        }
    }

    private func podklyuchit() {
        sostoyanie.nastroyki.host = host.trimmingCharacters(in: .whitespaces)
        sostoyanie.nastroyki.port = Int(port) ?? 22
        sostoyanie.nastroyki.polzovatel = polzovatel.trimmingCharacters(in: .whitespaces)
        let parolKopiya = parol
        parol = ""
        Task {
            await sostoyanie.podklyuchit(parol: parolKopiya, otpechatki: otpechatki, stroki: strokiKlyucha)
        }
    }
}
