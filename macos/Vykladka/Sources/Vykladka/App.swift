import SwiftUI
import AppKit

@main
struct VykladkaApp: App {

    @NSApplicationDelegateAdaptor(Delegat.self) var delegat
    @StateObject private var sostoyanie = Sostoyanie()

    var body: some Scene {
        WindowGroup("Выкладка") {
            GlavnoeOkno()
                .environmentObject(sostoyanie)
                .frame(minWidth: 940, minHeight: 620)
        }
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}

final class Delegat: NSObject, NSApplicationDelegate {
    /// Ключ при выходе не трогаем — он постоянный, как ~/.ssh/id_ed25519.
    /// А распакованные архивы за собой убираем: они большие и не нужны.
    func applicationWillTerminate(_ uvedomlenie: Notification) {
        Papki.pochistitVremennoe()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ prilozhenie: NSApplication) -> Bool {
        true
    }
}
